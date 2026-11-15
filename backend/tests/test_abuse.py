import pytest
from fastapi.testclient import TestClient

import app as backend_app
from api.catalog_port import MemoryCatalog, get_catalog
from api.graph_port import MemoryGraph, get_graph
from api.routes import get_cala
from chat.routes import get_llm


class EmptyCala:
    def __init__(self): self.calls = 0
    async def entities(self, query, kind):
        self.calls += 1
        return {"entities": []}


class FakeLLM:
    async def complete_json(self, system, user, schema):
        return {"parts": [{"type": "answer", "text": "OK"}]}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "chat.db"))
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog()
    backend_app.app.dependency_overrides[get_graph] = lambda: MemoryGraph()
    backend_app.app.dependency_overrides[get_llm] = lambda: FakeLLM()
    with TestClient(backend_app.app) as c:
        yield c
    backend_app.app.dependency_overrides.clear()


def register(client):
    result = client.post("/api/auth/register", json={"email": "user@example.test", "password": "password123",
        "name": "User", "company": "Acme", "role": "raiser"})
    data = result.json()
    return data["token"], data["user"]["session_id"]


def test_search_thirty_per_minute(client):
    backend_app.app.dependency_overrides[get_cala] = lambda: None
    for _ in range(30):
        assert client.get("/api/search?q=xx").status_code == 200
    response = client.get("/api/search?q=xx")
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


def test_live_chat_requires_token_and_accepts_valid_token(client, monkeypatch):
    monkeypatch.setenv("CALA_REQUIRE_AUTH", "1")
    cala = EmptyCala()
    backend_app.app.dependency_overrides[get_cala] = lambda: cala
    token, sid = register(client)
    assert client.post(f"/api/sessions/{sid}/messages", json={"text": "hello"}).status_code == 401
    response = client.post(f"/api/sessions/{sid}/messages", headers={"Authorization": f"Bearer {token}"}, json={"text": "hello"})
    assert response.status_code == 200


def test_entity_invalid_uuid_is_rejected_before_cala(client):
    cala = EmptyCala()
    backend_app.app.dependency_overrides[get_cala] = lambda: cala
    assert client.get("/api/entities/not-a-uuid").status_code == 422
    assert cala.calls == 0


def test_stats_hides_breakdowns_unless_admin_token(client, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin")
    public = client.get("/api/stats").json()
    assert "by_who" not in str(public) and "by_class" not in str(public)
    admin = client.get("/api/stats", headers={"X-Admin-Token": "test-admin"}).json()
    assert "by_who" in admin.get("cala_usage", {})
