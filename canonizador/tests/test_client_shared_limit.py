import asyncio

import httpx
import pytest

from canonizador.client import CalaClient
import canonizador.client as client_module


class Cache:
    def __init__(self, remote=None): self.data, self.remote = {}, remote
    def get_key(self, ns, key): return self.data.get((ns, key))
    def put_key(self, ns, key, value): self.data[(ns, key)] = value


class Pipeline:
    def __init__(self, store): self.store, self.key, self.ttl = store, None, None
    def incr(self, key): self.key = key; return self
    def expire(self, key, ttl): self.key, self.ttl = key, ttl; return self
    def execute(self):
        self.store.expirations[self.key] = self.ttl
        self.store.counts[self.key] = self.store.counts.get(self.key, 0) + 1
        return [self.store.counts[self.key], True]


class Valkey:
    def __init__(self, fail=False): self.counts, self.expirations, self.fail = {}, {}, fail
    def _run(self, operation):
        if self.fail: raise RuntimeError("down")
        class Client:
            def pipeline(inner): return Pipeline(self)
        return True, operation(Client())


def response(): return httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", "https://test"))


@pytest.mark.asyncio
async def test_clients_share_endpoint_window_and_expire_keys(monkeypatch):
    clock, starts = [100.0], []
    monkeypatch.setattr(client_module.time, "time", lambda: clock[0])
    async def sleep(delay): clock[0] += delay
    async def handler(request): starts.append(clock[0]); return response()
    shared, http = Valkey(), httpx.AsyncClient(transport=httpx.MockTransport(handler))
    clients = [CalaClient("x", client=http, sleep=sleep, knowledge_interval=8, cache=Cache(shared)) for _ in range(2)]
    await asyncio.gather(*(c.knowledge_query(str(i)) for i, c in enumerate(clients)))
    assert starts == [100.0, 104.0]
    assert list(shared.expirations.values()) == [10, 10]
    assert sum(c.stats["shared_limit_waits"] for c in clients) == 1
    assert sum(c.stats["pause_seconds"] for c in clients) >= 4
    await http.aclose()


@pytest.mark.asyncio
async def test_no_valkey_keeps_local_behavior(monkeypatch):
    monkeypatch.setenv("CALA_SHARED_LIMIT", "1")
    async def handler(request): return response()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, entities_interval=0, cache=Cache())
    await client.entities("x", "Company")
    assert client.shared_limiter is None and client.stats["shared_limit_errors"] == 0
    await http.aclose()


@pytest.mark.asyncio
async def test_valkey_error_falls_back_for_call_and_counts_error():
    async def handler(request): return response()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, cache=Cache(Valkey(fail=True)))
    assert await client.entities("x", "Company") == {"ok": True}
    assert client.stats["shared_limit_errors"] == 1
    await http.aclose()


@pytest.mark.asyncio
async def test_environment_can_disable_shared_limit(monkeypatch):
    monkeypatch.setenv("CALA_SHARED_LIMIT", "0")
    client = CalaClient("x", cache=Cache(Valkey()))
    assert client.shared_limiter is None

