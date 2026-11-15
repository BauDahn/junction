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
- `Message`: `{id, role: user|assistant, text, transcript?: string, created_at, blocks?: [Block], sources?: [Source], cards?: [Card]}`. En mensajes de usuario enviados por audio, `text` es la intención limpia (autocorrecciones aplicadas, sin muletillas) y `transcript` es lo dicho literalmente; en mensajes de texto, `transcript` es null. `text` en las respuestas pasa a ser una línea de contexto; el contenido está en `blocks`. `cards` se mantiene por compatibilidad con las recomendaciones.
- `Card`: `{type: investor|company|competitor|prospect|claim, title, subtitle?, reason, sources: [Source]}`

## Feed y detalle *(borrador, nuevo 14/11 noche)*
Cala Match. Detalle de cómo se calcula el puntaje en `docs/SPEC-grafo-afinidad.md`.
- `GET /api/feed?session_id=&mode=raising|investing&limit=20&cursor=` → `{mode, items: [FeedCard], next_cursor?, confidence_note?}`. `raising` devuelve inversores; `investing`, startups. Ordenado por `score` descendente y, a igual puntaje, por `confidence`. `session_id` es obligatorio (de qué sesión es el perfil; 404 si no existe). Sin `mode` se usa el guardado de la sesión (por defecto `raising`); un modo inválido da 422. `limit` de 1 a 100. `cursor` es el `next_cursor` de la página anterior (opaco). `confidence_note` (texto en inglés) avisa si el catálogo sigue cargando o si falta perfil; las claves opcionales se omiten, no van en `null`.
- `FeedCard`: `{id, type: investor|startup, name, one_liner, tags: [string], score: 0-100, confidence: 0-1, why_match: [string], sources: [Source]}`. Con `confidence < 0.5` la app muestra "partial data".
- `GET /api/entities/{id}?mode=&session_id=` → `EntityDetail`: `{id, type, name, description?, score?, confidence?, why_match: [{signal, text, sources: [Source]}], facts: [{label, value, sources: [Source]}], rounds: [{round_type, amount?, date?, leads: [string], investors: [string], sources: [Source]}], portfolio: [{id, name}], people: [{id, name, role, since?}], loaded_at}`. `session_id` es opcional: con él vienen `score`, `confidence` y `why_match` (el mismo puntaje que en el feed); sin él, `why_match` va vacío. `amount` y `date` son texto tal cual lo da Cala. `signal` es uno de `sector|stage|region|ticket|activity|closeness`.
- `GET /api/search?q=<texto>&limit=8` (q de 2 a 80 caracteres) → `{query, items: [{id, name, type: investor|startup|other, origin: catalog|cala, one_liner?}], tried: [catalog|cala]}`. `type` es `investor|startup` para `catalog`; los resultados `cala` usan `other` (sin clasificar, se clasifica al abrir el detalle). Busca nombres localmente y completa con Cala si faltan resultados; los ids abren el detalle.
- Si `GET /api/entities/{id}` no encuentra la entidad en catálogo ni grafo local, intenta cargarla de Cala en vivo con un retrieve y la guarda en el grafo con TTL. Si Cala no la conoce devuelve 404 `Entity not found in the graph or in Cala.`; si supera 25 segundos devuelve 504 `Cala did not answer in time.`. Las consultas posteriores usan el grafo local.
- `POST /api/sessions/{id}/mode` con `{mode}` → `{mode}`: guarda el modo activo de la sesión.
- Todo dato viaja con `sources`; si no hay fuente, el campo no se devuelve.
- Las etiquetas de sector y etapa generadas por Gemini a partir de la descripción de Cala llevan el sufijo ` (AI-tagged)` en `tags`, en `why_match` y en la etiqueta del `fact`.
- `GET /api/stats` → `{catalog: {investors, startups, total, status}, cala?}`: tamaño y progreso del catálogo y, si el cliente de Cala las expone, sus métricas.

## Perfil y recomendaciones *(borrador)*
- `GET /api/sessions/{id}/profile` → `{startup_name?, one_liner?, sector?, stage?, location?, raising?: {amount?, round?}, competitors: [string], target_customers?, role?: founder|investor|other, interests?: {sectors: [string], regions: [string], stages: [string], follows: {companies: [string], investors: [string]}}, facts: [{text, origin: user}], updated_at}`
- `GET /api/sessions/{id}/recommendations` → `{status: idle|running|ready|error, updated_at, investors: [Card], competitors: [Card], prospects: [Card]}`

## Journal diario *(borrador, nuevo 14/11)*
Dos ediciones armadas solo con consultas a Cala. Se genera bajo demanda la primera vez del día y queda cacheado.
- `GET /api/journal/ecosistema?date=YYYY-MM-DD` → `Journal` (edición genérica, la misma para todos)
- `GET /api/sessions/{id}/journal?date=YYYY-MM-DD` → `Journal` (edición `founders`, según el perfil y los intereses de la sesión)
- `POST /api/journal/ecosistema/regenerate` y `POST /api/sessions/{id}/journal/regenerate` → `{status: generating}` (para la demo)
- `Journal`: `{edition: ecosistema|founders, date, status: generating|ready|error, generated_at?, progress?: {done, total}, sections: [Section], error?}`. Mientras `status` es `generating`, la app hace polling cada 2 s.
- `Section`: `{id, title, description, items: [JournalItem]}`
- `JournalItem`: `{id, is_new: bool, block: Block}`. `id` sirve para preguntar desde el journal (`context.journal_item_id` en el chat).

## Reglas
- Todo dato que venga de Cala viaja con `sources`, y la app siempre las muestra.
- El modelo nunca escribe cifras ni nombres que no vengan de Cala. Si Cala no tiene el dato después de probar todas sus herramientas, se devuelve `not_found` con lo que se buscó.
- Nada de claves en respuestas ni logs.
