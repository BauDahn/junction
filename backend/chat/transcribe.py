"""Audio transcription and intent cleanup for chat."""
import asyncio
import logging
import os
from pathlib import Path

import httpx
from core.config import settings
from core.llm import make_llm

logger = logging.getLogger(__name__)
_model = None


def whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def effective_provider() -> str:
    configured = os.getenv("TRANSCRIPTION_PROVIDER")
    if configured:
        return configured.lower()
    if settings.gemini_api_key:
        return "gemini"
    return "whisper" if whisper_available() else "none"


def mime_for(path_o_nombre, content_type=None) -> str:
    aliases = {"audio/x-m4a": "audio/mp4", "audio/x-wav": "audio/wav", "application/ogg": "audio/ogg"}
    known = {"audio/webm", "audio/mp4", "audio/wav", "audio/mpeg", "audio/ogg"}
    if content_type:
        normalized = aliases.get(content_type.lower(), content_type.lower())
        if normalized in known:
            return normalized
    return {".webm": "audio/webm", ".m4a": "audio/mp4", ".wav": "audio/wav",
            ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}.get(Path(path_o_nombre).suffix.lower(), "audio/webm")


def _transcribe_whisper(path: Path, hint: str | None = None):
    global _model
    from faster_whisper import WhisperModel
    if _model is None:
        _model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    segments, info = _model.transcribe(str(path), vad_filter=True, language=None, initial_prompt=hint or None)
    text = " ".join(s.text.strip() for s in segments).strip()
    return {"text": text, "transcript": text, "language": info.language, "duration_s": info.duration}


async def _gemini_llm():
    llm, _ = make_llm("gemini", tier="fast", model=os.getenv("GEMINI_TRANSCRIBE_MODEL") or None)
    return llm


def _whisper_transcribe(path, hint=None):
    return _transcribe_whisper(path, hint)


SCHEMA = {"type": "object", "properties": {key: {"type": "string"} for key in ("transcript", "text", "language")}, "required": ["transcript", "text", "language"]}
SYSTEM = ('Return transcript as the exact words spoken, verbatim, word for word. Return text as only the speaker’s intended request or question, applying self-corrections and removing fillers and discourse openers wherever they occur, including "bueno", "a ver", "eh", "o sea", "um", "so", "like", and "you know". Preserve proper names exactly; do not add facts or answer the question, and keep the SAME language. Examples: "Series A... no, sorry, Series B of Amenitiz" → "Who led Series B of Amenitiz?"; "Bueno, a ver, compare Factorial with Amenitiz" → "Compare Factorial with Amenitiz." Return language as the ISO 639-1 language code.')


async def _gemini_transcribe(path: Path, hint: str | None, mime: str):
    llm = await _gemini_llm()
    user = "Transcribe and clean the attached audio."
    if hint:
        user += f" Known proper names (preserve spelling exactly): {hint}"
    result = await llm.complete_json(SYSTEM, user, SCHEMA, audio=(path.read_bytes(), mime))
    return result


async def transcribe(path: Path, hint: str | None = None, mime: str | None = None):
    provider = effective_provider()
    if provider == "none":
        raise RuntimeError("Transcripción no configurada")
    if provider == "whisper":
        return await asyncio.to_thread(_whisper_transcribe, path, hint)
    if provider == "gemini":
        original_error = None
        try:
            result = await _gemini_transcribe(path, hint, mime or mime_for(path))
            text = str(result.get("text") or "").strip()
            if not text:
                raise RuntimeError("Gemini devolvió texto vacío")
            transcript = str(result.get("transcript") or "").strip() or text
            return {"text": text, "transcript": transcript, "language": result.get("language") or ""}
        except Exception as exc:
            original_error = exc
        logger.warning("Gemini audio failed; attempting local whisper fallback")
        if whisper_available():
            return await asyncio.to_thread(_whisper_transcribe, path, hint)
        raise original_error
    if provider == "nvidia":
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY no está configurada para transcripción")
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                with path.open("rb") as audio:
                    response = await client.post("https://integrate.api.nvidia.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        data={"model": os.getenv("NVIDIA_ASR_MODEL", "nvidia/parakeet-ctc-1.1b-asr"), **({"prompt": hint} if hint else {})},
                        files={"file": (path.name, audio, mime or mime_for(path))})
            if response.is_error:
                raise RuntimeError(f"NVIDIA ASR respondió HTTP {response.status_code}: {response.text[:300]}")
            body = response.json()
            text = body.get("text", "")
            return {"text": text, "transcript": text, "language": body.get("language") or "", "duration_s": body.get("duration", 0)}
        except httpx.HTTPError as exc:
            raise RuntimeError("No se pudo conectar con NVIDIA ASR") from exc
    raise RuntimeError(f"Proveedor de transcripción no válido: {provider}")


def hint_from_profile(profile: dict | None) -> str:
    profile = profile or {}
    names = []
    def add(value):
        if isinstance(value, dict): value = value.get("name")
        if isinstance(value, str) and value.strip() and value not in names: names.append(value)
    add(profile.get("startup_name"))
    for item in profile.get("competitors") or []: add(item)
    interests = profile.get("interests") or {}
    follows = interests.get("follows") or {}
    for key in ("companies", "investors"):
        for item in follows.get(key) or []: add(item)
    terms = "pre-seed, seed, Series A, Series B, ARR, MRR, SaaS"
    return f"Startup founder talking. Terms: {terms}." + (f" Names: {', '.join(names)}." if names else "")
