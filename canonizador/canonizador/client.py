import asyncio
import hashlib
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlencode

import httpx

from .cache import load_env, make_cache


class CalaBudgetExceeded(RuntimeError):
    def __init__(self, cap):
        super().__init__(f"Daily Cala call cap reached ({cap})")
        self.cap = int(cap)


_usage_lock = threading.Lock()
_usage_memory = {}


def _utc_date():
    return datetime.now(timezone.utc).date().isoformat()


def _default_label():
    main = sys.modules.get("__main__")
    module = Path(getattr(main, "__file__", "") or "").stem or "python"
    return f"{socket.gethostname()}:{module}"


def cala_usage(remote=None, date=None):
    date = date or _utc_date()
    prefix = f"calls:v1:{date}:"
    if remote is not None:
        ok, vals = remote._run(lambda c: c.mget([prefix + "total", prefix + "class:entities", prefix + "class:knowledge"]))
        if ok:
            def integer(value):
                try: return int(value or 0)
                except (TypeError, ValueError): return 0
            who_keys_ok, who_keys = remote._run(lambda c: list(c.scan_iter(match=prefix + "who:*")))
            by_who = {}
            if who_keys_ok and who_keys:
                who_vals_ok, who_vals = remote._run(lambda c: c.mget(who_keys))
                if who_vals_ok:
                    by_who = {key[len(prefix + "who:"):]: integer(value) for key, value in zip(who_keys, who_vals)}
            return {"date": date, "total": integer(vals[0]),
                    "by_class": {"entities": integer(vals[1]), "knowledge": integer(vals[2])}, "by_who": by_who}
    with _usage_lock:
        data = _usage_memory.get(date, {"total": 0, "by_class": {"entities": 0, "knowledge": 0}, "by_who": {}})
        return {"date": date, "total": data["total"], "by_class": dict(data["by_class"]), "by_who": dict(data["by_who"])}


