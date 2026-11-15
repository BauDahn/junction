import asyncio

from cala_core import handle_message
from cala_core import _profile_patch
from cala_core.executor import _sources
from cala_core.router import SYSTEM, SCHEMA
from cala_core import executor
from cala_core.claims import check


class FakeLLM:
    def __init__(self, responses): self.responses = list(responses); self.calls = 0
    async def complete_json(self, system, user, schema):
        self.calls += 1
        return self.responses.pop(0)


class FakeCala:
    def __init__(self, entities=None, intro=None, retrieved=None, search=None):
        self.entities_result = entities or []; self.intro = intro or {}; self.retrieved = retrieved or {}; self.search_result = search or {"answer": "", "sources": []}; self.calls = []
    async def entities(self, name, entity_type): self.calls.append(("entity", name)); return self.entities_result
    async def introspection(self, entity_id): self.calls.append(("introspection", entity_id)); return self.intro
    async def retrieve(self, entity_id, **kwargs): self.calls.append(("retrieve", entity_id)); return self.retrieved
    async def search(self, input): self.calls.append(("search", input)); return self.search_result


def run(coro): return asyncio.run(coro)


def test_mixed_message_creates_each_block_type(monkeypatch):
    async def fake_execute(part, **kwargs): return {"type": "cala_table", "columns": ["amount"], "rows": [[50]], "sources": []}
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
    block = run(executor.execute({"text": "Mews", "canonical_question_en": "Who invested in Mews?", "has_entity": True}, cala=cala, llm=FakeLLM([]), cache_dir=tmp_path))
    assert block["type"] == "not_found"
    assert [call[0] for call in cala.calls] == ["entity", "search"]
    assert [x["tool"] for x in block["tried"]] == ["canonizer", "knowledge_query", "entity", "knowledge_search"]


def test_empty_canonizer_rows_fall_back_to_entity_table(monkeypatch, tmp_path):
    async def empty(*args, **kwargs):
        return {"intent": {"entities": [{"name": "Mews"}]}, "result": {"query": "Mews investors", "rows": []}}
    monkeypatch.setattr(executor, "answer", empty)
    cala = FakeCala(entities=[{"id": "mews", "name": "Mews"}],
                    intro={"properties": ["name"], "relationships": {}},
                    retrieved={"id": "mews", "name": "Mews", "properties": {"name": {"value": "Mews", "sources": [{"name": "Cala"}]}}})
    block = run(executor.execute({"text": "Mews", "canonical_question_en": "Who invested in Mews?", "has_entity": True}, cala=cala, cache_dir=tmp_path))
    assert block["type"] == "cala_table"


def test_canonizer_exception_falls_back_to_entity_retrieve(monkeypatch, tmp_path):
    async def broken(*args, **kwargs): raise TimeoutError("secret details")
    monkeypatch.setattr(executor, "answer", broken)
    cala = FakeCala(entities=[{"id": "mews", "name": "Mews"}],
                    intro={"properties": ["name"], "relationships": {}},
                    retrieved={"id": "mews", "name": "Mews", "properties": {"name": {"value": "Mews", "sources": [{"name": "Cala"}]}}})
    block = run(executor.execute({"text": "Mews", "canonical_question_en": "Who invested in Mews?", "has_entity": True}, cala=cala, cache_dir=tmp_path))
    assert block["type"] == "cala_table"
    assert block["call"]["tool"] == "entity"


def test_canonizer_exception_falls_back_to_cala_search(monkeypatch, tmp_path):
    async def broken(*args, **kwargs): raise TimeoutError("private error")
    monkeypatch.setattr(executor, "answer", broken)
    cala = FakeCala(search={"answer": "Cala result", "sources": [{"name": "Cala"}]})
    block = run(executor.execute({"text": "Mews", "canonical_question_en": "Who invested in Mews?", "has_entity": True}, cala=cala, cache_dir=tmp_path))
    assert block["type"] == "cala_answer" and block["markdown"] == "Cala result"
    assert block["call"]["tool"] == "knowledge_search"


