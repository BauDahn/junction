# Documentation map

Everything in `docs/`, what each file is for, and where to start. Back to the [project README](../README.md).

## Start here

| If you want to… | Read |
|---|---|
| Understand the product in 2 minutes | [Project README](../README.md) |
| See how Cala is used (Cala challenge) | [CALA.md](CALA.md) |
| See how Gemini is used (Google challenge) | [GOOGLE-GEMINI.md](GOOGLE-GEMINI.md) |
| See how Valkey and PostgreSQL are used (Aiven challenge) | [AIVEN.md](AIVEN.md) |
| See how the code was written (OpenAI Codex challenge) | [CODEX.md](CODEX.md) |

## Sponsor challenges

| File | What it is |
|---|---|
| [CALA.md](CALA.md) | How calado uses Cala: endpoints, where they are called in the code, the canonizer, and how calls are kept safe (cache, rate limit, daily caps, live fallback). |
| [GOOGLE-GEMINI.md](GOOGLE-GEMINI.md) | Where Gemini runs in the product: question routing, voice, startup context, sector and stage tagging, PDF action plan. |
| [AIVEN.md](AIVEN.md) | Aiven for Valkey (shared cache, rate limiter, catalogue and graph) and Aiven for PostgreSQL (accounts). |
| [CODEX.md](CODEX.md) | How the team built with Codex, directed by Claude: per-machine task logs, models, time and tokens. |

## Evidence and measurements

| File | What it is |
|---|---|
| [BENCHMARK-CANONIZER.md](BENCHMARK-CANONIZER.md) | Benchmark of the canonizer against direct questions and Cala's MCP: 9/9 consistent answers versus at most 1/9 without it. |
| [CALA-CONSISTENCY-REPORT.md](CALA-CONSISTENCY-REPORT.md) | Report for Cala: the same question returns different answers, with evidence and a proposed fix. |

## How it works

| File | What it is |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System architecture: how the app stays fast on a slow, rate-limited API (catalogue preload, shared graph, fallback). |
| [SPEC-GRAPH-AFFINITY.md](SPEC-GRAPH-AFFINITY.md) | The local subgraph, the BFS over it and the 0–100 affinity score (six weighted signals). |
| [API.md](API.md) | Contract between the app and the backend: every endpoint, request and response. |

## Folders

| Folder | What it is |
|---|---|
| [brand/](brand/) | calado brand: colors, logo and mark (SVG). |
| [design/](design/) | Google Stitch prototype the app was designed from (screens: feed, detail, chat, context, profile). |
| [brand-references/](brand-references/) | Visual references from other products used to define the minimalist look. |
| [internal/](internal/) | Working notes: Cala API reading notes, field guide, the official Cala skill, early ideas and the canonizer spec. Not needed to evaluate the project. |

## Rest of the repository

| Folder | What it is |
|---|---|
| [app/](../app/) | The app (Expo / React Native Web), deployed on Vercel. |
| [backend/](../backend/) | FastAPI backend: accounts, chat and voice, feed and affinity, company pages, search, PDF report, Slush catalogue. See [backend/README.md](../backend/README.md). |
| [canonizador/](../canonizador/) | The canonizer and the Cala client (cache, shared rate limit, call caps), plus the benchmarks. See [canonizador/README.md](../canonizador/README.md). |
