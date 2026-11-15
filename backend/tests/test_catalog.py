import asyncio
import json

import httpx
import pytest

from canonizador.cache import DiskCache
from canonizador.client import CalaClient
from catalog import (
    CatalogLockError,
    MemoryCatalogKV,
    RedisCatalogKV,
    SLUSH_EVENT_ID,
    export_catalog,
    import_catalog,
    run_catalog,
)
from catalog.__main__ import main as catalog_cli
from catalog.ingest import STATUS_KEY, TODO_KEY, _FallbackGraphStore
import catalog.ingest as catalog_ingest


class FakeRedis:
    """Cliente Redis mínimo en memoria compatible con SET NX, pipeline y scan_iter."""

    def __init__(self):
        self.data, self.ttl = {}, {}

    def get(self, k):
        return self.data.get(k)

    def mget(self, ks):
        return [self.get(k) for k in ks]

    def set(self, k, v, ex=None, nx=False):
        if nx and k in self.data:
            return False
        self.data[k] = v
        self.ttl[k] = ex
        return True

    def delete(self, *ks):
        for k in ks:
            self.data.pop(k, None)

    def sadd(self, k, *xs):
        self.data.setdefault(k, set()).update(xs)

    def smembers(self, k):
        return set(self.data.get(k, set()))

    def expire(self, k, t):
        if k not in self.data:
            return False
        self.ttl[k] = t
        return True

    def ping(self):
        return True

    def pipeline(self):
        return _FakePipe(self)

    def scan_iter(self, match):
        import fnmatch
        return (k for k in list(self.data) if fnmatch.fnmatch(k, match))


class _FakePipe:
    def __init__(self, c):
        self.c, self.ops = c, []

    def smembers(self, k):
        self.ops.append(k)

    def execute(self):
        return [self.c.smembers(k) for k in self.ops]


def _make_simulated_dataset(total=100):
    """Genera 100 asistentes simulados de Slush (startups, inversores y ambos) con formato Cala."""
    attendees = []
    entities = {}
    for i in range(total):
        eid = f"att-{i:03d}"
        name = f"Entity {i:03d}"
        attendees.append({"id": eid, "name": name, "entity_type": "Company"})
        is_inv = i % 3 == 0
        is_startup = i % 3 != 0 or i % 6 == 0
        props = {
            "name": {"value": name, "sources": [{"name": "Slush", "url": f"https://slush.test/{eid}"}]},
            "description": {
                "value": f"{name} builds B2B fintech software in Helsinki.",
                "sources": [{"name": "Cala Profile", "url": f"https://cala.test/{eid}"}],
            },
            "website": {"value": f"https://www.{eid}.example", "sources": [{"name": "Cala Profile"}]},
            "headquarters": {"value": "Helsinki, Finland", "sources": [{"name": "Cala Profile"}]},
        }
        if is_startup:
            props["funding_stage"] = {"value": "Seed", "sources": [{"name": "Cala Profile"}]}
            props["total_funding"] = {"value": "€2M", "sources": [{"name": "Cala Profile"}]}
        incoming, outgoing = {}, {}
        if is_inv:
            outgoing["INVESTED_IN"] = [
                {
                    "id": f"port-{i}-a",
                    "name": f"Portfolio A {i}",
                    "entity_type": "Company",
                    # Incluye raíz falsa para confirmar que solo se leen properties.sources.
                    "sources": [{"name": "ROOT_SHOULD_IGNORE"}],
                    "properties": {
                        "id": f"edge-inv-{i}-a",
                        "is_lead": True,
                        "event_date": "2025-05-01",
                        "funding_amount": 2_000_000,
                        "round_type": "Seed",
                        "sources": [{"name": "Filing", "url": f"https://filing.test/{i}/a"}],
                    },
                },
                {
                    "id": f"port-{i}-b",
                    "name": f"Portfolio B {i}",
                    "entity_type": "Company",
                    "properties": {
                        "id": f"edge-inv-{i}-b",
                        "is_lead": False,
                        "event_date": "2024-03-10",
                        "funding_amount": 4_000_000,
                        "round_type": "Series A",
                        "sources": [{"name": "Press", "url": f"https://press.test/{i}/b"}],
                    },
                },
            ]
        if is_startup:
            outgoing["PARTICIPATES_IN_FUNDING_ROUND"] = [
                {
                    "id": f"round-{i}",
                    "name": "Seed Round",
                    "entity_type": "PrivateCompanyFundingRound",
                    "sources": [{"name": "ROOT_SHOULD_IGNORE"}],
                    "properties": {
                        "role": "ISSUER",
                        "event_date": "2025-02-15",
                        "transaction_value": 1_500_000,
                        "sources": [{"name": "Registry", "url": f"https://reg.test/{i}"}],
                    },
                }
            ]
            incoming["FOUNDED"] = [
                {
                    "id": f"founder-{i}",
                    "name": f"Founder {i}",
                    "entity_type": "Person",
                    "properties": {
                        "id": f"edge-founder-{i}",
                        "sources": [{"name": "Bio", "url": f"https://bio.test/{i}"}],
                    },
                }
            ]
        entities[eid] = {
            "id": eid,
            "name": name,
            "entity_type": "Company",
            "properties": props,
            "relationships": {"incoming": incoming, "outgoing": outgoing},
        }
    return attendees, entities


