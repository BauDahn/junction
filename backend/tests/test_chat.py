import pytest
from fastapi.testclient import TestClient
import app as backend_app
from chat.routes import get_llm


class FakeLLM:
    def __init__(self, fail=False):
        self.fail = fail

    async def complete_json(self, system, user, schema):
        assert "current_profile" in user
        if self.fail:
            raise RuntimeError("offline")
        return {"reply": "Entendido. ¿En qué ciudad estás?", "profile_patch": {
            "startup_name": "Nube", "one_liner": "Datos simples", "sector": "SaaS", "stage": "pre-seed", "location": "Madrid", "raising_amount": "500k", "raising_round": "pre-seed", "competitors": ["Rival", "RIVAL"], "target_customers": "pymes", "new_facts": ["Fundada en 2025"]}}


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


def test_json_invalido_da_400(client):
    session_id = client.post("/api/sessions").json()["session_id"]
    response = client.post(
        f"/api/sessions/{session_id}/messages",
        content="no es json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
