import logging
import os
import asyncio
import inspect
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from verifier.llm import make_llm
from verifier.config import settings
from verifier.cala import CalaClient
from . import store
from .engine import handle_text
from .profile import empty_profile
from . import transcribe as transcription
from . import recommend

router = APIRouter()
_recommendation_tasks = set()
logger = logging.getLogger("uvicorn.error")


class MessageInput(BaseModel):
    text: str
    context: dict | None = None


def get_llm():
    return make_llm(tier="fast")[0]


def get_transcriber():
    return transcription.transcribe


def get_cala():
    return CalaClient(settings.cala_api_key, settings.cache_dir)


def _session(session_id):
    if not store.session_exists(session_id):
        raise HTTPException(404, "Session not found.")


@router.post("/api/sessions")
async def create_session():
    from uuid import uuid4
    session_id = uuid4().hex
    store.create_session(session_id, store.now_iso())
    return {"session_id": session_id}


async def _process_text(session_id, text, llm, cala, transcript=None, context=None):
    try:
        user, reply, profile = await handle_text(session_id, text, llm, transcript=transcript, cala=cala, context=context)
    except Exception as exc:
        logger.exception("chat: fallo procesando el mensaje")
        raise HTTPException(502, "El modelo no respondió, intenta de nuevo.") from exc
    store.add_message(user)
    store.add_message(reply)
    if profile is not None:
        store.save_profile(session_id, profile)
        fp = recommend.fingerprint(profile)
        previous = store.get_recommendations(session_id)
        if settings.cala_api_key and (profile.get("sector") or profile.get("one_liner")) and (not previous or previous["fingerprint"] != fp or previous["status"] == "error"):
            store.save_recommendations(session_id, "running", {}, fp, notified=0)
            task = asyncio.create_task(recommend.run_recommendations(session_id, profile, llm, cala))
            _recommendation_tasks.add(task)
            task.add_done_callback(_recommendation_tasks.discard)
    rec = store.get_recommendations(session_id)
    return {"message": {k: v for k, v in user.items() if k != "session_id"}, "reply": {k: v for k, v in reply.items() if k != "session_id"}, "profile_updated": profile is not None, "recommendations_status": rec["status"] if rec else "idle"}


@router.post("/api/sessions/{session_id}/messages")
async def post_message(session_id: str, request: Request, llm=Depends(get_llm), transcriber=Depends(get_transcriber), cala=Depends(get_cala)):
    _session(session_id)
    if "multipart/form-data" in request.headers.get("content-type", ""):
        form = await request.form()
        audio = form.get("audio")
        if not hasattr(audio, "read") or not hasattr(audio, "filename"):
            raise HTTPException(415, "Tipo de audio no admitido.")
        allowed = {".m4a", ".webm", ".wav", ".mp3", ".ogg"}
        content_types = {"audio/mp4", "audio/x-m4a", "audio/webm", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/ogg", "application/ogg"}
        suffix = Path(audio.filename or "").suffix.lower()
        if suffix not in allowed and audio.content_type not in content_types:
            raise HTTPException(415, "Tipo de audio no admitido.")
        data = await audio.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, "El audio debe pesar 10 MB o menos.")
        fd, filename = tempfile.mkstemp(prefix="chat-audio-", suffix=suffix if suffix in allowed else ".audio")
        path = Path(filename)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
            if os.getenv("CHAT_KEEP_AUDIO") == "1":  # depuración local de transcripciones
                keep = Path(store.DB_PATH).parent / "audio" if hasattr(store, "DB_PATH") else Path("data/audio")
                keep.mkdir(parents=True, exist_ok=True)
                (keep / f"{store.now_iso().replace(':', '-')}{suffix}").write_bytes(data)
            try:
                hint = transcription.hint_from_profile(store.get_profile(session_id))
                mime = transcription.mime_for(audio.filename, audio.content_type)
                parameters = inspect.signature(transcriber).parameters
                result = await transcriber(path, hint=hint, **({"mime": mime} if "mime" in parameters or any(p.kind == p.VAR_KEYWORD for p in parameters.values()) else {}))
            except Exception as exc:
                if "no configurada" in str(exc).lower():
                    raise HTTPException(503, "Transcripción no configurada") from exc
                logger.exception("chat: fallo transcribiendo %s (%s, %d bytes)", audio.filename, audio.content_type, len(data))
                raise HTTPException(502, "No se pudo transcribir el audio.") from exc
            text = result.get("text", "").strip()
            if not text:
                raise HTTPException(422, "No se entendió el audio.")
            if result.get("duration_s", 0) > 120:
                raise HTTPException(413, "El audio debe durar 2 minutos o menos.")
            transcript = result.get("transcript") or text
            return await _process_text(session_id, text, llm, cala, transcript=transcript)
        finally:
            path.unlink(missing_ok=True)
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "Body must be JSON with a text field.")
    text = payload.get("text", "") if isinstance(payload, dict) else ""
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(400, "Text must not be empty.")
    if len(text) > 4000:
        raise HTTPException(413, "Text must be 4000 characters or fewer.")
    context = payload.get("context") if isinstance(payload, dict) else None
    if context is not None and (not isinstance(context, dict) or ("journal_item_id" in context and not isinstance(context["journal_item_id"], str))):
        raise HTTPException(400, "Context inválido.")
    return await _process_text(session_id, text.strip(), llm, cala, context=context)


@router.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    _session(session_id)
    return {"messages": store.list_messages(session_id)}


@router.get("/api/sessions/{session_id}/profile")
async def get_session_profile(session_id: str):
    _session(session_id)
    return store.get_profile(session_id) or empty_profile()


@router.get("/api/sessions/{session_id}/recommendations")
async def get_session_recommendations(session_id: str):
    _session(session_id)
    rec = store.get_recommendations(session_id)
    if not rec:
        return {"status":"idle", "updated_at":None, "investors":[], "competitors":[], "prospects":[]}
    return {"status":rec["status"], "updated_at":rec["updated_at"], **{key:rec["data"].get(key, []) for key in ("investors","competitors","prospects")}}
