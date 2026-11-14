import pytest

from canonizador.cache import DiskCache
from canonizador.intent import IntentParser, SCHEMA, strict_schema
from canonizador.api import answer_intent
from canonizador.normalize import normalize
from canonizador.plan import build_plan, build_query, effective_attribute, _funding_literal
from canonizador.resolve import resolve_entities


def test_normalize():
    assert normalize("¿  ‘Mews’   Café!") == "'Mews' Café!"


def test_strict_schema_recurses_and_requires_every_property():
    strict = strict_schema(SCHEMA)
    assert strict["additionalProperties"] is False
    assert strict["required"] == ["entities", "attribute", "filters"]
    nested = strict["properties"]["entities"]["items"]
    assert nested["additionalProperties"] is False
    assert nested["required"] == ["name", "type"]
    assert strict["properties"]["filters"]["required"] == ["round_label", "year", "location", "sector", "min_funding"]
    assert "additionalProperties" not in SCHEMA


def test_cache_canonical_key(tmp_path):
    c = DiskCache(tmp_path)
    assert c.key({"ids": ["a"], "attribute": "funding"}) == c.key({"attribute": "funding", "ids": ["a"]})


@pytest.mark.asyncio
async def test_resolve_exact_alias_wins():
    class Fake:
        async def entities(self, name, entity_type):
            return [{"id": "2", "name": "Baron App, Inc.", "aliases": ["Amenitiz"]}, {"id": "1", "name": "Amenitiz", "aliases": []}]
    result = await resolve_entities({"entities": [{"name": "Amenitiz", "type": "Company"}]}, Fake())
    assert result[0]["chosen"]["id"] == "1"
    assert len(result[0]["alternatives"]) == 1


def test_funding_plan_filters_issuer_and_leads():
    plan = build_plan({"attribute": "lead_investors", "filters": {"round_label": "SERIES_B", "year": 2024}}, "x")
    assert plan[0]["request"]["relationships"]["outgoing"]["PARTICIPATES_IN_FUNDING_ROUND"] == {"limit": 100}
    assert plan[0]["filters"]["issuer_role"] == "ISSUER"
    assert plan[1]["filters"]["is_lead"] is True


def test_entity_relationship_request_uses_only_supported_limit_key():
    plan = build_plan({"attribute": "founders", "filters": {}}, "x")
    assert plan[0]["relationships"] == {"incoming": {"FOUNDED": {"limit": 100}}}


def test_fixed_queries_for_same_intent_and_templates():
    intent = {"attribute": "funding_round", "entities": [{"name": "Amenitiz"}], "filters": {"round_label": "SERIES_B"}}
    assert build_query(intent, "Amenitiz") == build_query(intent, "Amenitiz") == "Amenitiz.funding_round.series=B.return(amount, lead investor, investors, date)"
    assert build_query({"attribute": "company_list", "filters": {"location": "Finland", "sector": "Climate Tech", "min_funding": 10_000_000}}) == "startups.location=Finland.sector=climate tech.funding>10M.return(name, funding, sector, location)"
    assert build_query({"attribute": "profile", "entities": [{"name": "X"}], "filters": {}}) == "X.return(name, description, sector, location, funding, employee count)"


def test_company_list_filters_normalize_across_languages_and_fallback():
    expected = "startups.location=Spain.sector=hotel technology.funding>10M.return(name, funding, sector, location)"
    spanish = {"attribute": "company_list", "entities": [], "filters": {"location": "España", "sector": "tecnología hotelera", "min_funding": 10_000_000}}
    english = {"attribute": "company_list", "entities": [], "filters": {"location": "Spain", "sector": "hotel tech", "min_funding": 10_000_000}}
    fallback = {"attribute": "total_funding", "entities": [], "filters": {"location": "Spain", "sector": "hotel tech", "min_funding": 10_000_000}}
    assert build_query(spanish) == build_query(english) == expected
    assert effective_attribute(fallback) == "company_list"
    assert build_query(fallback) == expected


def test_funding_literal_compacts_base_currency_and_rejects_text():
    assert _funding_literal(10_000_000) == "10M"
    assert _funding_literal(1_500_000) == "1.5M"
    assert _funding_literal(2_000_000_000) == "2B"
    with pytest.raises(ValueError):
        _funding_literal("10MILLONES")


def test_amount_cross_check_marks_discrepancy():
    from canonizador.api import _amount_equal, _find_query_amount
    rows = [{"amount": {"value": "38.9M EUR"}}]
    amount = _find_query_amount(rows)
    assert amount == "38.9M EUR"
    assert not _amount_equal(3_000_000_000, amount)


