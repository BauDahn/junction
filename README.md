# Cala Match

**An event-driven deal-flow experience built on [Cala](https://cala.ai)'s knowledge graph.** Startups find investors who fit; investors find startups worth meeting. Every verified fact and affinity score is grounded in Cala data and shows its source.

Built at Junction 2026 in Espoo, Finland. The interface is available for web, iOS and Android.

## Product experience

### Onboarding gate

Users calibrate their operating role as a **Raiser** or **Investor** before entering the workspace. The selection shapes recommendations and the event outreach experience.

### Events: My Events and Explore Events

Explore a square event grid of major European venture gatherings: **Slush 2026**, **Arctic15**, **Techarena**, **Sifted Summit**, **Bits & Pretzels**, and **South Summit**. Saving an event in Explore Events adds it to My Events.

### Event workspace (`/event/[id]`)

Each event workspace combines a dynamic **Startup Outreach Brief**, tailored to the startup's context and verified Cala facts, with **Recommended Investors** attending that event. Investors are ranked by an affinity score from 0 to 100.

### Investor dossier (`/entity/[id]`)

The dossier presents concise Cala-verified facts: company or fund, industry, key match factors, and stage and ticket, with clickable sources. Its actionable **How to get investment** guide covers verified prior rounds and co-leads, suggested schedule windows, and Cala pitch signals.

### Floating Cala mascot assistant

The assistant stays available in the bottom-right corner for text and voice queries against Cala and Canonizer. It supports live recommender context updates and natural-language shortcuts, such as adding events to My Events or bookmarking investors.

### Context and profile

Calibrate context with a pitch deck PDF and voice note. The minimalist profile manages operating role, saved investors, attending events, and a summary of the recommender context.

## Cala and the data model

The language model interprets requests; Cala supplies verified facts. Every number and entity shown in a response is backed by Cala data and sources.

### Canonizer benchmark

Cala can answer the same question differently depending on phrasing, language, accents, and word order. In our benchmark, direct queries, MCP, and Cala's guide produced consistent results for at most 1 of 9 questions. The canonizer produced consistent results for 9 of 9. See [the benchmark](docs/BENCHMARK-CANONIZADOR.md) and [the error report](docs/INFORME-ERROR-CALA.md).

### Local graph benchmark

Measured on 14 November with Amenitiz as the seed (185 nodes, 246 edges):

| Operation | Result |
|---|---|
| Load from Cala (19 calls) | About 14–18 s of real work; entity endpoints respond in about 1 s per call |
| Rate limit | The 10th consecutive call returned HTTP 429 |
| Full BFS over the local subgraph | 0.13 ms |
| Shortest path to the farthest node | 0.13 ms |
| BFS over a synthetic 100,000-node graph | 337 ms |

### Shared cache benchmark

Aiven Valkey shares cached Cala queries and graph data. A repeated question went from 27.7 s to 1.45 s; a Valkey read takes about 30 ms and makes zero Cala calls. See [the Aiven integration](docs/AIVEN.md).

## Architecture

```text
Expo app (web, iOS, Android)
  Onboarding gate · Explore Events · My Events · Event workspace
  Investor dossier · Floating Cala assistant · Context · Profile
        │ REST (docs/API.md)
FastAPI backend · Gemini router, intent, audio, PDF context, judge
        │
Canonizer · Aiven Valkey shared cache and graph
        │
Cala API · entities, knowledge/query, knowledge/search
```

The canonizer normalizes user questions before they reach Cala. Local graph traversal makes neighbourhood exploration fast; Cala is queried at the graph edges. The cache reduces repeat latency and helps protect Cala's rate limit.

## Repository layout

| Folder | Contents |
|---|---|
| `app/` | Expo app (React Native and TypeScript) for web, iOS and Android |
| `backend/` | FastAPI API, chat, Cala core, feed, event catalog, graph, and shared modules |
| `canonizador/` | Query canonizer, cache layers, and benchmarks |
| `n8n/` | Automation flows against the API |
| `docs/` | API contract, Cala guides, benchmarks, and design materials |

## Run it

```bash
# Backend
cd backend && uv sync && uv run uvicorn app:app --port 8000
uv run pytest

# App (press w for web; set EXPO_PUBLIC_API_URL to the PC IP for Expo Go)
cd app && npm install && npx expo start
```

Set `CALA_API_KEY`, `GEMINI_API_KEY`, and `VALKEY_URL` only in `backend/.env` (template: `backend/.env.example`). Do not commit keys.

## Challenges

- **Cala:** the knowledge graph is the source of verified facts and recommendations.
- **Google Gemini:** powers routing, intent, audio, PDF context, and judging. [Why Gemini matters](docs/GOOGLE-GEMINI.md).
- **Aiven:** shared Valkey cache, graph, and rate limit. [How it helps](docs/AIVEN.md).
- **OpenAI Codex:** used to implement and verify the product. [Codex work log](docs/CODEX.md) and [process notes](docs/PROCESO.md).
