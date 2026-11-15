# Canonizador de consultas Cala

Normalizes questions, converts their intent to JSON with Gemini when `GEMINI_API_KEY` is set (otherwise NVIDIA if `NVIDIA_API_KEY` is set, then `codex exec`; `LLM_PROVIDER` overrides this), resolves entities, and queries entity endpoints with a local cache in `cache/`.

Desde esta carpeta:

```sh
uv sync --extra dev
uv run python -m canonizador "¿Quién lideró la Serie B de Amenitiz?"
uv run python bench.py
uv run pytest
```

The CLI loads `CALA_API_KEY` from `../backend/.env` if it is not in the environment. Requests use a raw cache. `CalaClient` rate-limits knowledge/query and knowledge/search with `knowledge_interval` (8 s), and entities with `entities_interval` (0.7 s); these can also be configured with `CALA_KNOWLEDGE_INTERVAL` and `CALA_ENTITIES_INTERVAL`. Entities allow up to 2 simultaneous requests (`entities_concurrency` / `CALA_ENTITIES_CONCURRENCY`). `CALA_429_WAIT` sets the base exponential backoff in seconds (5 by default); `Retry-After` is honored, up to a maximum of 60 s. Example: “¿Quién lideró la Serie B de Amenitiz?” (“Who led Amenitiz's Series B?”).

## Shared cache (Aiven Valkey)

Cala queries take 16–60 s. By default, they are cached only on disk (`cache/`, per machine). When `VALKEY_URL` is set, the cache has two layers: disk → Valkey. A query made by one machine is instantly available to the other.

Activarla:

1. In the [Aiven console](https://console.aiven.io): *Create service* → **Valkey** → choose a plan and region → wait until it is *Running*.
2. Copy the **Service URI** (`rediss://default:<password>@<host>:<port>`, with TLS) to `backend/.env`:
   ```sh
   VALKEY_URL=rediss://default:<password>@<host>:<port>
   # CACHE_TTL_S=604800   # optional: expiration in seconds (7 days by default; 0 = no expiration)
   # VALKEY_CONNECT_TIMEOUT=8  # initial connection (seconds)
   # VALKEY_TIMEOUT=3          # read/write (seconds)
   ```
   This is a secret: keep it only in `backend/.env`, like `CALA_API_KEY`.
3. Upload what is already on disk (to warm the demo cache): `uv run python -m canonizador.cache_sync` (prints how many entries it uploaded per namespace; accepts cache directories as arguments; defaults to `canonizador/cache` and `backend/cache`).

How it works (`canonizador/cache.py`):

- `make_cache(root)` returns `LayeredCache(DiskCache, ValkeyCache)` when `VALKEY_URL` is set, and `DiskCache` otherwise. It is used by `answer()` and `CalaClient` (raw responses, `cala` namespace).
- Reads: disk → Valkey (values from Valkey are copied to disk). Writes: both.
- Keys: `cala:v1:<namespace>:<sha256>`. Cala responses expire after `CACHE_TTL_S` seconds; LLM intents (`intents`) never expire.
- Valkey is truly optional: configurable connection timeout (`VALKEY_CONNECT_TIMEOUT`, 8 s) and read/write timeout (`VALKEY_TIMEOUT`, 3 s). If it fails, the system continues with disk only and does not retry for 60 s. The backend attempts to warm the connection in the background at startup.
- Savings for the demo: `cache.stats` (or `canonizador.cache.STATS`, accumulated per process) has `local_hits`, `remote_hits` and `misses`.
- With Valkey, `CALA_SHARED_LIMIT` (enabled by default; `0` disables it) applies a shared quota by endpoint class: knowledge every 8 s and entities according to their interval.
- The counter uses atomic `INCR` + `PEXPIRE` per window sized to the interval, with a quota of one request per window, and the cache's Valkey connection; processes wait for the next window when the quota is exhausted. An interval of 0 or less disables the shared limit for that endpoint.
- If Valkey fails, the local limit remains in effect and shared attempts are skipped for 30 s.
- The remote cache is disabled in tests (`VALKEY_URL=""` in `tests/conftest.py`).
