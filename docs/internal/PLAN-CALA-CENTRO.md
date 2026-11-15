# Plan: Cala at the center (14/11)

Change of focus decided by the team: **the assistant engine: one way to use Cala by voice or text.** Each message (text or transcribed audio) is interpreted and, when needed, converted into Cala queries. What is shown is **Cala's data as-is** (tables with sources), not text written by a model.

## 1. Router: what to do with each message

A message can contain several things at once. The router splits it into **parts** and classifies each one:

| Type | Example | What it does | Returned block |
|---|---|---|---|
| `query` | "Who led Amenitiz Series B?" | Canonicalizer → fixed Cala query → result as-is | `cala_table` (or `cala_answer`) |
| `claim` | "Mews raised 50 million" | Checks **what the user said** against Cala. Cala's result is treated as correct. | `claim_check` |
| `profile` | "I'm interested in Nordic fintechs at seed", "we are Stayflow…" | Updates the user's profile and preferences (which feed affinity) | `profile_update` |
| `chitchat` | "thanks" | Minimal response, no Cala query | `text` |

The model only classifies and extracts intent. **It never writes figures or names that do not come from Cala.** At most, it adds one summary line per block.

## 2. Running queries: never say "no information" without trying everything

For each `query` or `claim` part, try the following in order until data is found:

1. **Canonical query** (`POST /v1/knowledge/query`) using the canonicalizer's fixed template. Same intent → same string → same answer (see `docs/BENCHMARK-CANONIZER.md`).
2. **Entities**: `entity_search` → `entity_introspection` → `entity_retrieval` for the company, person, or round, with properties, relationships, and sources.
3. **Cala search** (`POST /v1/knowledge/search`) with a canonical question in English generated from the intent (not the user's text). Cala investigates in real time and returns an answer with sources.

Only if all three steps return empty should a `not_found` block be returned, stating **what was searched with each tool** and the closest result found. Do not make up data to avoid that block.

Everything goes through the canonical-query cache, one Cala call at a time, with retries on 429.

## 3. Format: Cala tables, not chatbot text

- `knowledge_query` rows → `cala_table` with the columns exactly as returned by Cala.
- **Entity** → `cala_table` of field · value · source · date · source type (`FILING`, `PRIMARY`, `PRESS`, `AGGREGATOR`).
- `knowledge_search` → Cala's markdown as-is, with its sources.
- Each block includes the **exact query** and the tool used, so it can be reproduced.

## 4. Checking user claims (`claim`)

1. Extract the claim as an intent (who, which attribute, what value the user stated).
2. Query Cala using the same path as in section 2.
3. Compare the user's value with Cala's: `confirmed`, `contradicted`, `partially_confirmed`, or `no_data`. The already-tested rules remain: lack of evidence is not a contradiction, and rounding or an equivalent currency count as confirmation.
4. Return `claim_check` with the verdict, a one-line explanation, and **Cala's table as evidence**.

## 5. Profile and preferences

The current profile (user's startup) is extended with:
- `role`: `founder` | `investor` | `other`.
- `interests`: `sectors`, `regions`, `stages`, and `follows` (companies and investors they want to follow).

These are populated from the router's `profile` parts and feed the affinity feed and recommendations.

## 6. Allocation and order

| # | What | Who | Depends on |
|---|---|---|---|
| A | Contract in `docs/API.md` (blocks and extended profile) | bau | — |
| B | `backend/cala_core/`: router, execution with fallback, table formatting, claim verification. Public function `handle_message(text, profile, llm, cala)` → `{blocks, profile_patch}` | bau (Codex) | A |
| C | Connect `cala_core.handle_message` to chat (`backend/chat/engine.py` and routes): messages return `blocks` | fabricio | B |
| D | App: render blocks (`cala_table`, `cala_answer`, `claim_check`, `profile_update`, `not_found`) in chat | fabricio | A |

While B is pending, the app can use simulated mode with examples of the contract blocks.
