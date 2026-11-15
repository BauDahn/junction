# Cala: what the API supports (according to docs.cala.ai, read on 13/11)

Base https://api.cala.ai · header `X-API-KEY` · no official SDK (requests/fetch) · MCP at https://api.cala.ai/mcp/ (not compatible with OpenAI strict mode).

| Endpoint | Input | Output |
|---|---|---|
| `POST /v1/knowledge/search` | `input`: natural-language question (or Cala QL); `explainability` (default true); `return_entities` | `content` in markdown + `explainability` (steps with references) + `context` (KnowBits with `origins`: source, name, and document URL) + `entities` |
| `POST /v1/knowledge/query` | `input`: natural language or dot syntax (`startups.location=Spain.funding>10M.funding<=50M`, `people.role=CEO.company.industry=AI`, `investors=A AND B`, `order_by=`, `limit=`, `return(f1,f2)`) | `results`: structured rows (e.g. `{company, funding_amount, round_type, sector, year}`) + `entities` |
| `GET /v1/entities?name=` | name, `entity_types`, `limit` | stubs `{id, name, entity_type, description}` |
| `POST /v1/entities/lookup` | LEI, CIK, Companies House, SIREN… identifier | one stub |
| `POST /v1/entities/{id}` | which properties, relationships (incoming/outgoing by type, paginated), and metrics to fetch | full profile; properties with source and date; typed relationships with `valid_since`/`valid_until` |
| `GET /v1/entities/{id}/introspection` | — | which properties and relationships the entity has |

Entity types: Company, Person, FundingRound, PrivateCompanyFundingRound, FundingRoundTranche, CorporateEvent (M&A), GPE, Country, Location, Law, Sanction… **There is no "Investor" type.**

**Undocumented (ask at the booth):** whether it distinguishes lead from follow in a round; credit cost per call; usage limits (there has only been one 429); latency; freshness; Nordic and Spanish coverage.

**Implications:** Cala already handles search and citations; the product adds user context, query strategy, cross-checking, ranking, and presentation. Risk for "who actually leads" and the investor ladder (they depend on lead/follow). The early-customer radar and deck verifier do not depend on this.
