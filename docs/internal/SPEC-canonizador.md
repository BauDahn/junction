# Spec: canonizador de consultas a Cala

## Problema (medido el 14/11 contra `POST /v1/knowledge/search`)
La misma pregunta escrita con acentos, sin acentos, reformulada o en inglés recupera hechos distintos: 0 hechos en común entre variantes (5, 4, 3 y 4 hechos), conjuntos de entidades distintos y respuestas con distinto nivel de detalle. El texto idéntico repetido sí devuelve lo mismo (5/5 hechos), así que depende de la forma del texto, no del azar. `GET /v1/entities?name=` no tiene el problema ("Telefónica" = "Telefonica"). Además el límite de uso es bajo: tras ~7 llamadas seguidas hubo HTTP 429 durante ~1 min.

## Objetivo
Misma intención → mismas llamadas a Cala → misma respuesta, sin importar acentos, redacción o idioma. Y menos llamadas (caché por intención).

## Diseño (paquete Python en `canonizador/`, con uv, independiente de `backend/`)
1. `normalize.py`: Unicode NFC, espacios, quitar `¿¡`, comillas tipográficas. Determinista.
2. `intent.py`: un LLM chico convierte la pregunta en una intención estructurada:
   `{entities: [{name, type: Company|Person|Event|Investor}], attribute: funding_round|total_funding|investors|lead_investors|founders|executives|headcount|acquisitions|profile|event_attendees|other, filters: {round_label?, year?}}`.
   Reglas: nombres propios tal cual aparecen (sin traducir), `round_label` en el código de Cala (SEED, SERIES_A, SERIES_B…). Proveedor de LLM configurable como en `backend/verifier/llm.py` (por defecto `codex exec` con `gpt-5.6-luna` y esfuerzo low; también NVIDIA), con caché en disco.
3. `resolve.py`: resuelve cada entidad a su id con `GET /v1/entities?name=&entity_types=` (ya ignora acentos). Si hay varias candidatas, elegir de forma determinista (coincidencia exacta de nombre o alias normalizado; si no, la primera) y devolver las alternativas.
4. `plan.py`: para atributos conocidos, **plan determinista sobre los endpoints de entidades** (ver `docs/internal/CALA-CAMPOS.md`), que es el camino que Cala recomienda:
   - `funding_round` / `lead_investors`: empresa → `PARTICIPATES_IN_FUNDING_ROUND` (role ISSUER) → ronda que cumpla los filtros → propiedades + participantes entrantes con `is_lead`.
   - `total_funding`, `profile`, `headcount`: propiedades y series de Company.
   - `investors`: `INVESTED_IN` entrante. `founders`/`executives`: `FOUNDED`, `IS_CEO_OF`… `acquisitions`: `PARTICIPATES_IN_CORPORATE_EVENT`. `event_attendees`: `PARTICIPATES_IN_EVENT` entrante del evento.
   - `other`: respaldo con `knowledge/search` usando UNA pregunta canónica en inglés generada por plantilla desde la intención (no el texto del usuario).
   Verificar contra la API real la ruta y el cuerpo de retrieval (`POST /v1/entities/{id}` con `{properties, relationships: {incoming|outgoing: {TIPO: {limit, offset}}}, numerical_observations}`) y de introspección (`GET /v1/entities/{id}/introspection`); ajustar si difiere.
5. `cache.py`: caché en disco; clave = hash de la intención canónica (ids de entidad ordenados + atributo + filtros). Todas las variantes de una pregunta pegan en la misma entrada.
6. `client.py`: cliente de Cala con **una sola llamada a la vez**, reintentos con backoff ante 429/5xx (esperas de 20, 40, 80 s) y caché de cada respuesta cruda.
7. API pública: `answer(question) -> {intent, entity_ids, plan, result: datos estructurados con fuentes, cache_hit, cala_calls}`. CLI: `uv run python -m canonizador "pregunta"`.

