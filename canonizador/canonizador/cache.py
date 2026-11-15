"""Query cache: local disk (per machine) and, optionally, shared Valkey (Aiven).

All caches use the same interface: `get(namespace, value)` y `put(namespace, value, result)`
(key = sha256 of canonical JSON), plus `get_key`/`put_key` for callers that already have the hash, and `stats`
with the `local_hits`, `remote_hits`, and `misses` counters.
"""
import hashlib
import json
import os
import time
from pathlib import Path

DEFAULT_TTL_S = 7 * 24 * 3600  # Cala responses: 7 days
NO_TTL_NAMESPACES = ("intents",)  # LLM intents: never expire
ENV_KEYS = ("CALA_API_KEY", "VALKEY_URL", "VALKEY_CONNECT_TIMEOUT", "VALKEY_TIMEOUT", "CACHE_TTL_S", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_FAST_MODEL", "LLM_PROVIDER")
STATS = {"local_hits": 0, "remote_hits": 0, "misses": 0}  # process-wide total (make_cache instances)


def _new_stats():
    return {"local_hits": 0, "remote_hits": 0, "misses": 0}


def cache_key(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def load_env(path=None, keys=ENV_KEYS):
    """Loads only `keys` missing from the environment from backend/.env. Prints nothing.

    An empty VALKEY_URL in the environment counts as set: it disables the cache
    remote cache even if it is set in .env (used by tests).
    """
    path = Path(path) if path else Path(__file__).resolve().parents[2] / "backend" / ".env"
    if not path.exists(): return
    for line in path.read_text().splitlines():
        name, sep, value = line.strip().partition("=")
        name = name.strip()
        if not sep or name not in keys: continue
        if os.environ.get(name) or (name == "VALKEY_URL" and name in os.environ): continue
        os.environ[name] = value.strip().strip("\"'")


class _Base:
    def key(self, value):
        return cache_key(value)

    def get(self, namespace, value):
        return self.get_key(namespace, self.key(value))

    def put(self, namespace, value, result):
        return self.put_key(namespace, self.key(value), result)


class DiskCache(_Base):
    def __init__(self, root, stats=None):
        self.root = Path(root)
        self.stats = stats if stats is not None else _new_stats()
        self.count = True  # LayeredCache LayeredCache disables this to track its own counts

    def _path(self, namespace, digest):
        return self.root / namespace / f"{digest}.json"

    def get_key(self, namespace, digest):
        path = self._path(namespace, digest)
        result = json.loads(path.read_text()) if path.exists() else None
        if self.count: self.stats["misses" if result is None else "local_hits"] += 1
        return result

    def put_key(self, namespace, digest, result):
        path = self._path(namespace, digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        return True

    def entries(self):
        """Itera (namespace, digest, result) de todo lo guardado en disco."""
        if not self.root.is_dir(): return
        for folder in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for path in sorted(folder.glob("*.json")):
                try: yield folder.name, path.stem, json.loads(path.read_text())
                except (OSError, ValueError): continue


class ValkeyCache(_Base):
    """Valkey/Redis cache. Never breaks a query: returns None on any error and skips writes,
    and stops retrying for `retry_after_s` to avoid adding latency."""

    def __init__(self, url, prefix="cala:v1", ttl_s=None, *, client=None, timeout_s=3, connect_timeout_s=8, retry_after_s=60,
                 no_ttl_namespaces=NO_TTL_NAMESPACES, clock=time.monotonic):
        self.url, self.prefix, self.ttl_s = url, prefix, ttl_s
        self.timeout_s, self.connect_timeout_s = timeout_s, connect_timeout_s
        self.retry_after_s, self.clock = retry_after_s, clock
        self.no_ttl_namespaces = tuple(no_ttl_namespaces)
        self._client, self._down_until = client, None
        self.stats = _new_stats()
        self.errors = 0

    def _name(self, namespace, digest):
        return f"{self.prefix}:{namespace}:{digest}"

    def ttl_for(self, namespace):
        return None if namespace in self.no_ttl_namespaces else (self.ttl_s or None)

    @property
    def available(self):
        return self._down_until is None or self.clock() >= self._down_until

    def _run(self, operation):
        """Runs operation(client). Returns (ok, value); marks the remote as unavailable on error."""
        if not self.available: return False, None
        try:
            if self._client is None:
                import redis
                self._client = redis.Redis.from_url(self.url, socket_connect_timeout=self.connect_timeout_s,
                                                    socket_timeout=self.timeout_s, decode_responses=True)
            value = operation(self._client)
            self._down_until = None
            return True, value
        except Exception:  # network, TLS, credentials, malformed URL: remote caching is optional
            self.errors += 1
            self._down_until = self.clock() + self.retry_after_s
            return False, None

    def get_key(self, namespace, digest):
        ok, raw = self._run(lambda c: c.get(self._name(namespace, digest)))
        result = None
        if ok and raw is not None:
            try: result = json.loads(raw)
            except ValueError: result = None
        self.stats["misses" if result is None else "remote_hits"] += 1
        return result

    def put_key(self, namespace, digest, result):
        raw = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        ok, _ = self._run(lambda c: c.set(self._name(namespace, digest), raw, ex=self.ttl_for(namespace)))
        return ok

    def ping(self):
        ok, _ = self._run(lambda c: c.ping())
        return ok


class LayeredCache(_Base):
    """get: local → remote (remote values are copied locally); put: both."""

    def __init__(self, local, remote, stats=None):
        self.local, self.remote = local, remote
        self.stats = stats if stats is not None else _new_stats()
        if hasattr(local, "count"): local.count = False

    def get_key(self, namespace, digest):
        result = self.local.get_key(namespace, digest)
        if result is not None:
            self.stats["local_hits"] += 1
            return result
        result = self.remote.get_key(namespace, digest)
        if result is not None:
            self.stats["remote_hits"] += 1
            self.local.put_key(namespace, digest, result)
            return result
        self.stats["misses"] += 1
        return None

    def put_key(self, namespace, digest, result):
        self.local.put_key(namespace, digest, result)
        self.remote.put_key(namespace, digest, result)
        return True


_REMOTES = {}


def ttl_from_env():
    """CACHE_TTL_S in seconds (7 days by default; 0 = no expiration)."""
    try: ttl = int(os.getenv("CACHE_TTL_S") or DEFAULT_TTL_S)
    except ValueError: ttl = DEFAULT_TTL_S
    return ttl if ttl > 0 else None


def remote_from_env():
    """ValkeyCache from VALKEY_URL (environment or backend/.env), or None. One instance is reused per process to
    share the connection and cooldown after a failure."""
    load_env()
    url = (os.getenv("VALKEY_URL") or "").strip()
    if not url: return None
    ttl = ttl_from_env()
    connect_timeout = _int_env("VALKEY_CONNECT_TIMEOUT", 8)
    timeout = _int_env("VALKEY_TIMEOUT", 3)
    key = (url, ttl, connect_timeout, timeout)
    if key not in _REMOTES:
        _REMOTES[key] = ValkeyCache(url, ttl_s=ttl, timeout_s=timeout, connect_timeout_s=connect_timeout)
    return _REMOTES[key]


def _int_env(name, default):
    try: return max(0.1, float(os.getenv(name, str(default))))
    except (TypeError, ValueError): return default


def warmup():
    """Attempts to establish the shared connection without propagating errors. False if unavailable."""
    try:
        remote = remote_from_env()
        return remote.ping() if remote is not None else False
    except Exception:
        return False


def make_cache(root):
    """LayeredCache(disk, Valkey) when VALKEY_URL is set; otherwise DiskCache. `stats` is the
    process-wide total (`canonizador.cache.STATS`)."""
    remote = remote_from_env()
    local = DiskCache(root, stats=STATS)
    return LayeredCache(local, remote, stats=STATS) if remote else local
