import pytest


@pytest.fixture(autouse=True)
def _sin_cache_remota(monkeypatch):
    """Los tests nunca usan la caché compartida real (Valkey), aunque VALKEY_URL esté en backend/.env."""
    monkeypatch.setenv("VALKEY_URL", "")
