import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import httpx
import pytest

from canonizador.client import CalaBudgetExceeded, CalaClient, _usage_memory, cala_usage


class Cache:
    def __init__(self): self.data = {}
    def get_key(self, ns, key): return self.data.get((ns, key))
    def put_key(self, ns, key, value): self.data[(ns, key)] = value


@pytest.mark.asyncio
async def test_real_call_usage_cache_and_daily_cap(monkeypatch):
    calls = 0
    async def handler(request):
        nonlocal calls
        calls += 1
        return response()
    monkeypatch.setenv("CALA_CLIENT_LABEL", "test:catalog")
    monkeypatch.setenv("CALA_DAILY_CALL_CAP", "1")
    _usage_memory.clear()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, entities_interval=0, cache=Cache())
    await client.entities("one", "Company")
    await client.entities("one", "Company")  # respuesta cacheada
    with pytest.raises(CalaBudgetExceeded, match="Daily Cala call cap reached \(1\)"):
        await client.entities("two", "Company")
    usage = cala_usage(date=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).date().isoformat())
    assert calls == 1 and usage["total"] == 1
    assert usage["by_class"] == {"entities": 1, "knowledge": 0}
    assert usage["by_who"] == {"test:catalog": 1}
    await http.aclose()


def response(status=200, headers=None, data=None):
    return httpx.Response(status, headers=headers, json=data or {"ok": True}, request=httpx.Request("GET", "https://test"))


@pytest.mark.asyncio
async def test_endpoint_intervals_and_legacy_min_interval():
    starts = []
    async def handler(request):
        starts.append((request.url.path, asyncio.get_running_loop().time()))
        return response()
    client = CalaClient("x", client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), sleep=asyncio.sleep,
                        entities_interval=0.01, min_interval=0.05, cache=Cache())
    await client.request("GET", "/entities", params={"name": "one"})
    await client.request("POST", "/knowledge/query", body={"input": "one"})
    await client.request("POST", "/knowledge/search", body={"input": "two"})
    assert starts[2][1] - starts[1][1] >= 0.045
    await client.client.aclose()


@pytest.mark.asyncio
async def test_entities_spacing_and_semaphore():
    starts, active, peak = [], 0, 0
    async def handler(request):
        nonlocal active, peak
        starts.append(asyncio.get_running_loop().time())
        active += 1; peak = max(peak, active)
        await asyncio.sleep(0.025)
        active -= 1
        return response()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, entities_interval=0.01, entities_concurrency=2, cache=Cache())
    await asyncio.gather(*(client.entities(str(i), "Company") for i in range(4)))
    assert peak == 2
    assert all(b - a >= 0.009 for a, b in zip(starts, starts[1:]))
    await http.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("header,expected", [("2", 2), ("120", 60)])
async def test_retry_after_and_cap(header, expected):
    waits, calls = [], 0
    async def sleep(seconds): waits.append(seconds)
    async def handler(request):
        nonlocal calls
        calls += 1
        return response(429, {"Retry-After": header}) if calls == 1 else response()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, sleep=sleep, entities_interval=0, cache=Cache())
    await client.entities("a", "Company")
    assert expected in waits and client.stats["429_wait_seconds"] == expected
    await http.aclose()


@pytest.mark.asyncio
async def test_retry_after_http_date():
    waits, calls = [], 0
    retry_date = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=3), usegmt=True)
    async def sleep(seconds): waits.append(seconds)
    async def handler(request):
        nonlocal calls
        calls += 1
        return response(429, {"Retry-After": retry_date}) if calls == 1 else response()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, sleep=sleep, entities_interval=0, cache=Cache())
    await client.entities("date", "Company")
    assert waits and 0 <= waits[0] <= 3
    await http.aclose()


@pytest.mark.asyncio
async def test_exponential_retry_and_deduplication():
    waits, calls = [], 0
    async def sleep(seconds): waits.append(seconds); await asyncio.sleep(0)
    async def handler(request):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return response(429) if calls == 1 else response()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, sleep=sleep, entities_interval=0, cache=Cache())
    a, b = await asyncio.gather(client.entities("same", "Company"), client.entities("same", "Company"))
    assert a == b and calls == 2 and waits == [5]
    assert client.stats["429"] == 1
    await http.aclose()


@pytest.mark.asyncio
async def test_missing_retry_after_uses_5_10_20_and_legacy_min_interval():
    waits, calls, starts = [], 0, []
    async def sleep(seconds): waits.append(seconds)
    async def handler(request):
        nonlocal calls
        calls += 1
        starts.append(asyncio.get_running_loop().time())
        return response(429)
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, sleep=sleep, min_interval=0.02, cache=Cache())
    with pytest.raises(httpx.HTTPStatusError):
        await client.knowledge_query("fails")
    assert waits.count(5) == 1 and waits.count(10) == 1 and waits.count(20) == 1
    assert calls == 4
    await http.aclose()


@pytest.mark.asyncio
async def test_429_pauses_other_entities_requests():
    starts, calls = [], 0
    async def handler(request):
        nonlocal calls
        calls += 1
        starts.append(asyncio.get_running_loop().time())
        return response(429, {"Retry-After": "0.06"}) if calls == 1 else response()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, entities_interval=0, entities_concurrency=2, cache=Cache())
    one = asyncio.create_task(client.entities("one", "Company"))
    while client.stats["429"] == 0:
        await asyncio.sleep(0.001)
    two = asyncio.create_task(client.entities("two", "Company"))
    await asyncio.gather(one, two)
    assert starts[1] - starts[0] >= 0.05
    await http.aclose()


@pytest.mark.asyncio
async def test_cache_still_avoids_http_call():
    calls = 0
    async def handler(request):
        nonlocal calls
        calls += 1
        return response()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("x", client=http, cache=Cache())
    await client.entities("same", "Company")
    await client.entities("same", "Company")
    assert calls == 1 and client.stats["cache_hits"] == 1
    await http.aclose()
