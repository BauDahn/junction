# How calado uses Cala

**Short version:** Cala is the only source of facts in calado. Every investor, startup, round, lead investor, person and number on screen comes from Cala and carries its source. Gemini only interprets what the user says. Building on Cala, we measured that its knowledge endpoints answer the same question differently depending on wording, so we built a **canonizer** that turns any phrasing into one canonical query (9 of 9 questions consistent, against 0 to 1 of 9 without it). We then wrapped Cala in a local graph, a shared cache and call caps, so the app is fast and cannot exhaust the API key.

All numbers were measured on 14–15 November 2026 against the real API (`https://api.cala.ai/v1`). The full evidence is in Spanish in [BENCHMARK-CANONIZADOR.md](BENCHMARK-CANONIZADOR.md) and [INFORME-ERROR-CALA.md](INFORME-ERROR-CALA.md); this page summarizes it in English.

## 1. Which Cala endpoints we use, and for what

| Endpoint | What we use it for | Where in the code |
|---|---|---|
| `GET /v1/entities?name=` (entity search) | Resolve a company or fund name to its Cala id; search companies outside our catalog | `canonizador/canonizador/resolve.py`, `GET /api/search` in `backend/api/routes.py` |
| Entity retrieval (properties and typed relations) | The graph: `INVESTED_IN`, `PARTICIPATES_IN_FUNDING_ROUND` (with `role` and `is_lead`), `FOUNDED`, `IS_CEO_OF`, board and employment relations, `PARTICIPATES_IN_EVENT`, each edge with its sources | `backend/graph/loader.py`, `backend/catalog/ingest.py` |
| `POST /v1/knowledge/query` | Canonical structured queries built by the canonizer from fixed templates | `canonizador/canonizador/plan.py`, `canonizador/canonizador/api.py` |
| `POST /v1/knowledge/search` | Last resort for open questions; Cala's answer and its sources are shown as they are | `backend/cala_core/executor.py` |

Slush 2026 comes from Cala itself: the incoming `PARTICIPATES_IN_EVENT` relation of the Slush 2026 entity lists **2,990 attendees**, fetched in 36 s as 30 pages of 100 (`backend/catalog/ingest.py`).

## 2. Cala as the core of the product

| Product feature | What Cala provides |
|---|---|
| Event page (ranked investors or startups) | The Slush 2026 attendee list, and for each attendee its rounds, investors and founders. Whoever has outgoing `INVESTED_IN` is treated as an investor; whoever has rounds with `role: ISSUER` as a startup. Loaded so far: **2,110 of 2,990** attendees (47 investors, 1,060 startups) |
| Affinity score 0–100 (`backend/api/affinity.py`) | Every signal is computed from Cala data: sector 0.30, stage 0.20, region 0.15, ticket 0.15, recent activity 0.10, closeness in the graph 0.10. Each signal returns a sentence with its data and its Cala sources. Missing data is omitted, not counted as zero, and lowers `confidence` |
| Company page (`GET /api/entities/{id}`) | Key facts, funding rounds with leads and investors, people and portfolio, each with its source |
| Assistant (chat, text and voice) | Canonical answers from `knowledge/query`, entity data, or `knowledge/search` with sources. Claims the user makes ("Mews raised 50 million") are checked against Cala's evidence (`backend/cala_core/claims.py`) |
| Favorites PDF (`POST /api/favorites/report`) | The facts per company, each with its source. Gemini proposes an action plan from those facts only, labeled as AI-generated |

Gemini also tags the sector and stage of catalog companies, but only from the description Cala returns, and those tags are shown as "AI-tagged from Cala's description". They rank the feed; they are never shown as Cala facts.

## 3. What we found: same question, different answers

Nine questions of seven kinds (a specific round, founders, acquisitions, total funding, investors, executives, and three filtered lists), each written three ways (Spanish with accents, Spanish without accents or reordered, English). Five ways of asking Cala:

| | Direct search | Direct query | Agent over MCP | Agent over MCP with Cala's guide | Canonizer |
|---|---|---|---|---|---|
| What reaches Cala | The question as typed, to `knowledge/search` | The question as typed, to `knowledge/query` | Whatever a Codex agent connected to Cala's MCP server sends | The same, with Cala's official guide in the prompt | A query built from a fixed template, to `knowledge/query` |
| Distinct queries reaching Cala | 27 | 27 | 24 (the agent rewrites the question) | 32 distinct arguments in 35 calls | **9** |
| Questions with the same data in all 3 phrasings | **0 of 9** | **0 of 9** | **1 of 9** | **0 of 9** | **9 of 9** |
| Mean time per call | 33.6 s (max 61 s) | 34.8 s (max 65 s) | 29.1 s (max 66 s) | 34.0 s (max 70 s) | mostly cached in this run |

