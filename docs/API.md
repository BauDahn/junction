# Contrato de la API (backend ↔ app)

Fuente de verdad entre las dos personas: la app (`app/`) y el backend (`backend/`) se programan contra este documento. **Cambiar algo que no esté marcado *(borrador)* requiere un PR propio que el otro apruebe antes de implementarlo.** El porqué de los bloques está en `docs/PLAN-CALA-CENTRO.md`.

Base: `http://localhost:8000` en desarrollo (en la app, `EXPO_PUBLIC_API_URL`). JSON UTF-8. Errores: HTTP 4xx/5xx con `{"error": {"code": "...", "message": "..."}}`. CORS abierto en desarrollo.

## Salud
- `GET /api/health` → `{provider, model, cala: bool, transcription: string}`

## Tipos comunes
- `Source`: `{name, url, date?, source_rank?: FILING|PRIMARY|PRESS|AGGREGATOR}`
- `CalaCall`: `{tool: knowledge_query|entity|knowledge_search, query: string}`. La consulta exacta enviada a Cala, para poder reproducirla.

## Bloques (lo que muestra la app) *(borrador, nuevo 14/11)*
Las respuestas del chat son listas de `Block`. Todos los bloques de datos son **datos de Cala tal cual**; el modelo solo agrega, como mucho, `summary` (una línea).

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
  - texto: JSON `{text}`
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
- `GET /api/stats` → `{catalog: {investors, startups, total, status}, cala?, cala_usage: {date, total, by_class, by_who}}`: tamaño y progreso del catálogo, métricas del cliente y contadores de llamadas reales a Cala del día UTC. `by_class` separa `entities` y `knowledge`; `by_who` agrupa por `CALA_CLIENT_LABEL` o etiqueta local. Si Valkey no está disponible, `cala_usage` es `{}`.

## Contexto *(borrador, nuevo 14/11 noche)*
Ingesta de contexto del usuario (deck PDF, nota de voz o texto libre) hacia el perfil de la sesión y edición manual de lo entendido.
- `GET /api/sessions/{id}/context` → `ContextPayload`: `{session_id, profile, what_we_understood, sources: [ContextSource], context_strength, source?}`.
- `POST /api/sessions/{id}/context/pdf` (multipart `file`: PDF ≤ 20 MB, hasta 15 páginas) → `ContextPayload` (incluye `source` con `kind: "pdf"`, `pages`).
- `POST /api/sessions/{id}/context/voice` (multipart `audio` o `file`: `m4a|webm|wav|mp3|ogg`, ≤ 10 MB, ≤ 2 min) → `ContextPayload` (incluye `source` con `kind: "voice"`, `duration_s`, `transcript` literal; la extracción al perfil usa `text` limpio cuando el transcriptor lo devuelve).
- `POST /api/sessions/{id}/context/note` (JSON `{text, title?}`, `text` no vacío ≤ 8000 caracteres) → `ContextPayload` (incluye `source` con `kind: "note"`).
- `PATCH /api/sessions/{id}/context/understood` (JSON parcial con claves de `what_we_understood`, cada una `[string]`) → `ContextPayload`: actualiza `what_we_understood`, `seeking`, `sector`/`stage`/`location`, `ticket`/`raising.amount`/`ticket_range` (al enviar `target_round_size`) e `interests.{sectors, stages, regions}` conservando `interests.follows` (`companies`, `investors`) preexistente.
- `DELETE /api/sessions/{id}/context/sources/{source_id}` → `ContextPayload`: elimina esa fuente de `sources` (`profile.context_sources`).
- `what_we_understood`: `{sector_focus: [string], target_stage: [string], target_round_size: [string], geography: [string], seeking: [string]}`.
- `sources` (`ContextSource`): `{id, kind: pdf|voice|note, title, subtitle, status: "ready", created_at, pages?, duration_s?, transcript?}`.
- `context_strength`: `{score: 0-100, signals_added: int, signals_total: 6, label: "Needs Context"|"Calibrating"|"Good Calibration"|"High Signal"}`.
- En `profile`: además de `ticket` (string para mostrar), se guarda `ticket_range?: {min: number, max: number, currency: "EUR"|"USD"|"GBP"|null}` en unidades base numéricas.
- Códigos HTTP: `400` (PDF vacío, JSON o campos inválidos, nota vacía), `404` (sesión o `source_id` inexistente), `413` (PDF > 20 MB, audio > 10 MB o > 2 min, nota > 8000 caracteres), `415` (formato PDF o audio no admitido), `422` (PDF ilegible o audio vacío/ininteligible), `502` (fallo de extracción LLM o transcripción), `503` (transcripción no configurada).


