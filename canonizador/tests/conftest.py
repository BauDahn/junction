import pytest
import os

os.environ["GEMINI_API_KEY"] = "test-only-not-a-key"
os.environ["GOOGLE_API_KEY"] = ""
os.environ["LLM_PROVIDER"] = "codex"


@pytest.fixture(autouse=True)
def _sin_cache_remota(monkeypatch):
    """Los tests nunca usan la caché compartida real (Valkey), aunque VALKEY_URL esté en backend/.env."""
    monkeypatch.setenv("VALKEY_URL", "")
    monkeypatch.setenv("GEMINI_API_KEY", "test-only-not-a-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "")
    monkeypatch.setenv("LLM_PROVIDER", "codex")
