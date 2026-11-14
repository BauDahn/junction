# Cala Match

**A two-sided funding marketplace built on [Cala](https://cala.ai)'s knowledge graph.** Startups find the investors that fit them; investors find the startups worth a call. Every card, score and answer comes from Cala and shows its source.

Built at Junction 2026 (Espoo, 13–15 November 2026) for the Cala challenge. Slush starts right after, so it has to be usable the next day.

## What it does

One app, two modes. A switch at the top changes everything: feed, chatbot suggestions and context prompts.

| Mode | Who | The feed shows |
|---|---|---|
| **Raising** | Startup looking for funding | Investors, ranked by affinity |
| **Investing** | Investor looking for startups | Startups, ranked by affinity |

| Tab | What you get |
|---|---|
| **Feed** | A grid of cards, one per investor or startup, each with an **affinity score** (0–100) and a one-line "why it matches". Tap a card for the full profile. |
| **Detail** | Everything Cala knows: funding rounds with lead investors, portfolio, people, key figures. Every fact carries its source and date. |
| **Chat** | Ask anything by text or voice ("Who led Amenitiz's Series B?"). Answers are tables of Cala data with sources, never invented numbers. |
| **Context** | Teach the app about you: upload a pitch deck (PDF), record a voice note or write a note. The app extracts sector, stage, region and ticket size, and the matches improve. |
| **Profile** | Mode, saved matches, settings. |

The whole interface is in English. The design prototype is in [`docs/design/stitch/`](docs/design/stitch/).

## What makes it different

**1. The canonizer.** Cala answers differently to the same question depending on how it is written (accents, language, word order). We built a canonizer that turns any phrasing into one canonical query. Asking directly, through MCP or with Cala's official guide, at most 1 of 9 questions was consistent; with the canonizer, 9 of 9. See [docs/BENCHMARK-CANONIZADOR.md](docs/BENCHMARK-CANONIZADOR.md) and [docs/INFORME-ERROR-CALA.md](docs/INFORME-ERROR-CALA.md).

**2. A local graph on top of Cala.** Cala is a graph of entities and relationships. We load the neighbourhood of each user into a local subgraph, so exploring it is instant and Cala is only called at the edges. Measured on 14 November with Amenitiz as the seed (185 nodes, 246 edges):

| | Result |
|---|---|
| Loading from Cala (19 calls) | about 14–18 s of real work; the entity endpoints answer in about 1 s per call |
| Rate limit | the 10th call in a row got an HTTP 429; the entity endpoints tolerate roughly 1–2 calls per second |
| Full BFS over the local subgraph | 0.13 ms |
| Shortest path, seed to farthest node | 0.13 ms |
| BFS over a synthetic 100,000-node graph | 337 ms |

**3. A shared cache on Aiven Valkey.** What one user (or one machine) asks Cala is instant for everyone else, and it protects the rate limit. The plan is to cache nodes and edges, not just raw answers, so one shared graph grows with use.

**4. Nothing invented.** The language model only interprets the request. It never writes a figure or a name that does not come from Cala, and every value is shown with its source.

## Architecture

```
 Expo app (web + iOS + Android)             Feed · Detail · Chat · Context · Profile
        │  REST (docs/API.md)
 FastAPI backend ───── Gemini: router, intent, audio, PDF context, judge
        │
 Canonizer ─────────── Aiven Valkey: shared cache (raw answers, graph)
        │
 Cala API: entities, knowledge/query, knowledge/search
```

Status: chat, router, canonizer, cache, journal and the Expo app are in `main`. The dual-mode feed, affinity score, context uploads and the local graph are the current work (see [CLAUDE.md](CLAUDE.md#workstreams)).

## Team

| Machine | Person | Focus |
|---|---|---|
| `bau` | Bau | Orchestration, architecture (local graph, affinity score), pitch and documentation |
| `fabricio` | Fabricio | Backend API, optimizer (rate limit, cache) and the Aiven integration |
| `gabriel` | Gabriel | Context ingestion (PDF and voice), n8n automations and extra tools |
| `adrian` | Adrian | Design and the app: the Stitch prototype turned into the Expo app |

## Repo layout

| Folder | What is in it |
|---|---|
| `app/` | Expo app (React Native + TypeScript) for web, iOS and Android |
| `backend/` | FastAPI API. `chat/`: sessions, messages, audio, profile. `cala_core/`: router and Cala queries. `journal/`: daily journal. `verifier/`: shared LLM and config modules (the deck verifier is out of the product). See [backend/README.md](backend/README.md) |
| `canonizador/` | The query canonizer, the cache layers and the benchmarks. See [canonizador/README.md](canonizador/README.md) |
| `n8n/` | n8n flows against the API |
| `docs/` | API contract, Cala guides, benchmarks, error report and design (index in [CLAUDE.md](CLAUDE.md#documentos)) |

## Run it

```bash
# Backend
cd backend && uv sync && uv run uvicorn app:app --port 8000
uv run pytest

# App (web: press w; in Expo Go set EXPO_PUBLIC_API_URL to the PC's IP)
cd app && npm install && npx expo start
```

Keys (`CALA_API_KEY`, `GEMINI_API_KEY`, `VALKEY_URL`) go only in `backend/.env` (template: `backend/.env.example`). They are never committed.

## Challenges

- **Cala** (main): real need, end-to-end execution, originality, Cala at the core.
- **Google Gemini**: the product's AI (router, intent, audio, PDF context).
- **Aiven**: shared Valkey cache for Cala queries and the local graph. **[How we use it and what it saves](docs/AIVEN.md)**: a repeated question goes from 27.7 s to 1.45 s, and a Valkey read takes ~30 ms with zero Cala calls.
- **OpenAI Codex**: the code was written with Codex, directed by Claude and verified against the real services. **[What Codex built and how much we used it](docs/CODEX.md)**: 19 tasks and 14.4 M input tokens on one machine alone, 9 of the tasks were corrections from real tests. Decisions in [docs/PROCESO.md](docs/PROCESO.md).
