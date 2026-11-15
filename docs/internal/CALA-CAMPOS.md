# Cala: field guide (summary of the official guide Cala shared on 14/11)

**For this challenge, Cala recommends the entity endpoints**, not natural-language search: they provide all fields with their sources and allow connections to be traversed.

## Recommended flow
1. `entity_search` (by name, fuzzy; `entity_types` filter, e.g. `["Company"]`, `["Event"]`) or `entity_lookup` (LEI, CIK, Companies House, SIREN, RSSD).
2. `entity_introspection` for the id: which properties, relationships, and series the entity has.
3. `entity_retrieval`: request only the required `properties`, `relationships`, and `numerical_observations`.
4. Repeat for linked entities (round, investor, person, event).

## Value format
`{"value": ..., "sources": [{name, document (URL), date, date_precision: day|month|year, source_rank: FILING|PRIMARY|PRESS|AGGREGATOR}]}`.
Relationships return `id`, `name`, `entity_type` for the linked entity, with its sources and extra fields (`role`, `is_lead`, `valid_since`, `valid_until`, `event_date`). Series are lists of dated observations with a source.
If a field does not apply to a company, it is not returned. A zero confirmed by a source is returned as 0 with a source.

## Company
- Properties: `name`, `legal_name`, `aliases`, `website`, `description`, `founding_date`, `headquarters_address`, `registered_address`, `operational_status`, `company_ownership_status`, `employee_count_range`, `total_funding` (+`_units`), `total_funding_excluding_debt` (+`_units`), `funding_stage` (PRE_SEED, SEED, SERIES_A…), `companies_house_uk_company_number`.
- Series: "Number of employees" (`employee_count`), "Annual recurring revenue", UK financial statement line items.
- Outgoing relationships: `HAS_DOMAIN_NAME`, `HAS_HEADQUARTERS_IN`, `IS_REGISTERED_IN`, `OPERATES_IN_INDUSTRY`, `PARTICIPATES_IN_FUNDING_ROUND`, `PARTICIPATES_IN_CORPORATE_EVENT`, `PARTICIPATES_IN_EVENT`.
- Incoming relationships: `FOUNDED`, `IS_CEO_OF`, `IS_CTO_OF`, `IS_VICEPRESIDENT_OF`, `IS_BOARD_MEMBER_OF`, `WORKS_AT` (with role), `IS_BENEFICIARY_OWNER_OF`, `IS_CONTROL_PERSON_OF`, `INVESTED_IN` (investors, all rounds).

## FundingRound
Reached from the company through `PARTICIPATES_IN_FUNDING_ROUND`; `role` = `ISSUER` (rounds it raised), `INVESTOR`, or `LENDER`.
- Properties: `name` (Seed, Series B, Venture Debt, Grant…), `round_label` (SEED, SERIES_A…), `instrument`, `transaction_value` (+`_units`), `announcement_date`, `event_date` (+`__precision`).
- Participants: incoming `PARTICIPATES_IN_FUNDING_ROUND` links from the round, each with `role` (INVESTOR/LENDER) and **`is_lead`** (marks lead investors).
- Filings-based financings (SEC Form D) also appear as `PrivateCompanyFundingRound` through `PARTICIPATES_IN_CORPORATE_EVENT`, without investors. The same round can appear in both: match by date and amount before summing.

## Acquisitions
`CorporateEvent` through `PARTICIPATES_IN_CORPORATE_EVENT`: `name` (MNA_COMPLETED, MATERIAL_AGREEMENT_ANNOUNCED…), `role` (ACQUIRER…), `event_date`.

## Events: Slush 2026
Event `Slush 2026`, id `bc844d56-6ab4-452b-96bf-2661e86e592b`. Its incoming `PARTICIPATES_IN_EVENT` links (role `ATTENDEE`) are the attending companies (startups, investors, and corporations):
`{"entity_id": "bc844d56-…", "relationships": {"incoming": {"PARTICIPATES_IN_EVENT": {"limit": 100}}}}`

## Notes
- Companies are registered under their legal name, with brands as aliases (Cameo = "Baron App, Inc."). Search can use the brand or legal name.
- A brand, legal entity, and subsidiaries may be separate `Company` entities: use `website` to choose.
- MCP: `https://api.cala.ai/mcp/` with `X-API-KEY`.
