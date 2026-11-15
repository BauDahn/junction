import pytest
from fastapi.testclient import TestClient
import app as backend_app
from chat.routes import get_llm, get_transcriber


class FakeLLM:
    async def complete_json(self, system, user, schema):
        assert "parts" in schema.get("properties", {})
        return {"parts": [{"type":"chitchat", "text":"Busco clientes", "claim":None, "subject":None, "attribute":None, "user_value":None, "profile_patch":{}}]}


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
    (None, RuntimeError("Transcription is not configured."), 503),
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


def test_pista_incluye_follows():
    from chat.transcribe import hint_from_profile
    hint = hint_from_profile({"startup_name": "Acme", "interests": {"follows": {
        "companies": ["Mews", {"name": "Amenitiz"}, {"name": "Mews"}],
        "investors": [{"name": "Northzone"}, "Seedcamp"]}}})
    assert all(name in hint for name in ("Acme", "Mews", "Amenitiz", "Northzone", "Seedcamp"))
    assert hint.count("Mews") == 1


@pytest.mark.parametrize("name,expected", [("a.webm", "audio/webm"), ("a.m4a", "audio/mp4"),
    ("a.wav", "audio/wav"), ("a.mp3", "audio/mpeg"), ("a.ogg", "audio/ogg")])
def test_mime_for(name, expected):
    from chat.transcribe import mime_for
    assert mime_for(name) == expected


def test_audio_message_uses_intent_and_keeps_literal(client):
    test_client, _ = client
    intended = "Who led Series B of Amenitiz?"
    literal = "Who led Series A... no, sorry, Series B of Amenitiz?"
    class IntentLLM:
        async def complete_json(self, system, user, schema):
            assert intended in user
            return {"parts": [{"type": "chitchat", "text": "ok", "claim": None, "subject": None,
                               "attribute": None, "user_value": None, "profile_patch": {}}]}
    async def fake_transcriber(path, hint=None):
        return {"text": intended, "transcript": literal, "language": "en"}
    backend_app.app.dependency_overrides[get_llm] = lambda: IntentLLM()
    backend_app.app.dependency_overrides[get_transcriber] = lambda: fake_transcriber
    sid = test_client.post("/api/sessions").json()["session_id"]
    response = test_client.post(f"/api/sessions/{sid}/messages", files={"audio": ("voice.webm", b"audio", "audio/webm")})
    assert response.status_code == 200
    message = response.json()["message"]
    assert message["text"] == intended and message["transcript"] == literal
    saved = test_client.get(f"/api/sessions/{sid}/messages").json()["messages"]
    assert saved[0]["text"] == intended and saved[0]["transcript"] == literal


def test_voice_profile_prompt_and_pipeline_preserve_uncertain_names(client, monkeypatch, tmp_path):
    import asyncio
    from chat import transcribe

    transcript = "Saiflow, software for hotels in Barcelona. We are raising a seed round of 2 million euros."
    cleaned = "Saiflow, hotel software in Barcelona. We are raising a seed round of 2 million euros."

    class AudioLLM:
        async def complete_json(self, system, user, schema, audio=None):
            assert "Preserve ALL factual information" in system
            assert "Keep uncertain or possibly misrecognized proper names exactly as heard" in system
            assert "Do not turn statements into questions" in system
            assert "transcript" in schema["required"] and audio
            return {"transcript": transcript, "text": cleaned, "language": "en"}

    async def fake_audio_llm():
        return AudioLLM()

    monkeypatch.setattr(transcribe, "_gemini_llm", fake_audio_llm)
    path = tmp_path / "founder.wav"
    path.write_bytes(b"audio")
    result = asyncio.run(transcribe._gemini_transcribe(path, None, "audio/wav"))
    assert result["text"] == cleaned

    class RouterLLM:
        async def complete_json(self, system, user, schema):
            assert cleaned in user
            assert "Stayflow" not in user  # router gets the uncertain ASR spelling as-is
            return {"parts": [{"type": "profile", "text": cleaned, "claim": None, "subject": None,
                "attribute": None, "user_value": None, "profile_patch": {
                    "startup_name": "Saiflow", "one_liner": "Hotel software", "sector": "hotel tech",
                    "location": "Barcelona", "raising_round": "seed", "raising_amount": "2 million euros"}}]}

    backend_app.app.dependency_overrides[get_llm] = lambda: RouterLLM()
    async def fake_transcriber(audio_path, hint=None): return result
    backend_app.app.dependency_overrides[get_transcriber] = lambda: fake_transcriber
    test_client, _ = client
    sid = test_client.post("/api/sessions").json()["session_id"]
    response = test_client.post(f"/api/sessions/{sid}/messages", files={"audio": ("founder.wav", b"audio", "audio/wav")})
    assert response.status_code == 200
    message = response.json()["message"]
    assert message["text"] == cleaned and message["transcript"] == transcript
    profile = test_client.get(f"/api/sessions/{sid}/profile").json()
    assert profile["startup_name"] == "Saiflow"
    assert profile["one_liner"] == "Hotel software" and profile["location"] == "Barcelona"


def test_gemini_fallbacks(monkeypatch, tmp_path):
    import asyncio
    import chat.transcribe as module
    monkeypatch.setenv("TRANSCRIPTION_PROVIDER", "gemini")
    monkeypatch.setattr(module, "whisper_available", lambda: True)
    monkeypatch.setattr(module, "_whisper_transcribe", lambda path, hint=None: {"text": "local", "transcript": "local", "language": "en"})
    async def broken(*args): raise RuntimeError("offline")
    monkeypatch.setattr(module, "_gemini_transcribe", broken)
    assert asyncio.run(module.transcribe(tmp_path / "a.webm"))["transcript"] == "local"
    async def empty(*args): return {"text": "  ", "transcript": "", "language": "en"}
    monkeypatch.setattr(module, "_gemini_transcribe", empty)
    assert asyncio.run(module.transcribe(tmp_path / "a.webm"))["text"] == "local"
    monkeypatch.setattr(module, "whisper_available", lambda: False)
    with pytest.raises(RuntimeError): asyncio.run(module.transcribe(tmp_path / "a.webm"))


def test_effective_provider_and_health(client, monkeypatch):
    from chat import transcribe as module
    from types import SimpleNamespace
    test_client, _ = client
    monkeypatch.delenv("TRANSCRIPTION_PROVIDER", raising=False)
    monkeypatch.setattr(module, "settings", SimpleNamespace(gemini_api_key="key"))
    assert test_client.get("/api/health").json()["transcription"] == "gemini"
    monkeypatch.setattr(module, "settings", SimpleNamespace(gemini_api_key=""))
    monkeypatch.setattr(module, "whisper_available", lambda: True)
    assert test_client.get("/api/health").json()["transcription"] == "whisper"
    monkeypatch.setattr(module, "whisper_available", lambda: False)
    assert test_client.get("/api/health").json()["transcription"] == "none"
    monkeypatch.setenv("TRANSCRIPTION_PROVIDER", "NVIDIA")
    assert test_client.get("/api/health").json()["transcription"] == "nvidia"
