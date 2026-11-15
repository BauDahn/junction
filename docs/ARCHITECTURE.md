# Architecture: how to make Cala Match fast

Complements `docs/SPEC-GRAPH-AFFINITY.md` (what we store and how affinity is calculated). This covers the system: where the data comes from, what runs in the background, and how latency stays low within Cala's limits and with Aiven. All measurements are from 14/11 against the live API; anything marked *(estimated)* was not measured.

## 1. Measurements that shape the design
| Fact | Number |
|---|---|
| Entity call (`entity retrieval`) | 0.9–1.3 s |
| `knowledge/query` and `knowledge/search` | 16–60 s |
| Entity usage limit | 10 calls in ~3 s returned 429; 30 calls spaced 0.7 s apart returned none (~1.4 sustained calls/s) |
| **Slush 2026 complete** | **2,990 attendees** (2,982 `Company`, 7 `Organization`, 1 `EducationalInstitution`, no `Person`; `role` is always `ATTENDEE`), fetched in **36 s** across 30 pages of 100 (`limit` and `offset` work, with no overlap) |
| Retrieval **without introspection** using a relationship that does not exist in the list | works: Cala ignores the nonexistent relationship and returns no error. Amenitiz: 1.3 s, 18 investors, 3 founders and its round |
| Aiven Valkey (version 9.1.3) | RTT ~29 ms; **200 reads in a pipeline: 31 ms**, one at a time: ~28 ms each; 6.5 MB used out of 2.43 GB; `noeviction` policy |
| BFS over the in-memory subgraph | 0.13 ms (185 nodes), 337 ms (100,000 synthetic nodes) |

Two consequences: **(a)** reading one node at a time from Valkey costs 28 ms per node, so we must read in batches; **(b)** because `noeviction` does not remove anything automatically, everything needs a TTL and the catalog needs a cap.

## 2. Decisions
1. **Precomputed catalog + live per-user layer.** The demo universe is finite: Slush's 2,990 attendees. It is calculated once in the background and shared in Valkey. The feed comes from there without calling Cala. What the user does live (their profile, questions, or a node outside the catalog) is a small layer on top.
2. **A single gateway to Cala.** Everything goes through one component with a priority queue, rate limits per endpoint type, only one in-flight request per key (if two users ask for the same thing, there is only one call), and automatic adjustment when 429 occurs. This is what delivers #63.
3. **Valkey is the graph store; process memory is only a hot cache.** Read in batches, one level at a time; never one node at a time.
4. **No introspection.** Today, each expansion takes 2 calls (introspection and retrieval). Since Cala ignores relationships that do not exist, we request the whitelist of relationships directly: **half the calls** for the same result. *(Measured on two entities; this needs confirmation with people and funds.)*
5. **Gemini normalizes text; Cala provides the facts.** Gemini tags each startup's sector and stage using the `description` already returned by Cala. This **does not use Cala quota** and runs in parallel. The tags are used for matching and shown as "AI-tagged from Cala's description" with the source of that description; figures, rounds, investors and people still come only from Cala.
6. **Progressive feed.** The screen never waits: it shows whatever is available and fills in the rest on its own (section 5). The affinity `confidence` honestly reflects how much data is missing.
7. **All background work is resumable and prioritized.** If it does not finish before the demo, completed work is used and missing work lowers `confidence`.
8. **Demo fallback**: a file containing the exported catalog, which can be reloaded into Valkey with a command if Cala or Aiven fails.
9. **Visible metrics** (`/api/stats`): Cala calls by type, 429s, cache-layer hits, queue depth, time to first card. These are the pitch numbers.

