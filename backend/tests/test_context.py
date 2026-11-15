import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as backend_app
from chat import store
from chat.profile import empty_profile
from chat.routes import get_llm as chat_get_llm
from context.routes import get_llm, get_transcriber
from context.service import _parse_ticket_range


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
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "chat.db"))
    llm = FakeLLM()
    paths = []
    async def transcriber(path, hint=None):
        paths.append(Path(path))
        return {"transcript": "Stayflow raises a Seed round in Barcelona", "text": "Stayflow raises a Seed round in Barcelona", "duration_s": 10}
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
    assert profile["ticket_range"] == {"min": 1_000_000, "max": 1_000_000, "currency": "EUR"}
    assert "Investors" in profile["seeking"]
    assert context["what_we_understood"]["target_stage"] == ["Seed"]
    assert context["sources"][0]["pages"] == 6
    assert context["context_strength"]["signals_total"] == 6
    assert store.get_raw_context(sid)["text"].startswith("From sample_deck.pdf:")


def test_voice_uses_transcriber_and_removes_temp_file(setup_context):
    client, sid, _, paths = setup_context
    response = client.post(f"/api/sessions/{sid}/context/voice", files={"audio": ("memo.wav", b"audio-data", "audio/wav")})
    assert response.status_code == 200, response.text
    assert paths and not paths[0].exists()
    assert response.json()["source"]["kind"] == "voice"
    assert store.get_raw_context(sid)["text"] == "Stayflow raises a Seed round in Barcelona"


def test_note_understood_and_delete_source(setup_context):
    client, sid, _, _ = setup_context
    added = client.post(f"/api/sessions/{sid}/context/note", json={"text": "We are raising Seed in Barcelona", "title": "Pitch"}).json()
    source_id = added["source"]["id"]
    assert store.get_raw_context(sid)["text"] == "We are raising Seed in Barcelona"
    patched = client.patch(f"/api/sessions/{sid}/context/understood", json={"geography": ["Barcelona", "SPAIN"], "seeking": ["Climate investors"]})
    assert patched.status_code == 200
    assert patched.json()["profile"]["seeking"] == ["Climate investors"]
    cleared = client.patch(f"/api/sessions/{sid}/context/understood", json={"geography": []})
    assert cleared.status_code == 200
    assert client.get(f"/api/sessions/{sid}/context").json()["what_we_understood"]["geography"] == []
    deleted = client.delete(f"/api/sessions/{sid}/context/sources/{source_id}")
    assert deleted.status_code == 200 and deleted.json()["sources"] == []


def test_authenticated_raw_context_roundtrip_and_profile_reextract(setup_context):
    client, _, llm, _ = setup_context
    registered = client.post("/api/auth/register", json={"email": "raw@example.com", "password": "secret-pass-123", "name": "Founder", "company": "Acme", "role": "raiser"}).json()
    headers = {"Authorization": f"Bearer {registered['token']}"}
    assert client.get("/api/me/context/raw").status_code == 401
    assert client.get("/api/me/context/raw", headers=headers).json() == {"text": "", "updated_at": None}
    raw = "Acme\nSEED — Montréal é"
    response = client.put("/api/me/context/raw", json={"text": raw}, headers=headers)
    assert response.status_code == 200 and response.json()["text"] == raw
    assert response.json()["profile_updated"] is True
    assert llm.calls[-1][0].endswith(raw)
    appended = client.post("/api/me/context/raw/append", json={"text": "Next line"}, headers=headers)
    assert appended.json()["text"] == raw + "\nNext line"
    assert llm.calls[-1][0].endswith(raw + "\nNext line")
    assert client.put("/api/me/context/raw", json={"text": "x" * 8001}, headers=headers).status_code == 422


def test_transcribe_preview_does_not_mutate_profile_or_messages(setup_context):
    client, sid, _, _ = setup_context
    before_profile = client.get(f"/api/sessions/{sid}/profile").json()
    before_messages = client.get(f"/api/sessions/{sid}/messages").json()
    response = client.post("/api/transcribe", files={"audio": ("note.wav", b"audio-data", "audio/wav")})
    assert response.status_code == 200
    assert response.json() == {"transcript": "Stayflow raises a Seed round in Barcelona", "text": "Stayflow raises a Seed round in Barcelona"}
    after_profile = client.get(f"/api/sessions/{sid}/profile").json()
    assert {k: v for k, v in after_profile.items() if k != "updated_at"} == {k: v for k, v in before_profile.items() if k != "updated_at"}
    assert client.get(f"/api/sessions/{sid}/messages").json() == before_messages


