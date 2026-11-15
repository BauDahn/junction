import asyncio
import pytest
from fastapi.testclient import TestClient
import app as backend_app
from api import enrich
from api.catalog_port import MemoryCatalog, get_catalog
from api.graph_port import MemoryGraph, get_graph
from api.routes import get_cala
from graph.store import GraphStore, MemoryKV
from chat import store

SOURCE = {"name": "Cala", "url": "https://cala.test"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "chat.db"))
    enrich.reset()
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog()
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


def test_detail_contract_sources_and_score_matches_feed(client):
    feature = {"id": "fund", "name": "Fund", "kinds": ["investor"], "description": "Fintech fund",
               "sectors": ["Fintech"], "stages": ["Seed"], "country": "Finland",
               "amount": {"min": 1_000_000, "max": 5_000_000}, "activity": {"rounds_24m": 2, "led_24m": 1},
               "rounds": [{"company": "Startup A", "round_type": "Seed", "funding_amount": "2M",
                            "year": 2026, "sector": "Fintech", "location": "Finland",
                            "is_lead": True, "sources": [SOURCE]}], "sources": [SOURCE]}
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog([feature])
    session_id = create_session(client, {"sector": "Fintech", "stage": "Seed", "location": "Finland",
                                         "raising": {"amount": "2M", "round": "Seed"}})
    card = client.get("/api/feed", params={"session_id": session_id}).json()["items"][0]
    detail = client.get("/api/entities/fund", params={"session_id": session_id}).json()
    assert detail["score"] == card["score"]
    assert detail["confidence"] == card["confidence"]
    detail_contract = {"id", "type", "name", "description", "score", "confidence", "why_match", "facts",
                       "rounds", "portfolio", "people", "loaded_at"}
    assert set(detail) <= detail_contract
    assert all(fact["sources"] for fact in detail["facts"])
    assert all(isinstance(fact["value"], str) for fact in detail["facts"])
    assert all(round_data["sources"] for round_data in detail["rounds"])
    round_contract = {"round_type", "amount", "date", "leads", "investors", "sources"}
    assert all(set(round_data) <= round_contract and "company" not in round_data for round_data in detail["rounds"])
    assert all(signal["sources"] for signal in detail["why_match"])
    assert [signal["signal"] for signal in detail["why_match"][:2]] == ["sector", "stage"]
    assert list(detail["rounds"][0]) == ["round_type", "amount", "date", "leads", "investors", "sources"]
    card = client.get("/api/feed", params={"session_id": session_id}).json()["items"][0]
    assert set(card) == {"id", "type", "name", "one_liner", "tags", "score", "confidence", "why_match", "sources"}
    size = next(fact["value"] for fact in detail["facts"] if fact["label"] == "Typical round size")
    assert size == "1M–5M"


def test_detail_score_matches_feed_for_roundless_investor_with_aggregate_features(client):
    feature = {"id": "fund", "name": "Fund", "kinds": ["investor"], "sectors": ["Fintech"],
               "stages": ["Seed"], "country": "Finland", "amount": {"min": 500_000, "max": 2_000_000},
               "activity": {"rounds_24m": 3, "led_24m": 1}, "rounds": [], "sources": [SOURCE]}
    graph = MemoryGraph()
    graph.add_node({"id": "seed", "name": "My Startup", "props": {}})
    graph.add_node({"id": "fund", "name": "Fund", "props": {}})
    graph.add_edge({"id": "edge", "src": "fund", "dst": "seed", "rel": "INVESTED_IN", "sources": [SOURCE]})
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog([feature])
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    session_id = create_session(client, {"startup_name": "My Startup", "sector": "Fintech", "stage": "Seed",
                                         "location": "Finland", "raising": {"amount": "1M", "round": "Seed"}})
    card = client.get("/api/feed", params={"session_id": session_id}).json()["items"][0]
    detail = client.get("/api/entities/fund", params={"session_id": session_id}).json()
    assert detail["score"] == card["score"]
    assert detail["confidence"] == card["confidence"]


def test_detail_without_session_omits_score_fields(client):
    feature = {"id": "fund", "name": "Fund", "kinds": ["investor"], "sources": [SOURCE]}
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog([feature])
    detail = client.get("/api/entities/fund").json()
    assert "score" not in detail and "confidence" not in detail
    assert detail["why_match"] == []


def test_detail_features_without_sources_are_not_shown(client):
    feature = {"id": "fund", "name": "Fund", "kinds": ["investor"], "description": "Unverified",
               "sectors": ["Fintech"], "sources": []}
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog([feature])
    detail = client.get("/api/entities/fund").json()
    assert "description" not in detail
    assert detail["facts"] == []


