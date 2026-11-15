# Report: Cala returns different answers to the same question

Junction 2026, Cala challenge. Measurements from 14/11/2026 against the live API (`https://api.cala.ai/v1`).
Audience: our team and the Cala team.

## Summary

1. The same question, phrased in equivalent ways (with or without accents, reworded, or in another language), makes Cala retrieve different sources and, for list queries, return different companies and figures.
2. Identical text always returns the same result: the variation depends on the wording, not randomness.
3. We measured that an exact repeat is served in 0.2–0.3 s with identical JSON (compared with 15–18 s the first time), and that `context` ids are generated per response: they do not identify stable facts.
4. We could not verify through the API whether a new query creates entity nodes in the graph; the public documentation neither confirms nor denies this. Persistent duplicate entities do exist (three "Leadwind" nodes).
5. Our solution: a canonicalizer that reduces each question to an intent and always builds the same query. 41 phrasings of 9 questions → 9 queries, with an identical response within each group.

## 1. The problem

Users do not phrase a question the same way twice. "¿Cuánto levantó Amenitiz en su Serie B?" (How much did Amenitiz raise in its Series B?), "cuanto levanto amenitiz en la serie b" (how much did Amenitiz raise in the Series B), and "How much did Amenitiz raise in its Series B?" are the same question. Cala treats them as three unrelated queries: each goes through the full process, retrieves different sources, and can produce a different answer. For a product that displays sourced data, this means two users (or the same user twice) see different answers, and each new phrasing costs a slow call against a low usage limit.

## 2. Evidence from our measurements

### 2.1 `POST /v1/knowledge/search`: Amenitiz Series B, 4 variants

| Variant | Facts (`context`) | Facts in common with variant 1 | Entities |
|---|---|---|---|
| 1. Spanish with accents | 5 | (reference) | 6 |
| 2. Spanish without accents | 4 | 0 | 12 |
| 3. Rephrased Spanish | 3 | 0 | 10 |
| 4. English | 4 | 0 | 10 |
| Control: variant 1 repeated identically | 5 | 5 (the same ones) | 6 (the same ones) |

The entity sets also differ between variants. The Amenitiz entity id (`db95edaa-058f-494d-a4f4-5f56bf81afd9`) was the same in all 7 queries, and `entity_search` for "Amenitiz" returns a single Company with that name.

### 2.2 `GET /v1/entities?name=`: no issue

| Queried pair | Result |
|---|---|
| "Telefónica" / "Telefonica" | exactly the same entities |
| "Inditex" / "Indítex" | exactly the same entities |
| "Société Générale" / "Societe Generale" | exactly the same entities |

Name search already ignores accents. The problem is with the knowledge endpoints, not the entity endpoint.

### 2.3 `POST /v1/knowledge/query` using the official guide and an LLM translating freely

We used Cala's official guide (`docs/internal/CALA-SKILL.md`) and let an LLM translate each question into a query.

| Question | Variants | Queries generated | Result |
|---|---|---|---|
| Amenitiz Series B | 4 | 4 different strings (`return(...)` changes) | Matching data: €38.9M, lead investor Kfund |
| Spanish hotel technology startups with more than 10 million | 3 | 3 different strings | Different results (table below) |
| Same exact string, repeated 3 times | 1 | 1 | Identical result all 3 times |

Filter results by variant:

| Variant | Companies returned |
|---|---|
| A | Amenitiz ~€77M, Room00 |
| B | Amenitiz ~€72M+, Lodgify |
| C | Amenitiz ~$83M (~€76M) |

### 2.4 Entity endpoints: round data

- Amenitiz's Series B round (FundingRound `5cd44a46-1403-5170-98f1-f8d866cfce8e`) has `transaction_value` = 3,000,000,000 EUR, sourced from eu-startups: an article titled "...processes €3 billion in bookings ahead of new €38.9 million funding". The bookings figure was taken as the round amount.
- The round is linked only to the issuer (Amenitiz), with no investors and no `is_lead`. However, `knowledge_query` does say that Kfund led it.

### 2.5 Usage limit and latency

- After ~7 consecutive calls: HTTP 429 for ~1 minute.
- Latency: 11–17 s for `knowledge_search`, 16–45 s for `knowledge_query`.

## 3. Are new nodes or paths created when an unseen query arrives?

We separate four levels of certainty. Only (a) is our own measurement.

