import json

import pytest

from canonizador import cache as cache_mod
from canonizador import cache_sync
from canonizador.cache import DiskCache, LayeredCache, ValkeyCache, load_env, make_cache


class FakeRedis:
    """Cliente Redis falso, sin red: guarda en memoria y puede simular caídas."""

    def __init__(self):
        self.data, self.ttl, self.calls, self.fail = {}, {}, 0, False

    def _call(self):
        self.calls += 1
        if self.fail: raise ConnectionError("sin red")

    def get(self, name):
        self._call()
        return self.data.get(name)

    def set(self, name, value, ex=None):
        self._call()
        self.data[name], self.ttl[name] = value, ex
        return True

    def ping(self):
        self._call()
        return True


class Clock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now


def layered(tmp_path, **kwargs):
    fake = FakeRedis()
    remote = ValkeyCache("rediss://falso", client=fake, **kwargs)
    return LayeredCache(DiskCache(tmp_path), remote), fake


def test_disk_cache_stats_and_file_layout(tmp_path):
    c = DiskCache(tmp_path)
    assert c.get("answers", {"a": 1}) is None
    c.put("answers", {"a": 1}, {"ok": True})
    assert c.get("answers", {"a": 1}) == {"ok": True}
    assert (tmp_path / "answers" / f"{c.key({'a': 1})}.json").exists()
    assert c.stats == {"local_hits": 1, "remote_hits": 0, "misses": 1}


def test_layered_local_hit_does_not_touch_remote(tmp_path):
    c, fake = layered(tmp_path)
    c.local.put("answers", "q", {"n": 1})
    assert c.get("answers", "q") == {"n": 1}
    assert fake.calls == 0
    assert c.stats == {"local_hits": 1, "remote_hits": 0, "misses": 0}


def test_layered_remote_hit_fills_local(tmp_path):
    c, fake = layered(tmp_path)
    c.remote.put("answers", "q", {"n": 2})
    assert c.local.get("answers", "q") is None
    assert c.get("answers", "q") == {"n": 2}
    assert c.local.get("answers", "q") == {"n": 2}
    calls = fake.calls
    assert c.get("answers", "q") == {"n": 2}  # ahora sale del disco
    assert fake.calls == calls
    assert c.stats == {"local_hits": 1, "remote_hits": 1, "misses": 0}


def test_layered_miss(tmp_path):
    c, _ = layered(tmp_path)
    assert c.get("answers", "nada") is None
    assert c.stats == {"local_hits": 0, "remote_hits": 0, "misses": 1}


def test_layered_put_writes_both_with_prefix_and_ttl(tmp_path):
    c, fake = layered(tmp_path, ttl_s=100)
    c.put("cala", "q", {"n": 3})
    c.put("intents", "q", {"attribute": "funding"})
    digest = c.key("q")
    assert c.local.get("cala", "q") == {"n": 3}
    assert json.loads(fake.data[f"cala:v1:cala:{digest}"]) == {"n": 3}
    assert fake.ttl[f"cala:v1:cala:{digest}"] == 100
    assert fake.ttl[f"cala:v1:intents:{digest}"] is None  # las intenciones del LLM no caducan


def test_remote_errors_degrade_to_disk_and_pause_retries(tmp_path):
    clock = Clock()
    c, fake = layered(tmp_path, clock=clock, retry_after_s=60)
    fake.fail = True
    assert c.get("answers", "q") is None  # no lanza
    assert fake.calls == 1
    c.put("answers", "q", {"n": 4})  # se guarda en disco; no reintenta el remoto
    assert c.get("answers", "otra") is None
    assert fake.calls == 1 and fake.data == {}
    assert c.get("answers", "q") == {"n": 4}
    assert c.remote.errors == 1 and not c.remote.available
    clock.now, fake.fail = 61, False  # pasada la pausa vuelve a usar el remoto
    c.put("answers", "q2", {"n": 5})
    assert len(fake.data) == 1 and c.remote.available


def test_valkey_bad_url_or_garbage_never_raises():
    bad = ValkeyCache("esto-no-es-una-url")
    assert bad.get("answers", "q") is None
    assert bad.put("answers", "q", {"n": 1}) is False
    fake = FakeRedis()
    remote = ValkeyCache("rediss://falso", client=fake)
    fake.data[f"cala:v1:answers:{remote.key('q')}"] = "{no es json"
    assert remote.get("answers", "q") is None


def test_valkey_reuses_one_client_and_passes_configured_timeouts(monkeypatch):
    import redis
    fake = FakeRedis()
    created = []
    def from_url(url, **kwargs):
        created.append((url, kwargs))
        return fake
    monkeypatch.setattr(redis.Redis, "from_url", from_url)
    monkeypatch.setattr(cache_mod, "load_env", lambda *a, **k: None)
    monkeypatch.setattr(cache_mod, "_REMOTES", {})
    monkeypatch.setenv("VALKEY_URL", "rediss://fake")
    monkeypatch.setenv("VALKEY_CONNECT_TIMEOUT", "8")
    monkeypatch.setenv("VALKEY_TIMEOUT", "3")
    remote = cache_mod.remote_from_env()
    remote.get("n", "one")
    remote.put("n", "two", {"ok": True})
    assert len(created) == 1
    assert created[0][1]["socket_connect_timeout"] == 8
    assert created[0][1]["socket_timeout"] == 3


