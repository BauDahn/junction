import logging
import os
import asyncio
import inspect
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from core.llm import make_llm
from core.config import settings
from core.cala import CalaClient
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
    if not settings.cala_api_key:
        return None
    return CalaClient(settings.cala_api_key, settings.cache_dir)


def _session(session_id):
    if not store.session_exists(session_id):
        raise HTTPException(404, "Session not found.")


@router.post("/api/transcribe")
async def preview_transcription(request: Request, transcriber=Depends(get_transcriber)):
    form = await request.form()
    audio = form.get("audio")
    allowed = {".m4a", ".webm", ".wav", ".mp3", ".ogg"}
    content_types = {"audio/mp4", "audio/x-m4a", "audio/webm", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/ogg", "application/ogg"}
    if not hasattr(audio, "read") or not hasattr(audio, "filename"):
        raise HTTPException(415, "Unsupported audio format.")
    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in allowed and audio.content_type not in content_types:
        raise HTTPException(415, "Unsupported audio format.")
    data = await audio.read(10 * 1024 * 1024 + 1)
    if not data:
        raise HTTPException(422, "Audio could not be understood.")
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Audio must be 10 MB or smaller.")
    fd, filename = tempfile.mkstemp(prefix="transcribe-preview-", suffix=suffix if suffix in allowed else ".audio")
    path = Path(filename)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        try:
            parameters = inspect.signature(transcriber).parameters
            kwargs = {"hint": None}
            if "mime" in parameters or any(p.kind == p.VAR_KEYWORD for p in parameters.values()):
                kwargs["mime"] = transcription.mime_for(audio.filename, audio.content_type)
            result = await transcriber(path, **kwargs)
        except Exception as exc:
            if "not configured" in str(exc).lower():
                raise HTTPException(503, "Transcription is not configured.") from exc
            raise HTTPException(502, "Audio transcription failed.") from exc
        transcript = str(result.get("transcript") or result.get("text") or "").strip()
        text = str(result.get("text") or transcript).strip()
        if not transcript or not text:
            raise HTTPException(422, "Audio could not be understood.")
        if result.get("duration_s", 0) > 120:
            raise HTTPException(413, "Audio must be 2 minutes or shorter.")
        return {"transcript": transcript, "text": text}
    finally:
        path.unlink(missing_ok=True)


@router.post("/api/sessions")
async def create_session(request: Request):
    from core.abuse import enforce, client_ip
    enforce(request, "sessions", f"ip:{client_ip(request)}", 5, 60)
    from uuid import uuid4
    session_id = uuid4().hex
    store.create_session(session_id, store.now_iso())
    return {"session_id": session_id}


async def _process_text(session_id, text, llm, cala, transcript=None, context=None):
    try:
        user, reply, profile = await handle_text(session_id, text, llm, transcript=transcript, cala=cala, context=context)
    except Exception as exc:
        if exc.__class__.__name__ == "CalaBudgetExceeded":
            logger.warning("Cala call cap reached client=session route=/api/sessions/{session_id}/messages")
            raise HTTPException(503, "Cala call cap reached.") from exc
        logger.exception("chat: fallo procesando el mensaje")
        raise HTTPException(502, "The model did not respond. Please try again.") from exc
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
    from core.abuse import account_for, client_ip, identity, enforce, daily, account_daily
    authorization = request.headers.get("authorization")
    user = account_for(authorization)
    subject = identity(request, user)
    enforce(request, "chat", subject, 10, 60)
    daily(request, "chat", subject, 150)
    if cala is not None:
        if os.getenv("CALA_REQUIRE_AUTH", "0") == "1" and user is None:
            raise HTTPException(401, "unauthorized")
        if user:
            account_daily(request, user)
    if "multipart/form-data" in request.headers.get("content-type", ""):
        form = await request.form()
        audio = form.get("audio")
        if not hasattr(audio, "read") or not hasattr(audio, "filename"):
            raise HTTPException(415, "Unsupported audio format.")
        allowed = {".m4a", ".webm", ".wav", ".mp3", ".ogg"}
        content_types = {"audio/mp4", "audio/x-m4a", "audio/webm", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/ogg", "application/ogg"}
        suffix = Path(audio.filename or "").suffix.lower()
        if suffix not in allowed and audio.content_type not in content_types:
            raise HTTPException(415, "Unsupported audio format.")
        data = await audio.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(413, "Audio must be 10 MB or smaller.")
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
                if "not configured" in str(exc).lower():
                    raise HTTPException(503, "Transcription is not configured.") from exc
                logger.exception("chat: fallo transcribiendo %s (%s, %d bytes)", audio.filename, audio.content_type, len(data))
                raise HTTPException(502, "Audio transcription failed.") from exc
            text = result.get("text", "").strip()
            if not text:
                raise HTTPException(422, "Audio could not be understood.")
            if result.get("duration_s", 0) > 120:
                raise HTTPException(413, "Audio must be 2 minutes or shorter.")
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
    if len(text) > 500:
        raise HTTPException(422, "Text must be 500 characters or fewer.")
    context = payload.get("context") if isinstance(payload, dict) else None
    if context is not None and (not isinstance(context, dict) or ("journal_item_id" in context and not isinstance(context["journal_item_id"], str))):
        raise HTTPException(400, "Invalid context.")
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