def test_all_fallbacks_catch_errors_and_report_complete_attempts(monkeypatch, tmp_path):
    async def broken(*args, **kwargs): raise RuntimeError("secret")
    monkeypatch.setattr(executor, "answer", broken)
    class BrokenCala(FakeCala):
        async def entities(self, *args): self.calls.append(("entity", args[0])); raise RuntimeError("hidden")
        async def search(self, *args): self.calls.append(("search", args[0])); raise TimeoutError("hidden")
    block = run(executor.execute({"text": "Mews", "canonical_question_en": "Who invested in Mews?", "has_entity": True}, cala=BrokenCala(), cache_dir=tmp_path))
    assert block["type"] == "not_found"
    assert [entry["tool"] for entry in block["tried"]] == ["canonizer", "knowledge_query", "entity", "knowledge_search"]
    assert block["tried"][0] == {"tool": "canonizer", "error": "RuntimeError"}
    assert "secret" not in str(block)


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


def test_search_real_response_extracts_context_origins_sources_and_title():
    canonical = "How many startups fail to secure venture capital, and how long does fundraising take?"
    context = [{"content": "evidence", "origins": [
        {"source": {"name": "fallback name", "url": "https://source.test/a"}, "document": {"name": "Cala report", "url": "https://docs.test/a"}},
        {"source": {"name": "duplicate", "url": "https://docs.test/a"}, "document": {"name": "Duplicate", "url": "https://docs.test/a"}},
        {"source": {"name": "Source only", "url": "https://source.test/b"}, "document": {"name": "", "url": ""}},
    ]}]
    for i in range(15):
        context[0]["origins"].append({"document": {"name": f"Doc {i}", "url": f"https://docs.test/{i}"}, "source": {}})
    cala = FakeCala(search={"content": "## Answer", "explainability": [{"content": "reason", "references": []}], "context": context, "entities": []})
    block = run(executor.execute({"text": "pregunta", "canonical_question_en": canonical, "has_entity": False}, cala=cala))
    assert block["type"] == "cala_answer"
    assert block["markdown"] == "## Answer"
    assert block["title"] == canonical[:80]
    assert block["sources"][:2] == [
        {"name": "Cala report", "url": "https://docs.test/a"},
        {"name": "Source only", "url": "https://source.test/b"},
    ]
    assert len(block["sources"]) == 12


def test_profile_patch_drops_empty_values_and_empty_interest_groups():
    assert _profile_patch({"startup_name": "", "competitors": [], "raising_amount": None,
                          "interests": {"regions": [], "stages": [""], "follows": {"companies": [], "investors": []}}}) == {}


def test_open_question_searches_canonical_without_entity_lookup(monkeypatch, tmp_path):
    async def unexpected_answer(*args, **kwargs): raise AssertionError("canonizador answer should not run")
    monkeypatch.setattr(executor, "answer", unexpected_answer)
    cala = FakeCala(search={"answer": "## Cala data", "sources": [{"name": "Cala source", "url": "https://example.test"}]})
    block = run(executor.execute({"text": "queremos saber cuánto...", "canonical_question_en": "How many startups fail to secure venture capital?", "has_entity": False}, cala=cala, cache_dir=tmp_path))
    assert block["type"] == "cala_answer"
    assert block["call"]["query"] == "How many startups fail to secure venture capital?"
    assert block["sources"][0]["name"] == "Cala source"
    assert cala.calls == [("search", "How many startups fail to secure venture capital?")]


