# API contract (backend ↔ app)

Source of truth shared by both people: the app (`app/`) and backend (`backend/`) are built against this document. **Changing anything not marked *(draft)* requires its own PR, approved by the other person before implementation.** The reason for the blocks is documented in `docs/internal/PLAN-CALA-CENTRO.md`.

Base: `http://localhost:8000` in development (in the app, `EXPO_PUBLIC_API_URL`). JSON UTF-8. Errors: HTTP 4xx/5xx with `{"error": {"code": "...", "message": "..."}}`. CORS is open in development.

## Health
- `GET /api/health` → `{provider, model, cala: bool, transcription: string}`

## Common types
- `Source`: `{name, url, date?, source_rank?: FILING|PRIMARY|PRESS|AGGREGATOR}`
- `CalaCall`: `{tool: knowledge_query|entity|knowledge_search, query: string}`. The exact query sent to Cala, so it can be reproduced.

## Blocks (what the app displays) *(draft, new 14/11)*
Chat responses are lists of `Block`. All data blocks are **Cala data as is**; at most, the model adds `summary` (one line).

| `type` | Fields | When |
|---|---|---|
| `cala_table` | `title`, `summary?`, `call: CalaCall`, `columns: [string]`, `rows: [[string \| number \| null]]`, `sources: [Source]`, `row_sources?: [[int]]` (indices in `sources` by row), `focus_rows?: [int]` (rows that answer the question; the app shows only those and “View all”), `answer?: string` (if there is a single row: its Cala cells joined with " · ") | Result of `knowledge_query` (rows) or an entity (field · value · source · date · source type) |
| `cala_answer` | `title`, `call: CalaCall`, `markdown`, `sources: [Source]` | Result of `knowledge_search`: Cala's answer as is |
| `claim_check` | `claim` (what the user said), `verdict: confirmed\|partially_confirmed\|contradicted\|no_data`, `explanation` (one line), `evidence: cala_table \| cala_answer`, `sources: [Source]` | The user stated a fact and it was checked against Cala |
| `profile_update` | `changes: {field: value}` | The user shared something about their startup or interests |
| `not_found` | `title`, `tried: [CalaCall]`, `closest?: cala_table \| cala_answer` | No Cala tool returned data; shows what was searched |
| `text` | `text` | Replies without data (greeting, clarification) |

## Chat with audio *(draft)*
One conversation per user. Send text or audio; the backend transcribes it and the **router** (`backend/cala_core`) decides what to do with each part of the message: query Cala, verify a claim, or update the profile.
- `POST /api/sessions` → `{session_id}` (no login in the demo; the app stores the id locally)
- `POST /api/sessions/{id}/messages`
  - text: JSON `{text}`
  - audio: multipart `audio` (m4a, webm, wav, mp3; ≤ 2 min)
  - → `{message: Message, reply: Message, profile_updated: bool, recommendations_status: idle|running|ready|error}`
- `GET /api/sessions/{id}/messages` → `{messages: [Message]}`
- `Message`: `{id, role: user|assistant, text, transcript?: string, created_at, blocks?: [Block], sources?: [Source], cards?: [Card]}`. In user messages sent by audio, `text` is the cleaned intent (with autocorrections applied and filler words removed), and `transcript` is what was said verbatim; in text messages, `transcript` is null. In replies, `text` becomes a context line; the content is in `blocks`. `cards` is retained for compatibility with recommendations.
- `Card`: `{type: investor|company|competitor|prospect|claim, title, subtitle?, reason, sources: [Source]}`

