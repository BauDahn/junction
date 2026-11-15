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


def test_issuer_round_classifies_as_startup_unless_investing_edges_outnumber_issuances(client):
    graph = MemoryGraph()
    graph.add_node({"id": "hybrid", "type": "Company", "name": "Hybrid", "props": {}})
    graph.add_node({"id": "round", "type": "FundingRound", "name": "Series B", "props": {}})
    graph.add_node({"id": "round-b", "type": "FundingRound", "name": "Series C", "props": {}})
    graph.add_node({"id": "portfolio-a", "type": "Company", "name": "Portfolio A", "props": {}})
    graph.add_node({"id": "portfolio-b", "type": "Company", "name": "Portfolio B", "props": {}})
    graph.add_edge({"id": "issuer", "src": "hybrid", "dst": "round", "rel": "PARTICIPATES_IN_FUNDING_ROUND",
                    "role": "ISSUER", "sources": [SOURCE]})
    graph.add_edge({"id": "investment-a", "src": "hybrid", "dst": "portfolio-a", "rel": "INVESTED_IN", "sources": [SOURCE]})
    graph.add_edge({"id": "investment-b", "src": "hybrid", "dst": "portfolio-b", "rel": "INVESTED_IN", "sources": [SOURCE]})
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    assert client.get("/api/entities/hybrid?mode=raising").json()["type"] == "startup"
    assert client.get("/api/entities/hybrid?mode=investing").json()["type"] == "investor"
    graph.add_edge({"id": "issuer-b", "src": "hybrid", "dst": "round-b", "rel": "PARTICIPATES_IN_FUNDING_ROUND",
                    "role": "ISSUER", "sources": [SOURCE]})
    assert client.get("/api/entities/hybrid?mode=investing").json()["type"] == "startup"


def test_repeated_fact_labels_merge_values_and_unique_sources(client):
    source_a = {"name": "Cala", "url": "https://cala.test/a"}
    source_b = {"name": "Cala", "url": "https://cala.test/b"}
    graph = MemoryGraph()
    graph.add_node({"id": "company", "type": "Company", "name": "Company", "props": {
        "industries": [
            {"name": "HOSPITALITY_AND_TOURISM", "sources": [source_a]},
            {"name": "HOSPITALITY_AND_TOURISM", "sources": [source_a]},
            {"name": "SOFTWARE_AND_SERVICES", "sources": [source_b]},
        ],
        "hq": {"name": "Spain", "sources": [source_a]},
    }})
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    backend_app.app.dependency_overrides[get_catalog] = lambda: MemoryCatalog([{
        "id": "company", "name": "Company", "hq": "Spain", "sources": [source_b],
    }])
    facts = client.get("/api/entities/company").json()["facts"]
    by_label = {fact["label"]: fact for fact in facts}
    assert by_label["Industry"]["value"] == "Hospitality And Tourism, Software And Services"
    assert by_label["Industry"]["sources"] == [source_a, source_b]
    assert by_label["Headquarters"]["value"] == "Spain"
    assert by_label["Headquarters"]["sources"] == [source_a, source_b]
    assert len(facts) == len(by_label)


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
    entity_id = "11111111-1111-4111-8111-111111111111"
    raw = {"id": entity_id, "name": "Live startup", "entity_type": "Company",
           "properties": {"description": {"value": "Sourced summary", "sources": [SOURCE]}},
           "relationships": {"incoming": {
               "PARTICIPATES_IN_FUNDING_ROUND": [neighbor("excluded-round", "Private round", "PrivateCompanyFundingRound", "e-private")],
               "INVESTED_IN": [neighbor("fund", "Live Fund", "Organization", "e-round", event_date="2025")],
           }, "outgoing": {"WORKS_AT": [neighbor("product", "A product", "Product", "e-product")]}}}
    cala = LiveCala(raw)
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    backend_app.app.dependency_overrides[get_cala] = lambda: cala
    first = client.get(f"/api/entities/{entity_id}")
    second = client.get(f"/api/entities/{entity_id}")
    assert first.status_code == second.status_code == 200
    assert first.json()["description"] == "Sourced summary"
    assert first.json()["loaded_at"]
    assert first.json()["rounds"] == [{"date": "2025", "leads": [], "investors": ["Live Fund"], "sources": [SOURCE]}]
    assert graph.get_node("excluded-round") is None and graph.get_node("product") is None
    assert cala.calls == 1


