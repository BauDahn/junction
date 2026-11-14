import asyncio
import json
import pytest
from pathlib import Path

from verifier.cala import CalaClient
from verifier.llm import CachedLLM, GeminiProvider, gemini_schema, make_llm, parse_json, strict_schema
from verifier.pipeline import CLAIMS_SCHEMA, JUDGE_SCHEMA, guard_no_finding, is_publicly_verifiable


def test_parse_json_tolerates_prose_and_fences():
    assert parse_json('Here it is: {"ok": true} trailing') == {"ok": True}
    assert parse_json('```json\n{"n": 2}\n```') == {"n": 2}


def test_strict_schema_populates_required():
    schema = strict_schema({"type": "object", "properties": {"x": {"type": "string"}}})
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["x"]


def test_gemini_schema_conversion():
    result = gemini_schema({"type":"object", "additionalProperties":False, "properties":{"user_value":{"type":["string","number","null"]}, "x":{"type":["string","null"],"enum":["a",None]}, "items":{"type":"array","items":{"type":"integer"}}}, "anyOf":[{"type":["integer","null"]},{"type":["string","number"]}], "oneOf":[{"type":["boolean","null"]}]})
    assert "additionalProperties" not in result
    assert result["properties"]["user_value"]["type"] == "string"
    assert result["properties"]["user_value"]["nullable"] is True
    assert result["properties"]["x"]["type"] == "string"
    assert result["properties"]["x"]["nullable"] is True
    assert result["properties"]["x"]["enum"] == ["a", None]
    assert result["properties"]["items"]["items"]["type"] == "integer"
    assert result["anyOf"][0] == {"type":"integer", "nullable":True}
    assert result["anyOf"][1]["type"] == "string"
    assert result["oneOf"][0] == {"type":"boolean", "nullable":True}


def test_gemini_http_error_redacts_key_and_url_and_truncates():
    import httpx
    class Client:
        async def post(self, *args, **kwargs):
            return httpx.Response(400, json={"error":{"message":"bad fake-secret https://host/path?token=secret " + "x" * 350}}, request=httpx.Request("POST", "https://host"))
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(GeminiProvider(api_key="fake-secret", client=Client()).complete_json("s", "u", {}))
    message = str(caught.value)
    assert "HTTP 400" in message and "fake-secret" not in message and "?token=" not in message
    assert "bad [redactado] [URL omitida]" in message
    assert len(message.split(": ", 1)[1]) == 300


def test_gemini_request_text_image_audio_and_parse():
    import base64
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"candidates":[{"content":{"parts":[{"text":"prefix {\"ok\":true} tail"}]}}]}
    class Client:
        async def post(self, url, **kwargs):
            self.url, self.kwargs = url, kwargs
            return Response()
    client = Client()
    provider = GeminiProvider(api_key="fake-key", model="test-model", client=client)
    result = asyncio.run(provider.complete_json("system", "user", {"type":"object"}, [b"png"], (b"wav", "audio/wav")))
    assert result == {"ok": True}
    assert client.url.endswith("/models/test-model:generateContent")
    assert client.kwargs["headers"] == {"x-goog-api-key":"fake-key"}
    body = client.kwargs["json"]
    assert body["systemInstruction"]["parts"][0]["text"] == "system"
    parts = body["contents"][0]["parts"]
    assert parts[0]["text"] == "user"
    assert parts[1]["inlineData"] == {"mimeType":"image/png", "data":base64.b64encode(b"png").decode()}
    assert parts[2]["inlineData"] == {"mimeType":"audio/wav", "data":base64.b64encode(b"wav").decode()}
    assert body["generationConfig"]["temperature"] == 0


def test_gemini_retries_rate_limit():
    class Response:
        def __init__(self, status): self.status_code = status
        def raise_for_status(self):
            if self.status_code >= 400: raise httpx.HTTPStatusError("failed", request=httpx.Request("POST", "https://example.test"), response=httpx.Response(self.status_code))
        def json(self): return {"candidates":[{"content":{"parts":[{"text":"{}"}]}}]}
    class Client:
        calls = 0
        async def post(self, *args, **kwargs):
            self.calls += 1
            return Response(429 if self.calls == 1 else 200)
    import httpx
    client = Client()
    assert asyncio.run(GeminiProvider(api_key="fake", client=client).complete_json("s", "u", {})) == {}
    assert client.calls == 2


def test_make_llm_gemini_tier(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import verifier.llm as module
    monkeypatch.setattr(module, "settings", SimpleNamespace(llm_provider="gemini", gemini_api_key="fake", gemini_model="strong-x", gemini_fast_model="fast-x", cache_dir=tmp_path))
    _, strong = make_llm()
    _, fast = make_llm(tier="fast")
    _, custom = make_llm("gemini", tier="fast", model="x")
    assert strong == "strong-x" and fast == "fast-x" and custom == "x"


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
