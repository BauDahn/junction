import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from verifier.llm import make_llm
from . import store
from .engine import handle_text
from .profile import empty_profile
from . import transcribe as transcription

router = APIRouter()


class MessageInput(BaseModel):
    text: str


def get_llm():
    return make_llm()[0]


def get_transcriber():
    return transcription.transcribe


def _session(session_id):
    if not store.session_exists(session_id):
        raise HTTPException(404, "Session not found.")


@router.post("/api/sessions")
async def create_session():
    from uuid import uuid4
    session_id = uuid4().hex
    store.create_session(session_id, store.now_iso())
    return {"session_id": session_id}


async def _process_text(session_id, text, llm, transcript=None):
    try:
        user, reply, profile = await handle_text(session_id, text, llm, transcript=transcript)
    except Exception as exc:
        raise HTTPException(502, "El modelo no respondió, intenta de nuevo.") from exc
    store.add_message(user)
    store.add_message(reply)
    if profile is not None:
        store.save_profile(session_id, profile)
    return {"message": {k: v for k, v in user.items() if k != "session_id"}, "reply": {k: v for k, v in reply.items() if k != "session_id"}, "profile_updated": profile is not None, "recommendations_status": "idle"}


@router.post("/api/sessions/{session_id}/messages")
async def post_message(session_id: str, request: Request, llm=Depends(get_llm), transcriber=Depends(get_transcriber)):
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
            try:
                hint = transcription.hint_from_profile(store.get_profile(session_id))
                result = await transcriber(path, hint=hint)
            except Exception as exc:
                if "no configurada" in str(exc).lower():
                    raise HTTPException(503, "Transcripción no configurada") from exc
                raise HTTPException(502, "No se pudo transcribir el audio.") from exc
            text = result.get("text", "").strip()
            if not text:
                raise HTTPException(422, "No se entendió el audio.")
            if result.get("duration_s", 0) > 120:
                raise HTTPException(413, "El audio debe durar 2 minutos o menos.")
            return await _process_text(session_id, text, llm, transcript=text)
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
    return await _process_text(session_id, text.strip(), llm)


@router.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    _session(session_id)
    return {"messages": store.list_messages(session_id)}


@router.get("/api/sessions/{session_id}/profile")
async def get_session_profile(session_id: str):
    _session(session_id)
    return store.get_profile(session_id) or empty_profile()
