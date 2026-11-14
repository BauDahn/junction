import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlencode

import httpx


class CalaClient:
    BASE = "https://api.cala.ai/v1"

    def __init__(self, api_key=None, cache_dir="cache", client=None, sleep=asyncio.sleep):
        self.api_key = api_key or os.getenv("CALA_API_KEY", "")
        if not self.api_key: raise RuntimeError("Definí CALA_API_KEY en el entorno o backend/.env")
        self.cache_dir, self.client, self.sleep = Path(cache_dir), client, sleep
        self._lock = asyncio.Lock()
        self.calls = 0

    def _cache(self, key): return self.cache_dir / "cala" / (key + ".json")

    async def request(self, method, path, *, params=None, body=None):
        cache_key = json.dumps([method, path, params, body], sort_keys=True, ensure_ascii=False)
        cp = self._cache(__import__("hashlib").sha256(cache_key.encode()).hexdigest())
        if cp.exists(): return json.loads(cp.read_text())
        async with self._lock:
            owns = self.client is None
            client = self.client or httpx.AsyncClient(timeout=120)
            try:
                response = None
                for attempt, delay in enumerate((20, 40, 80)):
                    self.calls += 1
                    response = await client.request(method, self.BASE + path, params=params, json=body, headers={"X-API-KEY": self.api_key})
                    if response.status_code != 429 and response.status_code < 500: break
                    if attempt < 2: await self.sleep(delay)
                response.raise_for_status(); value = response.json()
            finally:
                if owns: await client.aclose()
            cp.parent.mkdir(parents=True, exist_ok=True); cp.write_text(json.dumps(value, ensure_ascii=False))
            return value

    async def entities(self, name, entity_type):
        return await self.request("GET", "/entities", params={"name": name, "entity_types": entity_type})

    async def introspection(self, entity_id):
        return await self.request("GET", f"/entities/{entity_id}/introspection")

    async def retrieve(self, entity_id, *, properties=None, relationships=None, numerical_observations=None):
        body = {"entity_id": entity_id, "properties": properties or [], "relationships": relationships or {}}
        if numerical_observations is not None: body["numerical_observations"] = numerical_observations
        return await self.request("POST", f"/entities/{entity_id}", body=body)

    async def search(self, input):
        return await self.request("POST", "/knowledge/search", body={"input": input})
