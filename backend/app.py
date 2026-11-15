import os
import threading

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import settings
from core.llm import make_llm
from chat.routes import router as chat_router
from chat import transcribe
from api.routes import router as match_router
from context.routes import router as context_router
from accounts.routes import router as accounts_router

app = FastAPI(title="Cala Match")


@app.on_event("startup")
async def warmup_valkey():
    # La primera conexión TLS a Aiven puede tardar varios segundos; no retrases el arranque HTTP.
    def run():
        try:
            from canonizador.cache import warmup
            warmup()
        except Exception:
            pass  # Valkey es opcional; las consultas mantienen el respaldo local a disco.
    threading.Thread(target=run, name="valkey-warmup", daemon=True).start()


app.include_router(chat_router)
app.include_router(match_router)
app.include_router(context_router)
app.include_router(accounts_router)
ERROR_CODES = {
    401: "unauthorized",
    409: "conflict",
    400: "bad_request",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "invalid_request",
    429: "rate_limited",
}


def _error(status: int, message: str) -> JSONResponse:
    # Formato de docs/API.md: {"error": {"code", "message"}}
    code = ERROR_CODES.get(status, "server_error" if status >= 500 else "http_error")
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, str) and exc.detail in {"email_taken", "invalid_credentials", "unauthorized", "role_locked"}:
        return JSONResponse({"error": {"code": exc.detail, "message": exc.detail.replace("_", " ").capitalize()}}, status_code=exc.status_code)
    return _error(exc.status_code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(part) for part in first.get("loc", ()))
    return _error(422, f"{where}: {first.get('msg', 'invalid request')}".strip(": "))


# CORS abierto en desarrollo (docs/API.md); en producción, CORS_ORIGINS con los orígenes separados por comas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    try:
        _, model = make_llm()
    except Exception:
        model = os.getenv("LLM_MODEL", "")
    return {
        "provider": settings.llm_provider,
        "model": model,
        "cala": bool(settings.cala_api_key),
        "transcription": transcribe.effective_provider(),
    }


