# Contrato de la API (backend ↔ app)

Fuente de verdad entre las dos personas: la app (`app/`) y el backend (`backend/`) se programan contra este documento. **Cambiar algo que no esté marcado *(borrador)* requiere un PR propio que el otro apruebe antes de implementarlo.**

Base: `http://localhost:8000` en desarrollo (en la app, `EXPO_PUBLIC_API_URL`). JSON UTF-8. Errores: HTTP 4xx/5xx con `{"error": {"code": "...", "message": "..."}}`. CORS abierto en desarrollo.

## Salud
- `GET /api/health` → `{provider, model, cala: bool, transcription: string}`

## Verificador de decks (implementado)
- `POST /api/verify` (multipart `file`: PDF ≤ 20 MB) → `{job_id}`
- `POST /api/verify-sample` → `{job_id}` (deck de ejemplo)
- `GET /api/jobs/{job_id}` → `{status: queued|extracting|checking|judging|done|error, progress: {done, total}, report?, error?}`
- `report`: `{startup_name, provider, model, claims: [Claim], summary: {confirmed, partially_confirmed, contradicted, no_data, not_checked}, trust_score: 0-100, timings, dropped_urls}`
- `Claim`: `{id, page, quote, category, publicly_verifiable, cala_question, verdict: confirmed|partially_confirmed|contradicted|no_data|not_checked|error, explanation, evidence, sources: [Source]}`
- `Source`: `{name, url}`

## Chat con audio *(borrador)*
Una conversación por usuario. Manda texto o audio; el backend transcribe, actualiza el perfil de su startup, responde al momento (con la caché de Cala) y lanza en segundo plano la búsqueda de recomendaciones.
- `POST /api/sessions` → `{session_id}` (sin login en la demo; la app guarda el id localmente)
- `POST /api/sessions/{id}/messages`
  - texto: JSON `{text}`
  - audio: multipart `audio` (m4a, webm, wav, mp3; ≤ 2 min)
  - → `{message: Message, reply: Message, profile_updated: bool, recommendations_status: idle|running|ready|error}`
- `GET /api/sessions/{id}/messages` → `{messages: [Message]}`
- `Message`: `{id, role: user|assistant, text, transcript?: string, created_at, sources?: [Source], cards?: [Card]}`
- `Card`: `{type: investor|company|competitor|prospect|claim, title, subtitle?, reason, sources: [Source]}`

## Perfil y recomendaciones *(borrador)*
- `GET /api/sessions/{id}/profile` → `{startup_name?, one_liner?, sector?, stage?, location?, raising?: {amount?, round?}, competitors: [string], target_customers?, facts: [{text, origin: user|deck, verified?: Claim}], updated_at}`
- `GET /api/sessions/{id}/recommendations` → `{status: idle|running|ready|error, updated_at, investors: [Card], competitors: [Card], prospects: [Card]}`
- `POST /api/sessions/{id}/deck` (multipart `file`) → `{job_id}`: verifica el deck (mismo job que arriba) y suma sus afirmaciones al perfil.
- Cuando las recomendaciones pasan a `ready`, la siguiente respuesta del chat lo avisa.

## Reglas
- Todo dato que venga de Cala viaja con `sources`, y la app siempre las muestra.
- El chat no inventa datos: si Cala no lo tiene, lo dice.
- Nada de claves en respuestas ni logs.