def test_graph_edges_without_sources_are_hidden_and_people_have_roles(client):
    graph = MemoryGraph()
    graph.add_node({"id": "company", "type": "Company", "name": "Company", "props": {}})
    graph.add_node({"id": "person", "type": "Person", "name": "Person", "props": {}})
    graph.add_node({"id": "portfolio", "type": "Company", "name": "Portfolio", "props": {}})
    graph.add_edge({"id": "founder", "src": "person", "dst": "company", "rel": "FOUNDED",
                    "valid_since": "2020", "sources": [SOURCE]})
    graph.add_edge({"id": "uncited-person", "src": "person", "dst": "company", "rel": "WORKS_AT", "sources": []})
    graph.add_edge({"id": "portfolio-edge", "src": "company", "dst": "portfolio", "rel": "INVESTED_IN",
                    "sources": [SOURCE]})
    graph.add_edge({"id": "uncited-portfolio", "src": "company", "dst": "portfolio", "rel": "INVESTED_IN",
                    "sources": []})
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    detail = client.get("/api/entities/company").json()
    assert detail["people"] == [{"id": "person", "name": "Person", "role": "Founder", "since": "2020"}]
    assert detail["portfolio"] == [{"id": "portfolio", "name": "Portfolio"}]


def test_graph_entity_type_uses_invested_in_direction(client):
    graph = MemoryGraph()
    graph.add_node({"id": "startup", "type": "Company", "name": "Startup", "props": {}})
    graph.add_node({"id": "fund", "type": "Organization", "name": "Fund", "props": {}})
    graph.add_node({"id": "round", "type": "FundingRound", "name": "Series A", "props": {}})
    graph.add_edge({"id": "investment", "src": "fund", "dst": "startup", "rel": "INVESTED_IN", "sources": [SOURCE]})
    graph.add_edge({"id": "issuer", "src": "startup", "dst": "round", "rel": "PARTICIPATES_IN_FUNDING_ROUND",
                    "role": "ISSUER", "sources": [SOURCE]})
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    startup = client.get("/api/entities/startup").json()
    fund = client.get("/api/entities/fund").json()
    assert startup["type"] == "startup"
    assert fund["type"] == "investor"


def test_graph_entity_type_uses_mode_when_both_roles_are_evident(client):
    graph = MemoryGraph()
    graph.add_node({"id": "hybrid", "type": "Company", "name": "Hybrid", "props": {}})
    graph.add_node({"id": "other", "type": "Company", "name": "Other", "props": {}})
    graph.add_edge({"id": "outgoing", "src": "hybrid", "dst": "other", "rel": "INVESTED_IN", "sources": [SOURCE]})
    graph.add_edge({"id": "incoming", "src": "other", "dst": "hybrid", "rel": "INVESTED_IN", "sources": [SOURCE]})
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    assert client.get("/api/entities/hybrid?mode=raising").json()["type"] == "investor"
    assert client.get("/api/entities/hybrid?mode=investing").json()["type"] == "startup"


def test_startup_rounds_group_by_event_date_and_omit_empty_date(client):
    graph = MemoryGraph()
    graph.add_node({"id": "startup", "type": "Company", "name": "Startup", "props": {}})
    graph.add_node({"id": "fund-a", "type": "Company", "name": "Fund A", "props": {}})
    graph.add_node({"id": "fund-b", "type": "Company", "name": "Fund B", "props": {}})
    graph.add_edge({"id": "round-a", "src": "fund-a", "dst": "startup", "rel": "INVESTED_IN",
                    "event_date": "2025", "is_lead": True, "sources": [SOURCE]})
    graph.add_edge({"id": "round-b", "src": "fund-b", "dst": "startup", "rel": "INVESTED_IN",
                    "event_date": "2025", "sources": [SOURCE]})
    graph.add_edge({"id": "round-c", "src": "fund-b", "dst": "startup", "rel": "INVESTED_IN", "sources": [SOURCE]})
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    detail = client.get("/api/entities/startup").json()
    dated = next(row for row in detail["rounds"] if row.get("date") == "2025")
    undated = next(row for row in detail["rounds"] if "date" not in row)
    assert dated["investors"] == ["Fund A", "Fund B"]
    assert dated["leads"] == ["Fund A"]
    assert all(row["sources"] for row in detail["rounds"])
    assert "date" not in undated


def test_startup_uses_sourced_feature_rounds_without_company_key(client):
    feature = {"id": "startup", "name": "Startup", "kinds": ["startup"], "sources": [SOURCE],
               "rounds": [{"company": "Internal company label", "round_type": "Seed",
                           "funding_amount": "3M", "year": 2025, "sources": [SOURCE]}]}
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog([feature])
    graph = MemoryGraph()
    graph.add_node({"id": "startup", "name": "Startup", "props": {}})
    graph.add_node({"id": "fund", "name": "Fund", "props": {}})
    graph.add_edge({"id": "graph-round", "src": "fund", "dst": "startup", "rel": "INVESTED_IN",
                    "event_date": "2024", "sources": [SOURCE]})
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    detail = client.get("/api/entities/startup", params={"mode": "investing"}).json()
    assert detail["rounds"] == [{"round_type": "Seed", "amount": "3M", "date": "2025",
                                 "leads": [], "investors": [], "sources": [SOURCE]}]
    assert all("company" not in round_data for round_data in detail["rounds"])


