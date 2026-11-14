import asyncio
import os
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from verifier.config import settings
from verifier.llm import make_llm
from verifier.pipeline import verify_pdf

ROOT = Path(__file__).parent
MAX_PDF_BYTES = 20 * 1024 * 1024
app = FastAPI(title="Deck Verifier")
ERROR_CODES = {
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
jobs: dict[str, dict] = {}
tasks: dict[str, asyncio.Task] = {}


async def _run_job(job_id: str, path: Path):
    job = jobs[job_id]
    job["started_at"] = time.monotonic()

    def on_progress(stage, done, total):
        job.update(status=stage, progress={"done": done, "total": total})

    try:
        job["report"] = await verify_pdf(path, on_progress=on_progress)
        job.update(status="done", progress={"done": 1, "total": 1})
    except Exception as exc:
        job.update(status="error", error=str(exc))
    finally:
        job["elapsed_s"] = round(time.monotonic() - job["started_at"], 1)
        job.pop("started_at", None)
        path.unlink(missing_ok=True)


async def _create_job(data: bytes, suffix: str = ".pdf"):
    if not data:
        raise HTTPException(400, "The uploaded PDF is empty.")
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF must be 20 MB or smaller.")
    job_id = uuid.uuid4().hex
    fd, filename = tempfile.mkstemp(prefix="deck-", suffix=suffix, dir=ROOT)
    path = Path(filename)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    jobs[job_id] = {"status": "queued", "progress": {"done": 0, "total": 0}, "elapsed_s": 0}
    tasks[job_id] = asyncio.create_task(_run_job(job_id, path))
    return {"job_id": job_id}


@app.get("/")
async def index():
    return FileResponse(ROOT / "static" / "index.html")


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
        # Aún no hay transcripción: "none" hasta elegir proveedor (issue #4).
        "transcription": os.getenv("TRANSCRIPTION_PROVIDER", "none"),
    }


@app.post("/api/verify")
async def verify(file: UploadFile = File(...)):
    if file.content_type not in {"application/pdf", "application/octet-stream"} and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(415, "Upload a PDF file.")
    return await _create_job(await file.read())


@app.post("/api/verify-sample")
async def verify_sample():
    sample = ROOT / "examples" / "sample_deck.pdf"
    if not sample.exists():
        raise HTTPException(404, "Sample deck is unavailable.")
    return await _create_job(sample.read_bytes())


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    result = dict(job)
    if "started_at" in job:
        result["elapsed_s"] = round(time.monotonic() - job["started_at"], 1)
    return {"job_id": job_id, **result}
