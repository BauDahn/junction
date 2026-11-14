import asyncio
import time
import pytest
from fastapi.testclient import TestClient
import app as backend_app
from api import enrich
from api.catalog_port import MemoryCatalog, get_catalog
from api.graph_port import MemoryGraph, get_graph
from api.routes import get_cala
from chat import store

SOURCE = {"name": "Cala", "url": "https://cala.test"}


def investor(ident, name, **extra):
    return {"id": ident, "name": name, "kinds": ["investor"], "sectors": ["Fintech"],
            "stages": ["Seed"], "sources": [SOURCE], **extra}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "chat.db"))
    monkeypatch.delenv("FEED_ENRICH_TOP", raising=False)
    enrich.reset()
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog([
        investor("fund-a", "Fund A"), investor("fund-b", "Fund B"),
        {"id": "startup", "name": "Startup", "kinds": ["startup"], "sources": [SOURCE]}])
    backend_app.app.dependency_overrides[get_graph] = lambda: MemoryGraph()
    backend_app.app.dependency_overrides[get_cala] = lambda: None
    with TestClient(backend_app.app) as test_client:
        yield test_client
    backend_app.app.dependency_overrides.clear()
    enrich.reset()


def create_session(test_client, profile=None):
    session_id = test_client.post("/api/sessions").json()["session_id"]
    if profile is not None:
        store.save_profile(session_id, {"updated_at": "now", **profile})
    return session_id


def test_feed_modes_have_exact_card_contract(client):
    session_id = create_session(client, {"sector": "Fintech", "stage": "Seed"})
    for mode, expected_type in (("raising", "investor"), ("investing", "startup")):
        response = client.get("/api/feed", params={"session_id": session_id, "mode": mode})
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["type"] == expected_type
        assert set(item) == {"id", "type", "name", "one_liner", "tags", "score", "confidence",
                             "why_match", "sources"}


def test_feed_orders_by_score_then_confidence(client, monkeypatch):
    from api import routes
    monkeypatch.setattr(routes, "build_feed", lambda *args: {"note": None, "results": [
        {"id": "low", "name": "Low", "type": "investor", "score": 70, "confidence": .9,
         "why_match": [], "_candidate": {"attrs": {}}, "_features": {}},
        {"id": "tie-low", "name": "Tie low", "type": "investor", "score": 80, "confidence": .5,
         "why_match": [], "_candidate": {"attrs": {}}, "_features": {}},
        {"id": "tie-high", "name": "Tie high", "type": "investor", "score": 80, "confidence": .9,
         "why_match": [], "_candidate": {"attrs": {}}, "_features": {}}]})
    session_id = create_session(client, {})
    data = client.get("/api/feed", params={"session_id": session_id}).json()
    assert [item["id"] for item in data["items"]] == ["tie-high", "tie-low", "low"]


def test_empty_profile_and_catalog_loading_notes(client, monkeypatch):
    from api.routes import get_catalog as route_catalog
    session_id = create_session(client, {})
    response = client.get("/api/feed", params={"session_id": session_id})
    assert response.status_code == 200
    assert "Add your sector" in response.json()["confidence_note"]
    assert all(item["confidence"] < .5 for item in response.json()["items"])
    backend_app.app.dependency_overrides[route_catalog] = lambda: MemoryCatalog()
    empty = client.get("/api/feed", params={"session_id": session_id}).json()
    assert "Catalog is still loading." in empty["confidence_note"]
    backend_app.app.dependency_overrides[route_catalog] = lambda: MemoryCatalog([], {"done": 2, "total": 10})
    partial = client.get("/api/feed", params={"session_id": session_id}).json()
    assert "Catalog is still loading: 2 of 10 profiled." in partial["confidence_note"]


