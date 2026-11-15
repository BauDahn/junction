import pytest

from api.catalog_port import MemoryCatalog
from api.graph_port import MemoryGraph
from api.investor_pool import apply_evidence, portfolio_investors, reset
from api.candidates import build_feed, candidate_for_entity
from api.affinity import score_candidate
from api.routes import _feedcard

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


def test_evidence_scales_low_deal_count_but_caps_at_nine_and_preserves_inputs():
    candidate = {"id": "pool", "name": "Pool", "type": "investor",
                "rounds": [{"sector": "Fintech", "sources": [SOURCE]}],
                "attrs": {"sources": [SOURCE]}}
    base = score_candidate({"sectors": ["Fintech"]}, candidate)
    original_signals = [dict(signal) for signal in base["signals"]]
    one = apply_evidence(base, {**candidate, "deals": 1})
    nine = apply_evidence(base, {**candidate, "deals": 9})
    many = apply_evidence(base, {**candidate, "deals": 15})
    assert one["score"] < nine["score"]
    assert one["signals"][-1]["value"] == pytest.approx(0.6 + 0.4 / 3.321928094887362)
    assert "Based on 1 tracked deal(s)" in one["why_match"][-1]["text"]
    assert nine["score"] == base["score"]
    assert many["score"] == base["score"]
    assert not any(signal["signal"] == "evidence" for signal in nine["signals"] + many["signals"])
    assert base["signals"] == original_signals


def test_pool_evidence_appears_in_feed_card_and_entity_detail():
    catalog, graph = setup_graph()
    feed = build_feed("user", {"sector": "Fintech", "location": "Finland"}, "raising", catalog, graph)
    row = next(item for item in feed["results"] if item["id"] == "portfolio-only")
    card = _feedcard(row)
    evidence_text = "Based on 1 tracked deal(s) with Slush attendees; score scaled to 0.72"
    assert evidence_text in card["why_match"]

    detail = candidate_for_entity("portfolio-only", "user", {"sector": "Fintech", "location": "Finland"},
                                  "raising", catalog, graph)
    assert evidence_text in [signal["text"] for signal in detail["why_match"]]
    assert detail["score"] == row["score"]


def test_investor_with_features_is_not_evidence_scaled():
    catalog, graph = setup_graph()
    catalog = MemoryCatalog([*catalog.list_features("startup"),
                             {"id": "fund", "name": "Fund", "kinds": ["investor"],
                              "sectors": ["Fintech"], "sources": [SOURCE]}])
    feed = build_feed("user", {"sector": "Fintech"}, "raising", catalog, graph)
    fund = next(item for item in feed["results"] if item["id"] == "fund")
    assert "deals" not in fund["_candidate"]
    assert not any(signal["signal"] == "evidence" for signal in fund["signals"])
