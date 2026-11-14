# Backend

API en FastAPI con SQLite. Contrato con la app en [`docs/API.md`](../docs/API.md).

| Módulo | Qué hace | Dueño |
|---|---|---|
| `app.py` | Punto de entrada: CORS, formato de errores del contrato, `/api/health`, rutas del verificador y del chat | fabricio |
| `chat/` | Sesiones, mensajes de texto y audio (`transcribe.py`, Whisper local), perfil de la startup (`profile.py`), recomendaciones en segundo plano (`recommend.py`), persistencia (`store.py`, SQLite en `data/chat.db`) | fabricio |
| `cala_core/` | Router de mensajes, ejecución de consultas a Cala con canonizador y respaldos, formato de bloques, verificación de afirmaciones del usuario (en curso, ver `docs/PLAN-CALA-CENTRO.md`) | bau |
| `journal/` | Journal diario (ediciones ecosistema y founders) a partir de consultas a Cala (en curso) | bau |
| `verifier/` | Módulos compartidos del chat: proveedores de LLM (`llm.py`), configuración y cliente de Cala. El verificador de decks que vive ahí quedó **fuera del producto** (14/11) | bau |
| `api/` *(nuevo)* | Feed, detalle de una entidad y puntaje de afinidad para Cala Match | fabricio |
| `graph/` *(nuevo)* | Subgrafo local sobre Cala: nodos y aristas con fuente, BFS, caché en Valkey | bau (diseño) |
| `context/` *(nuevo)* | Ingesta de contexto: PDF y notas de voz, extracción con Gemini, actualización del perfil | gabriel |

## Correr

```bash
uv sync
uv run uvicorn app:app --port 8000     # UI de prueba del verificador en http://localhost:8000
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

## Verificador de decks por línea de comandos

```bash
uv run python examples/make_sample_deck.py                       # genera el deck de ejemplo
LLM_PROVIDER=codex uv run python -m verifier examples/sample_deck.pdf
```

El trust score parte de 50 y suma 50 × `(confirmadas + 0,5 × parciales − contradichas) / afirmaciones puntuadas`, acotado a 0–100.