def _make_mock_cala(tmp_path, attendees, entities, *, page_size=100, fail_ids=None):
    fail_ids = set(fail_ids or ())
    requests = []

    def handler(request: httpx.Request):
        path = request.url.path
        entity_id = path.rsplit("/", 1)[-1]
        body = json.loads(request.content.decode() or "{}")
        requests.append((entity_id, body))
        if entity_id == SLUSH_EVENT_ID:
            spec = body["relationships"]["incoming"]["PARTICIPATES_IN_EVENT"]
            offset = int(spec.get("offset", 0))
            limit = int(spec.get("limit", page_size))
            return httpx.Response(
                200,
                json={
                    "id": SLUSH_EVENT_ID,
                    "relationships": {"incoming": {"PARTICIPATES_IN_EVENT": attendees[offset:offset + limit]}},
                },
            )
        if entity_id in fail_ids:
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(200, json=entities[entity_id])

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    cala = CalaClient(
        "test-only",
        tmp_path / "cache",
        client=http,
        cache=DiskCache(tmp_path / "cache"),
        entities_interval=0,
        entities_concurrency=3,
    )
    return cala, http, requests


class FakeLLM:
    def __init__(self, delay_s=0.0):
        self.calls = []
        self.delay_s = delay_s
        self.active = 0
        self.peak = 0

    async def complete_json(self, system, prompt, schema):
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            self.calls.append(prompt)
            if self.delay_s:
                await asyncio.sleep(self.delay_s)
            return {
                "sectors": ["Fintech"],
                "stages": ["Seed"],
                "customer_type": "B2B",
                "country": "Finland",
                "hq": "Helsinki, Finland",
                "region": "Nordics",
            }
        finally:
            self.active -= 1


