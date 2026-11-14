# Cala: qué permite la API (según docs.cala.ai, leído el 13/11)

Base https://api.cala.ai · header `X-API-KEY` · sin SDK oficial (requests/fetch) · MCP en https://api.cala.ai/mcp/ (no es compatible con el modo estricto de OpenAI).

| Endpoint | Entrada | Salida |
|---|---|---|
| `POST /v1/knowledge/search` | `input`: pregunta en lenguaje natural (o Cala QL); `explainability` (def. true); `return_entities` | `content` en markdown + `explainability` (pasos con referencias) + `context` (KnowBits con `origins`: fuente, nombre y URL del documento) + `entities` |
| `POST /v1/knowledge/query` | `input`: lenguaje natural o con puntos (`startups.location=Spain.funding>10M.funding<=50M`, `people.role=CEO.company.industry=AI`, `investors=A AND B`, `order_by=`, `limit=`, `return(f1,f2)`) | `results`: filas estructuradas (p. ej. `{company, funding_amount, round_type, sector, year}`) + `entities` |
| `GET /v1/entities?name=` | nombre, `entity_types`, `limit` | stubs `{id, name, entity_type, description}` |
| `POST /v1/entities/lookup` | identificador LEI, CIK, Companies House, SIREN… | un stub |
| `POST /v1/entities/{id}` | qué propiedades, relaciones (entrantes/salientes por tipo, paginadas) y métricas traer | perfil completo; propiedades con fuente y fecha; relaciones tipadas con `valid_since`/`valid_until` |
| `GET /v1/entities/{id}/introspection` | — | qué propiedades y relaciones tiene esa entidad |

Tipos de entidad: Company, Person, FundingRound, PrivateCompanyFundingRound, FundingRoundTranche, CorporateEvent (M&A), GPE, Country, Location, Law, Sanction… **No figura un tipo "Investor".**

**No documentado (preguntar en el stand):** si distingue lead de follow en una ronda; costo en créditos por llamada; límites de uso (solo hay un 429); latencia; frescura; cobertura nórdica y española.

**Implicancias:** la búsqueda y las citas ya las resuelve Cala; el producto aporta el contexto de usuario, la estrategia de consultas, el cruce, el ranking y la presentación. Riesgo para "who actually leads" y la escalera de inversores (dependen de lead/follow). El radar de primeros clientes y el verificador de decks no dependen de eso.
