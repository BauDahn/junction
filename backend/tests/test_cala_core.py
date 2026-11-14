import asyncio

from cala_core import handle_message
from cala_core import _profile_patch
from cala_core.executor import _sources
from cala_core import executor
from cala_core.claims import check


class FakeLLM:
    def __init__(self, responses): self.responses = list(responses)
    async def complete_json(self, system, user, schema): return self.responses.pop(0)


class FakeCala:
    def __init__(self, entities=None, intro=None, retrieved=None, search=None):
        self.entities_result = entities or []; self.intro = intro or {}; self.retrieved = retrieved or {}; self.search_result = search or {"answer": "", "sources": []}; self.calls = []
    async def entities(self, name, entity_type): self.calls.append(("entity", name)); return self.entities_result
    async def introspection(self, entity_id): self.calls.append(("introspection", entity_id)); return self.intro
    async def retrieve(self, entity_id, **kwargs): self.calls.append(("retrieve", entity_id)); return self.retrieved
    async def search(self, input): self.calls.append(("search", input)); return self.search_result


def run(coro): return asyncio.run(coro)


def test_mixed_message_creates_each_block_type(monkeypatch):
    async def fake_execute(text, **kwargs): return {"type": "cala_table", "columns": ["amount"], "rows": [[50]], "sources": []}
    monkeypatch.setattr("cala_core.execute", fake_execute)
    llm = FakeLLM([{"parts": [
        {"type": "query", "text": "¿Quién invirtió en Mews?", "claim": None, "subject": None, "attribute": None, "user_value": None, "profile_patch": {}},
        {"type": "claim", "text": "Mews levantó 50 millones", "claim": "Mews levantó 50 millones", "subject": "Mews", "attribute": "funding", "user_value": "50 millones", "profile_patch": {}},
        {"type": "profile", "text": "somos Stayflow", "claim": None, "subject": None, "attribute": None, "user_value": None, "profile_patch": {"startup_name": "Stayflow", "one_liner": "", "competitors": [], "interests": {"sectors": ["FinTech"], "regions": ["nórdicas", "Nordic countries", "España"], "stages": ["seed", "Series A"], "follows": {"companies": [], "investors": []}}}},
        {"type": "chitchat", "text": "gracias", "claim": None, "subject": None, "attribute": None, "user_value": None, "profile_patch": {}}]},
        {"verdict": "confirmed", "explanation": "Coincide con la evidencia de Cala."}])
    got = run(handle_message("mixto", {}, llm))
    assert [x["type"] for x in got["blocks"]] == ["cala_table", "claim_check", "profile_update", "text"]
    assert got["profile_patch"]["startup_name"] == "Stayflow"
    assert got["profile_patch"]["interests"] == {"sectors": ["fintech"], "regions": ["Nordics", "Spain"], "stages": ["SEED", "SERIES_A"]}
    assert "one_liner" not in got["profile_patch"]
    assert got["blocks"][2]["changes"] == got["profile_patch"]


def test_empty_fallback_visits_entities_then_search_then_not_found(monkeypatch, tmp_path):
    async def fake_answer(*args, **kwargs): return {"intent": {"entities": [{"name": "Mews"}]}, "result": {"query": "canonical query", "rows": []}}
    monkeypatch.setattr(executor, "answer", fake_answer)
    cala = FakeCala()
    block = run(executor.execute("Mews", cala=cala, llm=FakeLLM([]), cache_dir=tmp_path))
    assert block["type"] == "not_found"
    assert [call[0] for call in cala.calls] == ["entity", "search"]
    assert [x["tool"] for x in block["tried"]] == ["knowledge_query", "entity", "knowledge_search"]


def test_claim_verdicts():
    for expected in ("confirmed", "contradicted", "no_data"):
        llm = FakeLLM([{"verdict": expected, "explanation": "resultado"}])
        result = run(check({"claim": "Mews raised 50m"}, {"type": "cala_table", "rows": [[50]], "sources": []}, llm))
        assert result["verdict"] == expected


def test_cala_rows_preserve_values(monkeypatch):
    rows = [{"amount": "€50m", "date": "2026-01-01"}]
    async def fake_answer(*args, **kwargs): return {"intent": {"attribute": "funding_round", "entities": [{"name": "Amenitiz"}], "filters": {"round_label": "SERIES_B"}}, "result": {"query": "exact", "rows": rows, "sources": []}}
    monkeypatch.setattr(executor, "answer", fake_answer)
    block = run(executor.execute("q", cala=None, llm=FakeLLM([])))
    assert block["columns"] == ["amount", "date"]
    assert block["rows"] == [["€50m", "2026-01-01"]]
    assert block["title"] == "Amenitiz · ronda Series B"


def test_sources_normalize_shape_and_deduplicate():
    sources = _sources({"sources": [
        {"name": "Cala filing", "document": "https://example.test/a", "date": "2026-01-01", "rank": "FILING"},
        {"name": "Cala filing", "url": "https://example.test/a", "date": "2026-01-01", "source_rank": "FILING"},
        {"name": "Cala internal source", "document": None},
    ]})
    assert sources == [
        {"name": "Cala filing", "url": "https://example.test/a", "date": "2026-01-01", "source_rank": "FILING"},
        {"name": "Cala internal source"},
    ]


def test_profile_patch_drops_empty_values_and_empty_interest_groups():
    assert _profile_patch({"startup_name": "", "competitors": [], "raising_amount": None,
                          "interests": {"regions": [], "stages": [""], "follows": {"companies": [], "investors": []}}}) == {}
