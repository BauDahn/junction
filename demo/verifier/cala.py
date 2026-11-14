import asyncio
import hashlib
import json
from pathlib import Path
import random

import httpx


class CalaClient:
    def __init__(self, api_key: str, cache_dir: Path, client=None, timeout=120):
        self.api_key, self.cache_dir = api_key, Path(cache_dir)
        self.client = client
        self.timeout = timeout
        self._limit = asyncio.Semaphore(6)

    def _path(self, question):
        digest = hashlib.sha256(question.encode()).hexdigest()
        return self.cache_dir / "cala" / f"{digest}.json"

    async def search(self, question: str) -> dict:
        path = self._path(question)
        if path.exists():
            return json.loads(path.read_text())
        async with self._limit:
            owns = self.client is None
            client = self.client or httpx.AsyncClient(timeout=self.timeout)
            try:
                response = None
                for attempt in range(3):
                    response = await client.post("https://api.cala.ai/v1/knowledge/search",
                        headers={"X-API-KEY": self.api_key}, json={"input": question})
                    if response.status_code != 429 and response.status_code < 500:
                        break
                    if attempt < 2:
                        await asyncio.sleep((2 ** attempt) + random.random() * 0.2)
                response.raise_for_status()
                raw = response.json()
            finally:
                if owns:
                    await client.aclose()
        result = self.normalize(raw)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return result

    @staticmethod
    def normalize(raw):
        sources, seen = [], set()
        facts, entities = [], []
        for item in raw.get("context", []) or []:
            content = str(item.get("content", ""))[:600]
            facts.append({"id": item.get("id"), "content": content})
            for origin in item.get("origins", []) or []:
                ref = origin.get("document") or origin.get("source") or {}
                if not ref:
                    continue
                pair = (ref.get("name", "Source"), ref.get("url", ""))
                if pair not in seen:
                    sources.append({"name": pair[0], "url": pair[1]})
                    seen.add(pair)
        for entity in raw.get("entities", []) or []:
            entities.append({k: entity.get(k) for k in ("id", "name", "entity_type")})
        return {"answer": str(raw.get("content", "")), "sources": sources, "facts": facts, "entities": entities}
