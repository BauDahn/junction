"""Caché de consultas: disco (por máquina) y, opcionalmente, Valkey compartido (Aiven).

Todas las cachés tienen la misma interfaz: `get(namespace, value)` y `put(namespace, value, result)`
(clave = sha256 del JSON canónico), más `get_key`/`put_key` para quien ya tiene el hash, y `stats`
con los contadores `local_hits`, `remote_hits` y `misses`.
"""
import hashlib
import json
import os
import time
from pathlib import Path

DEFAULT_TTL_S = 7 * 24 * 3600  # respuestas de Cala: 7 días
NO_TTL_NAMESPACES = ("intents",)  # intenciones del LLM: no caducan
ENV_KEYS = ("CALA_API_KEY", "VALKEY_URL", "CACHE_TTL_S", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_MODEL", "GEMINI_FAST_MODEL", "LLM_PROVIDER")
STATS = {"local_hits": 0, "remote_hits": 0, "misses": 0}  # acumulado del proceso (cachés de make_cache)


def _new_stats():
    return {"local_hits": 0, "remote_hits": 0, "misses": 0}


def cache_key(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def load_env(path=None, keys=ENV_KEYS):
    """Carga de backend/.env solo las variables de `keys` que falten en el entorno. No imprime nada.

    VALKEY_URL definida vacía en el entorno cuenta como definida: sirve para desactivar la caché
    remota aunque esté en el .env (lo usan los tests).
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
        self.count = True  # LayeredCache lo apaga para llevar la cuenta ella

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
    """Caché en Valkey/Redis. Nunca rompe una consulta: ante cualquier error devuelve None / no escribe,
    y deja de intentar durante `retry_after_s` para no sumar latencia."""

    def __init__(self, url, prefix="cala:v1", ttl_s=None, *, client=None, timeout_s=2, retry_after_s=60,
                 no_ttl_namespaces=NO_TTL_NAMESPACES, clock=time.monotonic):
        self.url, self.prefix, self.ttl_s = url, prefix, ttl_s
        self.timeout_s, self.retry_after_s, self.clock = timeout_s, retry_after_s, clock
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
        """Ejecuta operation(cliente). Devuelve (ok, valor); ante un error marca el remoto como caído."""
        if not self.available: return False, None
        try:
            if self._client is None:
                import redis
                self._client = redis.Redis.from_url(self.url, socket_connect_timeout=self.timeout_s,
                                                    socket_timeout=self.timeout_s, decode_responses=True)
            value = operation(self._client)
            self._down_until = None
            return True, value
        except Exception:  # red, TLS, credenciales, URL mal formada: la caché remota es opcional
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
    """get: local → remoto (lo que viene del remoto se copia al local); put: ambos."""

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
    """CACHE_TTL_S en segundos (por defecto 7 días; 0 = sin caducidad)."""
    try: ttl = int(os.getenv("CACHE_TTL_S") or DEFAULT_TTL_S)
    except ValueError: ttl = DEFAULT_TTL_S
    return ttl if ttl > 0 else None


def remote_from_env():
    """ValkeyCache según VALKEY_URL (entorno o backend/.env), o None. Se reutiliza una por proceso para
    compartir la conexión y la pausa tras un fallo."""
    load_env()
    url = (os.getenv("VALKEY_URL") or "").strip()
    if not url: return None
    ttl = ttl_from_env()
    if (url, ttl) not in _REMOTES: _REMOTES[(url, ttl)] = ValkeyCache(url, ttl_s=ttl)
    return _REMOTES[(url, ttl)]


def make_cache(root):
    """LayeredCache(disco, Valkey) si VALKEY_URL está definida; si no, DiskCache. `stats` es el
    acumulado del proceso (`canonizador.cache.STATS`)."""
    remote = remote_from_env()
    local = DiskCache(root, stats=STATS)
    return LayeredCache(local, remote, stats=STATS) if remote else local