def test_context_error_responses(setup_context, monkeypatch):
    client, sid, llm, _ = setup_context
    assert client.get("/api/sessions/nope/context").status_code == 404
    assert client.post(f"/api/sessions/{sid}/context/pdf", files={"file": ("a.txt", b"x", "text/plain")}).status_code == 415
    assert client.post(f"/api/sessions/{sid}/context/pdf", files={"file": ("a.pdf", b"", "application/pdf")}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/context/note", json={"text": " "}).status_code == 400
    assert client.post(f"/api/sessions/{sid}/context/voice", files={"audio": ("a.wav", b"", "audio/wav")}).status_code == 422
    assert client.post(f"/api/sessions/{sid}/context/audio", files={"audio": ("a.wav", b"x", "audio/wav")}).status_code == 404
    assert client.put(f"/api/sessions/{sid}/context/understood", json={"seeking": ["Investors"]}).status_code == 405
    backend_app.app.dependency_overrides[get_llm] = lambda: FakeLLM(fail=True)
    backend_app.app.dependency_overrides[chat_get_llm] = lambda: FakeLLM(fail=True)
    assert client.post(f"/api/sessions/{sid}/context/note", json={"text": "some context"}).status_code == 502


def test_parse_ticket_range_formats_and_bounds():
    assert _parse_ticket_range("€2M") == {"min": 2_000_000, "max": 2_000_000, "currency": "EUR"}
    assert _parse_ticket_range("1-3M EUR") == {"min": 1_000_000, "max": 3_000_000, "currency": "EUR"}
    assert _parse_ticket_range("$500k") == {"min": 500_000, "max": 500_000, "currency": "USD"}
    assert _parse_ticket_range("2 million") == {"min": 2_000_000, "max": 2_000_000, "currency": None}
    assert _parse_ticket_range("£1.5bn") == {"min": 1_500_000_000, "max": 1_500_000_000, "currency": "GBP"}
    assert _parse_ticket_range("2mm USD") == {"min": 2_000_000, "max": 2_000_000, "currency": "USD"}
    assert _parse_ticket_range("500 thousand") == {"min": 500_000, "max": 500_000, "currency": None}
    assert _parse_ticket_range(None, ticket_min=3_000_000, ticket_max=1_000_000, currency="EUR") == {"min": 1_000_000, "max": 3_000_000, "currency": "EUR"}
    assert _parse_ticket_range(None, ticket_min=750_000, currency="USD") == {"min": 750_000, "max": 750_000, "currency": "USD"}
    assert _parse_ticket_range("TBD") is None
    assert _parse_ticket_range("") is None


def test_ticket_range_persists_on_note_and_updates_or_clears_on_understood(setup_context):
    client, sid, _, _ = setup_context
    custom_llm = FakeLLM(result={"ticket": "1-3M EUR", "ticket_min": 1_000_000, "ticket_max": 3_000_000, "ticket_currency": "EUR"})
    backend_app.app.dependency_overrides[get_llm] = lambda: custom_llm
    backend_app.app.dependency_overrides[chat_get_llm] = lambda: custom_llm

    added = client.post(f"/api/sessions/{sid}/context/note", json={"text": "Raising 1-3M EUR"})
    assert added.status_code == 200
    profile = added.json()["profile"]
    assert profile["ticket"] == "1-3M EUR"
    assert profile["ticket_range"] == {"min": 1_000_000, "max": 3_000_000, "currency": "EUR"}

    updated = client.patch(f"/api/sessions/{sid}/context/understood", json={"target_round_size": ["$500k"]})
    assert updated.status_code == 200
    assert updated.json()["profile"]["ticket"] == "$500k"
    assert updated.json()["profile"]["ticket_range"] == {"min": 500_000, "max": 500_000, "currency": "USD"}

    non_numeric = client.patch(f"/api/sessions/{sid}/context/understood", json={"target_round_size": ["TBD"]})
    assert non_numeric.status_code == 200
    assert "ticket_range" not in non_numeric.json()["profile"]

    restored = client.patch(f"/api/sessions/{sid}/context/understood", json={"target_round_size": ["€2M"]})
    assert restored.json()["profile"]["ticket_range"] == {"min": 2_000_000, "max": 2_000_000, "currency": "EUR"}

    cleared = client.patch(f"/api/sessions/{sid}/context/understood", json={"target_round_size": []})
    assert cleared.status_code == 200
    assert "ticket" not in cleared.json()["profile"]
    assert "ticket_range" not in cleared.json()["profile"]


def test_understood_preserves_interests_follows_when_editing_or_clearing_tags(setup_context):
    client, sid, _, _ = setup_context
    profile = store.get_profile(sid) or empty_profile()
    profile["interests"] = {
        "sectors": ["fintech"],
        "stages": ["SEED"],
        "regions": ["Spain"],
        "follows": {"companies": ["Amenitiz"], "investors": ["Eight Roads"]},
    }
    store.save_profile(sid, profile)

    edited = client.patch(f"/api/sessions/{sid}/context/understood", json={"sector_focus": ["FinTech"], "geography": ["Nordics"]})
    assert edited.status_code == 200
    interests = edited.json()["profile"]["interests"]
    assert interests["sectors"] == ["fintech"]
    assert interests["regions"] == ["Nordics"]
    assert interests["follows"] == {"companies": ["Amenitiz"], "investors": ["Eight Roads"]}

    emptied = client.patch(f"/api/sessions/{sid}/context/understood", json={"sector_focus": [], "target_stage": [], "geography": []})
    assert emptied.status_code == 200
    kept_interests = emptied.json()["profile"]["interests"]
    assert kept_interests == {"follows": {"companies": ["Amenitiz"], "investors": ["Eight Roads"]}}


def test_voice_preserves_literal_transcript_and_extracts_from_clean_text(setup_context):
    client, sid, llm, _ = setup_context
    async def split_transcriber(path, hint=None):
        return {
            "transcript": "Eh bueno, buscamos €2M en Seed en Madrid",
            "text": "Buscamos €2M en Seed en Madrid",
            "duration_s": 12,
        }
    backend_app.app.dependency_overrides[get_transcriber] = lambda: split_transcriber

    response = client.post(f"/api/sessions/{sid}/context/voice", files={"audio": ("memo.wav", b"audio-data", "audio/wav")})
    assert response.status_code == 200, response.text
    assert response.json()["source"]["transcript"] == "Eh bueno, buscamos €2M en Seed en Madrid"
    assert llm.calls
    prompt = llm.calls[-1][0]
    assert "Buscamos €2M en Seed en Madrid" in prompt
    assert "Eh bueno" not in prompt
