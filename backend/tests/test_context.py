import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as backend_app
from chat import store
from chat.routes import get_llm as chat_get_llm
from context.routes import get_llm, get_transcriber


class FakeLLM:
    def __init__(self, result=None, fail=False):
        self.result = result or {"startup_name": "Stayflow", "sector": "Travel", "stage": "Seed", "location": "Barcelona", "ticket": "€1M", "raising_amount": "€1M", "raising_round": "Seed", "role": "founder", "what_we_understood": {"seeking": ["Investors"]}}
        self.calls = []
        self.fail = fail

    async def complete_json(self, system, prompt, schema, images=None):
        if self.fail: raise RuntimeError("offline")
        self.calls.append((prompt, images))
        return self.result


@pytest.fixture
def setup_context(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "chat.db"))
    llm = FakeLLM()
    paths = []
    async def transcriber(path, hint=None):
        paths.append(Path(path))
        return {"text": "Stayflow raises a Seed round in Barcelona", "duration_s": 10}
    backend_app.app.dependency_overrides[get_llm] = lambda: llm
    backend_app.app.dependency_overrides[chat_get_llm] = lambda: llm
    backend_app.app.dependency_overrides[get_transcriber] = lambda: transcriber
    with TestClient(backend_app.app) as client:
        session_id = client.post("/api/sessions").json()["session_id"]
        yield client, session_id, llm, paths
    backend_app.app.dependency_overrides.clear()


def test_pdf_sample_extracts_and_persists_context(setup_context):
    client, sid, llm, _ = setup_context
    sample = Path(__file__).parents[1] / "examples" / "sample_deck.pdf"
    response = client.post(f"/api/sessions/{sid}/context/pdf", files={"file": ("sample_deck.pdf", sample.read_bytes(), "application/pdf")})
    assert response.status_code == 200, response.text
    assert llm.calls and len(llm.calls[0][1]) == 6
    prompt, images = llm.calls[0]
    assert all(term in prompt for term in ("Stayflow", "Seed", "Barcelona"))
    assert response.json()["source"]["pages"] == 6
    assert response.json()["source"]["kind"] == "pdf"
    profile = client.get(f"/api/sessions/{sid}/profile").json()
    context = client.get(f"/api/sessions/{sid}/context").json()
    assert profile["sector"] == "Travel" and profile["stage"] == "Seed"
    assert profile["location"] == "Barcelona" and profile["ticket"] == "€1M"
    assert "Investors" in profile["seeking"]
    assert context["what_we_understood"]["target_stage"] == ["Seed"]
    assert context["sources"][0]["pages"] == 6
    assert context["context_strength"]["signals_total"] == 6


@pytest.mark.parametrize("route", ["voice", "audio"])
def test_voice_alias_uses_transcriber_and_removes_temp_file(setup_context, route):
    client, sid, _, paths = setup_context
    response = client.post(f"/api/sessions/{sid}/context/{route}", files={"audio": ("memo.wav", b"audio-data", "audio/wav")})
    assert response.status_code == 200, response.text
    assert paths and not paths[0].exists()
    assert response.json()["source"]["kind"] == "voice"


def test_note_understood_and_delete_source(setup_context):
    client, sid, _, _ = setup_context
    added = client.post(f"/api/sessions/{sid}/context/note", json={"text": "We are raising Seed in Barcelona", "title": "Pitch"}).json()
    source_id = added["source"]["id"]
    patched = client.patch(f"/api/sessions/{sid}/context/understood", json={"geography": ["Barcelona", "SPAIN"], "seeking": ["Climate investors"]})
    assert patched.status_code == 200
    assert patched.json()["profile"]["seeking"] == ["Climate investors"]
    cleared = client.patch(f"/api/sessions/{sid}/context/understood", json={"geography": []})
    assert cleared.status_code == 200
    assert client.get(f"/api/sessions/{sid}/context").json()["what_we_understood"]["geography"] == []
    deleted = client.delete(f"/api/sessions/{sid}/context/sources/{source_id}")
    assert deleted.status_code == 200 and deleted.json()["sources"] == []


def test_context_error_responses(setup_context, monkeypatch):
    client, sid, llm, _ = setup_context
    assert client.get("/api/sessions/nope/context").status_code == 404
    assert client.post(f"/api/sessions/{sid}/context/pdf", files={"file": ("a.txt", b"x", "text/plain")}).status_code == 415
    assert client.post(f"/api/sessions/{sid}/context/pdf", files={"file": ("a.pdf", b"", "application/pdf")}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/context/note", json={"text": " "}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/context/voice", files={"audio": ("a.wav", b"", "audio/wav")}).status_code == 422
    backend_app.app.dependency_overrides[get_llm] = lambda: FakeLLM(fail=True)
    backend_app.app.dependency_overrides[chat_get_llm] = lambda: FakeLLM(fail=True)
    assert client.post(f"/api/sessions/{sid}/context/note", json={"text": "some context"}).status_code == 502