## Cuentas *(borrador, 15/11)*
Registro real con correo. El rol se elige al registrarse y **no se puede cambiar**.
- `POST /api/auth/register` con `{email, password, name, company, role: raiser|investor}` → `201 {token, user}`. Contraseña de 8 caracteres o más. `409 email_taken` si el correo ya existe; `422` si falta algo o el correo no es válido.
- `POST /api/auth/login` con `{email, password}` → `{token, user}`; `401 invalid_credentials`.
- `POST /api/auth/logout` → `204`.
- `GET /api/me` → `User`.
- `User`: `{id, email, name, company, role: raiser|investor, session_id, created_at}`. `session_id` es la sesión de chat, contexto y feed de ese usuario: la app la usa en lugar de crear una sesión anónima.
- Autenticación: cabecera `Authorization: Bearer <token>` en `/api/me/*` y `/api/auth/logout`; sin token o con uno vencido, `401`.
- **Rol fijo:** ningún endpoint lo cambia. `POST /api/sessions/{id}/mode` con un modo distinto del rol del usuario dueño de la sesión responde `409 role_locked`.
- Almacenamiento: tabla de usuarios en `DATABASE_URL` (Aiven for PostgreSQL) o, si no está definida, en SQLite (`backend/data/app.db`). Contraseñas con scrypt; tokens aleatorios guardados como hash, con 30 días de vida. No se envían correos (sin verificación por ahora).

## Contexto en texto *(borrador, 15/11)*
El perfil muestra el contexto como **el texto del usuario, tal cual**, no como etiquetas. Las etiquetas siguen existiendo por debajo para el motor de recomendación.
- `GET /api/me/context/raw` → `{text, updated_at}`.
- `PUT /api/me/context/raw` con `{text}` → `{text, updated_at, profile_updated: bool}`. Guarda el texto sin tocarlo y vuelve a extraer el perfil (sector, etapa, región, ticket) con Gemini.
- `POST /api/me/context/raw/append` con `{text}` → lo mismo, agregando el texto al final (una línea nueva). Lo usan la nota de voz confirmada y el asistente cuando el usuario cuenta algo de sí mismo.
- Los tres endpoints requieren `Authorization: Bearer <token>`; el límite es 8.000 caracteres y se responde 422 al superarlo.
- Un PDF subido por `POST /api/sessions/{id}/context/pdf` agrega una línea propia al texto (`From <archivo>: <resumen de una línea>`).
- Las notas de texto y voz guardadas desde `backend/context` también agregan su texto al contexto crudo.

## Voz con vista previa *(borrador, 15/11)*
- `POST /api/transcribe` (multipart `audio`) → `{transcript, text}`. **No modifica nada**: sirve para mostrar lo que se entendió. Si el usuario lo confirma con el botón "Add to context", la app llama a `POST /api/me/context/raw/append` con `text`.
- Acepta los mismos formatos, tamaño máximo (10 MB) y duración máxima (120 segundos) que el audio del chat; es público y no requiere token.
- Mientras el usuario habla, la vista en vivo la hace el navegador (reconocimiento de voz del propio navegador, con resultados parciales); la transcripción del backend es la que vale al confirmar.

## Perfil y recomendaciones *(borrador)*
- `GET /api/sessions/{id}/profile` → `{startup_name?, one_liner?, sector?, stage?, location?, raising?: {amount?, round?}, competitors: [string], target_customers?, role?: founder|investor|other, interests?: {sectors: [string], regions: [string], stages: [string], follows: {companies: [string], investors: [string]}}, facts: [{text, origin: user}], updated_at}`
- `GET /api/sessions/{id}/recommendations` → `{status: idle|running|ready|error, updated_at, investors: [Card], competitors: [Card], prospects: [Card]}`

## Reglas
- Todo dato que venga de Cala viaja con `sources`, y la app siempre las muestra.
- El modelo nunca escribe cifras ni nombres que no vengan de Cala. Si Cala no tiene el dato después de probar todas sus herramientas, se devuelve `not_found` con lo que se buscó.
- Nada de claves en respuestas ni logs.
