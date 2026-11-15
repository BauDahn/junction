# Spec: Cala query canonicalizer

## Problem (measured on 14/11 against `POST /v1/knowledge/search`)
The same question, written with accents, without accents, rephrased, or in English, retrieves different facts: 0 facts in common across variants (5, 4, 3, and 4 facts), different entity sets, and answers with different levels of detail. Repeating the exact same text does return the same result (5/5 facts), so the result depends on the wording, not chance. `GET /v1/entities?name=` does not have this problem ("Telefónica" = "Telefonica"). The usage limit is also low: after ~7 consecutive calls, HTTP 429 occurred for ~1 min.

## Goal
Same intent → same Cala calls → same answer, regardless of accents, wording, or language. And fewer calls (cache by intent).

## Design (Python package in `canonizador/`, with uv, independent of `backend/`)
1. `normalize.py`: Unicode NFC, whitespace, remove `¿¡`, typographic quotation marks. Deterministic.
2. `intent.py`: a small LLM converts the question into a structured intent:
   `{entities: [{name, type: Company|Person|Event|Investor}], attribute: funding_round|total_funding|investors|lead_investors|founders|executives|headcount|acquisitions|profile|event_attendees|other, filters: {round_label?, year?}}`.
   Rules: proper names exactly as they appear (do not translate), `round_label` in Cala's code (SEED, SERIES_A, SERIES_B…). LLM provider configurable as in `backend/verifier/llm.py` (by default `codex exec` with `gpt-5.6-luna` and low effort; NVIDIA too), with disk cache.
3. `resolve.py`: resolves each entity to its id with `GET /v1/entities?name=&entity_types=` (already ignores accents). If there are multiple candidates, choose deterministically (exact name match or normalized alias; otherwise the first) and return the alternatives.
4. `plan.py`: for known attributes, **deterministic plan using entity endpoints** (see `docs/internal/CALA-CAMPOS.md`), which is the path Cala recommends:
   - `funding_round` / `lead_investors`: company → `PARTICIPATES_IN_FUNDING_ROUND` (role ISSUER) → round matching the filters → properties + incoming participants with `is_lead`.
   - `total_funding`, `profile`, `headcount`: Company properties and series.
   - `investors`: incoming `INVESTED_IN`. `founders`/`executives`: `FOUNDED`, `IS_CEO_OF`… `acquisitions`: `PARTICIPATES_IN_CORPORATE_EVENT`. `event_attendees`: incoming `PARTICIPATES_IN_EVENT` from the event.
   - `other`: fallback with `knowledge/search` using ONE canonical question in English generated from a template based on the intent (not the user's text).
   Verify the route and retrieval body against the real API (`POST /v1/entities/{id}` with `{properties, relationships: {incoming|outgoing: {TYPE: {limit, offset}}}, numerical_observations}`) and introspection (`GET /v1/entities/{id}/introspection`); adjust if it differs.
5. `cache.py`: disk cache; key = hash of the canonical intent (sorted entity ids + attribute + filters). All variants of a question hit the same entry.
6. `client.py`: Cala client with **only one call at a time**, retries with backoff on 429/5xx (waits of 20, 40, 80 s), and cache of each raw response.
7. Public API: `answer(question) -> {intent, entity_ids, plan, result: structured data with sources, cache_hit, cala_calls}`. CLI: `uv run python -m canonizador "question"`.

## Benchmark (`bench.py`) → `canonizador/REPORT.md`
- `bench/questions.json`: groups of variants of the same question (with accents, without accents, rephrased, English, Catalan). Start with 3 groups: Amenitiz Series B and who led it; Mews total funding; founders of a company with data.
- For each group, two modes: **direct** (text as-is to `knowledge/search`) and **canonicalized**.
- Metrics per group: mean Jaccard across variants for (a) returned fact or entity ids and (b) key answer values (amount, lead); number of Cala calls; latency.
- The report includes the before/after table and commands to reproduce it. It must be presentable to the Cala team as-is (in English).
- Respect the limit: everything sequential and cached; the benchmark must be resumable.

## Rules
- `CALA_API_KEY` is loaded from `backend/.env` (or the environment). Never print it.
- Tests with fake clients (no network): normalization, same cache key for variants, deterministic resolution, plans.
- Short README in `canonizador/`.

## Done when
- `uv run pytest` passes.
- `uv run python -m canonizador` returns the same result for the 4 Amenitiz variants (same ids, same amount and lead), with only one batch of Cala calls.
- `REPORT.md` generated with real data.

## Phase 2 (14/11): fixed-template query using `knowledge_query`
Measured: with the official guide (`docs/internal/CALA-SKILL.md`), an LLM translates specific questions correctly (4 Amenitiz variants → €38.9M, lead Kfund, correct), but writes a different query each time (changes `return(...)`), and variants with filters return different lists and figures (~€72M / ~€76M / ~€77M). Repeating the exact same query returns exactly the same result. Entity endpoints are stable, but this round has the wrong amount (3,000 M EUR) and no investors.

Change: the LLM **only** extracts the intent; code builds the query with a fixed template per attribute. Same intent → same query string, byte for byte → same answer and same cache entry.
- `POST /v1/knowledge/query` with `{"input": "<query>"}`; takes 16–45 s (timeout 200 s).
- Entity name in the query: the canonical name returned by `entity_search` for the resolved id (not the user's text).
- Templates (fields in `return` in a fixed order), to be verified against the API with few calls:
  - `funding_round` and `lead_investors`: `{Company}.funding_round.series={X}.return(amount, lead investor, investors, date)` (SERIES_B → `B`, SEED → `Seed`…; omit `series` when there is no filter).
  - `total_funding`, `investors`, `founders`, `executives`, `headcount`, `acquisitions`, `profile`: one template each.
  - List filters (new `company_list` attribute with `filters: {location?, sector?, min_funding?, round_label?}`): `startups.location={L}.sector={S}.funding>{N}.return(name, funding, sector, location)`, with normalized values (country in English, sector in lowercase English, amount as `10M`).
  - `other`: current fallback.
- Cache: key = canonical query string.
- **Cross-check with entities** (for rounds): in addition to the `knowledge_query` response, retrieve the structured value (`transaction_value`, participants with `is_lead`) and sources with `source_rank`; return `cross_check: {structured_amount, query_amount, match: bool, note}`. If they do not match, flag that (do not silently choose one).
- `result`: `{query, rows, sources, cross_check?}`; deterministic output.
- Benchmark: three modes per group of variants: direct text to `knowledge_search`, and canonicalized with template. Main metric: do all variants return exactly the same answer? (hash), key values, number of calls.
