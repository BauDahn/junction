import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from chat import recommend
from chat import routes
import app as backend_app


class FakeCala:
    def __init__(self, fail=()):
        self.fail = set(fail)
        self.calls = []

    async def search(self, question):
        self.calls.append(question)
        await asyncio.sleep(0)
        if any(word in question for word in self.fail):
            raise RuntimeError("offline")
        return {"answer":"Acme raised a seed round.", "sources":[{"name":"Cala","url":"https://example.test"}], "facts":[], "entities":[]}


class FakeLLM:
    async def complete_json(self, system, user, schema):
        return {"cards":[{"type":"investor","title":"Acme","subtitle":"Seed","reason":"Raised seed funding.","source_ids":[1]}, {"type":"investor","title":"No source","subtitle":"","reason":"unsupported","source_ids":[99]}]}


class FlowLLM:
    def __init__(self):
        self.messages = 0

    async def complete_json(self, system, user, schema):
        if "cards" in schema.get("properties", {}):
            kind = json.loads(user)["card_type"]
            title = {"investors":"Fund A", "competitors":"Rival Inc", "prospects":"Client Co"}[kind]
            return {"cards":[{"type":kind, "title":title, "subtitle":"Seed", "reason":"Raised seed funding.", "source_ids":[1]}]}
        self.messages += 1
        if self.messages == 1:
            patch = {"startup_name":"Nube", "one_liner":"SaaS for shops", "sector":"SaaS", "stage":"Seed", "location":"Madrid", "target_customers":"shops"}
            used = []
        else:
            patch = {}
            used = [True] if self.messages == 3 else []
        return {"reply":"Listo.", "used_cards":used, "profile_patch":patch}


class QuickCala(FakeCala):
    async def search(self, question):
        self.calls.append(question)
        await asyncio.sleep(0)
        return {"answer":"A company raised seed funding.", "sources":[{"name":"Cala source", "url":"https://example.test/source"}]}


def test_fingerprint_normalizes_case_and_competitor_order():
    a = {"sector":"SaaS", "location":"Madrid", "stage":"Seed", "competitors":["Zed", "Alpha"], "raising":{"round":"Seed"}}
    b = {"sector":"saas", "location":"madrid", "stage":"seed", "competitors":["alpha", "zed"], "raising":{"round":"seed"}}
    assert recommend.fingerprint(a) == recommend.fingerprint(b)


def test_same_intent_has_same_three_queries():
    profile = {"sector":"Climate Tech", "location":"Madrid", "stage":"Seed", "competitors":["Rival"]}
    assert recommend.queries(profile) == recommend.queries(dict(profile))
    assert len(recommend.queries(profile)) == 3
    assert "Spain" in recommend.queries(profile)["investors"]


def test_cards_without_valid_source_are_dropped(monkeypatch, tmp_path):
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "chat.db"))
    cards, dropped = asyncio.run(recommend._cards("investors", {"answer":"Acme raised seed funding", "sources":[{"name":"Cala","url":"u"}]}, FakeLLM(), "Startup"))
    assert len(cards) == 1 and dropped == 1


def test_one_category_failure_does_not_break_others(monkeypatch, tmp_path):
    from chat import store
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "chat.db"))
    profile = {"sector":"saas", "location":"Madrid"}
    data = asyncio.run(recommend.run_recommendations("s", profile, FakeLLM(), FakeCala(fail=("venture capital",))))
    assert store.get_recommendations("s")["status"] == "ready"
    assert data["investors"] == []
    assert data["competitors"] and data["prospects"]


