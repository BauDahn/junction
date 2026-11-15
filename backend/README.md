# Backend

API en FastAPI con SQLite. Contrato con la app en [`docs/API.md`](../docs/API.md).

| Módulo | Qué hace |
|---|---|
| `app.py` | Punto de entrada: CORS, formato de errores del contrato, `/api/health` y las rutas del chat y del feed |
| `accounts/` | Registro e inicio de sesión por correo con scrypt, rol fijo `raiser` o `investor` y tokens Bearer con TTL de 30 días; persistencia compartida en Valkey (`acct:v1:*`) con respaldo a PostgreSQL o SQLite |
| `chat/` | Sesiones, mensajes de texto y audio (`transcribe.py`: Gemini con respaldo de Whisper local), perfil de la startup (`profile.py`), recomendaciones en segundo plano (`recommend.py`), persistencia (`store.py`, SQLite en `data/chat.db`) |
| `context/` | Contexto en texto crudo (`GET/PUT/POST /api/me/context/raw*`), ingestión de PDF de pitch deck y notas de voz, y edición de `what_we_understood` |
| `cala_core/` | Router de mensajes, ejecución de consultas a Cala con canonizador y comprobación de afirmaciones. **`execute` nunca lanza:** canonizador, luego búsqueda de entidad, luego `knowledge_search` y, si todo falla, `not_found` con lo intentado |
| `api/` | Feed, detalle, búsqueda (`GET /api/search`), puntaje de afinidad (`docs/SPEC-grafo-afinidad.md`), informe de favoritos (`POST /api/favorites/report`, `favorites_report.py`), `investor_pool.py` y `enrich.py`. **Respaldo en vivo:** una entidad fuera del catálogo y del grafo se trae de Cala (un retrieve), se guarda con TTL y la segunda vez no llama a Cala |
| `graph/` | Grafo compartido sobre Cala: nodos y aristas con fuente, unión de duplicados, lectura por lotes en Valkey |
| `catalog/` | Ingesta reanudable del catálogo de Slush 2026 al grafo, con etiquetas de Gemini y respaldo a archivo (`python -m catalog run`) |
| `core/` | Módulos compartidos: proveedores de LLM (`llm.py`), configuración (`config.py`), cliente de Cala (`cala.py`), lectura de PDF (`pdf.py`) y protección antiabuso (`abuse.py`: límites por cliente/IP/cuenta, validación de UUID, caché negativa de 1 h y topes diarios) |

## Correr

```bash
uv sync
uv run uvicorn app:app --port 8000
uv run pytest
```

## Configuración (`.env`, plantilla en `.env.example`)

| Variable | Para qué |
|---|---|
| `CALA_API_KEY` | Clave de Cala (obligatoria) |
| `LLM_PROVIDER` | `gemini` (por defecto si hay clave Gemini), `nvidia` (si hay clave NVIDIA), `codex` o `claude` |
| `GEMINI_API_KEY`, `GOOGLE_API_KEY` | Clave para Gemini (se acepta cualquiera de los dos nombres) |
| `GEMINI_MODEL`, `GEMINI_FAST_MODEL` | Modelos Gemini fuerte (`gemini-flash-latest`) y rápido (`gemini-3.5-flash-lite`) |
| `NVIDIA_API_KEY`, `NVIDIA_BASE_URL`, `NVIDIA_MODEL` | Nemotron. build.nvidia.com: `https://integrate.api.nvidia.com/v1` con `nvidia/nemotron-3.5-super-vl-120b-a12b` y una clave `nvapi-` |
| `TRANSCRIPTION_PROVIDER`, `WHISPER_MODEL` | `gemini` (por defecto si hay clave Gemini), `whisper` (local, `uv sync --extra audio`, modelo por defecto `small`), `nvidia` o `none` |
| `CHAT_DB_PATH` | Base SQLite del chat (por defecto `data/chat.db`) |
| `ACCOUNTS_STORE` | `valkey`, `postgres` o `sqlite`; por defecto usa `VALKEY_URL` si está configurada y, si no, `DATABASE_URL` o SQLite (`data/app.db`). Valkey comparte cuentas y tokens entre máquinas; si no está disponible, la API devuelve `503`. |
| `DATABASE_URL` | PostgreSQL para cuentas (en la demo pública, Aiven for PostgreSQL) cuando `ACCOUNTS_STORE=postgres` |
| `TRUST_PROXY` | `1` para tomar la IP del cliente de `X-Forwarded-For` (detrás del túnel) |
| `VALKEY_URL` | Valkey compartido para cuentas cuando `ACCOUNTS_STORE` no fuerza otro backend |
| `CALA_REQUIRE_AUTH` | Exige Bearer para chat y respaldo en vivo a Cala (`0` por defecto) |
| `CALA_DAILY_CALL_CAP` | Tope diario de llamadas a Cala |
| `ADMIN_TOKEN` | Token para consultar las métricas administrativas de `/api/stats` |
| `CORS_ORIGINS` | Orígenes permitidos (por defecto `*`, solo desarrollo) |

Las respuestas de Cala y del LLM se cachean en `cache/` (ignorada por git).