class _ValkeySharedLimiter:
    def __init__(self, remote): self.remote = remote

    def increment(self, kind, interval, now):
        if interval <= 0:
            return 1, 1, 0
        size = interval
        window = int(now // size)
        limit = 1
        key = f"ratelimit:v1:cala:{kind}:{window}"
        ttl = int(size * 1000) + 2000
        existing_client = getattr(self.remote, "_client", None)
        if existing_client is not None and not callable(getattr(existing_client, "pipeline", None)):
            raise RuntimeError("Valkey client does not support pipelines")
        def operation(client):
            if not callable(getattr(client, "pipeline", None)):
                raise RuntimeError("Valkey client does not support pipelines")
            pipe = client.pipeline()
            pipe.incr(key)
            pipe.pexpire(key, ttl)
            result = pipe.execute()
            return result[0]
        ok, value = self.remote._run(operation)
        if not ok: raise RuntimeError("Valkey rate limiter unavailable")
        return value, limit, size


class CalaClient:
    BASE = "https://api.cala.ai/v1"

    def __init__(self, api_key=None, cache_dir="cache", client=None, sleep=asyncio.sleep, min_interval=8, cache=None,
                 knowledge_interval=None, entities_interval=None, entities_concurrency=None, shared_limiter=None):
        if not api_key: load_env()
        self.api_key = api_key or os.getenv("CALA_API_KEY", "")
        if not self.api_key: raise RuntimeError("Definí CALA_API_KEY en el entorno o backend/.env")
        self.cache_dir, self.client, self.sleep = Path(cache_dir), client, sleep
        # min_interval sigue siendo el valor predeterminado explícito para knowledge.
        self.min_interval = min_interval
        self.intervals = {
            "knowledge": float(knowledge_interval if knowledge_interval is not None else os.getenv("CALA_KNOWLEDGE_INTERVAL", min_interval)),
            "entities": float(entities_interval if entities_interval is not None else os.getenv("CALA_ENTITIES_INTERVAL", "0.7")),
        }
        concurrency = int(entities_concurrency if entities_concurrency is not None else os.getenv("CALA_ENTITIES_CONCURRENCY", "2"))
        if concurrency < 1: raise ValueError("entities_concurrency debe ser al menos 1")
        self._semaphores = {"knowledge": asyncio.Semaphore(1), "entities": asyncio.Semaphore(concurrency)}
        self._schedule_locks = {kind: asyncio.Lock() for kind in self.intervals}
        self._last_call = {kind: None for kind in self.intervals}
        self._paused_until = {kind: 0.0 for kind in self.intervals}
        self._inflight = {}
        self._inflight_lock = asyncio.Lock()
        self._wait_locks = {kind: asyncio.Lock() for kind in self.intervals}
        self._retry_base = float(os.getenv("CALA_429_WAIT", "5"))
        self.calls = 0
        self.stats = {"knowledge_calls": 0, "entities_calls": 0, "429": 0, "402": 0,
                      "pause_seconds": 0.0, "429_wait_seconds": 0.0, "402_wait_seconds": 0.0, "cache_hits": 0,
                      "shared_limit_waits": 0, "shared_limit_errors": 0}
        self.cache = cache or make_cache(self.cache_dir)
        remote = getattr(self.cache, "remote", None)
        if remote is None and hasattr(self.cache, "_client") and hasattr(self.cache, "_run"):
            remote = self.cache
        enabled = os.getenv("CALA_SHARED_LIMIT", "1") != "0"
        self.shared_limiter = shared_limiter if shared_limiter is not None else (
            _ValkeySharedLimiter(remote) if enabled and remote is not None else None)
        self._shared_down_until = 0.0
        raw_cap = os.getenv("CALA_DAILY_CALL_CAP", "2000").strip()
        try: self.daily_call_cap = int(raw_cap or 2000)
        except ValueError: raise ValueError("CALA_DAILY_CALL_CAP must be an integer")
        self.call_cap = 0
        self._run_start_calls = 0
        self._run_reserved = 0
        self.call_label = os.getenv("CALA_CLIENT_LABEL") or _default_label()

    def _record_real_call(self, kind):
        date = _utc_date()
        prefix = f"calls:v1:{date}:"
        cap = self.daily_call_cap if self.daily_call_cap > 0 else 0
        remote = getattr(self.cache, "remote", None)
        if remote is None and hasattr(self.cache, "_client") and hasattr(self.cache, "_run"):
            remote = self.cache
        if remote is not None:
            script = """
            local total = tonumber(redis.call('GET', KEYS[1]) or '0')
            local cap = tonumber(ARGV[1])
            if cap > 0 and total >= cap then return 0 end
            for i = 1, 3 do redis.call('INCR', KEYS[i]); redis.call('EXPIRE', KEYS[i], 259200) end
            return 1
            """
            keys = [prefix + "total", prefix + "class:" + kind, prefix + "who:" + self.call_label]
            with _usage_lock:
                if self.call_cap and self._run_reserved >= self.call_cap: raise CalaBudgetExceeded(self.call_cap)
                self._run_reserved += 1
            try:
                existing_client = getattr(remote, "_client", None)
                if existing_client is not None and not callable(getattr(existing_client, "pipeline", None)):
                    raise RuntimeError("Valkey client does not support pipelines")
                if cap:
                    ok, allowed = remote._run(lambda c: c.eval(script, len(keys), *keys, cap))
                    if ok:
                        if not allowed:
                            with _usage_lock: self._run_reserved -= 1
                            raise CalaBudgetExceeded(cap)
                        return
                else:
                    def increment(client):
                        pipe = client.pipeline()
                        for key in keys:
                            pipe.incr(key)
                            if hasattr(pipe, "expire"): pipe.expire(key, 259200)
                            else: pipe.pexpire(key, 259200000)
                        pipe.execute()
                    ok, _ = remote._run(increment)
                    if ok: return
            except CalaBudgetExceeded:
                raise
            except Exception:
                pass
            with _usage_lock: self._run_reserved -= 1
        with _usage_lock:
            if self.call_cap and self._run_reserved >= self.call_cap: raise CalaBudgetExceeded(self.call_cap)
            self._run_reserved += 1
            data = _usage_memory.setdefault(date, {"total": 0, "by_class": {"entities": 0, "knowledge": 0}, "by_who": {}})
            if cap and data["total"] >= cap: raise CalaBudgetExceeded(cap)
            data["total"] += 1
            data["by_class"][kind] += 1
            data["by_who"][self.call_label] = data["by_who"].get(self.call_label, 0) + 1

    async def _wait_shared_slot(self, kind):
        limiter = self.shared_limiter
        if limiter is None: return
        loop = asyncio.get_running_loop()
        if loop.time() < self._shared_down_until: return
        interval = self.intervals[kind]
        if interval <= 0: return
        for _ in range(10):
            try:
                now = time.time()
                count, limit, window_size = await asyncio.to_thread(limiter.increment, kind, interval, now)
            except Exception:
                self.stats["shared_limit_errors"] += 1
                self._shared_down_until = loop.time() + 30
                return
            if count <= limit: return
            wait = window_size - (now % window_size)
            self.stats["pause_seconds"] += wait
            self.stats["shared_limit_waits"] += 1
            await self.sleep(wait)
        self.stats["shared_limit_errors"] += 1
        self._shared_down_until = loop.time() + 30

    async def _wait_for_slot(self, kind):
        # Serializing only start times keeps the configured spacing without holding a lock over HTTP.
        async with self._schedule_locks[kind]:
            loop = asyncio.get_running_loop()
            while True:
                now = loop.time()
                wait = max(0.0, self._paused_until[kind] - now)
                if self._last_call[kind] is not None:
                    wait = max(wait, self.intervals[kind] - (now - self._last_call[kind]))
                if wait <= 0: break
                self.stats["pause_seconds"] += wait
                await self.sleep(wait)
            self._last_call[kind] = loop.time()
        await self._wait_shared_slot(kind)

    @staticmethod
    def _retry_after(response):
        value = response.headers.get("Retry-After")
        if value is None: return None
        try: return max(0.0, float(value))
        except ValueError:
            try:
                date = parsedate_to_datetime(value)
                if date.tzinfo is None: date = date.replace(tzinfo=timezone.utc)
                return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError): return None

    async def request(self, method, path, *, params=None, body=None):
        cache_key = json.dumps([method, path, params, body], sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(cache_key.encode()).hexdigest()
        cached = self.cache.get_key("cala", digest)
        if cached is not None:
            self.stats["cache_hits"] += 1
            return cached
        async with self._inflight_lock:
            future = self._inflight.get(digest)
            if future is None:
                future = asyncio.get_running_loop().create_future()
                self._inflight[digest] = future
                owner = True
            else: owner = False
        if not owner:
            value = await future
            self.stats["cache_hits"] += 1
            return value
        try:
            kind = "knowledge" if path.startswith("/knowledge/") else "entities"
            async with self._semaphores[kind]:
                cached = self.cache.get_key("cala", digest)
                if cached is not None:
                    self.stats["cache_hits"] += 1
                    future.set_result(cached)
                    return cached
                owns = self.client is None
                client = self.client or httpx.AsyncClient(timeout=120)
                try:
                    for attempt in range(4):
                        await self._wait_for_slot(kind)
                        self._record_real_call(kind)
                        self.calls += 1
                        self.stats[f"{kind}_calls"] += 1
                        response = await client.request(method, self.BASE + path, params=params, json=body,
                                                        headers={"X-API-KEY": self.api_key})
                        if response.status_code in (402, 429):
                            code = str(response.status_code)
                            self.stats[code] += 1
                            if attempt == 3:
                                response.raise_for_status()
                            retry = self._retry_after(response)
                            delay = min(60.0, retry if retry is not None else self._retry_base * (2 ** attempt))
                            async with self._wait_locks[kind]:
                                self._paused_until[kind] = max(self._paused_until[kind], asyncio.get_running_loop().time() + delay)
                            self.stats[f"{code}_wait_seconds"] += delay
                            await self.sleep(delay)
                            # The sleep hook may be virtual in tests; production sleep advances loop.time().
                            if asyncio.get_running_loop().time() < self._paused_until[kind]:
                                self._paused_until[kind] = asyncio.get_running_loop().time()
                            continue
                        if response.status_code < 500: break
                        if attempt < 3: await self.sleep(20 * (2 ** attempt))
                    response.raise_for_status()
                    value = response.json()
                finally:
                    if owns: await client.aclose()
                self.cache.put_key("cala", digest, value)
                future.set_result(value)
                return value
        except BaseException as exc:
            if not future.done(): future.set_exception(exc)
            # Retrieve the exception when there were no waiters, avoiding an unhandled-future warning.
            if not future.cancelled(): future.exception()
            raise
        finally:
            async with self._inflight_lock:
                self._inflight.pop(digest, None)

    async def entities(self, name, entity_type):
        return await self.request("GET", "/entities", params={"name": name, "entity_types": entity_type})

    async def introspection(self, entity_id):
        return await self.request("GET", f"/entities/{entity_id}/introspection")

    async def retrieve(self, entity_id, *, properties=None, relationships=None, numerical_observations=None):
        body = {"properties": properties or [], "relationships": relationships or {}}
        if numerical_observations:
            body["numerical_observations"] = (numerical_observations if isinstance(numerical_observations, dict)
                                              else {oid: {"limit": 100} for oid in numerical_observations})
        return await self.request("POST", f"/entities/{entity_id}", body=body)

    async def search(self, input):
        return await self.request("POST", "/knowledge/search", body={"input": input})

    async def knowledge_query(self, input):
        return await self.request("POST", "/knowledge/query", body={"input": input})