def test_two_queries_and_multiple_profile_parts_merge(monkeypatch):
    calls = []
    async def fake_execute(part, **kwargs):
        calls.append(part)
        return {"type": "cala_answer", "markdown": part["canonical_question_en"], "sources": []}
    monkeypatch.setattr("cala_core.execute", fake_execute)
    base = {"claim": None, "subject": None, "attribute": None, "user_value": None, "profile_patch": {}, "has_entity": False}
    llm = FakeLLM([{"parts": [
        {**base, "type": "query", "text": "a", "canonical_question_en": "How many startups fail to raise?"},
        {**base, "type": "query", "text": "b", "canonical_question_en": "How long does fundraising take?"},
        {**base, "type": "profile", "text": "city and interests", "canonical_question_en": None, "profile_patch": {"location": "Barcelona", "interests": {"sectors": ["fintech"], "regions": ["Nordics"], "stages": ["SEED"]}}},
        {**base, "type": "profile", "text": "startup", "canonical_question_en": None, "profile_patch": {"startup_name": "Stayflow"}},
    ]}])
    got = run(handle_message("mixed", {}, llm))
    assert [b["markdown"] for b in got["blocks"][:2]] == ["How many startups fail to raise?", "How long does fundraising take?"]
    assert got["blocks"][2] == {"type": "profile_update", "changes": {"location": "Barcelona", "interests": {"sectors": ["fintech"], "regions": ["Nordics"], "stages": ["SEED"]}, "startup_name": "Stayflow"}}
    assert got["profile_patch"] == got["blocks"][2]["changes"]
    assert len(calls) == 2


def test_router_prompt_declares_classification_rules():
    assert "cuánto/cuántos" in SYSTEM and "UNA sola parte profile" in SYSTEM
    assert "Somos Stayflow en Barcelona; nos interesan las fintech nórdicas en etapa seed" in SYSTEM
    assert "canonical_question_en" in SCHEMA["properties"]["parts"]["items"]["required"]
    assert "has_entity" in SCHEMA["properties"]["parts"]["items"]["required"]


def test_mixed_profile_parts_keep_location_and_interests(monkeypatch, tmp_path):
    async def fake_execute(part, **kwargs):
        return {"type": "cala_answer", "markdown": part["canonical_question_en"], "sources": []}
    monkeypatch.setattr("cala_core.execute", fake_execute)
    base = {"claim": None, "subject": None, "attribute": None, "user_value": None,
            "canonical_question_en": None, "has_entity": False, "profile_patch": {}}
    llm = FakeLLM([{"parts": [
        {**base, "type": "profile", "text": "Stayflow en Barcelona", "profile_patch": {"startup_name": "Stayflow", "location": "Barcelona"}},
        {**base, "type": "profile", "text": "gustos fintech nórdicas seed", "profile_patch": {"interests": {"sectors": ["fintech"], "regions": ["Nordics"], "stages": ["SEED"]}}},
        {**base, "type": "query", "text": "quién invirtió en Wolt", "canonical_question_en": "Who invested in Wolt?", "has_entity": True},
    ]}])
    got = run(handle_message("Somos Stayflow en Barcelona; nos interesan las fintech nórdicas en etapa seed y quiero saber quién invirtió en Wolt.", {}, llm, cache_dir=tmp_path))
    assert got["profile_patch"] == {"startup_name": "Stayflow", "location": "Barcelona", "interests": {"sectors": ["fintech"], "regions": ["Nordics"], "stages": ["SEED"]}}


def test_router_cache_normalizes_message_spacing_and_case(tmp_path):
    from cala_core.router import route
    response = {"parts": [{"type": "query", "text": "Who invested in Wolt?", "claim": None,
                           "subject": None, "attribute": None, "user_value": None, "profile_patch": {},
                           "canonical_question_en": "Who invested in Wolt?", "has_entity": True}]}
    llm = FakeLLM([response])
    first = run(route("Who invested in Wolt?", {"startup_name": "Stayflow"}, llm, cache_dir=tmp_path))
    second = run(route("  WHO   INVESTED in WOLT? ", {"startup_name": "Stayflow"}, llm, cache_dir=tmp_path))
    assert first == second
    assert llm.calls == 1