## 3. Components
```
 Web app ──REST/polling──► FastAPI (one process, asyncio)
                              │
        ┌─────────────────────┼─────────────────────────┐
   feed / detail         chat (router + canonicalizer)  context (PDF, voice → Gemini)
        │                     │                          │
        └──────────► Graph store (batches, views) ◄──────┘
                              │         ▲
                   hit        │         │ writes nodes and edges
              ┌───────────────┘         │
         memory (LRU) → Valkey (Aiven)  │
                              │ miss    │
                              ▼         │
                        Cala gateway ───┘   per-endpoint limit, priority,
                   (interactive > prefetch > batch)  one request per key, AIMD on 429
                              │
                          Cala API          Gemini (tags, router, audio, PDF)

 Background jobs (same process, asyncio tasks, state in Valkey):
   catalog-sync  → Slush attendees, each one's profile, Gemini tags
   frontier      → per-user expansions and prefetch of what is displayed
```
**Why one process and no external queues:** there are four people and one night. One asyncio process with state in Valkey is enough; if two machines are running, the rate limit is shared in Valkey (per-second counter with `INCR` and 2 s expiry) so their calls against the same Cala key do not add up.

## 4. The catalog (the big change)
**Stage 1, the list (36 s, already tested).** Incoming `PARTICIPATES_IN_EVENT` from Slush, 30 pages. Returns 2,990 ids and names.

