import httpx

from canonizador.client import CalaClient
from scripts.medir_limite import NoResponseCache


class Pipeline:
    def incr(self, key): return self
    def expire(self, key, ttl): return self
    def execute(self): return [1, True]


class FakeValkey:
    def _run(self, operation):
        class Client:
            def pipeline(self): return Pipeline()
        return True, operation(Client())


async def test_no_response_cache_keeps_shared_limiter_without_network():
    remote = FakeValkey()
    cache = NoResponseCache(remote)

    async def handler(request):
        return httpx.Response(200, json={"name": "Example"}, request=request)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CalaClient("fake", client=http, cache=cache, entities_interval=0)
    assert client.shared_limiter is not None
    assert client.shared_limiter.remote is remote

    result = await client.entities("Example", "Company")
    assert result == {"name": "Example"}
    assert cache.get_key("cala", "same-key") is None
    cache.put_key("cala", "same-key", result)
    assert cache.get_key("cala", "same-key") is None
    await http.aclose()
