import pytest
from fastapi.testclient import TestClient
import app as backend_app
from chat.routes import get_llm, get_transcriber


class FakeLLM:
    async def complete_json(self, system, user, schema):
        return {"reply": "Entendido. ¿En qué ciudad estás?", "profile_patch": {}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "chat.db"))
    backend_app.app.dependency_overrides[get_llm] = lambda: FakeLLM()
    yield TestClient(backend_app.app), tmp_path
    backend_app.app.dependency_overrides.clear()


def test_audio_formats_share_text_flow_and_remove_temp(client):
    test_client, tmp_path = client
    observed = []

    async def fake_transcriber(path, hint=None):
        assert path.exists()
        observed.append(path)
        return {"text": "Busco clientes", "language": "es", "duration_s": 3}

    backend_app.app.dependency_overrides[get_transcriber] = lambda: fake_transcriber
    sid = test_client.post("/api/sessions").json()["session_id"]
    for name, mime in [("founder.m4a", "audio/mp4"), ("founder.webm", "audio/webm")]:
        response = test_client.post(f"/api/sessions/{sid}/messages", files={"audio": (name, b"audio", mime)})
        assert response.status_code == 200
        assert response.json()["message"]["text"] == "Busco clientes"
        assert response.json()["message"]["transcript"] == "Busco clientes"
    saved = test_client.get(f"/api/sessions/{sid}/messages").json()["messages"]
    assert [m["transcript"] for m in saved if m["role"] == "user"] == ["Busco clientes"] * 2
    assert all(not p.exists() for p in observed)
    assert not list(tmp_path.glob("chat-audio-*"))


@pytest.mark.parametrize("filename,mime", [("voice.bin", "application/octet-stream"), ("voice.txt", "text/plain")])
def test_rejects_unsupported_type(client, filename, mime):
    test_client, _ = client
    sid = test_client.post("/api/sessions").json()["session_id"]
    response = test_client.post(f"/api/sessions/{sid}/messages", files={"audio": (filename, b"a", mime)})
    assert response.status_code == 415


def test_rejects_audio_over_10mb(client):
    test_client, _ = client
    sid = test_client.post("/api/sessions").json()["session_id"]
    response = test_client.post(f"/api/sessions/{sid}/messages", files={"audio": ("voice.wav", b"a" * (10 * 1024 * 1024 + 1), "audio/wav")})
    assert response.status_code == 413


@pytest.mark.parametrize("result,error,status", [
    (None, RuntimeError("decoder failed"), 502),
    ({"text": "  ", "duration_s": 1}, None, 422),
    ({"text": "hola", "duration_s": 121}, None, 413),
    (None, RuntimeError("Transcripción no configurada"), 503),
])
def test_transcription_errors_and_temp_cleanup(client, result, error, status):
    test_client, _ = client
    seen = []

    async def fake_transcriber(path, hint=None):
        seen.append(path)
        if error:
            raise error
        return result

    backend_app.app.dependency_overrides[get_transcriber] = lambda: fake_transcriber
    sid = test_client.post("/api/sessions").json()["session_id"]
    response = test_client.post(f"/api/sessions/{sid}/messages", files={"audio": ("voice.m4a", b"audio", "audio/mp4")})
    assert response.status_code == status
    assert not seen[0].exists()


def test_pista_del_asr_incluye_nombres_del_perfil():
    from chat.transcribe import hint_from_profile

    hint = hint_from_profile({"startup_name": "Stayflow", "competitors": ["Mews", "Cloudbeds"]})
    assert "Stayflow" in hint and "Mews" in hint and "seed" in hint
    assert "Names" not in hint_from_profile(None)