@pytest.mark.asyncio
async def test_funding_intent_filters_locally_and_retrieves_round_properties():
    class FakeCala:
        def __init__(self): self.calls = []
        async def entities(self, name, entity_type):
            return {"entities": [{"id": "company-id", "name": "Amenitiz", "entity_type": "Company"}]}
        async def introspection(self, entity_id):
            self.calls.append(("introspection", entity_id))
            if entity_id == "company-id":
                return {"properties": ["name"], "relationships": {"outgoing": ["PARTICIPATES_IN_FUNDING_ROUND"]}}
            return {"properties": ["name", "round_label", "transaction_value", "transaction_value_units", "announcement_date"], "relationships": {"incoming": ["PARTICIPATES_IN_FUNDING_ROUND"]}}
        async def retrieve(self, entity_id, *, properties, relationships, numerical_observations=None):
            self.calls.append(("retrieve", entity_id, properties, relationships, numerical_observations))
            assert set(relationships) <= {"incoming", "outgoing"}
            if entity_id == "company-id":
                return {"name": "Amenitiz", "relationships": {"outgoing": {"PARTICIPATES_IN_FUNDING_ROUND": [
                    {"id": "r1", "name": "Series B", "properties": {"role": "ISSUER", "sources": [{"name": "Press", "document": "https://example.test"}]}},
                    {"id": "r2", "name": "Seed", "properties": {"role": "ISSUER"}},
                ]}}}
            assert properties == ["name", "round_label", "transaction_value", "transaction_value_units", "announcement_date"]
            label = "SERIES_B" if entity_id == "r1" else "SEED"
            name = "Series B" if entity_id == "r1" else "Seed"
            participants = [{"name": "Lead Fund", "properties": {"role": "INVESTOR", "is_lead": True}}] if entity_id == "r1" else []
            return {"properties": {"name": {"value": name, "sources": []}, "round_label": {"value": label}, "transaction_value": {"value": 50}, "transaction_value_units": {"value": "EUR"}, "announcement_date": {"value": "2023-01-01"}}, "relationships": {"incoming": {"PARTICIPATES_IN_FUNDING_ROUND": participants}}}
    client = FakeCala()
    result = await answer_intent({"entities": [{"name": "Amenitiz", "type": "Company"}], "attribute": "lead_investors", "filters": {"round_label": "SERIES_B"}}, client)
    assert result["rounds"] == [{"name": "Series B", "amount": 50, "currency": "EUR", "date": "2023-01-01", "lead_investors": ["Lead Fund"], "investors": [], "sources": [{"name": "Press", "document": "https://example.test"}]}]
    assert len([c for c in client.calls if c[0] == "retrieve"]) == 3


@pytest.mark.asyncio
async def test_intent_parser_fake_provider_is_cached(tmp_path):
    class FakeLLM:
        calls = 0
        async def complete_json(self, system, user, schema):
            self.calls += 1
            return {"entities": [], "attribute": "profile", "filters": {}}
    provider = FakeLLM()
    parser = IntentParser(provider, DiskCache(tmp_path))
    first = await parser.parse("Tell me about Mews")
    second = await parser.parse("Tell me about Mews")
    assert first == second
    assert provider.calls == 1


@pytest.mark.asyncio
async def test_entity_422_keeps_knowledge_query_rows_and_filters_retrieval(tmp_path):
    class FakeLLM:
        async def complete_json(self, system, user, schema):
            return {"entities": [{"name": "Factorial", "type": "Company"}], "attribute": "total_funding", "filters": {}}

    class FakeCala:
        calls = 0
        async def knowledge_query(self, query):
            assert query == "Factorial.return(total funding)"
            self.calls += 1
            return {"results": [{"total_funding": 123}], "sources": [{"name": "query-source"}]}
        async def entities(self, name, entity_type):
            return [{"id": "factorial-id", "name": "Factorial"}]
        async def introspection(self, entity_id):
            return {"properties": ["name", "total_funding"], "relationships": {"incoming": ["INVESTED_IN"]},
                    "numerical_observations": {"FinancialMetric": [{"id": "obs-id", "name": "Number of employees"}]}}
        async def retrieve(self, entity_id, *, properties, relationships, numerical_observations):
            assert properties == ["name", "total_funding"]
            assert relationships == {}
            assert numerical_observations == []
            raise RuntimeError("422 Unprocessable Entity")

    result = await __import__("canonizador.api", fromlist=["answer"]).answer(
        "How much funding has Factorial raised?", llm=FakeLLM(), client=FakeCala(), cache_dir=tmp_path)
    assert result["result"]["rows"] == [{"total_funding": 123}]
    assert result["result"]["structured_error"] == "422 Unprocessable Entity"
    assert result["result"]["sources"] == [{"name": "query-source"}]


@pytest.mark.asyncio
async def test_retrieve_body_has_only_cala_supported_keys(tmp_path):
    from canonizador.client import CalaClient
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {}
    class Http:
        async def request(self, method, url, **kwargs):
            self.body = kwargs["json"]
            return Response()
    http = Http()
    client = CalaClient(api_key="test", cache_dir=tmp_path, client=http)
    await client.retrieve("entity-id", properties=["name"], relationships={})
    assert http.body == {"properties": ["name"], "relationships": {}}
