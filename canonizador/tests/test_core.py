import pytest

from canonizador.cache import DiskCache
from canonizador.intent import IntentParser, SCHEMA, strict_schema
from canonizador.api import answer_intent
from canonizador.normalize import normalize
from canonizador.plan import build_plan
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
    assert strict["properties"]["filters"]["required"] == ["round_label", "year"]
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