## Benchmark (`bench.py`) → `canonizador/REPORT.md`
- `bench/questions.json`: grupos de variantes de la misma pregunta (con acentos, sin acentos, reformulada, inglés, catalán). Empezar con 3 grupos: Serie B de Amenitiz y quién la lideró; financiación total de Mews; fundadores de una empresa con datos.
- Para cada grupo, dos modos: **directo** (texto tal cual a `knowledge/search`) y **canonizado**.
- Métricas por grupo: Jaccard medio entre variantes de (a) ids de hechos o de entidades devueltas y (b) los valores clave de la respuesta (monto, líder); nº de llamadas a Cala; latencia.
- El reporte incluye la tabla antes/después y los comandos para reproducirlo. Tiene que poder mostrarse al equipo de Cala tal cual (en inglés).
- Cuidar el límite: todo secuencial y cacheado; el benchmark debe poder reanudarse.

## Reglas
- `CALA_API_KEY` se carga de `backend/.env` (o del entorno). Nunca imprimirla.
- Tests con clientes falsos (sin red): normalización, clave de caché igual para variantes, resolución determinista, planes.
- README corto en `canonizador/`.

## Hecho cuando
- `uv run pytest` en verde.
- `uv run python -m canonizador` responde igual para las 4 variantes de Amenitiz (mismos ids, mismo monto y líder), con una sola tanda de llamadas a Cala.
- `REPORT.md` generado con datos reales.

## Fase 2 (14/11): consulta con plantilla fija sobre `knowledge_query`
Medido: con la guía oficial (`docs/internal/CALA-SKILL.md`), un LLM traduce bien las preguntas puntuales (4 variantes de Amenitiz → €38.9M, líder Kfund, correcto), pero escribe una consulta distinta cada vez (cambia `return(...)`), y en filtros las variantes devuelven listas y cifras distintas (~€72M / ~€76M / ~€77M). La misma consulta exacta repetida devuelve exactamente lo mismo. Los endpoints de entidades son estables pero esta ronda tiene el monto mal (3.000 M EUR) y sin inversores.

Cambio: el LLM **solo** extrae la intención; la consulta la arma el código con una plantilla fija por atributo. Misma intención → misma cadena de consulta, byte a byte → misma respuesta y misma entrada de caché.
- `POST /v1/knowledge/query` con `{"input": "<consulta>"}`; tarda 16–45 s (timeout 200 s).
- Nombre de la entidad en la consulta: el nombre canónico que devuelve `entity_search` para el id resuelto (no el texto del usuario).
- Plantillas (campos de `return` en orden fijo), a verificar contra la API con pocas llamadas:
  - `funding_round` y `lead_investors`: `{Empresa}.funding_round.series={X}.return(amount, lead investor, investors, date)` (SERIES_B → `B`, SEED → `Seed`…; sin `series` si no hay filtro).
  - `total_funding`, `investors`, `founders`, `executives`, `headcount`, `acquisitions`, `profile`: una plantilla cada uno.
  - Filtros de lista (nuevo atributo `company_list` con `filters: {location?, sector?, min_funding?, round_label?}`): `startups.location={L}.sector={S}.funding>{N}.return(name, funding, sector, location)`, con valores normalizados (país en inglés, sector en minúsculas en inglés, monto como `10M`).
  - `other`: respaldo actual.
- Caché: clave = la cadena de consulta canónica.
- **Cruce con entidades** (para rondas): además de la respuesta de `knowledge_query`, traer el valor estructurado (`transaction_value`, participantes con `is_lead`) y las fuentes con `source_rank`; devolver `cross_check: {structured_amount, query_amount, match: bool, note}`. Si no coinciden, marcarlo (no elegir en silencio).
- `result`: `{query, rows, sources, cross_check?}`; salida determinista.
- Benchmark: tres modos por grupo de variantes: texto directo a `knowledge_search`, y canonizado con plantilla. Métrica principal: ¿todas las variantes devuelven la misma respuesta exacta? (hash), valores clave, nº de llamadas.
