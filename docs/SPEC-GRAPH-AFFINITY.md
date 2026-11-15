# Spec: local subgraph and affinity score (Cala Match)

Issue #68. It is read by `fabricio` (#64 Valkey graph, #65 feed API), `adrian` (#62 app) and `gabriel` (#66 context). This is a **proposal**: anything marked *(to validate)* depends on data we have not measured yet.

## 1. What we know (measured on 14/11, Amenitiz seed, 185 nodes and 246 edges)
- Entity endpoints respond in ~1 s; `knowledge/query` and `knowledge/search` take 16–60 s. The usage limit was hit with 10 consecutive calls.
- Traversing the local subgraph: full BFS in 0.13 ms. Size is not a problem.
- **Each edge includes its sources**, but inside `properties`, not on the element: `{id, name, entity_type, properties: {role, is_lead, valid_since, valid_until, event_date, sources: [...], id: <edge id>}}`. (My first script read the wrong path and counted zero sources; it is corrected here.)
- A lot of noise: 54 of 185 nodes were `PrivateCompanyFundingRound` (records with no investors and the same generic name), plus products, awards and countries.
- Real duplicates: the same fund appears as both `Organization` and `Company` ("Chalfen Ventures" and "CHALFEN VENTURES LLP", "Otium Capital" twice: 2 of 33 neighbors). And "Amenitiz" exists as both a company and a product, which are **not** the same thing.

## 2. Data model
**Node** `{id, type, name, aliases[], props{}, loaded_at, expanded: {<relationship set>: <date>}}`. Canonical `id` = the `Company` id if there are duplicates (section 4).

**Edge** `{id, src, dst, rel, role?, is_lead?, valid_since?, valid_until?, event_date?, sources[], loaded_at}`.
- Always stored oriented as `src → dst` according to Cala's semantic direction (`INVESTED_IN`: investor → company), regardless of which node it was read from. This way, an edge read from both ends is stored only once.
- Without `sources`, it is not shown to the user (project rule: all data must have its source).

**Valkey** (prefix `graph:v1:`, TTL 7 days, same as the raw cache):
| Key | Value |
|---|---|
| `node:<id>` | the node |
| `adj:<id>` | edges touching that node (list of edge ids) |
| `edge:<id>` | the edge |
| `alias:<normalized name>` | canonical id (for merging duplicates and resolving names) |
| `view:<user>:seeds` | user's seed ids |
| `view:<user>:nodes` | set of ids they are interested in |
One shared graph; **each user's subgraph is a view** (list of ids), not a copy. A user node that does not yet exist in Cala is **temporary and local**: it is not written to the shared `node:`; it is connected to their seeds in memory.

## 3. What we traverse and what we don't
Traverse only edges with business meaning:
`INVESTED_IN`, `PARTICIPATES_IN_FUNDING_ROUND` (with `role` and `is_lead`), `FOUNDED`, `IS_CEO_OF`, `IS_CTO_OF`, `IS_BOARD_MEMBER_OF`, `WORKS_AT`, `IS_MEMBER_OF`, `PARTICIPATES_IN_CORPORATE_EVENT` only for M&A (`MNA_*`), `PARTICIPATES_IN_EVENT` (Slush 2026).

**Read as attributes but do not traverse** (they connect everything to everything): `OPERATES_IN_INDUSTRY`, `HAS_HEADQUARTERS_IN`, `IS_REGISTERED_IN`, `HAS_DOMAIN_NAME`. They are used for the affinity's sector and region.

**Exclude**: `PrivateCompanyFundingRound` nodes (counted, not stored), `Product`, `Award`, `Country`, `Group`, `EducationalInstitution`. Exception: store the product only if it needs to be shown in detail.

Request `limit: 100` per relationship. If exactly 100 are returned, mark `truncated: true`: there are more and the node is a hub (Eight Roads returned 74 edges with this limit).

## 4. Merge duplicates
Merge key = normalized name (lowercase, no accents, no legal suffix: `LLP, Ltd, Inc, GmbH, AB, Oy, SA, SL, BV`) **+** compatible type (`Company` and `Organization` merge; never with `Product` or `Award`) **+** `website` if both have one. When in doubt, do not merge. The canonical id is the `Company` id; the other goes in `aliases` and `alias:`. *(to validate on 20 real funds: how many false positives it produces.)*

