# Contrato de la API (backend ↔ app)

Fuente de verdad entre las dos personas: la app (`app/`) y el backend (`backend/`) se programan contra este documento. **Cambiar algo que no esté marcado *(borrador)* requiere un PR propio que el otro apruebe antes de implementarlo.** El porqué de los bloques y del journal está en `docs/PLAN-CALA-CENTRO.md`.

Base: `http://localhost:8000` en desarrollo (en la app, `EXPO_PUBLIC_API_URL`). JSON UTF-8. Errores: HTTP 4xx/5xx con `{"error": {"code": "...", "message": "..."}}`. CORS abierto en desarrollo.

## Salud
- `GET /api/health` → `{provider, model, cala: bool, transcription: string}`

## Tipos comunes
- `Source`: `{name, url, date?, source_rank?: FILING|PRIMARY|PRESS|AGGREGATOR}`
- `CalaCall`: `{tool: knowledge_query|entity|knowledge_search, query: string}`. La consulta exacta enviada a Cala, para poder reproducirla.

## Bloques (lo que muestra la app) *(borrador, nuevo 14/11)*
Las respuestas del chat y las secciones del journal son listas de `Block`. Todos los bloques de datos son **datos de Cala tal cual**; el modelo solo agrega, como mucho, `summary` (una línea).

| `type` | Campos | Cuándo |
|---|---|---|
| `cala_table` | `title`, `summary?`, `call: CalaCall`, `columns: [string]`, `rows: [[string \| number \| null]]`, `sources: [Source]`, `row_sources?: [[int]]` (índices en `sources` por fila), `focus_rows?: [int]` (filas que responden la pregunta; la app muestra solo esas y "Ver todas"), `answer?: string` (si es una sola fila: sus celdas de Cala unidas con " · ") | Resultado de `knowledge_query` (filas) o de una entidad (campo · valor · fuente · fecha · tipo de fuente) |
| `cala_answer` | `title`, `call: CalaCall`, `markdown`, `sources: [Source]` | Resultado de `knowledge_search`: la respuesta de Cala tal cual |
| `claim_check` | `claim` (lo que dijo el usuario), `verdict: confirmed\|partially_confirmed\|contradicted\|no_data`, `explanation` (una línea), `evidence: cala_table \| cala_answer`, `sources: [Source]` | El usuario afirmó un dato y se contrastó con Cala |
| `profile_update` | `changes: {campo: valor}` | El usuario contó algo de su startup o de sus intereses |
| `not_found` | `title`, `tried: [CalaCall]`, `closest?: cala_table \| cala_answer` | Ninguna herramienta de Cala devolvió datos; se muestra qué se buscó |
| `text` | `text` | Respuestas sin datos (saludo, aclaración) |

## Chat con audio *(borrador)*
Una conversación por usuario. Manda texto o audio; el backend transcribe y el **router** (`backend/cala_core`) decide qué hacer con cada parte del mensaje: consultar Cala, verificar una afirmación o actualizar el perfil.
- `POST /api/sessions` → `{session_id}` (sin login en la demo; la app guarda el id localmente)
- `POST /api/sessions/{id}/messages`
  - texto: JSON `{text}`; opcional `context: {journal_item_id}` cuando se pregunta desde el journal
  - audio: multipart `audio` (m4a, webm, wav, mp3; ≤ 2 min)
  - → `{message: Message, reply: Message, profile_updated: bool, recommendations_status: idle|running|ready|error}`
- `GET /api/sessions/{id}/messages` → `{messages: [Message]}`
- `Message`: `{id, role: user|assistant, text, transcript?: string, created_at, blocks?: [Block], sources?: [Source], cards?: [Card]}`. `text` en las respuestas pasa a ser una línea de contexto; el contenido está en `blocks`. `cards` se mantiene por compatibilidad con las recomendaciones.
- `Card`: `{type: investor|company|competitor|prospect|claim, title, subtitle?, reason, sources: [Source]}`

## Perfil y recomendaciones *(borrador)*
- `GET /api/sessions/{id}/profile` → `{startup_name?, one_liner?, sector?, stage?, location?, raising?: {amount?, round?}, competitors: [string], target_customers?, role?: founder|investor|other, interests?: {sectors: [string], regions: [string], stages: [string], follows: {companies: [string], investors: [string]}}, facts: [{text, origin: user, verified?: Claim}], updated_at}`
- `GET /api/sessions/{id}/recommendations` → `{status: idle|running|ready|error, updated_at, investors: [Card], competitors: [Card], prospects: [Card]}`

## Journal diario *(borrador, nuevo 14/11)*
Dos ediciones armadas solo con consultas a Cala. Se genera bajo demanda la primera vez del día y queda cacheado.
- `GET /api/journal/ecosistema?date=YYYY-MM-DD` → `Journal` (edición genérica, la misma para todos)
- `GET /api/sessions/{id}/journal?date=YYYY-MM-DD` → `Journal` (edición `founders`, según el perfil y los intereses de la sesión)
- `POST /api/journal/ecosistema/regenerate` y `POST /api/sessions/{id}/journal/regenerate` → `{status: generating}` (para la demo)
- `Journal`: `{edition: ecosistema|founders, date, status: generating|ready|error, generated_at?, progress?: {done, total}, sections: [Section], error?}`. Mientras `status` es `generating`, la app hace polling cada 2 s.
- `Section`: `{id, title, description, items: [JournalItem]}`
- `JournalItem`: `{id, is_new: bool, block: Block}`. `id` sirve para preguntar desde el journal (`context.journal_item_id` en el chat).

## Verificador de decks (fuera del producto desde el 14/11)
La app no usa estos endpoints. Siguen en el backend, sin mantenimiento.
- `POST /api/verify` (multipart `file`: PDF ≤ 20 MB) → `{job_id}`
- `POST /api/verify-sample` → `{job_id}` (deck de ejemplo)
- `GET /api/jobs/{job_id}` → `{status: queued|extracting|checking|judging|done|error, progress: {done, total}, report?, error?}`
- `report`: `{startup_name, provider, model, claims: [Claim], summary: {confirmed, partially_confirmed, contradicted, no_data, not_checked}, trust_score: 0-100, timings, dropped_urls}`
- `Claim`: `{id, page, quote, category, publicly_verifiable, cala_question, verdict: confirmed|partially_confirmed|contradicted|no_data|not_checked|error, explanation, evidence, sources: [Source]}`

## Reglas
- Todo dato que venga de Cala viaja con `sources`, y la app siempre las muestra.
- El modelo nunca escribe cifras ni nombres que no vengan de Cala. Si Cala no tiene el dato después de probar todas sus herramientas, se devuelve `not_found` con lo que se buscó.
- Nada de claves en respuestas ni logs.
