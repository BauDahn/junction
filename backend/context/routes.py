import asyncio
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from chat import store
from chat.profile import empty_profile
from chat.routes import get_transcriber
from chat.transcribe import hint_from_profile
from core.llm import make_llm
from core.pdf import read_pdf
from .service import UNDERSTOOD_KEYS, _items, _parse_ticket_range, build_context_payload, extract_context, understood_from_profile, update_profile
from accounts.routes import current_user

router = APIRouter()
MAX_PDF = 20 * 1024 * 1024
MAX_AUDIO = 10 * 1024 * 1024
AUDIO_SUFFIXES = {".m4a", ".webm", ".wav", ".mp3", ".ogg"}
AUDIO_TYPES = {"audio/mp4", "audio/x-m4a", "audio/webm", "audio/wav", "audio/x-wav", "audio/mpeg", "audio/ogg", "application/ogg"}
MAX_RAW_CONTEXT = 8000


class RawContextInput(BaseModel):
    text: str


def _append_raw(session_id, line):
    current = store.get_raw_context(session_id)["text"]
    combined = f"{current}\n{line}" if current else line
    if len(combined) > MAX_RAW_CONTEXT:
        raise HTTPException(422, "Context must be 8000 characters or fewer.")
    store.save_raw_context(session_id, combined)


async def _update_profile_from_raw(session_id, text, llm):
    try:
        extracted = await extract_context(llm, text)
    except Exception as exc:
        raise HTTPException(502, "Context extraction failed.") from exc
    profile, _ = update_profile(_profile(session_id), extracted, {"id": uuid.uuid4().hex, "kind": "text", "title": "Context", "subtitle": "Context updated"})
    store.save_profile(session_id, profile)


def get_llm(request: Request):
    from chat.routes import get_llm as chat_get_llm
    override = request.app.dependency_overrides.get(chat_get_llm)
    if override:
        return override()
    return make_llm(tier="fast")[0]


def _session(session_id):
    if not store.session_exists(session_id): raise HTTPException(404, "Session not found.")


def _profile(session_id):
    return store.get_profile(session_id) or empty_profile()


async def _save(session_id, llm, text, source, images=None):
    try:
        extracted = await extract_context(llm, text, images)
    except Exception as exc:
        raise HTTPException(502, "Context extraction failed.") from exc
    profile, added = update_profile(_profile(session_id), extracted, source)
    store.save_profile(session_id, profile)
    if source.get("kind") == "pdf":
        summary = "; ".join(str(extracted.get(k)).strip() for k in ("one_liner", "sector", "stage", "location", "ticket") if extracted.get(k)) or "Pitch deck context"
        line = f"From {source.get('title') or 'Pitch deck'}: {summary.splitlines()[0]}"
    else:
        line = text
    _append_raw(session_id, line)
    return build_context_payload(session_id, profile, added)


@router.get("/api/me/context/raw")
async def get_raw_context(user=Depends(current_user)):
    return store.get_raw_context(user["session_id"])


@router.put("/api/me/context/raw")
async def put_raw_context(body: RawContextInput, user=Depends(current_user), llm=Depends(get_llm)):
    if len(body.text) > MAX_RAW_CONTEXT:
        raise HTTPException(422, "Context must be 8000 characters or fewer.")
    saved = store.save_raw_context(user["session_id"], body.text)
    await _update_profile_from_raw(user["session_id"], body.text, llm)
    return saved | {"profile_updated": True}


@router.post("/api/me/context/raw/append")
async def append_raw_context(body: RawContextInput, user=Depends(current_user), llm=Depends(get_llm)):
    session_id = user["session_id"]
    current = store.get_raw_context(session_id)["text"]
    combined = f"{current}\n{body.text}" if current else body.text
    if len(combined) > MAX_RAW_CONTEXT:
        raise HTTPException(422, "Context must be 8000 characters or fewer.")
    saved = store.save_raw_context(session_id, combined)
    await _update_profile_from_raw(session_id, combined, llm)
    return saved | {"profile_updated": True}


@router.get("/api/sessions/{session_id}/context")
async def get_context(session_id: str):
    _session(session_id)
    return build_context_payload(session_id, _profile(session_id))


