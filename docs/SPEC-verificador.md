# Spec: Deck Verifier (demo)

Un founder o un inversor sube el PDF de un pitch deck. El sistema extrae las afirmaciones públicamente verificables (rondas, inversores, competidores, clientes, datos de mercado, trayectoria del equipo), las contrasta con Cala y devuelve un veredicto por afirmación **con las fuentes de Cala**. Usuario de la demo: un inversor de un fondo seed que revisa 30 decks antes de Slush. UI y respuestas en **inglés** (jurado internacional).

## Stack
- Todo dentro de `demo/`. Python 3.11+ con **uv** (`pyproject.toml`), FastAPI + uvicorn, httpx (async), pymupdf, python-dotenv. Sin frameworks de frontend: `demo/static/index.html` con JS y CSS vanilla, servido por FastAPI.
- Correr: `cd demo && uv run uvicorn app:app --port 8000`. CLI: `uv run python -m verifier <pdf>` imprime el reporte (sirve para probar sin UI).
- Claves en `demo/.env` (`CALA_API_KEY`, `NVIDIA_API_KEY`, `NVIDIA_MODEL`, `LLM_PROVIDER`). **Nunca imprimir, loguear ni devolver las claves.**

## Módulos (`demo/verifier/`)
1. **`config.py`**: carga `.env`. `LLM_PROVIDER` ∈ `nvidia | codex | claude`; por defecto `nvidia` si hay `NVIDIA_API_KEY`, si no `codex`.
2. **`cala.py`**: cliente async de `POST https://api.cala.ai/v1/knowledge/search` (header `X-API-KEY`, body `{"input": question}`). Latencia real ~16 s por llamada, así que:
   - semáforo de 6 llamadas concurrentes, timeout 120 s, reintentos con backoff en 429/5xx (3 intentos);
   - **caché en disco** `demo/cache/cala/<sha256(question)>.json`;
   - devuelve `{answer: str (markdown), sources: [{name, url}] (únicas, sacadas de context[].origins[].document, o .source si no hay document), facts: [{id, content (recortado a 600 chars)}], entities: [...]}`.
   Formato real de la respuesta: `content` (markdown), `explainability` [{content, references}], `context` [{id, content, origins: [{source: {name,url}, document: {name,url}}]}], `entities` [{id, name, entity_type, mentions}].
3. **`llm.py`**: interfaz `async complete_json(system: str, user: str, schema: dict, images: list[bytes] | None) -> dict`, con caché en disco `demo/cache/llm/` (clave = hash de proveedor + prompts + imágenes) y tres proveedores:
   - **NvidiaProvider**: API compatible con OpenAI en `https://integrate.api.nvidia.com/v1/chat/completions`, modelo `NVIDIA_MODEL` (por defecto `nvidia/nemotron-3.5-super-vl`; el ID exacto se confirma mañana), imágenes como `image_url` con data URL base64, pedir JSON y parsearlo de forma tolerante (extraer el primer objeto JSON). Reintentos con backoff (límite free ~40 req/min).
   - **CodexProvider** (temporal hasta tener la clave de NVIDIA): `codex exec --skip-git-repo-check --ephemeral -s read-only -m gpt-6-luna -c model_reasoning_effort="low" --output-schema <schema.json> -o <out.txt> [-i img.png ...] "<prompt>"`, en un directorio temporal, vía `asyncio.create_subprocess_exec`. Buscar el binario con `shutil.which("codex")` o en `~/.nvm/versions/node/*/bin/codex`. Timeout 180 s.
   - **ClaudeProvider** (alternativa): `claude -p --output-format json "<prompt>"`, parsear el campo `result`. Solo texto.
   El schema que se pasa a Codex tiene que cumplir el modo estricto: todos los objetos con `additionalProperties: false` y todas las propiedades en `required`.