def test_unknown_company_detail_uses_sourced_cala_properties_and_round_cache(client):
    graph = GraphStore(MemoryKV())
    def neighbor(ident, name, entity_type, edge_id, **props):
        return {"id": ident, "name": name, "entity_type": entity_type,
                "properties": {"id": edge_id, "sources": [SOURCE], **props}}
    round_ref = neighbor("round-live", "Series A", "FundingRound", "issuer-edge", role="ISSUER")
    person_ref = neighbor("person-live", "A. Founder", "Person", "founder-edge")
    entity_id = "22222222-2222-4222-8222-222222222222"
    company = {"id": entity_id, "name": "Cala Company", "entity_type": "Company",
               "properties": {
                   "description": {"value": "Useful summary", "sources": [SOURCE]},
                   "website": {"value": "example.test", "sources": [SOURCE]},
                   "founding_date": {"value": "2020-04-01", "sources": [SOURCE]},
                   "funding_stage": {"value": "series_a", "sources": [SOURCE]},
                   "total_funding": {"value": 12000000, "sources": [SOURCE]},
                   "total_funding_units": {"value": "USD", "sources": [SOURCE]},
                   "employee_count_range": {"value": "51-100", "sources": [SOURCE]},
                   "operational_status": {"value": "active", "sources": [SOURCE]},
               }, "relationships": {
                   "incoming": {"FOUNDED": [person_ref]},
                   "outgoing": {
                       "PARTICIPATES_IN_FUNDING_ROUND": [round_ref],
                       "OPERATES_IN_INDUSTRY": [neighbor("industry", "Hospitality", "Industry", "industry-edge")],
                       "HAS_HEADQUARTERS_IN": [neighbor("country", "Spain", "Country", "hq-edge")],
                   }}}
    funding_round = {"id": "round-live", "name": "Series A", "entity_type": "FundingRound",
                     "properties": {
                         "round_label": {"value": "Series A", "sources": [SOURCE]},
                         "transaction_value": {"value": 12000000, "sources": [SOURCE]},
                         "transaction_value_units": {"value": "USD", "sources": [SOURCE]},
                         "announcement_date": {"value": "2024-06-01", "sources": [SOURCE]},
                     }, "relationships": {"incoming": {}, "outgoing": {}}}
    class Cala:
        def __init__(self): self.calls = []
        async def retrieve(self, ident, **kwargs):
            self.calls.append(ident)
            return {entity_id: company, "round-live": funding_round}[ident]
    cala = Cala()
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    backend_app.app.dependency_overrides[get_cala] = lambda: cala
    first = client.get(f"/api/entities/{entity_id}").json()
    second = client.get(f"/api/entities/{entity_id}").json()
    assert first["description"] == "Useful summary"
    facts = {fact["label"]: fact["value"] for fact in first["facts"]}
    assert facts == {"Website": "example.test", "Founded": "2020", "Stage": "Series A",
                     "Total funding": "12000000 USD", "Employees": "51-100", "Industry": "Hospitality",
                     "Headquarters": "Spain", "Status": "Active"}
    assert len(first["rounds"]) == 1
    assert first["rounds"][0]["round_type"] == "Series A"
    assert first["rounds"][0]["amount"] == "12000000 USD"
    assert first["rounds"][0]["date"] == "2024-06-01"
    assert first["people"] == [{"id": "person-live", "name": "A. Founder", "role": "Founder"}]
    assert all(fact["sources"] for fact in first["facts"])
    assert first["rounds"][0]["sources"] and first["loaded_at"]
    assert second["facts"] == first["facts"] and second["rounds"] == first["rounds"]
    assert cala.calls == [entity_id, "round-live"]


def test_detail_live_cala_request_error_is_502(client):
    backend_app.app.dependency_overrides[get_cala] = lambda: LiveCala(fail=True)
    response = client.get("/api/entities/33333333-3333-4333-8333-333333333333")
    assert response.status_code == 502
    assert response.json()["error"]["message"] == "Cala request failed."


def test_detail_live_entity_unknown_and_timeout(client, monkeypatch):
    graph = GraphStore(MemoryKV())
    backend_app.app.dependency_overrides[get_graph] = lambda: graph
    backend_app.app.dependency_overrides[get_cala] = lambda: LiveCala()
    assert client.get("/api/entities/44444444-4444-4444-8444-444444444444").status_code == 404
    from graph import loader as graph_loader
    async def slow(*args, **kwargs):
        await asyncio.sleep(0.1)
    monkeypatch.setattr(graph_loader, "expand_node", slow)
    real_wait_for = asyncio.wait_for
    monkeypatch.setattr("api.routes.asyncio.wait_for", lambda coro, timeout: real_wait_for(coro, timeout=0.01))
    response = client.get("/api/entities/55555555-5555-4555-8555-555555555555")
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
    from api import routes as api_routes
    api_routes._refresh_stats(catalog, Cala(), None)
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin")
    with TestClient(backend_app.app) as test_client:
        headers = {"X-Admin-Token": "test-admin"}
        data = test_client.get("/api/stats", headers=headers).json()
        assert data["catalog"] == {"investors": 1, "startups": 1, "total": 1,
                                    "status": {"done": 2, "total": 8}}
        assert data["cala"] == {"calls": 3}
        assert data["cala_usage"]["total"] == 0 and "by_who" in data["cala_usage"]
        backend_app.app.dependency_overrides[get_cala] = lambda: None
        assert "cala" not in test_client.get("/api/stats", headers=headers).json()
        assert test_client.get("/api/stats", headers=headers).json()["cala_usage"]["total"] == 0
    backend_app.app.dependency_overrides.clear()
