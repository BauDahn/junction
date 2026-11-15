import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, Request
from pydantic import BaseModel, Field

from accounts import security, store
from chat import store as chat_store

router = APIRouter()
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class RegisterInput(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str
    company: str
    role: str


class LoginInput(BaseModel):
    email: str
    password: str


def _public(user):
    return {key: user[key] for key in ("id", "email", "name", "company", "role", "session_id", "created_at")}


def _issue_token(user_id):
    token, digest = security.new_token()
    store.create_token(digest, user_id, store.token_expiry())
    return token


def _authenticated(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "unauthorized")
    user = store.get_user_by_token(security.token_hash(authorization[7:]))
    if not user:
        raise HTTPException(401, "unauthorized")
    return user


async def current_user(authorization: str | None = Header(default=None)):
    return _authenticated(authorization)


@router.post("/api/auth/register", status_code=201)
async def register(body: RegisterInput, request: Request):
    from core.abuse import enforce, client_ip
    enforce(request, "register", f"ip:{client_ip(request)}", 5, 60)
    email = body.email.strip().lower()
    if not EMAIL_RE.fullmatch(email) or body.role not in ("raiser", "investor"):
        raise HTTPException(422, "Invalid email or role.")
    if store.get_user_by_email(email):
        raise HTTPException(409, "email_taken")
    now = datetime.now(timezone.utc).isoformat()
    session_id = uuid4().hex
    chat_store.create_session(session_id, now)
    chat_store.save_mode(session_id, "raising" if body.role == "raiser" else "investing")
    user = {"id": uuid4().hex, "email": email, "password_hash": security.hash_password(body.password),
            "name": body.name, "company": body.company, "role": body.role,
            "session_id": session_id, "created_at": now}
    try:
        store.create_user(user)
    except Exception as exc:
        if store.get_user_by_email(email):
            raise HTTPException(409, "email_taken") from exc
        raise
    return {"token": _issue_token(user["id"]), "user": _public(user)}


@router.post("/api/auth/login")
async def login(body: LoginInput):
    user = store.get_user_by_email(body.email.strip().lower())
    if not user or not security.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "invalid_credentials")
    return {"token": _issue_token(user["id"]), "user": _public(user)}


@router.post("/api/auth/logout", status_code=204)
async def logout(authorization: str | None = Header(default=None)):
    _authenticated(authorization)
    store.delete_token(security.token_hash(authorization[7:]))
    return Response(status_code=204)


@router.get("/api/me")
async def me(user=Depends(current_user)):
    return _public(user)
