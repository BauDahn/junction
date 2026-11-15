# CalaDo

**A funding marketplace around events, built on [Cala](https://cala.ai)'s knowledge graph: startups find the investors worth meeting at an event, investors find the startups, and every fact on screen shows its Cala source.**

Built at Junction 2026 (Espoo, 13–15 November 2026) for the Cala challenge, with Google Gemini, Aiven and OpenAI Codex. Slush 2026 opens in Helsinki on 18 November, so the first event in the app is Slush. The project was called "Cala Match" during the hackathon; some older docs still use that name.

## The problem

Raising money is a search problem. Before an event like Slush, a founder has a list of thousands of attendees and no quick way to tell which investors actually back companies like theirs. Investors have the mirror problem. The data to answer that exists in Cala's graph (funding rounds, lead investors, portfolios, people, all with sources), but it is hard to use directly:

- Cala's knowledge endpoints answer the **same question differently** depending on phrasing, accents or language. In our benchmark, asking directly (search, query, or an agent over MCP, even with Cala's own guide) gave the same data across three phrasings for at most **1 of 9** questions.
- The knowledge endpoints take **16–60 s** per call, and the API returns HTTP 429 after a handful of calls in a row.

calado addresses both: a **canonizer** that turns any phrasing into one canonical Cala query (9 of 9 consistent), and a local graph plus a shared cache so the app answers in milliseconds and calls Cala only at the edges.

## What you can do in the app

| Screen | What it does |
|---|---|
| Sign-up | Email and password, and a fixed role: **Raiser** (startup looking for money) or **Investor**. The role decides what every screen shows. |
| Explore Events / My Events | A grid of European venture events. Saving an event moves it to My Events. Only Slush 2026 has a participant list in Cala; the app says so for the others. |
| Event page | Recommended investors (or startups, for an Investor) ranked by an **affinity score from 0 to 100**, with the reasons and their sources. |
| Company page | What Cala has on an investor or startup: key facts, funding rounds with lead investors, people, portfolio and why it matches, each with its source. Fetched from Cala once (at most 4 calls), then served from the local graph. |
| Assistant | A floating mascot bubble that opens a text and voice chat. Questions go to Cala through the canonizer; it can also add notes to the user's context. |
| Profile | Role, context (free text, a voice note with a preview before adding, or a pitch-deck PDF), favorites and saved events. Favorites can be downloaded as a **PDF report** with Cala facts and a Gemini-proposed action plan, labeled as AI-generated. |

**When something is not in the graph,** the app does not invent and does not give up after the first miss: the assistant tries the canonizer, then Cala's entity lookup, then Cala's search, and only then answers "not found" with the list of what it tried. A company page outside the local graph is fetched live from Cala and stored for next time.

### Demo flow (about 2 minutes)

1. Sign up as a **Raiser** and write one line of context (sector, stage, region, ticket).
2. In **Explore Events**, save **Slush 2026**; open it from **My Events**.
3. Read the ranked investors and open one: rounds, leads, portfolio and people, each with a source link.
4. Open the **assistant** and ask, by voice or text, "Who led Amenitiz's Series B?". Ask again with different wording: same canonical query, same answer.
5. In **Profile**, add a favorite and download the **favorites report** (PDF).

The web app is deployed on Vercel from `app/` (see `app/vercel.json`). The public backend runs on a team laptop behind a Cloudflare tunnel, so its URL changes when the tunnel restarts; ask the team for the current link. Demo accounts exist for each role (credentials are shared privately). If the backend cannot be reached, the app falls back to sample data and labels it as such.

## Architecture at a glance

```text
  Expo app (web build on Vercel; also runs in Expo Go)
     |  REST + JSON (docs/API.md)
     v
  FastAPI backend (backend/)
     |  accounts, context, chat, feed, company page, search, favorites PDF
     |  affinity score over the local graph (backend/api/affinity.py)
     |
     |--> Google Gemini ........ router, intent, audio, claim judge, catalog tags, action plan
     |
     |--> Canonizer (canonizador/) -----------------> Cala API
     |      phrasing -> intent -> one canonical query    entities, knowledge/query, knowledge/search
     |
     |--> Aiven for Valkey ..... shared cache of Cala responses, graph store, shared rate limit,
     |                           daily Cala call counter, abuse limits, negative cache
     '--> Aiven for PostgreSQL . user accounts on the public backend
```

Rule across the stack: **Gemini interprets, Cala asserts.** Gemini understands and classifies what the user says; every number, name and date shown comes from Cala with its source.

## Measured numbers

Measured against the real services on 14–15 November 2026. Method and raw data in the linked docs.

