import pytest
from fastapi.testclient import TestClient
import app as backend_app
from api.catalog_port import MemoryCatalog, get_catalog
from api.graph_port import MemoryGraph, get_graph
from api.routes import get_cala


class SearchCala:
    def __init__(self, fail=False): self.calls, self.fail = [], fail
    async def entities(self, query, kind):
        self.calls.append((query, kind))
        if self.fail: raise RuntimeError("unavailable")
        return {"entities": [{"id": "cala-1", "name": "Café Ventures", "entity_type": "Organization"},
                             {"id": "cala-2", "name": "Other", "entity_type": "Company"}]}


@pytest.fixture
def client():
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog([
        {"id": "local-1", "name": "Cafe Capital", "kinds": ["investor"], "description": "Local fund"},
        {"id": "local-2", "name": "Cafe Labs", "kinds": ["startup"]},
    ])
    backend_app.app.dependency_overrides[get_graph] = lambda: MemoryGraph()
    backend_app.app.dependency_overrides[get_cala] = lambda: None
    with TestClient(backend_app.app) as test_client:
        yield test_client
    backend_app.app.dependency_overrides.clear()


def test_search_folds_accents_and_merges_cala(client):
    cala = SearchCala()
    backend_app.app.dependency_overrides[get_cala] = lambda: cala
    response = client.get("/api/search", params={"q": "café", "limit": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["tried"] == ["catalog", "cala"]
    assert [item["id"] for item in data["items"]] == ["local-1", "local-2", "cala-1"]
    assert [item["type"] for item in data["items"]] == ["investor", "startup", "other"]
    assert data["items"][0]["one_liner"] == "Local fund"
    assert len(cala.calls) == 2


def test_search_returns_locals_when_cala_fails(client):
    backend_app.app.dependency_overrides[get_cala] = lambda: SearchCala(fail=True)
    result = client.get("/api/search", params={"q": "ca", "limit": 8}).json()
    assert result["tried"] == ["catalog", "cala"]
    assert [item["origin"] for item in result["items"]] == ["catalog", "catalog"]


@pytest.mark.parametrize(
    ("query", "expected_ids"),
    [("Cafe", ["local-1", "local-2"]), ("no local match", [])],
)
def test_search_without_auth_skips_cala_and_returns_catalog(client, monkeypatch, query, expected_ids):
    monkeypatch.setenv("CALA_REQUIRE_AUTH", "1")
    cala = SearchCala()
    backend_app.app.dependency_overrides[get_cala] = lambda: cala

    response = client.get("/api/search", params={"q": query, "limit": 8})

    assert response.status_code == 200
    data = response.json()
    assert data["tried"] == ["catalog"]
    assert [item["id"] for item in data["items"]] == expected_ids
    assert cala.calls == []


@pytest.mark.parametrize("query", ["x", "a" * 81])
def test_search_validates_query_length(client, query):
    assert client.get("/api/search", params={"q": query}).status_code == 422