## Feed and detail *(draft, new on the night of 14/11)*
Cala Match. Details on how the score is calculated are in `docs/SPEC-GRAPH-AFFINITY.md`.
- `GET /api/feed?session_id=&mode=raising|investing&limit=20&cursor=` → `{mode, items: [FeedCard], next_cursor?, confidence_note?}`. `raising` returns investors; `investing` returns startups. Sorted by descending `score`, then by `confidence` for equal scores. `session_id` is required (the session whose profile is used; 404 if it does not exist). If `mode` is omitted, the session's saved mode is used (default `raising`); an invalid mode returns 422. `limit` ranges from 1 to 100. `cursor` is the `next_cursor` from the previous page (opaque). `confidence_note` (English text) indicates whether the catalog is still loading or the profile is missing; optional keys are omitted, not set to `null`.
- `FeedCard`: `{id, type: investor|startup, name, one_liner, tags: [string], score: 0-100, confidence: 0-1, why_match: [string], sources: [Source]}`. When `confidence < 0.5`, the app displays “partial data”.
- `GET /api/entities/{id}?mode=&session_id=` → `EntityDetail`: `{id, type, name, description?, score?, confidence?, why_match: [{signal, text, sources: [Source]}], facts: [{label, value, sources: [Source]}], rounds: [{round_type, amount?, date?, leads: [string], investors: [string], sources: [Source]}], portfolio: [{id, name}], people: [{id, name, role, since?}], loaded_at}`. `session_id` is optional: when provided, `score`, `confidence`, and `why_match` are included (the same score as in the feed); without it, `why_match` is empty. `amount` and `date` are text exactly as Cala provides them. `signal` is one of `sector|stage|region|ticket|activity|closeness`.
- `GET /api/search?q=<text>&limit=8` (`q` from 2 to 80 characters) → `{query, items: [{id, name, type: investor|startup|other, origin: catalog|cala, one_liner?}], tried: [catalog|cala]}`. `type` is `investor|startup` for `catalog`; `cala` results use `other` (unclassified, classified when the detail is opened). Searches names locally and supplements with Cala if results are missing; ids open the detail. Local catalog results are always public and never return 401 for lack of a token. With `CALA_REQUIRE_AUTH=1` and no Bearer token, only the live Cala fallback is skipped (#138).
- To require an account for Cala, set `CALA_REQUIRE_AUTH=1` in `backend/.env` (enable when registration is on main). By default (`0`), live queries remain accessible without a token and are still protected by usage limits.
- If `GET /api/entities/{id}` does not find the entity in the catalog or local graph, it attempts to retrieve it from Cala live and stores it in the graph with a TTL. If Cala does not know it, returns 404 `Entity not found in the graph or in Cala.`; if it takes more than 25 seconds, returns 504 `Cala did not answer in time.`. Subsequent queries use the local graph.
- `POST /api/sessions/{id}/mode` with `{mode}` → `{mode}`: saves the session's active mode.
- All data is sent with `sources`; if no source is available, the field is not returned.
- Sector and stage tags generated by Gemini from Cala's description have the suffix ` (AI-tagged)` in `tags`, `why_match`, and the `fact` label.
- `GET /api/stats` → `{catalog: {investors, startups, total, status}, cala?, cala_usage: {date, total, by_class, by_who}}`: responds in milliseconds from a summary cached for 60 s (#136); requires `X-Admin-Token: <ADMIN_TOKEN>` to expose `cala` and the `by_class`/`by_who` breakdown (#134). Catalog size and progress, client metrics, and actual Cala call counters for the UTC day. If Valkey is unavailable, `cala_usage` is `{}`.

## Context *(draft, new on the night of 14/11)*
Ingest user context (PDF deck, voice note, or free text) into the session profile, and manually edit what was understood.
- `GET /api/sessions/{id}/context` → `ContextPayload`: `{session_id, profile, what_we_understood, sources: [ContextSource], context_strength, source?}`.
- `POST /api/sessions/{id}/context/pdf` (multipart `file`: PDF ≤ 20 MB, up to 15 pages) → `ContextPayload` (includes `source` with `kind: "pdf"`, `pages`).
- `POST /api/sessions/{id}/context/voice` (multipart `audio` or `file`: `m4a|webm|wav|mp3|ogg`, ≤ 10 MB, ≤ 2 min) → `ContextPayload` (includes `source` with `kind: "voice"`, `duration_s`, verbatim `transcript`; profile extraction uses clean `text` when the transcriber returns it).
- `POST /api/sessions/{id}/context/note` (JSON `{text, title?}`, non-empty `text` ≤ 8000 characters) → `ContextPayload` (includes `source` with `kind: "note"`).
- `PATCH /api/sessions/{id}/context/understood` (partial JSON with `what_we_understood` keys, each `[string]`) → `ContextPayload`: updates `what_we_understood`, `seeking`, `sector`/`stage`/`location`, `ticket`/`raising.amount`/`ticket_range` (when `target_round_size` is sent), and `interests.{sectors, stages, regions}`, preserving pre-existing `interests.follows` (`companies`, `investors`).
- `DELETE /api/sessions/{id}/context/sources/{source_id}` → `ContextPayload`: deletes that source from `sources` (`profile.context_sources`).
- `what_we_understood`: `{sector_focus: [string], target_stage: [string], target_round_size: [string], geography: [string], seeking: [string]}`.
- `sources` (`ContextSource`): `{id, kind: pdf|voice|note, title, subtitle, status: "ready", created_at, pages?, duration_s?, transcript?}`.
- `context_strength`: `{score: 0-100, signals_added: int, signals_total: 6, label: "Needs Context"|"Calibrating"|"Good Calibration"|"High Signal"}`.
- In `profile`, in addition to `ticket` (string for display), `ticket_range?: {min: number, max: number, currency: "EUR"|"USD"|"GBP"|null}` is stored in numeric base units.
- HTTP codes: `400` (empty PDF, invalid JSON or fields, empty note), `404` (session or `source_id` not found), `413` (PDF > 20 MB, audio > 10 MB or > 2 min, note > 8000 characters), `415` (unsupported PDF or audio format), `422` (unreadable PDF or empty/unintelligible audio), `502` (LLM extraction or transcription failure), `503` (transcription not configured).


## Accounts *(draft, 15/11)*
Real registration with email. The role is selected at registration and **cannot be changed**.
- `POST /api/auth/register` with `{email, password, name, company, role: raiser|investor}` → `201 {token, user}`. Password must be at least 8 characters. `409 email_taken` if the email already exists; `422` if a field is missing or the email is invalid.
- `POST /api/auth/login` with `{email, password}` → `{token, user}`; `401 invalid_credentials`.
- `POST /api/auth/logout` → `204`.
- `GET /api/me` → `User`.
- `User`: `{id, email, name, company, role: raiser|investor, session_id, created_at}`. `session_id` is that user's chat, context, and feed session: the app uses it instead of creating an anonymous session.
- Authentication: `Authorization: Bearer <token>` header on `/api/me/*` and `/api/auth/logout`; without a token or with an expired one, `401`.
- **Fixed role:** no endpoint changes it. `POST /api/sessions/{id}/mode` with a mode different from the role of the session's owner returns `409 role_locked`.
- Storage: `ACCOUNTS_STORE=valkey|postgres|sqlite`; by default, uses shared Valkey if `VALKEY_URL` is defined, otherwise `DATABASE_URL` or SQLite (`backend/data/app.db`). If Valkey fails, registration and login return `503`. Passwords use scrypt; random tokens are stored as hashes and expire after 30 days. No emails are sent (no verification for now).

## Context as text *(draft, 15/11)*
The profile displays the context as **the user's text, exactly as written**, not as tags. Tags still exist behind the scenes for the recommendation engine.
- `GET /api/me/context/raw` → `{text, updated_at}`.
- `PUT /api/me/context/raw` with `{text}` → `{text, updated_at, profile_updated: bool}`. Saves the text unchanged and re-extracts the profile (sector, stage, region, ticket) with Gemini.
- `POST /api/me/context/raw/append` with `{text}` → same response, appending the text at the end (on a new line). Used by the confirmed voice note and by the assistant when the user shares something about themselves.
- All three endpoints require `Authorization: Bearer <token>`; the limit is 8,000 characters, with 422 returned if exceeded.
- A PDF uploaded via `POST /api/sessions/{id}/context/pdf` adds its own line to the text (`From <file>: <one-line summary>`).
- Text and voice notes saved from `backend/context` also append their text to the raw context.

## Voice with preview *(draft, 15/11)*
- `POST /api/transcribe` (multipart `audio`) → `{transcript, text}`. **Does not modify anything**: used to show what was understood. If the user confirms with the “Add to context” button, the app calls `POST /api/me/context/raw/append` with `text`.
- Accepts the same formats, maximum size (10 MB), and maximum duration (120 seconds) as chat audio; it is public and does not require a token.
- While the user speaks, the live view is handled by the browser (the browser's own speech recognition, with partial results); the backend transcription is authoritative on confirmation.

## Profile and recommendations *(draft)*
- `GET /api/sessions/{id}/profile` → `{startup_name?, one_liner?, sector?, stage?, location?, raising?: {amount?, round?}, competitors: [string], target_customers?, role?: founder|investor|other, interests?: {sectors: [string], regions: [string], stages: [string], follows: {companies: [string], investors: [string]}}, facts: [{text, origin: user}], updated_at}`
- `GET /api/sessions/{id}/recommendations` → `{status: idle|running|ready|error, updated_at, investors: [Card], competitors: [Card], prospects: [Card]}`

## Events *(draft, 15/11, #111 part 3)*
Each event has its own catalog in Cala (keys `cat:v1:<event_id>:*`, see section 10 of `docs/ARCHITECTURE.md`). Only Slush 2026 has participants; the other events have speakers only.
- `GET /api/events` → `{items: [Event]}`. Public; with `Authorization: Bearer <token>`, each event also includes `saved`. Order: ascending date.
- `Event`: `{id, name, slogan?, date, city, image_url?, counts: {participants, speakers, investors, startups}, has_participants: bool, status: loading|ready|empty, saved?: bool}`. `date` is `YYYY-MM-DD` (start date). `counts` are the data currently available in that event's catalog (0 if none); `has_participants` is `counts.participants > 0`. `status`: `loading` if loading is still in progress, `empty` if there is nothing. Optional keys are omitted, not set to `null`.
- `POST /api/me/events/{id}` → `204`: saves the event for the user (idempotent). `404 event_not_found` if the id does not exist.
- `DELETE /api/me/events/{id}` → `204`: removes it (idempotent, including if it was not saved). `404 event_not_found` if the id does not exist.
- `GET /api/me/events` → `{items: [Event]}`: saved events only (with `saved: true`).
- All three `/api/me/events*` endpoints require `Authorization: Bearer <token>` (accounts, see *Accounts*); without a token or with an expired one, `401`. Stored in the same database as accounts (table `saved_events`: `user_id`, `event_id`, `created_at`).
- `GET /api/events/{id}/feed?session_id=&mode=raising|investing&limit=20&cursor=` → same shape and rules as `GET /api/feed` (`{mode, items: [FeedCard], next_cursor?, confidence_note?}`), but with candidates only from that event, scored against the session profile. `404 event_not_found` if the event does not exist; `404` if the session does not exist; `422` for an invalid mode. An event with no participants returns `items` with speakers only, and `confidence_note` indicates this (in English).
- Compatibility: `GET /api/feed` without an event remains unchanged and is equivalent to the default event (Slush 2026).

## Favorites report in PDF *(draft, 15/11)*
For users who favorite investors or companies: a PDF with those entities, additional data **from Cala only** (each item with its source), and an action plan proposed by Gemini, clearly separated.
- `POST /api/favorites/report` with `{entity_ids: [string] (1 to 10, no duplicates), session_id?: string, mode?: raising|investing}` → `200 application/pdf`, `Content-Disposition: attachment; filename="cala-match-favorites.pdf"`.
- Each id is loaded by calling the same logic as `GET /api/entities/{id}`: UUID per id when Cala is available, limit of 20 requests/minute and 200/day per client, daily limit per account, negative cache, Cala call cap, and graph cache (an already expanded entity does not call Cala again). Thus the report never makes more Cala calls than ten entity-detail opens.
- The report requires `Authorization: Bearer <token>` when `CALA_REQUIRE_AUTH=1`, even if all entities are already cached; without a valid token it returns `401 unauthorized`. It also has its own limit of **3 reports per minute and 30 per day per client**; returns `429` with `Retry-After` when reached.
- With `session_id`, the detail includes `score` and `why_match`, and the session profile is passed to Gemini; without a session there is no score.
- Content (in English): cover (Cala Match, Favorites report, date, mode) and, for each entity, name, type, score if available, description, facts, rounds, people, why it matches, and Cala sources as links. Anything Cala does not have is omitted or says “Not available in Cala”. Footer: “Data: Cala · Plan: Gemini”.
- **Action plan:** a separate block per entity, “Proposed action plan”, with the label “Generated by Gemini from the Cala data above. Not Cala data.” There are 3 to 5 steps. Gemini receives **only** the Cala data for that entity (and the user profile if there is a session); the backend discards any step with figures not present in that input. If Gemini fails, takes more than 30 s, or returns fewer than 3 valid steps, the PDF is still generated and that entity says “Action plan unavailable”; the plan is never an HTTP error.
- Entities absent from the catalog, graph, and Cala, with a non-UUID id when Cala is enabled, or that could not be loaded (per-entity limit, call cap, Cala down), do not break the report: they appear under “Not included” with the reason and in `X-Favorites-Not-Included` (comma-separated ids). An invalid id displays `Invalid id (not a Cala id)`.
- Errors (common format): `422` for an empty list, more than 10 ids, or empty ids; `401` if `CALA_REQUIRE_AUTH=1` and no valid token is provided; `404` if the session does not exist or **all** entities return 404; `422` if all fail due to invalid ids; `429` if a limit is reached (the report propagates the original message for per-entity limits); `503` if all failed due to the Cala call cap; `502` if all failed due to a Cala error; `504` if the report exceeds 90 seconds.

## Rules
- All data from Cala is sent with `sources`, and the app always displays them.
- The model never writes figures or names that do not come from Cala. If Cala does not have the data after all its tools have been tried, `not_found` is returned with what was searched.
- No keys in responses or logs.
