# Cala Match

**A funding marketplace built around events, on [Cala](https://cala.ai)'s knowledge graph.** At an event like Slush, a startup finds the investors worth meeting and knows how to approach each one; an investor finds the startups worth a call. Every fact on screen comes from Cala and shows its source.

Built at Junction 2026 (Espoo, 13–15 November 2026) for the Cala challenge. Slush 2026 opens on 18 November, so it has to be usable right after.

## What it does

**You choose who you are when you sign up: Raiser or Investor.** It is required to enter the web, and it decides what every screen shows. The raiser flow below is the first one specified; the investor flow mirrors it with startups to meet.

### Raiser (a startup looking for funding)

| Screen | What it does |
|---|---|
| **Explore events** | All events, as squares with image, name, slogan and date. One tap saves an event as "I am attending", or removes it. Saved events move to My events. |
| **My events** | The events you saved, in the same square format. Inside an event: the **investors recommended for you** by the recommendation engine, and for each one a short **contact letter**, a draft of how to approach that investor for your startup. Tap an investor for a simple, concise card of what Cala knows (the firm, its industry and the key factors Cala returns, such as its funds), and a plain **how to get this investment**: what the investor's earlier deals suggest, with schedules and dates that Cala has. |
| **Profile** | Your context (the data the recommendation engine uses), your favourite investors and your personal data. Minimal. |
| **Assistant** | There is no Ask tab. A small mascot sits in the bottom-right corner; a tap opens an overlay panel of comfortable size with a chat, by text or voice. It answers questions about companies through Cala and the canonizer, and it **edits your context** ("we now raise 2 million in seed"). It also works as a shortcut: say "I want to go to Slush 2026" and the event is added to your favourites. |

### Investor
Same structure, the other way round: events to attend and the startups worth meeting. Specified next.

### When something is not in the graph
The app never invents an answer and never gives up after the first miss.
- **Chat:** if the canonizer fails or finds nothing, it tries Cala's entity lookup, then Cala's search, and only then answers "not found" together with the list of what it tried.
- **Detail:** an investor or company outside the local graph is fetched live from Cala (one call), stored for next time and shown with its sources.
- **Search:** `GET /api/search` looks in the local catalog first and then in Cala.

The assistant uses the same rule: Gemini interprets, Cala asserts. See [docs/GOOGLE-GEMINI.md](docs/GOOGLE-GEMINI.md).

### What data exists today
Slush 2026 has **2,990 participating companies** in Cala, and most of them have people linked (founders, executives, board). Slush 2025 has only **8 speakers** and no participant list, so Slush 2026 is the event we can show in full. Cala has no email, LinkedIn or phone for people, so the app never shows a contact it does not have.

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
 Web app                       Explore events · My events · Profile · floating assistant
        │  REST (docs/API.md)
 FastAPI backend ───── Gemini: router, intent, audio, PDF context, judge
        │
 Canonizer ─────────── Aiven Valkey: shared cache (raw answers, graph)
        │
 Cala API: entities, knowledge/query, knowledge/search
```

Status: chat with voice, router, canonizer, shared cache and rate limit, shared graph, the Slush catalog, the feed and detail API with the affinity score, and the live fallback and search are in `main`. The new web (sign-up with role, events, floating assistant, profile) is being built with Gemini and is not in `main` yet.

## Team

| Machine | Person | Focus |
|---|---|---|
| `bau` | Bau | Orchestration, review, architecture, backend with Codex, pitch and documentation |
| `gabriel` | Gabriel | The new web, built with Gemini |
| `fabricio` | Fabricio | Backend, optimizer and Aiven integration (feed API, graph store, shared rate limit) |
| `adrian` | Adrian | Design review and presentation |

Claude plans and reviews, Codex writes the backend, Gemini is both the AI inside the product and the tool building the new web.

## Repo layout

| Folder | What is in it |
|---|---|
| `app/` | The web app (Expo, React Native and TypeScript today). The new version is being built with Gemini |
| `backend/` | FastAPI API. `chat/`: sessions, messages, audio, profile. `cala_core/`: router and Cala queries. `api/`: feed, detail and affinity. `graph/`: shared graph on Valkey. `catalog/`: Slush ingestion. `core/`: shared LLM, config and Cala client modules.md) |
| `canonizador/` | The query canonizer, the cache layers and the benchmarks. See [canonizador/README.md](canonizador/README.md) |
| `docs/` | API contract, Cala guides, benchmarks, error report, one page per challenge and the first Stitch design (superseded). Index in [CLAUDE.md](CLAUDE.md#documentos) |

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
- **Google Gemini**: the product's AI (router, intent, audio, PDF context). **[Where it sits, why Gemini, and the one rule that keeps it honest](docs/GOOGLE-GEMINI.md)**: Gemini interprets, Cala asserts. One multimodal call turns audio into a literal transcript plus a clean intent.
- **Aiven**: shared Valkey cache for Cala queries and the local graph. **[How we use it and what it saves](docs/AIVEN.md)**: a repeated question goes from 27.7 s to 1.45 s, and a Valkey read takes ~30 ms with zero Cala calls.
- **OpenAI Codex**: the code was written with Codex, directed by Claude and verified against the real services. **[What Codex built and how much we used it](docs/CODEX.md)**: 19 tasks and 14.4 M input tokens on one machine alone, 9 of the tasks were corrections from real tests. Decisions in [docs/PROCESO.md](docs/PROCESO.md).