def test_warmup_swallows_connection_failure(monkeypatch):
    class Failing:
        def ping(self): raise ConnectionError("offline")
    monkeypatch.setattr(cache_mod, "remote_from_env", lambda: Failing())
    assert cache_mod.warmup() is False


def test_warmup_without_url_does_not_connect(monkeypatch):
    monkeypatch.setattr(cache_mod, "load_env", lambda *a, **k: None)
    monkeypatch.setattr(cache_mod, "_REMOTES", {})
    monkeypatch.setenv("VALKEY_URL", "")
    assert cache_mod.warmup() is False
    assert cache_mod._REMOTES == {}


def test_make_cache_without_valkey_url_is_disk(tmp_path, monkeypatch):
    monkeypatch.delenv("VALKEY_URL", raising=False)
    monkeypatch.setattr(cache_mod, "load_env", lambda *a, **k: None)
    assert isinstance(make_cache(tmp_path), DiskCache)
    monkeypatch.setenv("VALKEY_URL", "")
    assert isinstance(make_cache(tmp_path), DiskCache)


def test_make_cache_with_valkey_url_is_layered(tmp_path, monkeypatch):
    monkeypatch.setattr(cache_mod, "_REMOTES", {})
    monkeypatch.setenv("VALKEY_URL", "rediss://default:secreto@valkey.invalid:12345")
    monkeypatch.delenv("CACHE_TTL_S", raising=False)
    c = make_cache(tmp_path)
    assert isinstance(c, LayeredCache) and isinstance(c.local, DiskCache) and isinstance(c.remote, ValkeyCache)
    assert c.remote.ttl_s == 7 * 24 * 3600 and c.remote.prefix == "cala:v1"
    assert make_cache(tmp_path / "otra").remote is c.remote  # una conexión por proceso
    monkeypatch.setenv("CACHE_TTL_S", "30")
    assert make_cache(tmp_path).remote.ttl_s == 30
    monkeypatch.setenv("CACHE_TTL_S", "0")
    assert make_cache(tmp_path).remote.ttl_s is None


def test_load_env_reads_only_known_keys_and_respects_environment(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('CALA_API_KEY="k"\nVALKEY_URL=rediss://x\nCACHE_TTL_S=60\nOTRA_CLAVE=no\n# VALKEY_URL=comentada\n')
    for name in ("CALA_API_KEY", "VALKEY_URL", "CACHE_TTL_S", "OTRA_CLAVE"): monkeypatch.delenv(name, raising=False)
    load_env(env)
    import os
    assert (os.environ["CALA_API_KEY"], os.environ["VALKEY_URL"], os.environ["CACHE_TTL_S"]) == ("k", "rediss://x", "60")
    assert "OTRA_CLAVE" not in os.environ
    monkeypatch.setenv("VALKEY_URL", "")  # vacía = desactivada a propósito
    load_env(env)
    assert os.environ["VALKEY_URL"] == ""


@pytest.mark.asyncio
async def test_cala_client_raw_cache_is_shared_through_remote(tmp_path):
    from canonizador.client import CalaClient

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self): return {"results": [1]}

    class Http:
        calls = 0
        async def request(self, method, url, **kwargs):
            self.calls += 1
            return Response()

    fake = FakeRedis()
    http = Http()
    one = CalaClient(api_key="test", client=http,
                     cache=LayeredCache(DiskCache(tmp_path / "a"), ValkeyCache("rediss://falso", client=fake)))
    assert await one.knowledge_query("q") == {"results": [1]}
    assert http.calls == 1 and len(fake.data) == 1
    assert len(list((tmp_path / "a" / "cala").glob("*.json"))) == 1  # mismo formato en disco que antes
    # "Otra máquina": disco vacío, mismo Valkey → no llama a Cala.
    other = CalaClient(api_key="test", client=http,
                       cache=LayeredCache(DiskCache(tmp_path / "b"), ValkeyCache("rediss://falso", client=fake)))
    assert await other.knowledge_query("q") == {"results": [1]}
    assert http.calls == 1 and other.calls == 0
    assert other.cache.stats["remote_hits"] == 1


def test_cache_sync_uploads_by_namespace(tmp_path, capsys):
    disk = DiskCache(tmp_path)
    disk.put("cala", "a", {"n": 1})
    disk.put("cala", "b", {"n": 2})
    disk.put("intents", "c", {"n": 3})
    (tmp_path / "cala" / "rota.json").write_text("{")  # se ignora
    fake = FakeRedis()
    remote = ValkeyCache("rediss://falso", client=fake, ttl_s=100)
    assert cache_sync.main([str(tmp_path)], remote=remote) == 0
    out = capsys.readouterr().out
    assert "cala: 2" in out and "intents: 1" in out and "Total: 3" in out
    assert remote.get("cala", "a") == {"n": 1} and len(fake.data) == 3


def test_cache_sync_without_valkey_url_exits_with_message(tmp_path, capsys):
    assert cache_sync.main([str(tmp_path)]) == 1  # conftest deja VALKEY_URL vacía
    assert "VALKEY_URL" in capsys.readouterr().out


def test_cache_sync_reports_remote_down(tmp_path, capsys):
    DiskCache(tmp_path).put("cala", "a", {"n": 1})
    fake = FakeRedis()
    fake.fail = True
    assert cache_sync.main([str(tmp_path)], remote=ValkeyCache("rediss://falso", client=fake)) == 1
    assert "upload is incomplete" in capsys.readouterr().out
