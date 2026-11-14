# Backend

API en FastAPI con SQLite. Contrato con la app en [`docs/API.md`](../docs/API.md).

| Módulo | Qué hace |
|---|---|
| `app.py` | Punto de entrada: CORS, formato de errores del contrato, `/api/health` y las rutas del chat y del feed |
| `chat/` | Sesiones, mensajes de texto y audio (`transcribe.py`: Gemini con respaldo de Whisper local), perfil de la startup (`profile.py`), recomendaciones en segundo plano (`recommend.py`), persistencia (`store.py`, SQLite en `data/chat.db`) |
| `cala_core/` | Router de mensajes, ejecución de consultas a Cala con canonizador y respaldos, formato de bloques y comprobación de afirmaciones del usuario |
| `api/` | Feed, detalle de una entidad y puntaje de afinidad para Cala Match (`docs/SPEC-grafo-afinidad.md`) |
| `graph/` | Grafo compartido sobre Cala: nodos y aristas con fuente, unión de duplicados, lectura por lotes en Valkey |
| `catalog/` | Ingesta reanudable del catálogo de Slush 2026 al grafo, con etiquetas de Gemini y respaldo a archivo (`python -m catalog run`) |
| `core/` | Módulos compartidos: proveedores de LLM (`llm.py`), configuración (`config.py`), cliente de Cala (`cala.py`) y lectura de PDF (`pdf.py`) |

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
| `TRANSCRIPTION_PROVIDER`, `WHISPER_MODEL` | `whisper` (local, por defecto `small`), `nvidia` o `none` |
| `CHAT_DB_PATH` | Base SQLite del chat (por defecto `data/chat.db`) |
| `CORS_ORIGINS` | Orígenes permitidos (por defecto `*`, solo desarrollo) |

Las respuestas de Cala y del LLM se cachean en `cache/` (ignorada por git).


```bash
```

El trust score parte de 50 y suma 50 × `(confirmadas + 0,5 × parciales − contradichas) / afirmaciones puntuadas`, acotado a 0–100.