| What | Result | Source |
|---|---|---|
| Same data across 3 phrasings, without the canonizer | 0 to 1 of 9 questions (direct search, direct query, MCP agent, MCP agent with Cala's guide) | [benchmark](docs/BENCHMARK-CANONIZADOR.md) |
| Same data across 3 phrasings, with the canonizer | **9 of 9** | [benchmark](docs/BENCHMARK-CANONIZADOR.md) |
| Phrasings collapsed by the canonizer | **41 phrasings of 9 questions -> 9 queries**, identical answer within each group | [error report](docs/INFORME-ERROR-CALA.md) |
| Cala, exact same text repeated | 0.2–0.3 s vs 15–18 s the first time (Cala caches by exact text; a paraphrase misses) | [error report](docs/INFORME-ERROR-CALA.md) |
| Slush 2026 attendee list from Cala | **2,990** attendees, fetched in 36 s (30 pages of 100) | [architecture](docs/ARQUITECTURA.md) |
| Catalog loaded into the graph | **2,110 of 2,990** attendees profiled: 47 investors, 1,060 startups | team status, 15 Nov |
| BFS over a local subgraph (185 nodes, 246 edges) | **0.13 ms** | [architecture](docs/ARQUITECTURA.md) |
| Aiven Valkey, 200 reads in one pipeline | **31 ms** (one by one: ~28 ms each) | [Aiven](docs/AIVEN.md) |
| Repeated chat question through the backend | 27.7 s the first time, 1.45 s the second | [Aiven](docs/AIVEN.md) |

The affinity score combines six signals with fixed weights (`backend/api/affinity.py`): sector 0.30, stage 0.20, region 0.15, ticket 0.15, recent activity 0.10, closeness in the graph 0.10. A signal without data is left out instead of counted as zero, and lowers the card's `confidence`. The weights are a first proposal and are not calibrated.

## For each challenge

| Challenge | Read | In one line |
|---|---|---|
| **Cala** (main) | [docs/CALA.md](docs/CALA.md) | Cala is the only source of facts; the canonizer fixes the consistency problem we measured, and the graph, cache and call caps make Cala fast and safe to call. |
| **Google Gemini** | [docs/GOOGLE-GEMINI.md](docs/GOOGLE-GEMINI.md) | Gemini is the AI inside the product: audio, router, intent, claim judge, catalog tags and the action plan, always with strict JSON schemas and never as a source of facts. |
| **Aiven** | [docs/AIVEN.md](docs/AIVEN.md) | Valkey is the shared memory in front of Cala (cache, graph, rate limit, counters); PostgreSQL holds the accounts. |
| **OpenAI Codex** | [docs/CODEX.md](docs/CODEX.md) | The application code was written by Codex from concrete tasks, then reviewed and tested against the real services; task log per machine. |

## Run it locally

Requirements: Python 3.11+ with [uv](https://docs.astral.sh/uv/), and Node.js with npm.

```bash
# Backend (FastAPI on :8000)
cd backend
cp .env.example .env          # fill in your own keys; .env is git-ignored
uv sync                       # add --extra audio for local Whisper transcription
uv run uvicorn app:app --port 8000
uv run pytest                 # tests switch off the shared Valkey and PostgreSQL

# App (Expo), in another terminal
cd app
npm install
npx expo start --web          # or `npx expo start` and open it in Expo Go
npm run build                 # static web export to dist/, as deployed on Vercel
```

The app calls `http://localhost:8000` unless `EXPO_PUBLIC_API_URL` is set (use your PC's IP when testing from a phone). `EXPO_PUBLIC_MOCK=1` forces sample data.

Backend environment variables go in `backend/.env` (never committed; template in `backend/.env.example`):

| Variable | Use |
|---|---|
| `CALA_API_KEY` | Cala API key (needed for live data) |
| `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | Gemini; when present it is the default LLM and transcription provider |
| `GEMINI_FAST_MODEL`, `GEMINI_MODEL`, `GEMINI_TRANSCRIBE_MODEL` | Model overrides (defaults `gemini-3.5-flash-lite`, `gemini-flash-latest`, and the fast model for audio) |
| `LLM_PROVIDER`, `TRANSCRIPTION_PROVIDER`, `WHISPER_MODEL` | Provider overrides (`gemini`, `nvidia`, `codex`, `claude`; and `gemini`, `whisper`, `nvidia`, `none`) |
| `VALKEY_URL` | Aiven for Valkey service URI (`rediss://...`). Optional: without it the cache is disk only |
| `ACCOUNTS_STORE`, `DATABASE_URL` | Where accounts live: `valkey`, `postgres` (connects to `DATABASE_URL`) or `sqlite` |
| `CALA_REQUIRE_AUTH`, `TRUST_PROXY`, `CALA_DAILY_CALL_CAP`, `ADMIN_TOKEN` | Public deployment: require an account for live Cala calls, trust `X-Forwarded-For`, daily Cala call cap (default 2000), admin metrics in `/api/stats` |
| `CORS_ORIGINS` | Allowed origins (default `*`, development only) |

Loading the Slush catalog (`cd backend && uv run python -m catalog run`) spends real Cala calls; each run stops at 150 calls unless `--max-calls` says otherwise.

## Repository layout

| Folder | Contents |
|---|---|
| `app/` | Expo app (React Native, TypeScript, Expo Router): sign-up, events, event and company pages, assistant, profile |
| `backend/` | FastAPI API: accounts, chat and voice, context, Cala core (router, executor, claims), feed and affinity, company page with live fallback, search, favorites PDF, Slush catalog, graph store, abuse protection. See [backend/README.md](backend/README.md) (Spanish) |
| `canonizador/` | The query canonizer, the Cala client (pacing, retries, caps), the two-layer cache and the benchmarks |
| `docs/` | One doc per challenge, the [API contract](docs/API.md), [architecture](docs/ARQUITECTURA.md) and [affinity spec](docs/SPEC-grafo-afinidad.md) (Spanish), the benchmark and error report (Spanish, summarized in English in [CALA.md](docs/CALA.md)), the [process log](docs/PROCESO.md), brand and presentation drafts |
| `docs/internal/` | Working notes from the hackathon (ideas, plans, Cala reference guides); not needed to evaluate the project |

## Further work to considerate

- Cala does not say which investors attend an event. For Slush 2026 the event page ranks the investors in the Slush catalog and says so; the other events show "No participant data in Cala yet" instead of guessing.
- The events list is fixed in the app for now (`app/src/api/events.ts`); there is no events backend yet.
- The canonizer guarantees the same answer for the same intent, not that the answer is correct. When Cala's structured data and its query answer disagree (Amenitiz's Series B), it flags the discrepancy instead of picking one.
- The affinity weights are not yet calibrated against known investor–startup pairs.