4. **`pdf.py`**: texto por página con pymupdf y render PNG por página (máx. 15 páginas, ancho 1024 px). Si una página no tiene texto (deck escaneado), solo se puede analizar con un proveedor que acepte imágenes; avisarlo en el reporte.
5. **`pipeline.py`**:
   1. **Extraer afirmaciones** (1 llamada al LLM con el texto de todas las páginas; imágenes solo si el proveedor es `nvidia`): `{startup_name, claims: [{id, page, quote (cita literal del deck), category: funding|investor|competitor|customer|partner|market|team|traction|other, publicly_verifiable: bool, cala_question (pregunta en inglés, concreta, autocontenida, con nombres propios)}]}`. Máximo 12 afirmaciones, priorizando las verificables. Las métricas internas no públicas (MRR, churn) van como `publicly_verifiable: false` y no se consultan.
   2. **Consultar Cala** en paralelo para cada afirmación verificable.
   3. **Juzgar** (1 llamada al LLM con todas las afirmaciones y su evidencia de Cala): por afirmación `{id, verdict: confirmed|partially_confirmed|contradicted|no_data, explanation (1–2 frases), evidence (cita breve de la evidencia de Cala), source_urls: [..]}`. Regla dura: si Cala no trae evidencia relevante → `no_data`, nunca inventar.
   4. **Anti-alucinación en código**: descartar de `source_urls` cualquier URL que no esté en las `sources` que devolvió Cala para esa afirmación; si un veredicto `confirmed`/`contradicted` queda sin fuentes válidas, bajarlo a `no_data` y marcarlo. Contar cuántas URLs se descartaron (métrica para el reto de NVIDIA).
   5. **Reporte**: `{startup_name, provider, model, claims: [...afirmación + veredicto + fuentes...], summary: {confirmed, partially_confirmed, contradicted, no_data, not_checked}, trust_score (0–100: confirmadas pesan 1, parciales 0.5, contradichas restan; documentar la fórmula), timings: {extract_s, cala_s, judge_s, total_s}, dropped_urls}`.
   Errores: si falla Cala para una afirmación → `verdict: "error"` con el mensaje, sin tirar el resto. Si falla el LLM → error claro en el job.
6. **`app.py`** (en `demo/`): `GET /` sirve la UI; `POST /api/verify` (multipart, PDF ≤ 20 MB) crea un job en segundo plano y devuelve `{job_id}`; `GET /api/jobs/{id}` devuelve `{status: queued|extracting|checking|judging|done|error, progress: {checked, total}, report | error}`; `POST /api/verify-sample` corre el deck de ejemplo; `GET /api/health` devuelve `{provider, model, cala: bool}` (sin claves).

## UI (`demo/static/index.html`)
- Encabezado: "Deck Verifier · powered by Cala", subtítulo de una línea.
- Zona de arrastrar y soltar el PDF + botón "Try sample deck".
- Progreso por pasos (Extracting claims → Checking with Cala n/N → Judging), con polling cada 1,5 s.
- Resumen: trust score grande, contadores por veredicto, proveedor/modelo usado, tiempos.
- Una tarjeta por afirmación: cita del deck con número de página, badge (✔ Confirmed verde, ◐ Partially amber, ✖ Contradicted rojo, ? No data gris, — Not checked), explicación, evidencia y **links a las fuentes**. Filtro por veredicto.
- Sobria, legible, responsive, modo claro y oscuro.

## Deck de ejemplo
`demo/examples/make_sample_deck.py` genera `demo/examples/sample_deck.pdf` (6–8 páginas, con pymupdf) de una startup **ficticia** "Stayflow" (software para hoteles boutique, Barcelona). Afirmaciones mezcladas a propósito (todas sobre empresas reales, verificadas contra Cala el 14/11):
- Competidor Amenitiz levantó €39M en Serie B en noviembre de 2025, liderada por KFund → debería salir **confirmed**.
- "Mews, our main competitor, has raised less than $100M in total" → **contradicted** (Cala: ~$710M).
- Un inversor ficticio de Stayflow ("backed by Seedcamp and K Fund") → **no_data** o contradicted (Stayflow no existe).
- Una métrica interna (MRR €40k) → not checked.
- 1–2 afirmaciones de mercado sobre la hotelería independiente en España.
El PDF tiene que decir en el pie "Fictional startup — demo deck".

## Hecho cuando
- `uv run python -m verifier examples/sample_deck.pdf` termina con `LLM_PROVIDER=codex` y muestra al menos un confirmed y un contradicted con fuentes de Cala.
- La UI corre en `:8000`, el botón del deck de ejemplo muestra el reporte completo.
- Tests mínimos (`uv run pytest`): validación de URLs anti-alucinación, cálculo del trust score, parseo tolerante de JSON, caché.
- `demo/README.md` con cómo correrlo y cómo cambiar de proveedor.