def test_full_100_attendees_stages_1_to_3_and_zero_calls_on_second_run(tmp_path, monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    attendees, entities = _make_simulated_dataset(100)
    cala, http, requests = _make_mock_cala(tmp_path, attendees, entities)
    llm = FakeLLM(delay_s=0.005)
    kv = RedisCatalogKV(client=FakeRedis())
    store = _FallbackGraphStore(kv)

    async def scenario():
        try:
            status = await run_catalog(cala=cala, llm=llm, kv=kv, store=store, cala_concurrency=3, llm_concurrency=6)
            assert status["done"] == 100
            assert status["total"] == 100
            assert status["stage"] == "done"
            assert status["ai_tagged"] == 100
            assert json.loads(kv.get(TODO_KEY)) == []
            assert kv.get("cat:v1:lock") is None
            assert cala.calls == 102  # 2 páginas en etapa 1 (100 + vacía) + 100 entidades en etapa 2
            assert len(llm.calls) == 100
            assert llm.peak >= 2  # etapa 3 corre concurrentemente sin esperar secuencial

            inv = json.loads(kv.get("cat:v1:feat:att-000"))
            assert inv["kinds"] == ["investor", "startup"]
            assert inv["ai_tagged"] is True
            assert inv["sectors"] == ["Fintech"]
            assert inv["country"] == "Finland"
            assert inv["activity"]["rounds_24m"] == 2
            assert inv["activity"]["led_24m"] == 1
            assert inv["amount"] == {"min": 2_500_000.0, "max": 3_500_000.0}
            assert all(s["name"] != "ROOT_SHOULD_IGNORE" for s in inv["sources"])
            assert all(s["name"] != "ROOT_SHOULD_IGNORE" for r in inv["rounds"] for s in r["sources"])

            st = json.loads(kv.get("cat:v1:feat:att-001"))
            assert st["kinds"] == ["startup"]
            assert st["amount"] == {"min": 2_000_000.0, "max": 2_000_000.0}
            assert store.get_node("round-1") is None  # PrivateCompanyFundingRound excluido del grafo
            assert len(store.neighbors("att-001", rels={"FOUNDED"})) == 1
            assert store.get_nodes(["att-000", "att-001"])["att-000"]["expanded"]

            # Segunda corrida con cliente Cala nuevo sin caché: debe hacer 0 llamadas.
            cala2, http2, req2 = _make_mock_cala(tmp_path / "run2", attendees, entities)
            try:
                status2 = await run_catalog(cala=cala2, llm=llm, kv=kv, store=store)
                assert status2["done"] == 100
                assert cala2.calls == 0
                assert cala2.stats["cache_hits"] == 0
                assert req2 == []
            finally:
                await http2.aclose()
        finally:
            await http.aclose()

    asyncio.run(scenario())


def test_resumable_limit_and_lock_enforcement(tmp_path, monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    attendees, entities = _make_simulated_dataset(20)
    cala1, http1, _ = _make_mock_cala(tmp_path / "r1", attendees, entities)
    llm = FakeLLM()
    kv = MemoryCatalogKV()
    store = _FallbackGraphStore(kv)

    async def scenario():
        try:
            # Lock ocupado bloquea otra ingesta concurrente.
            assert kv.set_nx("cat:v1:lock", "other-worker", ttl=60)
            with pytest.raises(CatalogLockError):
                await run_catalog(limit=10, cala=cala1, llm=llm, kv=kv, store=store)
            kv.delete("cat:v1:lock")

            partial = await run_catalog(limit=8, cala=cala1, llm=llm, kv=kv, store=store)
            assert partial["done"] == 8 and partial["total"] == 20
            assert len(json.loads(kv.get(TODO_KEY))) == 12
            calls_after_partial = cala1.calls

            # Reanudar hasta 20 procesa solo los 12 pendientes sin repetir los 8 anteriores ni etapa 1.
            resumed = await run_catalog(limit=20, cala=cala1, llm=llm, kv=kv, store=store)
            assert resumed["done"] == 20 and resumed["stage"] == "done"
            assert cala1.calls == calls_after_partial + 12
        finally:
            await http1.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("failures,expected_status", [(2, 200), (5, 402), (1, 404)])
def test_stage2_retries_payment_failures_and_records_terminal_errors(monkeypatch, failures, expected_status):
    monkeypatch.setenv("VALKEY_URL", "")
    monkeypatch.setenv("CATALOG_402_WAIT", "0.01")
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(catalog_ingest, "_sleep", fake_sleep)
    ids = ["target", "other"] if expected_status == 402 else ["target"]
    attendees = {eid: {"id": eid, "name": eid, "type": "Company"} for eid in ids}
    monkeypatch.setattr(catalog_ingest, "_fetch_stage1", _fake_stage1(attendees))

    class FakeCala:
        def __init__(self):
            self.calls = {}

        async def retrieve(self, eid, **kwargs):
            self.calls[eid] = self.calls.get(eid, 0) + 1
            if eid == "target" and self.calls[eid] <= failures:
                response = httpx.Response(402 if expected_status == 200 else expected_status, request=httpx.Request("GET", f"https://cala.test/{eid}"))
                raise httpx.HTTPStatusError(f"Cala {expected_status}", request=response.request, response=response)
            return {}

    async def scenario():
        kv = MemoryCatalogKV()
        cala = FakeCala()
        status = await run_catalog(cala=cala, llm=None, kv=kv, store=_FallbackGraphStore(kv))
        if expected_status == 200:
            assert cala.calls["target"] == 3
            assert status.get("errors", 0) == 0
            assert kv.get("cat:v1:failed:target") is None
        elif expected_status == 402:
            assert cala.calls["target"] == 5
            assert cala.calls["other"] == 1
            failed = json.loads(kv.get("cat:v1:failed:target"))
            assert failed["status"] == 402 and failed["error"] and failed["at"]
            assert status["payment_required"] == 1 and status["errors"] == 1
            assert "target" in json.loads(kv.get(TODO_KEY))
        else:
            assert cala.calls["target"] == 1
            failed = json.loads(kv.get("cat:v1:failed:target"))
            assert failed["status"] == 404
            assert status["not_found"] == 1 and status["errors"] == 1
        assert len(sleeps) == (2 if expected_status == 200 else 4 if expected_status == 402 else 0)

    asyncio.run(scenario())


def _fake_stage1(attendees):
    async def fetch(cala, kv, limit, page_size=100, *, lock_token=None, lock_ttl=600):
        return ({"done": 0, "errors": 0}, list(attendees), attendees)
    return fetch


def test_402_backoff_refreshes_lock_in_bounded_chunks(monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    monkeypatch.setenv("CATALOG_402_WAIT", "0.12")
    sleeps, refreshes = [], []
    async def fake_sleep(seconds):
        sleeps.append(seconds)
    monkeypatch.setattr(catalog_ingest, "_sleep", fake_sleep)
    original_refresh = catalog_ingest._refresh_lock
    def record_refresh(kv, token, lock_ttl=600):
        refreshes.append(lock_ttl)
        return original_refresh(kv, token, lock_ttl)
    monkeypatch.setattr(catalog_ingest, "_refresh_lock", record_refresh)
    attendees = {"one": {"id": "one", "name": "one"}}
    monkeypatch.setattr(catalog_ingest, "_fetch_stage1", _fake_stage1(attendees))

    class Cala:
        calls = 0
        async def retrieve(self, eid, **kwargs):
            self.calls += 1
            if self.calls == 1:
                response = httpx.Response(402, request=httpx.Request("GET", "https://cala.test/one"))
                raise httpx.HTTPStatusError("402", request=response.request, response=response)
            return {}

    async def scenario():
        kv = MemoryCatalogKV()
        await run_catalog(cala=Cala(), llm=None, kv=kv, store=_FallbackGraphStore(kv), lock_ttl=0.09)
    asyncio.run(scenario())
    assert len(sleeps) > 1 and len(refreshes) >= len(sleeps)
    assert max(sleeps) < 0.09 / 3


def test_payment_breaker_pauses_and_success_resets_consecutive_count(monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    monkeypatch.setenv("CATALOG_402_TRIP", "2")
    monkeypatch.setattr(catalog_ingest, "_sleep", lambda _: asyncio.sleep(0))
    ids = ["a", "b", "c", "d", "e"]
    attendees = {eid: {"id": eid, "name": eid} for eid in ids}
    monkeypatch.setattr(catalog_ingest, "_fetch_stage1", _fake_stage1(attendees))

    class Cala:
        def __init__(self): self.calls = {}
        async def retrieve(self, eid, **kwargs):
            self.calls[eid] = self.calls.get(eid, 0) + 1
            # a and c persist, b succeeds (reset), d trips the breaker.
            if eid in {"a", "c", "d", "e"}:
                response = httpx.Response(402, request=httpx.Request("GET", f"https://cala.test/{eid}"))
                raise httpx.HTTPStatusError("402", request=response.request, response=response)
            return {}

    async def scenario():
        kv, cala = MemoryCatalogKV(), Cala()
        status = await run_catalog(cala=cala, llm=None, kv=kv, store=_FallbackGraphStore(kv), cala_concurrency=1)
        assert status["stopped"] == "payment_required" and status["stage"] == "paused"
        todo = json.loads(kv.get(TODO_KEY))
        assert "e" in todo
        assert kv.get("cat:v1:failed:e") is None
        assert cala.calls["b"] == 1
        assert kv.get(catalog_ingest.LOCK_KEY) is None
        # A new run removes the prior stop marker before continuing.
        monkeypatch.setenv("CATALOG_402_TRIP", "10")
        followup = await run_catalog(cala=cala, llm=None, kv=kv, store=_FallbackGraphStore(kv), cala_concurrency=1)
        assert "stopped" not in followup
    asyncio.run(scenario())


def test_run_call_budget_pauses_and_resumes(monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    monkeypatch.setattr(catalog_ingest, "_sleep", lambda _: asyncio.sleep(0))
    attendees = {eid: {"id": eid, "name": eid} for eid in ("a", "b")}
    monkeypatch.setattr(catalog_ingest, "_fetch_stage1", _fake_stage1(attendees))

    class Cala:
        call_cap = 0
        _run_reserved = 0
        async def retrieve(self, eid, **kwargs):
            from canonizador.client import CalaBudgetExceeded
            if self._run_reserved >= self.call_cap:
                raise CalaBudgetExceeded(self.call_cap)
            self._run_reserved += 1
            return {}

    async def scenario():
        kv, cala = MemoryCatalogKV(), Cala()
        first = await run_catalog(cala=cala, llm=None, kv=kv, store=_FallbackGraphStore(kv),
                                  cala_concurrency=1, max_calls=1)
        assert first["stage"] == "paused" and first["stopped"] == "call budget reached (1)"
        assert json.loads(kv.get(TODO_KEY)) == ["b"]
        second = await run_catalog(cala=cala, llm=None, kv=kv, store=_FallbackGraphStore(kv),
                                   cala_concurrency=1, max_calls=2)
        assert second["stage"] == "done"
    asyncio.run(scenario())


def test_put_expansion_pr81_and_legacy_adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    attendees, entities = _make_simulated_dataset(2)
    cala, http, _ = _make_mock_cala(tmp_path, attendees, entities)

    class PR81GraphStore:
        def __init__(self):
            self.calls = []

        def put_expansion(self, node, edges, neighbors, *, rels, truncated=False):
            self.calls.append((node, edges, neighbors, rels, truncated))
            return node["id"]

    class LegacyGraphStore:
        def __init__(self):
            self.nodes, self.edges, self.expanded = [], [], []

        def put_node(self, node):
            self.nodes.append(node)
            return node["id"]

        def put_edge(self, edge):
            self.edges.append(edge)
            return edge["id"]

        def mark_expanded(self, node_id, key, truncated=False):
            self.expanded.append((node_id, key, truncated))

    async def scenario():
        try:
            pr81 = PR81GraphStore()
            await run_catalog(limit=2, cala=cala, llm=FakeLLM(), kv=MemoryCatalogKV(), store=pr81)
            assert len(pr81.calls) == 2
            node, edges, neighbors, rels, truncated = pr81.calls[0]
            assert set(rels) == {"INVESTED_IN", "PARTICIPATES_IN_FUNDING_ROUND", "FOUNDED"}
            assert "aliases" in node and "merged_ids" in node and "expanded" in node
            assert node["props"]["website"]["value"].startswith("https://")
            assert node["props"]["hq"] == {"id": None, "name": "Helsinki, Finland", "sources": [{"name": "Cala Profile"}]}
            assert edges and all(e["sources"] for e in edges)

            legacy = LegacyGraphStore()
            await run_catalog(limit=2, cala=cala, llm=FakeLLM(), kv=MemoryCatalogKV(), store=legacy)
            assert len(legacy.nodes) >= 2 and len(legacy.edges) >= 1 and len(legacy.expanded) == 2
        finally:
            await http.aclose()

    asyncio.run(scenario())


def test_export_import_json_and_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    attendees, entities = _make_simulated_dataset(15)
    cala, http, _ = _make_mock_cala(tmp_path, attendees, entities)
    llm = FakeLLM()
    src_kv = MemoryCatalogKV()
    src_store = _FallbackGraphStore(src_kv)

    async def run_ingest():
        try:
            await run_catalog(cala=cala, llm=llm, kv=src_kv, store=src_store)
        finally:
            await http.aclose()

    asyncio.run(run_ingest())

    backup_path = tmp_path / "slush_backup.json"
    exp = export_catalog(backup_path, kv=src_kv, store=src_store)
    assert exp["features"] == 15 and exp["nodes"] >= 15 and exp["edges"] >= 15
    assert not backup_path.read_bytes().startswith(b"\xef\xbb\xbf")  # sin BOM UTF-8

    dst_kv = MemoryCatalogKV()
    dst_store = _FallbackGraphStore(dst_kv)
    imp = import_catalog(backup_path, kv=dst_kv, store=dst_store)
    assert imp["features"] == 15 and imp["nodes"] == exp["nodes"] and imp["edges"] == exp["edges"]
    assert json.loads(dst_kv.get(STATUS_KEY))["done"] == 15
    assert json.loads(dst_kv.get("cat:v1:feat:att-000"))["sectors"] == ["Fintech"]
    assert dst_store.get_node("att-000")["name"] == "Entity 000"

    # Re-ejecutar sobre el store restaurado hace 0 llamadas a Cala.
    cala2, http2, _ = _make_mock_cala(tmp_path / "r2", attendees, entities)
    async def check_zero():
        try:
            st = await run_catalog(cala=cala2, llm=llm, kv=dst_kv, store=dst_store)
            assert st["done"] == 15 and cala2.calls == 0
        finally:
            await http2.aclose()
    asyncio.run(check_zero())

    # CLI smoke test (export + import + status)
    cli_out = tmp_path / "cli_backup.json"
    assert catalog_cli(["export", str(cli_out)]) == 0
    assert catalog_cli(["import", str(cli_out)]) == 0
    assert catalog_cli(["status"]) == 0


def test_default_cala_client_uses_entities_interval_0_7(tmp_path, monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    monkeypatch.setenv("CALA_API_KEY", "test-only")
    captured = {}

    class SpyCalaClient(CalaClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["interval"] = self.intervals["entities"]
            captured["has_http"] = self.client is not None

        async def retrieve(self, entity_id, *, properties=None, relationships=None, numerical_observations=None):
            return {"relationships": {"incoming": {"PARTICIPATES_IN_EVENT": []}}}

    monkeypatch.setattr("catalog.ingest.CalaClient", SpyCalaClient)
    status = asyncio.run(run_catalog(kv=MemoryCatalogKV()))
    assert status["total"] == 0 and status["stage"] == "done"
    assert captured == {"interval": 0.7, "has_http": True}


def test_no_quadratic_feat_scans_and_lock_refresh(tmp_path, monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    attendees, entities = _make_simulated_dataset(100)
    cala, http, _ = _make_mock_cala(tmp_path / "perf", attendees, entities)
    llm = FakeLLM()

    class CountingKV(MemoryCatalogKV):
        def __init__(self):
            super().__init__()
            self.feat_scans = 0
            self.feat_mgets = 0
            self.refresh_calls = 0

        def scan_prefix(self, prefix):
            if prefix == "cat:v1:feat:":
                self.feat_scans += 1
            return super().scan_prefix(prefix)

        def mget(self, keys):
            if keys and any(k.startswith("cat:v1:feat:") for k in keys):
                self.feat_mgets += 1
            return super().mget(keys)

        def refresh_lock_if_equals(self, key, expected, ttl=600):
            self.refresh_calls += 1
            return super().refresh_lock_if_equals(key, expected, ttl=ttl)

    kv = CountingKV()
    store = _FallbackGraphStore(kv)

    async def scenario():
        try:
            status = await run_catalog(cala=cala, llm=llm, kv=kv, store=store, cala_concurrency=4, llm_concurrency=8)
            assert status["done"] == 100
            # Sin escaneo O(N^2): como mucho 1 semilla inicial + 1 comprobación final.
            assert kv.feat_scans <= 2
            assert kv.feat_mgets <= 2
            # Lock renovado durante el progreso (stage1 + cada entidad completada).
            assert kv.refresh_calls >= 100
        finally:
            await http.aclose()

    asyncio.run(scenario())


def test_lock_kept_alive_across_ttl_and_aborts_if_stolen(tmp_path, monkeypatch):
    monkeypatch.setenv("VALKEY_URL", "")
    attendees, entities = _make_simulated_dataset(6)
    cala, http, _ = _make_mock_cala(tmp_path / "slow", attendees, entities)
    orig_retrieve = cala.retrieve

    async def slow_retrieve(entity_id, *, properties=None, relationships=None, numerical_observations=None):
        await asyncio.sleep(0.06)
        return await orig_retrieve(
            entity_id, properties=properties, relationships=relationships, numerical_observations=numerical_observations
        )

    cala.retrieve = slow_retrieve
    kv = MemoryCatalogKV()
    store = _FallbackGraphStore(kv)

    async def run_slow():
        try:
            # Duración total > 0.35s con lock_ttl=0.18s: debe renovarse y completar sin perder el lock.
            st = await run_catalog(cala=cala, llm=FakeLLM(), kv=kv, store=store, cala_concurrency=1, lock_ttl=0.18)
            assert st["done"] == 6 and st["stage"] == "done"
            assert kv.get("cat:v1:lock") is None
        finally:
            await http.aclose()

    asyncio.run(run_slow())

    # Si otro worker toma el lock en mitad de la corrida, aborta con CatalogLockError sin borrar el lock ajeno.
    cala2, http2, _ = _make_mock_cala(tmp_path / "stolen", attendees, entities)
    orig_retrieve2 = cala2.retrieve
    kv2 = MemoryCatalogKV()
    store2 = _FallbackGraphStore(kv2)
    hijacked = False

    async def hijack_retrieve(entity_id, *, properties=None, relationships=None, numerical_observations=None):
        nonlocal hijacked
        if not hijacked and entity_id == "att-002":
            hijacked = True
            kv2.set("cat:v1:lock", "intruder-token", ttl=60)
        return await orig_retrieve2(
            entity_id, properties=properties, relationships=relationships, numerical_observations=numerical_observations
        )

    cala2.retrieve = hijack_retrieve

    async def run_hijack():
        try:
            with pytest.raises(CatalogLockError):
                await run_catalog(cala=cala2, llm=FakeLLM(), kv=kv2, store=store2, cala_concurrency=1)
            assert kv2.get("cat:v1:lock") == "intruder-token"
        finally:
            await http2.aclose()

    asyncio.run(run_hijack())


def test_redis_kv_refresh_lock_lua_and_fallback():
    from catalog.ingest import RedisCatalogKV

    class LuaClient:
        def __init__(self):
            self.eval_calls = []

        def eval(self, script, numkeys, key, expected, ttl_s):
            self.eval_calls.append((script, numkeys, key, expected, ttl_s))
            return 1 if expected == "tok-1" else 0

    lua_kv = RedisCatalogKV(client=LuaClient())
    assert lua_kv.refresh_lock_if_equals("cat:v1:lock", "tok-1", ttl=600) is True
    assert lua_kv.refresh_lock_if_equals("cat:v1:lock", "tok-2", ttl=600) is False
    assert lua_kv.client.eval_calls[0][1:] == (1, "cat:v1:lock", "tok-1", 600)

    class SimpleClient:
        def __init__(self):
            self.store = {"cat:v1:lock": "tok-1"}
            self.expired = []

        def get(self, key):
            return self.store.get(key)

        def expire(self, key, ttl_s):
            self.expired.append((key, ttl_s))
            return True

    fb_kv = RedisCatalogKV(client=SimpleClient())
    assert fb_kv.refresh_lock_if_equals("cat:v1:lock", "tok-2", ttl=120) is False
    assert fb_kv.refresh_lock_if_equals("cat:v1:lock", "tok-1", ttl=120) is True
    assert fb_kv.client.expired == [("cat:v1:lock", 120)]