### (a) Measured by us (additional experiment, 6 calls, no 429)

A new question about Swappie's Series B (Finland) in `knowledge/search`: once in English, repeated identically, and once in Spanish. Also, variant 1 of Amenitiz repeated later the same day, and two entity searches.

| Observation | Data |
|---|---|
| New question, first time | 15.5 s, 5 facts |
| Same string, repeated | 0.3 s; complete JSON identical (same ids, same text) |
| Amenitiz variant 1, repeated later the same day | 0.2 s; same 5 fact ids and same 6 entities |
| Spanish paraphrase of the new question | 18.4 s; 5 facts, **0 ids in common** with the English version |
| Source documents (URLs), English vs. Spanish | 5 and 5; only 1 in common (privateequitywire.co.uk) |
| Entities, English vs. Spanish | 11 and 12; 10 in common; same id for Swappie |
| Answer | Essentially matching (June 2020 Series B, $40.6M / €35.8M, same investors) |

Three conclusions are supported by these data:

1. **There is an exact-text response cache.** An identical repeat takes 0.2–0.3 s instead of 15–18 s and returns byte-for-byte identical JSON. A paraphrase misses that cache and runs the full process again. This explains the control in section 2.1.
2. **`context` ids are generated per response; they do not identify a stored fact.** The same privateequitywire article appears in both variants with different ids (`0f4a2f66-…` and `582ea4d0-…`). The fact text matches for the first 504 characters and, after a `[...]`, continues with a different excerpt from the same article depending on the question (the financial adviser in one, the founders in the other). The 10 observed ids are version 4 UUIDs (random). In other words, the KnowBit content is an excerpt tailored to the query.
3. **Entity ids are stable across variants, but persistent duplicate entities exist.** `GET /v1/entities?name=Leadwind` returns three nodes for the same thing: "Kfund's Leadwind fund" (Organization, `c10b7226-…`, described as "a venture capital fund that led the Series B financing of hospitality software company Amenitiz"), "Leadwind" (Organization, `37ea4d4a-…`) and "Leadwind" (Product, `99140378-…`). The Amenitiz variants also included "Point9" (`3fb8df43-…`) and "Point Nine Capital" (`c934f7e3-…`).

Implication for our own evidence: "0 facts in common" (section 2.1) is true, but overstates the divergence because ids change even when the document is the same. A fairer measure is overlap in source documents, which is low but not zero (1 of 5 for Swappie).

What we **could not** measure: whether any of those entity nodes were created as a result of a query. The API does not expose the node's creation date or origin, and with 6 calls it was not possible to verify that an entity did not already exist.

### (b) Observed by the team in Cala's tool (not verified through the API)

The team reports that Cala's tool shows the graph expanding when a query has no existing answer, and that if two equivalent queries are not recognized as identical, unnecessary paths and nodes are created. We could not reproduce or refute this through the public API. It would be useful to document it with screenshots and confirm it with the Cala team.

### (c) What the public documentation says

| Source | Direct quote |
|---|---|
| https://cala.ai | "Cala pre-processes the world's public information into verified, structured facts — so agents query knowledge, not chaos." |
| https://docs.cala.ai/index.md | "Cala abstracts away ingestion, normalization, and verification behind a simple API" |
| https://docs.cala.ai/index.md | "It's a verified entity graph made of typed entities with structured fields, deterministic queries" |
| https://api.cala.ai/openapi.json (schema `KnowBit`) | "A KnowBit is like a fact, a piece of information that supports the answer." |
| https://api.cala.ai/openapi.json (`KnowBit.origins`) | "The origins from which the KnowBit was extracted." |
| https://api.cala.ai/openapi.json (`GET /v1/entities`) | "spans many domains and keeps growing" |
| https://api.cala.ai/openapi.json (`knowledge/search`) | "Best when you have a question and want a researched narrative with citations" |
| https://docs.cala.ai/features/structured-answer.md | "Input can be a Cala QL expression or a natural-language question — both produce the same structured response shape." |
| https://github.com/cala-ai/entity-watch-demo (README) | "Responses are cached in the `cala_cache` table so repeat views are instant." |

What we **did not** find in any of these sources (docs.cala.ai and its `llms.txt`, the OpenAPI, the `cala-skill`, `cala-claude-plugin`, `entity-watch-demo`, and `cala-n8n-node` repositories, or the cala.ai website):