def test_detail_single_typical_amount_and_activity_facts_are_strings(client):
    feature = {"id": "fund", "name": "Fund", "kinds": ["investor"],
               "amount": {"min": 3_000_000, "max": 3_000_000},
               "activity": {"rounds_24m": 4.0, "led_24m": 2.0}, "sources": [SOURCE]}
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog([feature])
    detail = client.get("/api/entities/fund").json()
    facts = {fact["label"]: fact["value"] for fact in detail["facts"]}
    assert facts["Typical round size"] == "3M"
    assert facts["Rounds in the last 24 months"] == "4"
    assert facts["Rounds led in the last 24 months"] == "2"
    assert all(isinstance(fact["value"], str) for fact in detail["facts"])


def test_detail_not_found(client):
    assert client.get("/api/entities/missing").status_code == 404


class LiveCala:
    def __init__(self, raw=None, fail=False): self.raw, self.fail, self.calls = raw, fail, 0
    async def retrieve(self, ident, **kwargs):
        self.calls += 1
        if self.fail: raise RuntimeError("Cala request failed")
        if self.raw is None: raise KeyError(ident)
        return self.raw


def test_detail_loads_unknown_entity_once_and_reuses_graph(client):
    graph = GraphStore(MemoryKV())
    def neighbor(ident, name, entity_type, edge_id, **props):
        return {"id": ident, "name": name, "entity_type": entity_type,
                "properties": {"id": edge_id, "sources": [SOURCE], **props}}
    raw = {"id": "live-id", "name": "Live startup", "entity_type": "Company",
           "properties": {"description": {"value": "Sourced summary", "sources": [SOURCE]}},
           "relationships": {"incoming": {
               "PARTICIPATES_IN_FUNDING_ROUND": [neighbor("excluded-round", "Private round", "PrivateCompanyFundingRound", "e-private")],
               "INVESTED_IN": [neighbor("fund", "Live Fund", "Organization", "e-round", event_date="2025")],
           }, "outgoing": {"WORKS_AT": [neighbor("product", "A product", "Product", "e-product")]}}}
    cala = LiveCala(raw)
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    backend_app.app.dependency_overrides[get_cala] = lambda: cala
    first = client.get("/api/entities/live-id")
    second = client.get("/api/entities/live-id")
    assert first.status_code == second.status_code == 200
    assert first.json()["description"] == "Sourced summary"
    assert first.json()["loaded_at"]
    assert first.json()["rounds"] == [{"date": "2025", "leads": [], "investors": ["Live Fund"], "sources": [SOURCE]}]
    assert graph.get_node("excluded-round") is None and graph.get_node("product") is None
    assert cala.calls == 1


def test_detail_live_cala_request_error_is_502(client):
    backend_app.app.dependency_overrides[get_cala] = lambda: LiveCala(fail=True)
    response = client.get("/api/entities/failed-live")
    assert response.status_code == 502
    assert response.json()["error"]["message"] == "Cala request failed."


def test_detail_live_entity_unknown_and_timeout(client, monkeypatch):
    graph = GraphStore(MemoryKV())
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    backend_app.app.dependency_overrides[get_cala] = lambda: LiveCala()
    assert client.get("/api/entities/unknown-live").status_code == 404
    from graph import loader as graph_loader
    async def slow(*args, **kwargs):
        await asyncio.sleep(0.1)
    monkeypatch.setattr(graph_loader, "expand_node", slow)
    real_wait_for = asyncio.wait_for
    monkeypatch.setattr("api.routes.asyncio.wait_for", lambda coro, timeout: real_wait_for(coro, timeout=0.01))
    response = client.get("/api/entities/slow-live")
    assert response.status_code == 504
    assert response.json()["error"]["message"] == "Cala did not answer in time."


def test_stats_catalog_counts_status_and_optional_cala(tmp_path, monkeypatch):
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "stats.db"))
    catalog = MemoryCatalog([{"id": "both", "name": "Both", "kinds": ["investor", "startup"]}],
                            {"done": 2, "total": 8})
    class Cala:
        stats = {"calls": 3}

    backend_app.app.dependency_overrides[get_catalog] = lambda: catalog
    backend_app.app.dependency_overrides[get_cala] = Cala
    with TestClient(backend_app.app) as test_client:
        data = test_client.get("/api/stats").json()
        assert data == {"catalog": {"investors": 1, "startups": 1, "total": 1,
                                    "status": {"done": 2, "total": 8}}, "cala": {"calls": 3}, "cala_usage": {}}
        backend_app.app.dependency_overrides[get_cala] = lambda: None
        assert "cala" not in test_client.get("/api/stats").json()
        assert test_client.get("/api/stats").json()["cala_usage"] == {}
    backend_app.app.dependency_overrides.clear()
