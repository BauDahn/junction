from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from verifier.llm import make_llm
from . import store
from .engine import handle_text
from .profile import empty_profile

router = APIRouter()


class MessageInput(BaseModel):
    text: str


def get_llm():
    return make_llm()[0]


def _session(session_id):
    if not store.session_exists(session_id):
        raise HTTPException(404, "Session not found.")


@router.post("/api/sessions")
async def create_session():
    from uuid import uuid4
    session_id = uuid4().hex
    store.create_session(session_id, store.now_iso())
    return {"session_id": session_id}


@router.post("/api/sessions/{session_id}/messages")
async def post_message(session_id: str, request: Request, llm=Depends(get_llm)):
    _session(session_id)
    if "multipart/form-data" in request.headers.get("content-type", ""):
        raise HTTPException(415, "Audio aún no soportado")
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(400, "Body must be JSON with a text field.")
    text = payload.get("text", "") if isinstance(payload, dict) else ""
    if not isinstance(text, str) or not text.strip():
        raise HTTPException(400, "Text must not be empty.")
    if len(text) > 4000:
        raise HTTPException(413, "Text must be 4000 characters or fewer.")
    try:
        user, reply, profile = await handle_text(session_id, text.strip(), llm)
    except Exception as exc:
        raise HTTPException(502, "El modelo no respondió, intenta de nuevo.") from exc
    store.add_message(user)
    store.add_message(reply)
    if profile is not None:
        store.save_profile(session_id, profile)
    return {"message": {k: v for k, v in user.items() if k != "session_id"}, "reply": {k: v for k, v in reply.items() if k != "session_id"}, "profile_updated": profile is not None, "recommendations_status": "idle"}


@router.get("/api/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    _session(session_id)
    return {"messages": store.list_messages(session_id)}


@router.get("/api/sessions/{session_id}/profile")
async def get_session_profile(session_id: str):
    _session(session_id)
    return store.get_profile(session_id) or empty_profile()