def test_cursor_pages_without_overlap_and_invalid_cursor(client):
    from api.routes import get_catalog as route_catalog
    features = [investor(str(i), f"Fund {i}") for i in range(5)]
    backend_app.app.dependency_overrides[route_catalog] = lambda: MemoryCatalog(features)
    session_id = create_session(client, {"sector": "Fintech"})
    seen = []
    cursor = None
    for _ in range(3):
        params = {"session_id": session_id, "limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = client.get("/api/feed", params=params).json()
        seen.extend(item["id"] for item in page["items"])
        cursor = page.get("next_cursor")
        if not cursor:
            break
    assert len(seen) == 5 and len(set(seen)) == 5
    assert "next_cursor" not in page
    bad = client.get("/api/feed", params={"session_id": session_id, "cursor": "!bad"})
    assert bad.status_code == 422


def test_feed_validates_session_id_session_and_mode(client):
    assert client.get("/api/feed").status_code == 422
    assert client.get("/api/feed", params={"session_id": "missing"}).status_code == 404
    session_id = create_session(client, {})
    assert client.get("/api/feed", params={"session_id": session_id, "mode": "invalid"}).status_code == 422
    assert client.get("/api/entities/fund-a", params={"mode": "invalid"}).status_code == 422
    assert client.post(f"/api/sessions/{session_id}/mode", json={"mode": "invalid"}).status_code == 422


def test_saved_mode_drives_feed_without_mode(client):
    session_id = create_session(client, {})
    assert client.post(f"/api/sessions/{session_id}/mode", json={"mode": "investing"}).json() == {"mode": "investing"}
    response = client.get("/api/feed", params={"session_id": session_id}).json()
    assert response["mode"] == "investing"
    assert all(item["type"] == "startup" for item in response["items"])


def test_feed_does_not_call_cala_without_enrichment(client, monkeypatch):
    class FakeCala:
        calls = 0

        async def knowledge_query(self, query):
            self.calls += 1
            return {"results": []}

    cala = FakeCala()
    from api.routes import get_cala as route_cala
    backend_app.app.dependency_overrides[route_cala] = lambda: cala
    session_id = create_session(client, {"sector": "Fintech"})
    client.get("/api/feed", params={"session_id": session_id})
    assert cala.calls == 0


def test_background_enrichment_increases_confidence_once_per_investor(client, monkeypatch):
    from api.routes import get_cala as route_cala
    monkeypatch.setenv("FEED_ENRICH_TOP", "2")

    class FakeCala:
        def __init__(self):
            self.calls = []

        async def knowledge_query(self, query):
            self.calls.append(query)
            name = "Fund A" if "Fund A" in query else "Fund B"
            return {"results": [{"company": "A Startup", "sector": "Fintech", "round_type": "Seed",
                                 "funding_amount": "2M", "year": 2026, "location": "Finland",
                                 "sources": [SOURCE]}]}

    cala = FakeCala()
    backend_app.app.dependency_overrides[route_cala] = lambda: cala
    session_id = create_session(client, {"sector": "Fintech", "stage": "Seed", "location": "Finland",
                                         "raising": {"amount": "2M", "round": "Seed"}})
    before = client.get("/api/feed", params={"session_id": session_id}).json()["items"]
    # Deja que las tareas del TestClient finalicen antes de consultar la instantánea actualizada.
    async def wait_for_enrichment():
        for _ in range(30):
            if not enrich._active:
                return
            await asyncio.sleep(.01)
    client.portal.call(wait_for_enrichment)
    after = client.get("/api/feed", params={"session_id": session_id}).json()["items"]
    old = {item["id"]: item["confidence"] for item in before}
    new = {item["id"]: item["confidence"] for item in after}
    assert new["fund-a"] > old["fund-a"]
    assert new["fund-b"] > old["fund-b"]
    assert len(cala.calls) == 2


def test_graph_distance_extra_candidates_and_seed_exclusion(client):
    from api.routes import get_catalog as route_catalog, get_graph as route_graph
    graph = MemoryGraph()
    graph.add_node({"id": "seed", "type": "Company", "name": "My Startup", "props": {}})
    graph.add_node({"id": "near", "type": "Company", "name": "Extra Fund", "props": {"sources": [SOURCE], "industries": ["Fintech"]}})
    graph.add_node({"id": "far", "type": "Company", "name": "Far Fund", "props": {"sources": [SOURCE], "industries": ["Fintech"]}})
    graph.add_edge({"id": "near-edge", "src": "near", "dst": "seed", "rel": "INVESTED_IN", "sources": [SOURCE]})
    graph.add_edge({"id": "link", "src": "far", "dst": "near", "rel": "INVESTED_IN", "sources": [SOURCE]})
    # La semilla resuelta por nombre se excluye siempre del catálogo.
    catalog = MemoryCatalog([investor("seed", "My Startup"), investor("near", "Near Fund"),
                             investor("isolated", "Isolated Fund")])
    backend_app.app.dependency_overrides[route_catalog] = lambda: catalog
    backend_app.app.dependency_overrides[route_graph] = lambda: graph
    session_id = create_session(client, {"startup_name": "My Startup", "sector": "Fintech"})
    rows = client.get("/api/feed", params={"session_id": session_id}).json()["items"]
    scores = {row["id"]: row["score"] for row in rows}
    assert "seed" not in scores
    assert scores["near"] > scores["isolated"]
    assert "far" in scores
    graph.set_view(session_id, ["seed"], {"seed", "near"})
    backend_app.app.dependency_overrides[route_catalog] = lambda: MemoryCatalog([investor("seed", "My Startup")])
    assert all(row["id"] != "seed" for row in client.get("/api/feed", params={"session_id": session_id}).json()["items"])


def test_ai_tagged_tags_and_why_match(client):
    from api.routes import get_catalog as route_catalog
    tagged = investor("tagged", "Tagged", ai_tagged=True)
    backend_app.app.dependency_overrides[route_catalog] = lambda: MemoryCatalog([tagged])
    session_id = create_session(client, {"sector": "Fintech", "stage": "Seed"})
    item = client.get("/api/feed", params={"session_id": session_id}).json()["items"][0]
    assert "Fintech (AI-tagged)" in item["tags"]
    assert any("AI-tagged" in why for why in item["why_match"])


def test_profile_ticket_range_and_sector_focus_fallback():
    from api.candidates import normalize_profile
    profile = {"sector": "Other", "interests": {"sectors": ["other"]}, "what_we_understood": {"sector_focus": "Climate"},
               "raising": {"amount": "2M"}, "ticket_range": {"min": 4_000_000, "max": 8_000_000}}
    normalized = normalize_profile(profile, "raising", [])
    assert normalized["sectors"] == ["Climate"]
    assert normalized["ticket"] == {"min": 4_000_000, "max": 8_000_000}


def test_profile_normalizes_sector_focus_lists_and_ticket_priority():
    from api.candidates import normalize_profile
    profile = {"sector": "OTHER", "interests": {"sectors": ["Other"]},
               "what_we_understood": {"sector_focus": ["Fintech", "SaaS", "other"]},
               "ticket_range": {"min": 1_000_000, "max": 3_000_000},
               "ticket": "9M", "raising": {"amount": "10M"}}
    normalized = normalize_profile(profile, "raising", [])
    assert normalized["sectors"] == ["Fintech", "SaaS"]
    assert normalized["ticket"] == {"min": 1_000_000, "max": 3_000_000}
    fallback = normalize_profile({"ticket": "500k-1M"}, "investing", [])
    assert fallback["ticket"] == {"min": 500_000, "max": 1_000_000}


def test_feed_and_detail_work_with_scalar_only_neighbors(client):
    from api.routes import get_catalog as route_catalog, get_graph as route_graph
    class ScalarGraph(MemoryGraph):
        def neighbors(self, node_id, rels=None):
            if isinstance(node_id, (list, tuple, set)):
                raise TypeError("scalar id required")
            return super().neighbors(node_id, rels)
    graph = ScalarGraph()
    graph.add_node({"id": "seed", "name": "My Startup", "props": {}})
    graph.add_node({"id": "fund", "name": "Fund", "props": {"sources": [SOURCE], "industries": ["Fintech"]}})
    graph.add_edge({"id": "edge", "src": "fund", "dst": "seed", "rel": "INVESTED_IN", "sources": [SOURCE]})
    backend_app.app.dependency_overrides[route_graph] = lambda: graph
    backend_app.app.dependency_overrides[route_catalog] = lambda: MemoryCatalog([investor("fund", "Fund")])
    session_id = create_session(client, {"startup_name": "My Startup", "sector": "Fintech"})
    assert client.get("/api/feed", params={"session_id": session_id}).status_code == 200
    assert client.get("/api/entities/fund", params={"session_id": session_id}).status_code == 200


def test_feed_ranks_three_thousand_candidates_under_one_second():
    from api.candidates import build_feed
    features = [investor(str(i), f"Fund {i:04}") for i in range(3000)]
    started = time.perf_counter()
    result = build_feed("user", {"sector": "Fintech", "stage": "Seed"}, "raising",
                        MemoryCatalog(features), MemoryGraph())
    assert len(result["results"]) == 3000
    assert time.perf_counter() - started < 1


def test_feed_uses_catalog_snapshot_without_per_item_get(client):
    class SnapshotOnlyCatalog:
        def list_features(self, kind):
            return [investor("snapshot", "Snapshot Fund")]

        def get_features(self, ident):
            raise AssertionError("feed must use list_features snapshot")

        def status(self):
            return {}

    from api.routes import get_catalog as route_catalog
    backend_app.app.dependency_overrides[route_catalog] = lambda: SnapshotOnlyCatalog()
    session_id = create_session(client, {"sector": "Fintech"})
    response = client.get("/api/feed", params={"session_id": session_id})
    assert response.status_code == 200
    assert response.json()["items"][0]["id"] == "snapshot"


def test_one_liner_word_boundary_and_ellipsis():
    from api.routes import _one_liner
    description = "word " * 40
    result = _one_liner(description)
    assert result.endswith("…")
    assert len(result) <= 161
    assert not result.removesuffix("…").endswith(" ")
