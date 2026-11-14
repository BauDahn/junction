import asyncio
import json
from pathlib import Path

from verifier.cala import CalaClient
from verifier.llm import CachedLLM, parse_json, strict_schema
from verifier.pipeline import CLAIMS_SCHEMA, JUDGE_SCHEMA, guard_no_finding, is_publicly_verifiable


def test_parse_json_tolerates_prose_and_fences():
    assert parse_json('Here it is: {"ok": true} trailing') == {"ok": True}
    assert parse_json('```json\n{"n": 2}\n```') == {"n": 2}


def test_strict_schema_populates_required():
    schema = strict_schema({"type": "object", "properties": {"x": {"type": "string"}}})
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["x"]


def test_pipeline_schemas_are_strict_at_every_object():
    for schema in (CLAIMS_SCHEMA, JUDGE_SCHEMA):
        def check(node):
            if isinstance(node, dict):
                if node.get("type") == "object":
                    assert node["additionalProperties"] is False
                    assert set(node["required"]) == set(node["properties"])
                for value in node.values():
                    check(value)
            elif isinstance(node, list):
                for value in node:
                    check(value)
        check(schema)


def test_public_claim_filter_keeps_named_third_party_facts_and_skips_internal_metrics():
    assert is_publicly_verifiable({"category":"investor", "quote":"Backed by Seedcamp and K Fund", "publicly_verifiable":False})
    assert is_publicly_verifiable({"category":"competitor", "quote":"Mews raised $100M", "publicly_verifiable":False})
    assert is_publicly_verifiable({"category":"market", "quote":"Spain has 14,000 hotels", "publicly_verifiable":False})
    assert not is_publicly_verifiable({"category":"traction", "quote":"€40k monthly recurring revenue", "publicly_verifiable":True})
    assert not is_publicly_verifiable({"category":"traction", "quote":"25 pilot hotels", "publicly_verifiable":True})


def test_no_finding_evidence_cannot_be_contradicted():
    for evidence in ("I was unable to find any evidence", "No record found", "Could not find this", "No information available"):
        assert guard_no_finding("contradicted", evidence) == "no_data"
    assert guard_no_finding("contradicted", "Cala reports $2m, while the claim says $1m") == "contradicted"


def test_cala_cache_and_normalization(tmp_path):
    class FakeResponse:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"content": "answer", "context": [{"id": "1", "content": "fact" * 200, "origins": [{"source": {"name": "Source", "url": "https://x"}, "document": {"name": "Doc", "url": "https://x"}}]}], "entities": []}
    class Client:
        calls = 0
        async def post(self, *args, **kwargs):
            self.calls += 1
            return FakeResponse()
    client = Client()
    cala = CalaClient("not-a-real-secret", tmp_path, client=client)
    one = asyncio.run(cala.search("question"))
    two = asyncio.run(cala.search("question"))
    assert one == two
    assert client.calls == 1
    assert one["sources"] == [{"name": "Doc", "url": "https://x"}]
    assert len(one["facts"][0]["content"]) == 600


def test_cached_llm(tmp_path):
    class Fake:
        calls = 0
        async def complete_json(self, *args):
            self.calls += 1
            return {"ok": True}
    fake = Fake()
    llm = CachedLLM(fake, "fake:model", tmp_path)
    assert asyncio.run(llm.complete_json("s", "u", {})) == {"ok": True}
    assert asyncio.run(llm.complete_json("s", "u", {})) == {"ok": True}
    assert fake.calls == 1


def test_url_allowlist_and_trust_score_with_fake_providers(tmp_path):
    from verifier.pipeline import verify_pdf
    import pymupdf as fitz
    pdf = tmp_path / "deck.pdf"
    doc = fitz.open(); page = doc.new_page(); page.insert_text((40, 50), "Acme raised $1m") ; doc.save(pdf)
    class FakeLLM:
        calls = 0
        async def complete_json(self, system, user, schema, images=None):
            self.calls += 1
            if self.calls == 1:
                return {"startup_name":"Acme","claims":[{"id":"c1","page":1,"quote":"Acme raised $1m","category":"funding","publicly_verifiable":True,"cala_question":"Acme funding"}]}
            return {"claims":[{"id":"c1","verdict":"confirmed","explanation":"Evidence supports it.","evidence":"raised $1m","source_urls":["https://allowed.test","https://evil.test"]}]}
    class FakeCala:
        async def search(self, question):
            return {"answer":"round", "facts":[], "sources":[{"name":"Known","url":"https://allowed.test"}]}
    events = []
    report = asyncio.run(verify_pdf(pdf, provider="codex", llm=(FakeLLM(), "fake"), cala=FakeCala(), on_progress=lambda *event: events.append(event)))
    assert report["claims"][0]["verdict"] == "confirmed"
    assert report["claims"][0]["sources"] == [{"name":"Known","url":"https://allowed.test"}]
    assert report["dropped_urls"] == 1
    assert report["trust_score"] == 100
    assert events == [
        ("extracting", 0, 0),
        ("checking", 0, 1),
        ("checking", 1, 1),
        ("judging", 0, 1),
        ("judging", 1, 1),
    ]
