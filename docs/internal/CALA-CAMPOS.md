# Cala: guía de campos (resumen de la guía oficial que nos pasó Cala el 14/11)

**Cala recomienda para este reto los endpoints de entidades**, no la búsqueda en lenguaje natural: dan todos los campos con sus fuentes y permiten recorrer las conexiones.

## Flujo recomendado
1. `entity_search` (por nombre, difuso; filtro `entity_types`, p. ej. `["Company"]`, `["Event"]`) o `entity_lookup` (LEI, CIK, Companies House, SIREN, RSSD).
2. `entity_introspection` sobre el id: qué propiedades, relaciones y series tiene esa entidad.
3. `entity_retrieval`: pedir solo `properties`, `relationships` y `numerical_observations` necesarios.
4. Repetir sobre las entidades enlazadas (ronda, inversor, persona, evento).

## Formato de un valor
`{"value": ..., "sources": [{name, document (URL), date, date_precision: day|month|year, source_rank: FILING|PRIMARY|PRESS|AGGREGATOR}]}`.
Las relaciones devuelven `id`, `name`, `entity_type` de la entidad enlazada, con sus fuentes y campos extra (`role`, `is_lead`, `valid_since`, `valid_until`, `event_date`). Las series son listas de observaciones fechadas con origen.
Si un campo no aplica a una empresa, no viene. Un cero confirmado por una fuente viene como 0 con fuente.

## Company
- Propiedades: `name`, `legal_name`, `aliases`, `website`, `description`, `founding_date`, `headquarters_address`, `registered_address`, `operational_status`, `company_ownership_status`, `employee_count_range`, `total_funding` (+`_units`), `total_funding_excluding_debt` (+`_units`), `funding_stage` (PRE_SEED, SEED, SERIES_A…), `companies_house_uk_company_number`.
- Series: "Number of employees" (`employee_count`), "Annual recurring revenue", líneas de estados financieros (UK).
- Relaciones salientes: `HAS_DOMAIN_NAME`, `HAS_HEADQUARTERS_IN`, `IS_REGISTERED_IN`, `OPERATES_IN_INDUSTRY`, `PARTICIPATES_IN_FUNDING_ROUND`, `PARTICIPATES_IN_CORPORATE_EVENT`, `PARTICIPATES_IN_EVENT`.
- Relaciones entrantes: `FOUNDED`, `IS_CEO_OF`, `IS_CTO_OF`, `IS_VICEPRESIDENT_OF`, `IS_BOARD_MEMBER_OF`, `WORKS_AT` (con rol), `IS_BENEFICIARY_OWNER_OF`, `IS_CONTROL_PERSON_OF`, `INVESTED_IN` (inversores, todas las rondas).

## FundingRound
Se llega desde la empresa por `PARTICIPATES_IN_FUNDING_ROUND`; `role` = `ISSUER` (rondas que levantó), `INVESTOR` o `LENDER`.
- Propiedades: `name` (Seed, Series B, Venture Debt, Grant…), `round_label` (SEED, SERIES_A…), `instrument`, `transaction_value` (+`_units`), `announcement_date`, `event_date` (+`__precision`).
- Participantes: enlaces entrantes `PARTICIPATES_IN_FUNDING_ROUND` de la ronda, cada uno con `role` (INVESTOR/LENDER) y **`is_lead`** (marca a los inversores líderes).
- Las financiaciones de registros (SEC Form D) aparecen además como `PrivateCompanyFundingRound` vía `PARTICIPATES_IN_CORPORATE_EVENT`, sin inversores. Una misma ronda puede estar en los dos: emparejar por fecha y monto antes de sumar.

## Adquisiciones
`CorporateEvent` vía `PARTICIPATES_IN_CORPORATE_EVENT`: `name` (MNA_COMPLETED, MATERIAL_AGREEMENT_ANNOUNCED…), `role` (ACQUIRER…), `event_date`.

## Eventos: Slush 2026
Evento `Slush 2026`, id `bc844d56-6ab4-452b-96bf-2661e86e592b`. Sus enlaces entrantes `PARTICIPATES_IN_EVENT` (rol `ATTENDEE`) son las empresas asistentes (startups, inversores y corporaciones):
`{"entity_id": "bc844d56-…", "relationships": {"incoming": {"PARTICIPATES_IN_EVENT": {"limit": 100}}}}`

## A tener en cuenta
- Las empresas se registran por nombre legal, con marcas como alias (Cameo = "Baron App, Inc."). Se puede buscar por marca o nombre legal.
- Marca, entidad legal y filiales pueden ser entidades `Company` separadas: usar `website` para elegir.
- MCP: `https://api.cala.ai/mcp/` con `X-API-KEY`.