@router.post("/api/sessions/{session_id}/context/pdf")
async def post_pdf(session_id: str, file: UploadFile = File(...), llm=Depends(get_llm)):
    _session(session_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".pdf" and file.content_type != "application/pdf": raise HTTPException(415, "Upload a PDF file.")
    data = await file.read(MAX_PDF + 1)
    if not data: raise HTTPException(400, "The uploaded PDF is empty.")
    if len(data) > MAX_PDF: raise HTTPException(413, "PDF must be 20 MB or smaller.")
    fd, name = tempfile.mkstemp(prefix="context-", suffix=".pdf")
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream: stream.write(data)
        try: pages = await asyncio.to_thread(read_pdf, path, max_pages=15, width=1024)
        except Exception as exc: raise HTTPException(422, "The PDF could not be opened.") from exc
        text = "\n\n".join(page.get("text", "") for page in pages)
        if not text.strip() and not pages: raise HTTPException(422, "The PDF could not be opened.")
        source = {"id": uuid.uuid4().hex, "kind": "pdf", "title": file.filename or "Pitch deck", "subtitle": "Pitch deck analyzed", "pages": len(pages)}
        return await _save(session_id, llm, text, source, [p["image"] for p in pages if p.get("image")])
    finally:
        path.unlink(missing_ok=True)


async def _voice(session_id, request, llm, transcriber):
    _session(session_id)
    form = await request.form()
    audio = form.get("audio") or form.get("file")
    if not hasattr(audio, "read"): raise HTTPException(415, "Unsupported audio format.")
    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in AUDIO_SUFFIXES and audio.content_type not in AUDIO_TYPES: raise HTTPException(415, "Unsupported audio format.")
    data = await audio.read(MAX_AUDIO + 1)
    if not data: raise HTTPException(422, "Audio could not be understood.")
    if len(data) > MAX_AUDIO: raise HTTPException(413, "Audio must be 10 MB or smaller.")
    fd, name = tempfile.mkstemp(prefix="context-audio-", suffix=suffix if suffix in AUDIO_SUFFIXES else ".audio")
    path = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream: stream.write(data)
        profile = _profile(session_id)
        try: result = await transcriber(path, hint=hint_from_profile(profile))
        except Exception as exc:
            if "not configured" in str(exc).lower(): raise HTTPException(503, "Transcription is not configured.") from exc
            raise HTTPException(502, "Audio transcription failed.") from exc
        raw_transcript = str(result.get("transcript") or result.get("text") or "").strip()
        if not raw_transcript: raise HTTPException(422, "Audio could not be understood.")
        clean_text = str(result.get("text") or raw_transcript).strip()
        duration = result.get("duration_s", 0)
        if duration and duration > 120: raise HTTPException(413, "Audio must be 2 minutes or shorter.")
        source = {"id": uuid.uuid4().hex, "kind": "voice", "title": "Voice note", "subtitle": "Voice note analyzed", "duration_s": duration, "transcript": raw_transcript}
        return await _save(session_id, llm, clean_text, source)
    finally:
        path.unlink(missing_ok=True)


@router.post("/api/sessions/{session_id}/context/voice")
async def post_voice(session_id: str, request: Request, llm=Depends(get_llm), transcriber=Depends(get_transcriber)):
    return await _voice(session_id, request, llm, transcriber)


@router.post("/api/sessions/{session_id}/context/note")
async def post_note(session_id: str, request: Request, llm=Depends(get_llm)):
    _session(session_id)
    try: body = await request.json()
    except ValueError: raise HTTPException(400, "Body must be JSON with a text field.")
    text = body.get("text") if isinstance(body, dict) else None
    if not isinstance(text, str) or not text.strip(): raise HTTPException(400, "Text must not be empty.")
    if len(text) > 8000: raise HTTPException(413, "Text must be 8000 characters or fewer.")
    title = body.get("title") if isinstance(body.get("title"), str) and body.get("title").strip() else "Note"
    return await _save(session_id, llm, text, {"id": uuid.uuid4().hex, "kind": "note", "title": title, "subtitle": "Note analyzed"})


@router.patch("/api/sessions/{session_id}/context/understood")
async def update_understood(session_id: str, request: Request):
    _session(session_id)
    try: body = await request.json()
    except ValueError: raise HTTPException(400, "Body must be a JSON object.")
    if not isinstance(body, dict) or any(k not in UNDERSTOOD_KEYS or not isinstance(v, list) or any(not isinstance(x, str) for x in v) for k, v in body.items()):
        raise HTTPException(400, "Context fields must be lists of strings.")
    profile = _profile(session_id)
    understood = understood_from_profile(profile)
    for key, value in body.items(): understood[key] = _items(value)
    profile["what_we_understood"] = understood
    profile["seeking"] = understood["seeking"]
    mapping = {"sector_focus": "sector", "target_stage": "stage", "geography": "location"}
    for key, field in mapping.items():
        if key in body:
            if understood[key]: profile[field] = understood[key][0]
            else: profile.pop(field, None)
    if "target_round_size" in body:
        if understood["target_round_size"]:
            profile["ticket"] = understood["target_round_size"][0]
            profile.setdefault("raising", {})["amount"] = understood["target_round_size"][0]
            ticket_range = _parse_ticket_range(understood["target_round_size"][0])
            if ticket_range:
                profile["ticket_range"] = ticket_range
            else:
                profile.pop("ticket_range", None)
        else:
            profile.pop("ticket", None)
            profile.setdefault("raising", {}).pop("amount", None)
            profile.pop("ticket_range", None)
    existing_follows = (profile.get("interests") or {}).get("follows")
    interests = {"sectors": understood["sector_focus"], "stages": understood["target_stage"], "regions": understood["geography"]}
    if isinstance(existing_follows, dict) and any(existing_follows.get(k) for k in ("companies", "investors")):
        interests["follows"] = {k: list(existing_follows.get(k) or []) for k in ("companies", "investors") if existing_follows.get(k)}
    try:
        from cala_core import _normalize_interests
        interests = _normalize_interests(interests)
    except ImportError:
        interests = {k: v for k, v in interests.items() if v}
    if interests:
        profile["interests"] = interests
    else:
        profile.pop("interests", None)
    profile["updated_at"] = store.now_iso()
    store.save_profile(session_id, profile)
    return build_context_payload(session_id, profile)


@router.delete("/api/sessions/{session_id}/context/sources/{source_id}")
async def delete_source(session_id: str, source_id: str):
    _session(session_id)
    profile = _profile(session_id)
    sources = list(profile.get("context_sources") or [])
    filtered = [source for source in sources if source.get("id") != source_id]
    if len(filtered) == len(sources): raise HTTPException(404, "Context source not found.")
    profile["context_sources"] = filtered
    profile["updated_at"] = store.now_iso()
    store.save_profile(session_id, profile)
    return build_context_payload(session_id, profile)
