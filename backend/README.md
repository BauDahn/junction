# Backend

FastAPI API with SQLite. App contract in [`docs/API.md`](../docs/API.md).

| Module | What it does |
|---|---|
| `app.py` | Entry point: CORS, contract error format, `/api/health`, and chat and feed routes |
| `accounts/` | Email registration and login with scrypt, fixed `raiser` or `investor` role, and Bearer tokens with a 30-day TTL; shared persistence in Valkey (`acct:v1:*`) with PostgreSQL or SQLite fallback |
| `chat/` | Sessions, text and audio messages (`transcribe.py`: Gemini with local Whisper fallback), startup profile (`profile.py`), background recommendations (`recommend.py`), persistence (`store.py`, SQLite in `data/chat.db`) |
| `context/` | Raw text context (`GET/PUT/POST /api/me/context/raw*`), pitch deck PDF and voice note ingestion, and editing of `what_we_understood` |
| `cala_core/` | Message router, Cala query execution through the canonicalizer, and claim checking. **`execute` never throws:** canonicalizer, then entity search, then `knowledge_search`, and if all fail, `not_found` with what was attempted |
| `api/` | Feed, detail, search (`GET /api/search`), affinity score (`docs/SPEC-GRAPH-AFFINITY.md`), favorites report (`POST /api/favorites/report`, `favorites_report.py`), `investor_pool.py`, and `enrich.py`. **Live fallback:** an entity outside the catalog and graph is fetched from Cala (one retrieve), saved with a TTL, and the second time it does not call Cala |
| `graph/` | Shared graph over Cala: nodes and edges with sources, duplicate merging, batch reads in Valkey |
| `catalog/` | Resumable ingestion of the Slush 2026 catalog into the graph, with Gemini tags and file fallback (`python -m catalog run`) |
| `core/` | Shared modules: LLM providers (`llm.py`), configuration (`config.py`), Cala client (`cala.py`), PDF reading (`pdf.py`), and abuse protection (`abuse.py`: per-client/IP/account limits, UUID validation, 1-hour negative cache, and daily caps) |

## Correr

```bash
uv sync
uv run uvicorn app:app --port 8000
uv run pytest
```

## Configuration (`.env`, template in `.env.example`)

| Variable | Purpose |
|---|---|
| `CALA_API_KEY` | Cala key (required) |
| `LLM_PROVIDER` | `gemini` (default if a Gemini key is present), `nvidia` (if an NVIDIA key is present), `codex`, or `claude` |
| `GEMINI_API_KEY`, `GOOGLE_API_KEY` | Gemini key (either name is accepted) |
| `GEMINI_MODEL`, `GEMINI_FAST_MODEL` | Strong (`gemini-flash-latest`) and fast (`gemini-3.5-flash-lite`) Gemini models |
| `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL` | Nemotron. build.nvidia.com: `https://integrate.api.nvidia.com/v1` with `nvidia/nemotron-3.5-super-vl-120b-a12b` and an `nvapi-` key |
| `TRANSCRIPTION_PROVIDER`, `WHISPER_MODEL` | `gemini` (default if a Gemini key is present), `whisper` (local, `uv sync --extra audio`, default model `small`), `nvidia`, or `none` |
| `CHAT_DB_PATH` | Chat SQLite database (default `data/chat.db`) |
| `ACCOUNTS_STORE` | `valkey`, `postgres`, or `sqlite`; by default uses `VALKEY_URL` if configured, otherwise `DATABASE_URL` or SQLite (`data/app.db`). Valkey shares accounts and tokens across machines; if unavailable, the API returns `503`. |
| `DATABASE_URL` | PostgreSQL for accounts (Aiven for PostgreSQL in the public demo) when `ACCOUNTS_STORE=postgres` |
| `TRUST_PROXY` | `1` to use the client IP from `X-Forwarded-For` (behind the tunnel) |
| `VALKEY_URL` | Shared Valkey for accounts when `ACCOUNTS_STORE` does not force another backend |
| `CALA_REQUIRE_AUTH` | Requires Bearer for chat and live fallback to Cala (`0` by default) |
| `CALA_DAILY_CALL_CAP` | Daily cap on Cala calls |
| `ADMIN_TOKEN` | Token for querying administrative metrics at `/api/stats` |
| `CORS_ORIGINS` | Allowed origins (default `*`, development only) |

Cala and LLM responses are cached in `cache/` (ignored by git).
