import pytest

from api.catalog_port import MemoryCatalog
from api.graph_port import MemoryGraph
from api.investor_pool import portfolio_investors, reset
from api.candidates import build_feed

SOURCE = {"name": "Cala", "url": "https://cala.test"}


@pytest.fixture(autouse=True)
def clear_pool(monkeypatch):
    reset()
    monkeypatch.delenv("INVESTOR_POOL_PERSONS", raising=False)
    monkeypatch.setenv("INVESTOR_POOL_MIN_DEALS", "1")
    yield
    reset()


def setup_graph():
    catalog = MemoryCatalog([
        {"id": "startup-a", "name": "Alpha", "kinds": ["startup"],
         "sectors": ["Fintech", "Payments"], "country": "Finland", "sources": [SOURCE]},
        {"id": "startup-b", "name": "Beta", "kinds": ["startup"],
         "sectors": ["Climate"], "hq": "Sweden", "sources": [SOURCE]},
    ])
    graph = MemoryGraph()
    graph.add_node({"id": "fund", "name": "Fund", "type": "Organization", "props": {}})
    graph.add_node({"id": "portfolio-only", "name": "Portfolio Fund", "type": "Company", "props": {}})
    graph.add_node({"id": "person", "name": "Person", "type": "Person", "props": {}})
    graph.add_node({"id": "no-source", "name": "No Source", "type": "Company", "props": {}})
    graph.add_edge({"id": "a", "src": "fund", "dst": "startup-a", "rel": "INVESTED_IN",
                    "event_date": "2024-03-01", "sources": [SOURCE]})
    graph.add_edge({"id": "b", "src": "fund", "dst": "startup-b", "rel": "INVESTED_IN",
                    "is_lead": True, "sources": [SOURCE]})
    graph.add_edge({"id": "c", "src": "portfolio-only", "dst": "startup-a", "rel": "INVESTED_IN",
                    "sources": [SOURCE]})
    graph.add_edge({"id": "p", "src": "person", "dst": "startup-a", "rel": "INVESTED_IN",
                    "sources": [SOURCE]})
    graph.add_edge({"id": "n", "src": "no-source", "dst": "startup-a", "rel": "INVESTED_IN", "sources": []})
    return catalog, graph


def test_pool_groups_investments_and_excludes_people_and_uncited_edges():
    catalog, graph = setup_graph()
    candidates = portfolio_investors(catalog, graph)
    assert [item["id"] for item in candidates] == ["fund", "portfolio-only"]
    fund = candidates[0]
    assert fund["deals"] == 2
    assert [round_["company"] for round_ in fund["rounds"]] == ["Alpha", "Beta"]
    assert fund["rounds"][0]["sector"] == "Fintech, Payments"
    assert fund["rounds"][0]["year"] == 2024
    assert "round_type" not in fund["rounds"][0]
    assert fund["rounds"][1]["is_lead"] is True


def test_pool_min_deals_and_person_setting(monkeypatch):
    catalog, graph = setup_graph()
    monkeypatch.setenv("INVESTOR_POOL_MIN_DEALS", "2")
    assert [item["id"] for item in portfolio_investors(catalog, graph)] == ["fund"]
    monkeypatch.setenv("INVESTOR_POOL_MIN_DEALS", "3")
    assert portfolio_investors(catalog, graph) == []
    monkeypatch.setenv("INVESTOR_POOL_MIN_DEALS", "1")
    monkeypatch.setenv("INVESTOR_POOL_PERSONS", "1")
    assert {item["id"] for item in portfolio_investors(catalog, graph)} == {"fund", "portfolio-only", "person"}


def test_raising_feed_uses_pool_rounds_without_duplicates_and_investing_unchanged():
    catalog, graph = setup_graph()
    catalog = MemoryCatalog([*catalog.list_features("startup"),
                             {"id": "fund", "name": "Fund", "kinds": ["investor"],
                              "sectors": ["Fintech"], "sources": [SOURCE]}])
    raising = build_feed("user", {"sector": "Fintech", "location": "Finland"}, "raising", catalog, graph)
    fund_rows = [row for row in raising["results"] if row["id"] == "fund"]
    assert len(fund_rows) == 1
    assert fund_rows[0]["signals"][0]["value"] == 1
    assert fund_rows[0]["why_match"]
    assert fund_rows[0]["signals"][0]["sources"] == [SOURCE]
    pool_row = next(row for row in raising["results"] if row["id"] == "portfolio-only")
    assert pool_row["signals"][0]["value"] == 1
    assert pool_row["signals"][2]["value"] == 1
    assert pool_row["why_match"]
    assert pool_row["signals"][0]["sources"] == [SOURCE]
    investing = build_feed("user", {"sector": "Fintech"}, "investing", catalog, graph)
    assert {row["id"] for row in investing["results"]} == {"startup-a", "startup-b"}
    assert "portfolio-only" not in {row["id"] for row in investing["results"]}