## 5. Traversal (BFS with a per-level cap)
1. **Seeds**: Gemini extracts named entities from the profile and context (their startup, investors, competitors) and resolves them with `entity_search`. Sector, stage, region and ticket **are not nodes**: they are constraints (section 6).
2. **Level 0 → 1**: introspection + retrieval of each seed with the section 3 relationship whitelist. To profile each candidate investor, **one** `knowledge/query` (`startups.investors=<fund> return(company, round_type, funding_amount, year, sector, location)`) retrieves all its rounds at once; it is slow but one call, not forty.
3. **Later levels**: expand by priority, not arrival order: first the nodes that best satisfy the constraints. **Cap per level: 15 expansions** (at ~1 s per call, ~15–30 s; adjust when #63 measures the actual limit). Maximum depth 2; third level only in the background.
4. Each call respects the per-endpoint pause from #63. Until then, use 1 s for entities.
5. **Background**: when showing a response or a card, enqueue expansions for the nodes shown in it (prefetch). Do not expand what the user dismisses.

**Distance** = BFS level in the undirected graph, with every edge weighted 1 (equivalent to Dijkstra). This is the shortest path **within what has been explored**, not across all of Cala; do not present it as "the shortest path that exists". If we ever add weights (cofounder < same employer, current < historical), the queue becomes a priority queue.

## 6. Affinity score (v1)
Input: user profile `{sector[], stage, region[], ticket {min,max}, seeds[]}` and a candidate entity. The calculation is the same in both modes; only the candidate changes.

| Signal | Weight | How it is calculated (0 to 1) | Cala data |
|---|---|---|---|
| Sector | 0,30 | Raising: percentage of the investor's rounds in the user's sector. Investing: the startup is in a sector from the investor's thesis | Investor `knowledge/query` (sector column), `OPERATES_IN_INDUSTRY` |
| Stage | 0,20 | Percentage of the investor's rounds at the stage the startup is seeking (`round_type`) | `knowledge/query` |
| Region | 0,15 | 1 same country, 0,6 same region (Nordics, DACH, Iberia), 0 elsewhere | `location`, `HAS_HEADQUARTERS_IN` |
| Ticket | 0,15 | 1 if the desired amount falls within the investor's usual range (median ± one quartile), decreases outside it | `funding_amount` from its rounds |
| Activity | 0,10 | Rounds led or followed in the last 24 months (cap at 5) | `year`, `is_lead` |
| Graph proximity | 0,10 | 1 investor already in common, 0,6 at distance 2, 0,3 at distance 3, 0 if there is no path | local subgraph |

- `score = round(100 × Σ wᵢ·sᵢ / Σ wᵢ)` **only across signals with data**. A signal without data does not count as zero: it is omitted and lowers `confidence`.
- `confidence` = sum of weights with data (0 to 1). The card shows the score; `confidence < 0,5` is marked as "partial data".
- Card colors (match the Stitch design): green ≥ 80, amber 60–79, gray < 60.
- **Always explainable**: each signal returns a sentence with its data and sources ("Led 3 similar rounds in 2025"). `why_match` on the card contains the two signals with the greatest contribution.
- The weights are an initial proposal, **not calibrated**. Calibrate with 10 known pairs (for example, Amenitiz with Eight Roads and Chalfen should get a high score) before the demo.
- Feed order: descending score; for ties, higher `confidence` first.

## 7. Contract (draft, in `docs/API.md`)
Added as *(draft)*: `GET /api/feed`, `GET /api/entities/{id}` and `FeedCard`. `fabricio` and `adrian` coordinate changes with each other and notify `bau` if anything already marked stable breaks.

## 8. Open questions
1. Is `is_lead` always present? It is key for "activity" and "who actually leads". *(ask at the Cala booth)*
2. Is a fund an `Organization` or a `Company`? The sample had both; confirm with more funds.
3. How many consecutive calls can entities handle? #63 will measure it; it determines the cap in section 5.
4. Coverage of Nordic and Spanish startups? Without them, Investing mode may be thin.
5. The user's startup may not be in Cala: affinity must work with the temporary node and only the profile constraints.

## 9. Definition of done for this spec
- With the Amenitiz seed, the saved graph contains no `PrivateCompanyFundingRound` or products, and "Chalfen" and "Otium" each end up as a single node.
- A repeated search by the same user makes no calls to Cala.
- Each feed card includes `score`, `confidence`, `why_match` and `sources`.