Examples of data that changed with wording (not just formatting):

| Question | Without canonizer (3 phrasings) | Canonizer |
|---|---|---|
| Factorial total funding | direct query: $420M · $572M / €523M · €523M | $572M every time |
| Glovo founders | 2 · 3 (with Gerard Olivé) · 2 | 2 (Oscar Pierre, Sacha Michaud) |
| Spanish hotel tech, > 10M | different company lists per phrasing | Amenitiz and Room00, always |

Direct `knowledge/query` also changes the shape of the rows: for the same question the company field came back as `company`, `name`, `empresa`, `investor` or `startup`, so a program cannot rely on field names.

What we learned about why (section 3 of the error report):

- **Cala caches by exact text.** Repeating the identical string returned the byte-identical JSON in **0.2–0.3 s** instead of 15–18 s. A paraphrase misses that cache and runs the full process again.
- **`context[].id` is generated per answer.** The same source article appeared under different ids in two phrasings; the ids are random UUIDs and the fact text is an excerpt tailored to the question. Entity ids, on the other hand, are stable.
- **Duplicate entities exist**: three "Leadwind" nodes (two Organizations and a Product), and "Point9" next to "Point Nine Capital".
- **One round amount is wrong in the structured data**: Amenitiz's Series B has `transaction_value` = 3,000,000,000 EUR, which is the bookings figure from the source article's title; the round was €38.9M. The round also has no investors or `is_lead` linked, although `knowledge/query` answers that Kfund led it.
- The entity search endpoint does **not** have the problem: "Telefónica" and "Telefonica" return exactly the same entities.

We could not verify from the API whether a new query creates nodes in Cala's graph; the report keeps that as a hypothesis.

## 4. The canonizer (`canonizador/`)

Principle: **the LLM only extracts the intent; code builds the query.**

| Step | Module | What it does |
|---|---|---|
| 1 | `normalize.py` | Unicode NFC, whitespace, strips `¿¡` and typographic quotes. Deterministic |
| 2 | `intent.py` | A small LLM call (Gemini by default) turns the question into a structured intent: entities, attribute (round, total funding, investors, founders, executives, acquisitions, company list) and filters in canonical English (`España` -> `Spain`, "10 millones" -> `10000000`). Cached, so the same phrasing never pays the model twice |
| 3 | `resolve.py` | Resolves each entity to its Cala id with `GET /v1/entities`, with a deterministic choice among candidates |
| 4 | `plan.py` | Builds the `knowledge/query` string from a fixed template per attribute, with fields in a fixed order. Same intent -> byte-identical query |
| 5 | `cache.py`, `client.py` | Cache keyed by the canonical query; pacing and retries (section 5) |
| 6 | cross-check | For rounds, compares the query answer with the entity's structured value and flags a discrepancy in `cross_check` instead of silently picking one |

Canonical queries it produced in the benchmark (the same string for all three phrasings):

```text
Amenitiz.funding_round.series=B.return(amount, lead investor, investors, date)
Glovo.founders.return(name)
Factorial.return(total funding)
startups.location=Finland.sector=fintech.funding>5M.return(name, funding, sector, location)
```

Result: **41 phrasings of 9 questions collapsed into 9 queries**, with an identical answer within each group. Because every phrasing maps to one key, the cache also starts hitting: without canonization it almost never would.

Limits we state openly: the canonizer guarantees consistency, not correctness (we did not verify which Glovo founder count is right); it depends on the LLM extracting the same intent, which it did for all 41 phrasings tested but is not a general guarantee; questions outside the known attributes use a less controlled fallback; and the sample is 9 questions with one run per mode.

## 5. Calling Cala safely: cache, rate limit, caps, live fallback

Cala's knowledge endpoints take 16–60 s and entity calls about 1 s; ten entity calls in about 3 s returned HTTP 429. One API key is shared by four developers and a public demo, so every call goes through the same client (`canonizador/canonizador/client.py`).

