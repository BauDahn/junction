"""Audio transcription providers used by the chat endpoint."""
import asyncio
import os
from pathlib import Path

import httpx


def _default_provider():
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return "none"
    return "whisper"


_model = None


def _transcribe_whisper(path: Path, hint: str | None = None):
    global _model
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")
    segments, info = _model.transcribe(str(path), vad_filter=True, language=None, initial_prompt=hint or None)
    segments = list(segments)
    return {"text": " ".join(s.text.strip() for s in segments).strip(),
            "language": info.language, "duration_s": info.duration}


async def transcribe(path: Path, hint: str | None = None):
    provider = os.getenv("TRANSCRIPTION_PROVIDER", _default_provider()).lower()
    if provider == "none":
        raise RuntimeError("Transcripción no configurada")
    if provider == "whisper":
        return await asyncio.to_thread(_transcribe_whisper, path, hint)
    if provider == "nvidia":
        api_key = os.getenv("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY no está configurada para transcripción")
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                with path.open("rb") as audio:
                    response = await client.post(
                        "https://integrate.api.nvidia.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        data={"model": os.getenv("NVIDIA_ASR_MODEL", "nvidia/parakeet-ctc-1.1b-asr"), **({"prompt": hint} if hint else {})},
                        files={"file": (path.name, audio, "application/octet-stream")},
                    )
            if response.is_error:
                raise RuntimeError(f"NVIDIA ASR respondió HTTP {response.status_code}: {response.text[:300]}")
            body = response.json()
            return {"text": body.get("text", ""), "language": body.get("language"),
                    "duration_s": body.get("duration", 0)}
        except httpx.HTTPError as exc:
            raise RuntimeError("No se pudo conectar con NVIDIA ASR") from exc
    raise RuntimeError(f"Proveedor de transcripción no válido: {provider}")


def hint_from_profile(profile: dict | None) -> str:
    """Pista para el ASR: nombres que ya conocemos y jerga de rondas, para que no los deforme."""
    profile = profile or {}
    names = [profile.get("startup_name"), *profile.get("competitors", [])]
    names = [n for n in names if n]
    terms = "pre-seed, seed, Series A, Series B, ARR, MRR, SaaS"
    return f"Startup founder talking. Terms: {terms}." + (f" Names: {', '.join(names)}." if names else "")