- No description of on-demand graph expansion or what happens when a query has no existing answer.
- No mention of Cala-side caching or consistency across phrasings or languages. The phrase "same response shape" refers to the response structure, not its content.
- No ingestion details. The term "KnowBit" appears only in the OpenAPI schema.
- The website has FAQs ("How does Cala stay accurate?", "How fresh is the data?", "Where does Cala's data come from?") whose answers load dynamically; we could not read them. We found no blog.

Two useful points of context. The public wording ("pre-processes") describes a graph prepared in advance, not one that grows with every query. And Cala's own reference application (`entity-watch-demo`) already applies the idea we propose: it builds the query from a fixed template and stores the response under a structured key (`ew_${companyId}_${topicId}_${period}`), not under the free text.

### (d) Hypotheses (unproven)

- **H1.** `knowledge/search` combines the graph with passage retrieval at query time, and the `context` KnowBits are assembled then. Supporting evidence: different excerpts from the same document depending on the question, random ids per response, 15–18 s latency. Not confirmed by Cala.
- **H2 (the team's hypothesis).** A query with no existing answer causes the graph to expand with new nodes and paths. This is consistent with what we measured (duplicate entities such as "Kfund's Leadwind fund", whose name and description come from a mention in a text), but those duplicates may also originate during article ingestion. We have no way to distinguish this from the outside.
- **H3.** If H2 is true, every unrecognized phrasing creates redundant work and records. Even if H2 is false, the measurements are enough to establish a cost: each new phrasing repeats the full process (15–18 s) and occupies its own cache entry.

In summary, it is measured that each new phrasing produces a new response, with new fact records. It is not measured that it produces new nodes in the entity graph.

### Context: knowledge graphs and query canonicalization

In GraphRAG-style systems, an LLM extracts entities and relationships from documents and builds the graph during indexing; a query traverses it. Some designs update it incrementally as new information arrives. In all of them, entity resolution is a delicate point: if two mentions of the same object ("Point9" and "Point Nine Capital") are not recognized as identical, the graph accumulates duplicate nodes and paths are split between them. The same applies to queries: without a canonical form, two equivalent questions do not share a cache entry or result.

- Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" (Microsoft GraphRAG): https://arxiv.org/abs/2404.16130
- Guo et al., "LightRAG: Simple and Fast Retrieval-Augmented Generation" (incremental graph update): https://arxiv.org/abs/2410.05779
- Rasmussen et al., "Zep: A Temporal Knowledge Graph Architecture for Agent Memory" (graph that grows by episodes, with entity resolution on insertion): https://arxiv.org/abs/2501.13956
- GPTCache (semantic cache for LLM queries): https://github.com/zilliztech/GPTCache

Canonicalization addresses the problem before the call: normalizing the text, resolving entities to an id, and reducing the question to a stable key makes every phrasing use the same query and cache entry.

## 4. The solution: canonicalizer (`canonizador/`)

Full design in `docs/internal/SPEC-canonizador.md`. Principle: **the LLM only extracts the intent; code builds the query.**

| Step | Module | What it does |
|---|---|---|
| 1 | `normalize.py` | Unicode NFC, whitespace, removes `¿¡` and typographic quotation marks. Deterministic. |
| 2 | `intent.py` | A small LLM converts the question into a structured intent: entities, attribute (round, total funding, investors, founders, executives, acquisitions, company list…) and filters. Filters use canonical English: "España" (Spain) → `Spain`, sector as a fixed lowercase value, "10 millones" (10 million) → `10000000`. |
| 3 | `resolve.py` | Resolves each entity to its id with `GET /v1/entities` (which already ignores accents), using a deterministic choice among candidates. |
| 4 | `plan.py` | Builds the `knowledge_query` query with a fixed template for each attribute, with `return(...)` fields in a fixed order and the entity's canonical name. Same intent → same string, byte for byte. |
| 5 | `cache.py`, `client.py` | Disk cache keyed by the canonical query; one call at a time and wait on a 429. |
| 6 | cross-check | For rounds, compares the `knowledge_query` response with the entity's structured value (`transaction_value`, participants with `is_lead`) and marks the discrepancy in `cross_check` instead of silently choosing one. |

## 5. Measured results

| Test | Phrasings | Queries to Cala | Result |
|---|---|---|---|
| 2 questions | 20 | 2 | Identical response within each group |
| 7 question types | 21 | 7 | Identical response within each group |

The 7 types: Glovo founders, Mews acquisitions, Factorial total funding, Wolt investors, TravelPerk executives, list of fintech companies in Finland with more than 5M, and list of climate tech companies in Germany with more than 20M.

The entity cross-check detects the Amenitiz Series B discrepancy (3,000M EUR in the entity versus €38.9M in `knowledge_query`).

Side-by-side benchmark (9 questions × 3 phrasings, direct versus canonicalized, with examples of different figures in direct mode): `docs/BENCHMARK-CANONIZER.md`.

## 6. Limitations

- We verified **consistency** (same intent → same response), not the **truthfulness** of each response.
- The canonicalizer depends on the LLM extracting the same intent from each phrasing. It did so for the 41 phrasings tested; this is not a general guarantee.
- Questions outside the known attributes use a fallback path with a canonical English question, which is less controlled.
- The experiment in section 3 is one new question with one paraphrase. It is enough to show the cache and id mechanism, but not to quantify it.
- We cannot see inside Cala: claims about node creation remain hypotheses unless Cala confirms them.

## 7. Recommendations for Cala

1. **Canonicalize the query before caching and retrieval**: normalize Unicode and accents, resolve entities to their ids, and use a key per intent, not per exact text. The entity endpoint already ignores accents; the knowledge endpoints do not.
2. **Stable fact ids**: make `context[].id` identify the passage or fact (for example, derived from the document and excerpt), so clients can deduplicate and compare responses.
3. **Merge duplicate entities**: "Leadwind" / "Kfund's Leadwind fund" / "Leadwind" (Product); "Point9" / "Point Nine Capital".
4. **Validate amounts when extracting rounds**: Amenitiz's Series B is listed as 3,000,000,000 EUR (the bookings figure). A consistency check against the source title would have caught this.
5. **Link investors and `is_lead` to the round**, since `knowledge_query` knows the lead investor (Kfund) and the entity does not.
6. **Document** caching, the usage limit (how many calls per minute; include `Retry-After` in the 429), expected latency, and whether queries modify the graph.
7. **Deterministic default ordering and fields** in `knowledge_query` when the query does not include `return(...)` or `order_by`.

## 8. How to reproduce

Requirements: `CALA_API_KEY` in `backend/.env` (not printed or saved in the repository). The API accepts only a few consecutive calls: make them one at a time and wait about 15 s between calls.

**Problem (direct text to Cala).** Send each phrasing and compare `context[].id`, the URLs in `context[].origins[].document.url`, and `entities[].id`:

```sh
curl -s -X POST https://api.cala.ai/v1/knowledge/search \\
  -H "X-API-KEY: $CALA_API_KEY" -H "Content-Type: application/json" \\
  -d '{"input": "¿Cuánto levantó Amenitiz en su Serie B y quién lideró la ronda?"}'
```

Equivalent phrasings to test:

- "¿Cuánto levantó Amenitiz en su Serie B y quién lideró la ronda?" (How much did Amenitiz raise in its Series B and who led the round?)
- "quien lidero y de cuanto fue la serie b de amenitiz" (who led Amenitiz's Series B and how much was it?)
- "How much did Amenitiz raise in its Series B and who led the round?"
- "¿Qué startups españolas de tecnología hotelera levantaron más de 10 millones?" (Which Spanish hotel technology startups raised more than 10 million?)
- "mas de 10 millones levantados startups hoteleras tecnologia españa" (more than 10 million raised Spanish hotel technology startups)
- "Which Spanish hotel tech startups have raised more than 10 million?"

Repeating one without changing anything shows the exact-text cache (response in under 1 s, identical JSON).

**Duplicate entities.**

```sh
curl -s "https://api.cala.ai/v1/entities?name=Leadwind&limit=10" -H "X-API-KEY: $CALA_API_KEY"
```

**Solution (canonicalizer).**

```sh
cd canonizador && uv sync --extra dev
uv run python -m canonizador "¿Cuánto levantó Amenitiz en su Serie B y quién lideró la ronda?"
uv run python -m canonizador "quien lidero y de cuanto fue la serie b de amenitiz"
uv run python -m canonizador "How much did Amenitiz raise in its Series B and who led the round?"
```

All three outputs should show the same query and result; the second and third reuse the cache and do not repeat the knowledge query. The complete groups of phrasings are in `canonizador/bench/questions.json` and are run with `uv run python bench.py`. Offline tests: `uv run pytest`.