| Protection | How it works | Where |
|---|---|---|
| Two-layer cache | Disk first, then Aiven Valkey shared by every machine; a Valkey hit is copied to disk. Cala responses expire after 7 days (`CACHE_TTL_S`) | `canonizador/canonizador/cache.py` |
| Pacing per endpoint class | `knowledge/*` at most one call every 8 s, entities every 0.7 s with up to 2 in flight (`CALA_KNOWLEDGE_INTERVAL`, `CALA_ENTITIES_INTERVAL`, `CALA_ENTITIES_CONCURRENCY`) | `client.py` |
| One request per key | Identical concurrent requests share one in-flight call | `client.py` |
| 429 handling | Honors `Retry-After`; otherwise exponential backoff from `CALA_429_WAIT` (5 s), capped at 60 s | `client.py` |
| Shared rate limit | With Valkey, one counter per time window and endpoint class (`ratelimit:v1:cala:*`), so several machines do not add up against the same key | `client.py` |
| Daily call cap | Every real call is counted in Valkey (`calls:v1:<date>:*`, by endpoint class and by machine); above `CALA_DAILY_CALL_CAP` (default 2000) the client refuses and the API answers 503 | `client.py`, `backend/api/routes.py` |
| Per-run budget | The catalog loader stops after 150 real calls unless `--max-calls` is given | `backend/catalog/__main__.py` |
| Per-client limits | Defaults: company page 20 per minute and 200 per day, chat 10 per minute and 150 per day, search 30 per minute; HTTP 429 with `Retry-After` | `backend/core/abuse.py`, route handlers |
| Input checks and negative cache | Entity ids must be UUIDs before any Cala call; an id Cala does not know is remembered for one hour (`neg:v1:*`) | `backend/api/routes.py`, `backend/core/abuse.py` |
| Accounts for live calls | With `CALA_REQUIRE_AUTH=1` (set on the public backend) only signed-in users trigger live Cala calls; local catalog data stays available | `backend/api/routes.py`, `backend/chat/routes.py` |
| Usage visible | `/api/stats` reports Cala calls by class and by machine, with `ADMIN_TOKEN` | `backend/api/routes.py` |

Measured effect of the client optimizer: with the old fixed 8 s pause, 19 calls took 162 s. With per-class pacing, 40 distinct entity lookups ran at 1.89 calls/s and 30 at 1.33 calls/s, with **zero 429s** in three runs. Two processes sharing the Valkey rate limit made 40 calls in 27.9 s (1.43 calls/s combined) with zero 429s ([PROCESO.md](PROCESO.md)).

**Live fallback, never a dead end.**

- **Assistant** (`backend/cala_core/executor.py`): canonizer -> entity lookup and retrieval -> `knowledge/search` -> a `not_found` block listing every Cala call it tried. `execute` never raises.
- **Company page** (`GET /api/entities/{id}`): an entity outside the catalog and the graph is fetched live (one retrieval plus up to its three latest rounds, so at most 4 calls), stored with a TTL, and served with zero Cala calls the next time. 404 if Cala does not know it, 502 if Cala fails, 504 after about 25 s.
- **Search** (`GET /api/search`): the local catalog first, then Cala's entity search, without duplicates.

**Local graph.** Entity relations are stored as nodes and edges with their sources (`backend/graph/`). Traversal is local: a full BFS over a 185-node subgraph takes **0.13 ms**, so Cala is only called at the edge of what is already known.

## 6. What we would ask Cala to change

From section 7 of the error report:

1. Canonicalize queries before caching and retrieval (Unicode and accents, entity ids, a key per intent instead of per exact text). The entity endpoint already ignores accents; the knowledge endpoints do not.
2. Make `context[].id` stable for the same passage, so clients can deduplicate and compare answers.
3. Merge duplicate entities ("Leadwind", "Kfund's Leadwind fund"; "Point9", "Point Nine Capital").
4. Validate round amounts at extraction (Amenitiz Series B recorded as €3B).
5. Link investors and `is_lead` on funding rounds, since `knowledge/query` already knows the lead.
6. Document the cache, the rate limit (and send `Retry-After` on 429), the expected latency, and whether queries modify the graph.
7. Deterministic default order and fields in `knowledge/query` when the query has no `return(...)` or `order_by`.

## 7. Reproduce

```bash
cd canonizador
uv sync --extra dev
uv run python -m canonizador "Who led Amenitiz's Series B?"
uv run python bench.py              # the 9 x 3 benchmark, resumable; writes bench/results.json
python3 bench_mcp.py [--guia]       # the MCP agent runs, with or without Cala's guide
uv run pytest                       # canonizer tests, no network
```

These call the real Cala API and need `CALA_API_KEY` in `backend/.env`. Questions are in `canonizador/bench/questions.json`; raw results of our runs are in `canonizador/bench/`.