**Stage 2, each entity's profile (1 call per entity).** Direct retrieval with `properties` (description, `funding_stage`, `total_funding`, employee range, headquarters, website) and relationships: incoming and outgoing `INVESTED_IN`, outgoing `PARTICIPATES_IN_FUNDING_ROUND`, incoming `FOUNDED`, all with `limit` 100. That single response provides:
- **Who is an investor and who is a startup.** Slush does not distinguish them (almost everything is `Company`): an entity with outgoing `INVESTED_IN` is an investor; one with rounds where `role: ISSUER` is a startup. Some are both.
- Subgraph edges (rounds, investors, founders) with their sources.
Cost: 2,990 × ~1.3 s ≈ **65 min sequentially; about 22 min with 3 in parallel** *(estimated; depends on the actual limit measured by #63)*. This is the work to start running tonight; it can resume.

**Stage 3, Gemini tags.** From each company's description: sector, stage, customer type and region. In parallel with stage 2, without using Cala quota. ~3,000 short calls to the fast model.

**Stage 4, enrichment (best effort).** Portfolio sectors and stages for the investors most relevant to the demo profile. Work by priority (investors with the strongest match to the demo user first) and stop when time runs out. One `knowledge/query` per investor (16–60 s), only for the 20–30 most relevant, in parallel with the rest because it uses a different endpoint.

**Keys**: those in `SPEC-GRAPH-AFFINITY.md`, plus `cat:v1:status` (stage and progress), `cat:v1:todo` (set of ids pending per stage) and `cat:v1:feat:<id>` (features already extracted for affinity calculation: sector, stage, region, amount range, activity).

**Size**: ~3,000 catalog nodes and around 15–25 thousand neighboring nodes and edges at ~0.4 KB each is **on the order of 10 MB**, compared with the 2.43 GB available. Memory is not a problem; everything does need a TTL because of the `noeviction` policy.

## 5. Latency budget
| Action | Target | How it is achieved |
|---|---|---|
| Open the feed | first card in < 1.5 s, full feed in < 3 s | Affinity calculated from features already extracted from the catalog (in-memory calculation, milliseconds) + one batch read from Valkey (~30 ms) |
| Switch mode (Raising / Investing) | < 500 ms | Same catalog, different filter: already in memory |
| Newly created profile | feed with low `confidence` immediately; rises in 10–30 s | Profile constraints (sector, stage, region, ticket) rank the catalog instantly; graph signals (proximity) arrive later |
| Open detail | < 500 ms if in the catalog; < 3 s if not | Edges already stored with sources; if anything is missing, 1 direct retrieval with interactive priority |
| Chat question Cala must resolve (canonicalizer) | 16–60 s, unavoidable | First answer from the graph if available (ms) and show "looking it up in Cala"; Cala's answer completes the card when it arrives |
| Question about something already in the graph (for example "who led Amenitiz's Series B?") | < 1 s | Comes from the graph with `is_lead` and sources, without calling Cala |

**Screen updates**: poll every 2 s while work is pending; each card has `score` and `confidence` and updates in place. SSE if there is time.

## 6. Build order
**Tonight (what unlocks everything)**
1. Gateway with per-endpoint limits, one request per key and short waits on 429 (#63, `fabricio`). Initial value: 1.4 calls/s for entities.
2. Graph store in Valkey with batch reads and TTL (#64, `fabricio`). Publish the interface first (`get_nodes(ids)`, `neighbors(ids)`, `put_expansion(...)`) so others can program against it.
3. Catalog job, stages 1 to 3, resumable (new issue, `gabriel`). Launch as soon as the interface in point 2 exists and let it run all night.

**Early tomorrow**
4. Feed and detail endpoints over the catalog (#65, `fabricio`).
5. App with feed and detail using real data (#62, `adrian`).
6. Calibrate affinity weights with 10 known pairs (`bau`).
7. Stage 4 and the per-user prefetch queue.

**If there is time**: introduction path between people (requires expanding to `Person`: the Slush catalog has no people, so they would need to be added from `FOUNDED` and `IS_CEO_OF`), SSE and learned weights.

## 7. Risks
| Risk | What we do |
|---|---|
| The actual limit is lower than 1.4 calls/s at peak hours or with several machines | Shared limit in Valkey and automatic adjustment; the catalog resumes on its own and whatever is available is used |
| The catalog does not finish before the demo | Prioritized stages; the feed works with completed data and `confidence` says so. Before the demo, freeze a backup file |
| Gemini tags a sector incorrectly | Tags only sort the feed; they are never shown as Cala data. Omit the signal if uncertain |
| Aiven goes down or fills up | Continue with memory and disk; everything has a TTL because of `noeviction`; the file backup reloads the catalog |
| Two machines fill the catalog at once | One owner for the job (marked with `SET NX` in Valkey); the other only reads |
| Stale data | Each node and edge stores `loaded_at`; detail shows it ("loaded Nov 14") |

## 8. Open questions
- Is the 429 limit per key, per IP or per endpoint? This changes how much parallelism we can use. #63 will measure it.
- How many of the 2,990 are investors? Stage 2 will tell us; if there are few, Raising mode has a short catalog and it is worth adding neighboring funds (investors in attendees' rounds).
- Is `is_lead` always present in rounds? `bau` will ask at the Cala booth.

## 9. If something is not in the graph (on main since 15/11)
Rule: never make things up and never stop after the first failure.
| Where | What it does |
|---|---|
| **Chat** (`cala_core/executor.py`) | `execute` never raises. Canonicalizer → entity search (`entities`, `retrieve`) → `knowledge_search` → `not_found` with the list of attempted steps, including the one that failed |
| **Detail** (`GET /api/entities/{id}`) | Outside the catalog and graph: `graph.loader.expand_node` fetches the Cala entity (one retrieve, no introspection) and stores it with a TTL; next time, zero calls. 404 if Cala does not know it, 502 on failure, 504 if it takes more than ~25 s |
| **Search** (`GET /api/search?q=`) | First the local catalog, then Cala (`entities` for Company and Organization), with no duplicates and no 500. Cala results appear as type `other` until their detail is opened |
Measured against live Cala on 15/11: search 1.5 s; live Amenitiz detail with 7 people; 215 tests.

## 10. Events (next architecture change)
The new web app is organized around **events** (Explore and My events). Today the catalog is **just one, Slush 2026**: the event id is fixed in `backend/catalog/ingest.py` and the `cat:v1:*` keys are global. To save multiple events, the event must be parameterized and keys and state must be **per event**. Live Cala data: Slush 2026 has 2,990 participating companies; Slush 2025 has only 8 speakers and no participant list.
