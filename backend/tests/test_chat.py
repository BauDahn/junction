import pytest
from fastapi.testclient import TestClient
import app as backend_app
from chat.routes import get_llm


class FakeLLM:
    def __init__(self, fail=False):
        self.fail = fail

    async def complete_json(self, system, user, schema):
        if self.fail:
            raise RuntimeError("offline")
        assert "parts" in schema.get("properties", {})
        return {"parts": [{"type":"profile", "text":"Tengo una startup", "claim":None, "subject":None, "attribute":None, "user_value":None, "profile_patch": {
            "startup_name": "Nube", "one_liner": "Datos simples", "sector": "SaaS", "stage": "pre-seed", "location": "Madrid", "raising_amount": "500k", "raising_round": "pre-seed", "competitors": ["Rival", "RIVAL"], "target_customers": "pymes", "new_facts": ["Fundada en 2025"]}}
        ]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "chat.db"))
    instance = TestClient(backend_app.app)
    backend_app.app.dependency_overrides[get_llm] = lambda: FakeLLM()
    yield instance
    backend_app.app.dependency_overrides.clear()


def test_chat_flow_and_profile_dedupe(client):
    sid = client.post("/api/sessions").json()["session_id"]
    first = client.post(f"/api/sessions/{sid}/messages", json={"text": "Tengo una startup"})
    assert first.status_code == 200 and first.json()["profile_updated"]
    client.post(f"/api/sessions/{sid}/messages", json={"text": "Busco clientes"})
    profile = client.get(f"/api/sessions/{sid}/profile").json()
    assert profile["startup_name"] == "Nube"
    assert profile["competitors"] == ["Rival"]
    messages = client.get(f"/api/sessions/{sid}/messages").json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert messages == sorted(messages, key=lambda m: m["created_at"])
    assert messages[-1]["blocks"][0]["type"] == "profile_update"


def test_validation_and_missing_session(client):
    assert client.get("/api/sessions/nope/messages").status_code == 404
    sid = client.post("/api/sessions").json()["session_id"]
    assert client.post(f"/api/sessions/{sid}/messages", json={"text": " "}).status_code == 400


def test_llm_failure_does_not_store_user_message(client):
    backend_app.app.dependency_overrides[get_llm] = lambda: FakeLLM(fail=True)
    sid = client.post("/api/sessions").json()["session_id"]
    response = client.post(f"/api/sessions/{sid}/messages", json={"text": "Hola"})
    assert response.status_code == 502
    assert client.get(f"/api/sessions/{sid}/messages").json()["messages"] == []


def test_query_blocks_context_and_sources(monkeypatch, client):
    from cala_core import handle_message
    async def fake(text, profile, llm, cala=None, cache_dir=None):
        assert cala is None  # el canonizador crea su propio cliente
        return {"blocks":[{"type":"cala_table", "title":"Inversores", "columns":["name"], "rows":[["Fondo"]], "sources":[{"name":"Cala", "url":"https://example.test"}]}], "profile_patch":{}}
    monkeypatch.setattr("chat.engine.cala_handle_message", fake)
    sid = client.post("/api/sessions").json()["session_id"]
    result = client.post(f"/api/sessions/{sid}/messages", json={"text":"¿Quién invirtió?", "context":{"journal_item_id":"x"}})
    assert result.status_code == 200
    assert result.json()["reply"]["text"] == "Fondo"  # una sola fila: la respuesta es la celda de Cala
    assert result.json()["reply"]["blocks"][0]["type"] == "cala_table"
    assert result.json()["reply"]["sources"] == [{"name":"Cala", "url":"https://example.test"}]
    saved = client.get(f"/api/sessions/{sid}/messages").json()["messages"]
    assert saved[-1]["blocks"] == result.json()["reply"]["blocks"]


def test_profile_role_and_interests_are_merged(monkeypatch, client):
    async def fake(text, profile, llm, cala=None, cache_dir=None):
        patch = {"role":"investor", "interests":{"sectors":["fintech"], "regions":["Spain"], "stages":["SEED"], "follows":{"companies":["Nube"], "investors":["Fund A"]}}}
        return {"blocks":[{"type":"profile_update", "changes":patch}], "profile_patch":patch}
    monkeypatch.setattr("chat.engine.cala_handle_message", fake)
    sid = client.post("/api/sessions").json()["session_id"]
    result = client.post(f"/api/sessions/{sid}/messages", json={"text":"Sigo fintech"})
    assert result.status_code == 200 and result.json()["profile_updated"]
    profile = client.get(f"/api/sessions/{sid}/profile").json()
    assert profile["role"] == "investor"
    assert profile["interests"] == {"sectors":["fintech"], "regions":["Spain"], "stages":["SEED"], "follows":{"companies":["Nube"], "investors":["Fund A"]}}


def test_json_invalido_da_400(client):
    session_id = client.post("/api/sessions").json()["session_id"]
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        content="no es json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_missing_fields_no_incluye_lo_que_ya_sabemos():
    from chat.engine import missing_fields

    profile = {"sector": "hoteltech", "location": "Barcelona", "competitors": ["Mews"], "raising": {"round": "seed"}}
    missing = missing_fields(profile)
    assert "sector" not in missing and "city" not in missing and "competitors" not in missing
    assert "what they are raising" not in missing
    assert "stage" in missing and "what the startup does" in missing


def test_executor_accepts_entity_list_result(monkeypatch):
    import asyncio
    from cala_core import executor
    async def fake_answer(text, **kw):
        return {"intent": {"entities": [{"name": "Mews"}], "attribute": "funding"}, "entity_ids": ["e1"],
                "result": [{"properties": {"total_funding": {"value": "300M", "sources": [{"name": "Cala", "url": "https://example.test"}]}}}]}
    monkeypatch.setattr(executor, "answer", fake_answer)
    block = asyncio.run(executor.execute("¿Cuánto levantó Mews?"))
    assert block["type"] == "cala_table" and block["rows"][0][:2] == ["total_funding", "300M"]


def test_executor_falls_back_to_not_found_when_cala_errors(monkeypatch):
    import asyncio
    from cala_core import executor
    async def fake_answer(text, **kw):
        return {"intent": {}, "result": {}}
    class BrokenCala:
        async def entities(self, *a, **k): raise RuntimeError("422")
        async def search(self, *a, **k): raise RuntimeError("429")
    monkeypatch.setattr(executor, "answer", fake_answer)
    block = asyncio.run(executor.execute("¿Esto es verdad?", cala=BrokenCala()))
    assert block["type"] == "not_found" and len(block["tried"]) == 4