def test_chat_recommendation_notice_once_and_get_endpoint(monkeypatch, tmp_path):
    async def scenario():
        monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "flow.db"))
        monkeypatch.setattr(routes, "settings", SimpleNamespace(cala_api_key="test", cache_dir=tmp_path))
        llm, cala = FlowLLM(), QuickCala()
        backend_app.app.dependency_overrides[routes.get_llm] = lambda: llm
        backend_app.app.dependency_overrides[routes.get_cala] = lambda: cala
        try:
            transport = httpx.ASGITransport(app=backend_app.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                sid = (await client.post("/api/sessions")).json()["session_id"]
                first = await client.post(f"/api/sessions/{sid}/messages", json={"text":"Tengo una startup"})
                assert first.json()["recommendations_status"] == "running"
                await asyncio.gather(*list(routes._recommendation_tasks))
                rec = await client.get(f"/api/sessions/{sid}/recommendations")
                assert rec.json()["status"] == "ready"
                assert all(len(rec.json()[key]) == 1 for key in ("investors", "competitors", "prospects"))
                second = (await client.post(f"/api/sessions/{sid}/messages", json={"text":"¿Qué encontraste?"})).json()["reply"]
                assert len(second["cards"]) == 3
                assert second["sources"]
                third = (await client.post(f"/api/sessions/{sid}/messages", json={"text":"Gracias"})).json()["reply"]
                assert third["cards"] == []
                assert third["sources"] == []
        finally:
            backend_app.app.dependency_overrides.clear()

    asyncio.run(scenario())


def test_empty_cala_key_leaves_recommendations_idle(monkeypatch, tmp_path):
    async def scenario():
        monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "idle.db"))
        monkeypatch.setattr(routes, "settings", SimpleNamespace(cala_api_key="", cache_dir=tmp_path))
        cala = QuickCala()
        backend_app.app.dependency_overrides[routes.get_llm] = lambda: FlowLLM()
        backend_app.app.dependency_overrides[routes.get_cala] = lambda: cala
        try:
            transport = httpx.ASGITransport(app=backend_app.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                sid = (await client.post("/api/sessions")).json()["session_id"]
                result = await client.post(f"/api/sessions/{sid}/messages", json={"text":"Tengo una startup"})
                assert result.json()["recommendations_status"] == "idle"
                assert (await client.get(f"/api/sessions/{sid}/recommendations")).json()["status"] == "idle"
                assert cala.calls == []
        finally:
            backend_app.app.dependency_overrides.clear()

    asyncio.run(scenario())


def test_unexpected_recommendation_exception_sets_error(monkeypatch, tmp_path):
    class BrokenCala:
        async def search(self, question):
            raise AssertionError("unexpected task failure")

    from chat import store
    monkeypatch.setenv("CHAT_DB_PATH", str(tmp_path / "error.db"))
    monkeypatch.setattr(recommend, "queries", lambda _profile: (_ for _ in ()).throw(RuntimeError("unexpected failure")))
    data = asyncio.run(recommend.run_recommendations("s", {"sector":"saas"}, FakeLLM(), BrokenCala()))
    assert data["error"] == "unexpected failure"
    rec = store.get_recommendations("s")
    assert rec["status"] == "error" and rec["data"] == data


def test_prospects_excluyen_competidores_y_la_propia_startup():
    class LLM:
        async def complete_json(self, system, user, schema):
            return {"cards": [
                {"title": "Amenitiz", "subtitle": "", "reason": "", "source_ids": [1]},
                {"title": "Stayflow", "subtitle": "", "reason": "", "source_ids": [1]},
                {"title": "Hotel Arts", "subtitle": "", "reason": "", "source_ids": [1]},
            ]}

    profile = {"startup_name": "Stayflow", "competitors": ["Amenitiz"]}
    result = {"answer": "x", "sources": [{"name": "s", "url": "u"}]}
    cards, _ = asyncio.run(recommend._cards("prospects", result, LLM(), profile))
    assert [c["title"] for c in cards] == ["Hotel Arts"]
    cards, _ = asyncio.run(recommend._cards("competitors", result, LLM(), profile))
    assert "Amenitiz" in [c["title"] for c in cards] and "Stayflow" not in [c["title"] for c in cards]
