# Informe: respuestas distintas de Cala para la misma pregunta

Junction 2026, reto de Cala. Mediciones del 14/11/2026 contra la API real (`https://api.cala.ai/v1`).
Destinatarios: nuestro equipo y el equipo de Cala.

## Resumen

1. La misma pregunta, escrita de formas equivalentes (con o sin acentos, reformulada, en otro idioma), hace que Cala recupere fuentes distintas y, en consultas de lista, devuelva empresas y cifras distintas.
2. El texto idéntico sí devuelve siempre lo mismo: la variación depende de la forma del texto, no del azar.
3. Medimos que una repetición exacta se sirve en 0,2–0,3 s con el JSON idéntico (frente a 15–18 s la primera vez), y que los ids de `context` se generan por respuesta: no identifican hechos estables.
4. No pudimos verificar desde la API que una consulta nueva cree nodos de entidad en el grafo; la documentación pública no lo confirma ni lo niega. Sí hay entidades duplicadas persistentes (tres "Leadwind").
5. Solución nuestra: un canonizador que reduce cada pregunta a una intención y arma siempre la misma consulta. 41 redacciones de 9 preguntas → 9 consultas, con respuesta idéntica dentro de cada grupo.

## 1. El problema

Un usuario no escribe dos veces igual. "¿Cuánto levantó Amenitiz en su Serie B?", "cuanto levanto amenitiz en la serie b" y "How much did Amenitiz raise in its Series B?" son la misma pregunta. Cala las trata como tres consultas sin relación: cada una recorre el proceso completo, recupera otras fuentes y puede dar otra respuesta. Para un producto que muestra datos con fuente, eso significa que dos usuarios (o el mismo usuario dos veces) ven respuestas distintas, y que cada redacción nueva cuesta una llamada lenta contra un límite de uso bajo.

## 2. Evidencia medida por nosotros

### 2.1 `POST /v1/knowledge/search`: Serie B de Amenitiz, 4 variantes

| Variante | Hechos (`context`) | Hechos en común con la variante 1 | Entidades |
|---|---|---|---|
| 1. Español con acentos | 5 | (referencia) | 6 |
| 2. Español sin acentos | 4 | 0 | 12 |
| 3. Español reformulada | 3 | 0 | 10 |
| 4. Inglés | 4 | 0 | 10 |
| Control: variante 1 repetida idéntica | 5 | 5 (los mismos) | 6 (las mismas) |

Los conjuntos de entidades también difieren entre variantes. El id de la entidad Amenitiz (`db95edaa-058f-494d-a4f4-5f56bf81afd9`) fue el mismo en las 7 consultas, y `entity_search` de "Amenitiz" devuelve una sola Company con ese nombre.

### 2.2 `GET /v1/entities?name=`: sin el problema

| Par consultado | Resultado |
|---|---|
| "Telefónica" / "Telefonica" | exactamente las mismas entidades |
| "Inditex" / "Indítex" | exactamente las mismas entidades |
| "Société Générale" / "Societe Generale" | exactamente las mismas entidades |

La búsqueda por nombre ya ignora acentos. El problema está en los endpoints de conocimiento, no en el de entidades.

### 2.3 `POST /v1/knowledge/query` con la guía oficial y un LLM traduciendo libremente

Usamos la guía oficial de Cala (`docs/internal/CALA-SKILL.md`) y dejamos que un LLM tradujera cada pregunta a una consulta.

| Pregunta | Variantes | Consultas generadas | Resultado |
|---|---|---|---|
| Serie B de Amenitiz | 4 | 4 cadenas distintas (cambia `return(...)`) | Datos coincidentes: €38.9M, líder Kfund |
| Startups españolas de tecnología hotelera con más de 10 millones | 3 | 3 cadenas distintas | Resultados distintos (tabla siguiente) |
| La misma cadena exacta, repetida 3 veces | 1 | 1 | Resultado idéntico las 3 veces |

Resultados del filtro, por variante:

| Variante | Empresas devueltas |
|---|---|
| A | Amenitiz ~€77M, Room00 |
| B | Amenitiz ~€72M+, Lodgify |
| C | Amenitiz ~$83M (~€76M) |

### 2.4 Endpoints de entidades: datos de la ronda

- La ronda Serie B de Amenitiz (FundingRound `5cd44a46-1403-5170-98f1-f8d866cfce8e`) tiene `transaction_value` = 3.000.000.000 EUR, con fuente eu-startups: un artículo titulado "...processes €3 billion in bookings ahead of new €38.9 million funding". Es la cifra de reservas tomada como monto de la ronda.
- La ronda solo tiene enlazado al emisor (Amenitiz): sin inversores ni `is_lead`. Sin embargo, `knowledge_query` sí responde que la lideró Kfund.

### 2.5 Límite de uso y latencia

- Tras ~7 llamadas seguidas: HTTP 429 durante ~1 minuto.
- Latencia: 11–17 s en `knowledge_search`, 16–45 s en `knowledge_query`.

## 3. ¿Se crean nodos o caminos nuevos cuando llega una consulta no vista?

Separamos cuatro niveles de certeza. Solo (a) es medición nuestra.

### (a) Medido por nosotros (experimento adicional, 6 llamadas, sin ningún 429)

Pregunta nueva sobre la Serie B de Swappie (Finlandia) en `knowledge/search`: una vez en inglés, repetida idéntica, y una vez en español. Además, la variante 1 de Amenitiz repetida más tarde el mismo día, y dos búsquedas de entidades.

| Observación | Dato |
|---|---|
| Pregunta nueva, primera vez | 15,5 s, 5 hechos |
| La misma cadena, repetida | 0,3 s; JSON completo idéntico (mismos ids, mismo texto) |
| Variante 1 de Amenitiz, repetida más tarde el mismo día | 0,2 s; los mismos 5 ids de hechos y las mismas 6 entidades |
| Paráfrasis en español de la pregunta nueva | 18,4 s; 5 hechos, **0 ids en común** con la versión en inglés |
| Documentos fuente (URLs), inglés vs. español | 5 y 5; solo 1 en común (privateequitywire.co.uk) |
| Entidades, inglés vs. español | 11 y 12; 10 en común; mismo id para Swappie |
| Respuesta | Coincidente en lo esencial (Serie B de junio de 2020, $40,6M / €35,8M, mismos inversores) |

Tres conclusiones que sí se sostienen con estos datos:

1. **Hay una caché de respuestas por texto exacto.** Una repetición idéntica tarda 0,2–0,3 s en vez de 15–18 s y devuelve el JSON byte a byte. Una paráfrasis no acierta en esa caché y vuelve a ejecutar todo el proceso. Esto explica el control de la sección 2.1.
2. **Los ids de `context` se generan por respuesta; no identifican un hecho almacenado.** El mismo artículo de privateequitywire aparece en las dos variantes con ids distintos (`0f4a2f66-…` y `582ea4d0-…`). El texto del hecho coincide en los primeros 504 caracteres y, tras un `[...]`, continúa con un fragmento distinto del mismo artículo según la pregunta (el asesor financiero en una, los fundadores en la otra). Los 10 ids observados son UUID versión 4 (aleatorios). Es decir, el contenido del KnowBit es un extracto armado a la medida de la consulta.
3. **Los ids de entidad sí son estables entre variantes**, pero existen entidades duplicadas persistentes. `GET /v1/entities?name=Leadwind` devuelve tres nodos para lo mismo: "Kfund's Leadwind fund" (Organization, `c10b7226-…`, descrita como "a venture capital fund that led the Series B financing of hospitality software company Amenitiz"), "Leadwind" (Organization, `37ea4d4a-…`) y "Leadwind" (Product, `99140378-…`). En las variantes de Amenitiz aparecían además "Point9" (`3fb8df43-…`) y "Point Nine Capital" (`c934f7e3-…`).

Consecuencia para nuestra propia evidencia: "0 hechos en común" (sección 2.1) es cierto, pero sobrestima la divergencia, porque los ids cambian aunque el documento sea el mismo. La medida más justa es el solape de documentos fuente, que es bajo pero no nulo (1 de 5 en Swappie).

Lo que **no** pudimos medir: si alguno de esos nodos de entidad se creó a raíz de una consulta. La API no expone fecha de creación ni origen del nodo, y con 6 llamadas no era posible comprobar la ausencia previa de una entidad.

### (b) Observado por el equipo en la herramienta de Cala (no verificado desde la API)

El equipo indica que en la herramienta de Cala se ve que, cuando una consulta no tiene respuesta existente, el grafo se expande, y que si dos consultas equivalentes no se reconocen como iguales se crean caminos y nodos innecesarios. No lo pudimos reproducir ni refutar desde la API pública. Convendría documentarlo con capturas y confirmarlo con el equipo de Cala.

### (c) Lo que dice la documentación pública

| Fuente | Cita textual |
|---|---|
| https://cala.ai | "Cala pre-processes the world's public information into verified, structured facts — so agents query knowledge, not chaos." |
| https://docs.cala.ai/index.md | "Cala abstracts away ingestion, normalization, and verification behind a simple API" |
| https://docs.cala.ai/index.md | "It's a verified entity graph made of typed entities with structured fields, deterministic queries" |
| https://api.cala.ai/openapi.json (esquema `KnowBit`) | "A KnowBit is like a fact, a piece of information that supports the answer." |
| https://api.cala.ai/openapi.json (`KnowBit.origins`) | "The origins from which the KnowBit was extracted." |
| https://api.cala.ai/openapi.json (`GET /v1/entities`) | "spans many domains and keeps growing" |
| https://api.cala.ai/openapi.json (`knowledge/search`) | "Best when you have a question and want a researched narrative with citations" |
| https://docs.cala.ai/features/structured-answer.md | "Input can be a Cala QL expression or a natural-language question — both produce the same structured response shape." |
| https://github.com/cala-ai/entity-watch-demo (README) | "Responses are cached in the `cala_cache` table so repeat views are instant." |

Lo que **no** encontramos en ninguna de estas fuentes (docs.cala.ai y su `llms.txt`, el OpenAPI, los repos `cala-skill`, `cala-claude-plugin`, `entity-watch-demo` y `cala-n8n-node`, y el sitio cala.ai):

- Ninguna descripción de expansión del grafo bajo demanda, ni de qué ocurre cuando una consulta no tiene respuesta existente.
- Ninguna mención de caché del lado de Cala, ni de consistencia entre redacciones o idiomas. La frase "same response shape" habla de la forma de la respuesta, no del contenido.
- Ningún detalle de la ingesta. El término "KnowBit" solo aparece en el esquema del OpenAPI.
- El sitio tiene preguntas frecuentes ("How does Cala stay accurate?", "How fresh is the data?", "Where does Cala's data come from?") cuyas respuestas se cargan de forma dinámica; no pudimos leerlas. No encontramos un blog.

Dos datos de contexto útiles. La redacción pública ("pre-processes") describe un grafo preparado de antemano, no uno que crece con cada consulta. Y la propia aplicación de referencia de Cala (`entity-watch-demo`) ya aplica la idea que proponemos: arma la consulta con una plantilla fija y guarda la respuesta bajo una clave estructurada (`ew_${companyId}_${topicId}_${period}`), no bajo el texto libre.

### (d) Hipótesis (no demostradas)

- **H1.** `knowledge/search` combina el grafo con una recuperación de pasajes en el momento de la consulta, y los KnowBits de `context` se arman entonces. A favor: extractos distintos del mismo documento según la pregunta, ids aleatorios por respuesta, 15–18 s de latencia. No confirmado por Cala.
- **H2 (la del equipo).** Una consulta sin respuesta existente hace que el grafo se expanda con nodos y caminos nuevos. Compatible con lo medido (entidades duplicadas como "Kfund's Leadwind fund", cuyo nombre y descripción salen de una mención en un texto), pero esos duplicados también pueden nacer en la ingesta de artículos. No tenemos forma de distinguirlo desde afuera.
- **H3.** Si H2 es cierta, cada redacción no reconocida genera trabajo y registros redundantes. Aunque H2 fuera falsa, lo medido ya basta para afirmar un costo: cada redacción nueva repite el proceso completo (15–18 s) y ocupa una entrada de caché propia.

En síntesis: está medido que cada redacción nueva produce una respuesta nueva, con registros de hechos nuevos. No está medido que produzca nodos nuevos en el grafo de entidades.

### Contexto: grafos de conocimiento y canonización de consultas

En los sistemas tipo GraphRAG, un LLM extrae entidades y relaciones de los documentos y construye el grafo en la indexación; la consulta lo recorre. Algunos diseños lo actualizan de forma incremental a medida que llega información nueva. En todos, el punto delicado es la resolución de entidades: si dos menciones del mismo objeto ("Point9" y "Point Nine Capital") no se reconocen como iguales, el grafo acumula nodos duplicados y los caminos se reparten entre ellos. Lo mismo vale para las consultas: sin una forma canónica, dos preguntas equivalentes no comparten caché ni resultado.

- Edge et al., "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" (Microsoft GraphRAG): https://arxiv.org/abs/2404.16130
- Guo et al., "LightRAG: Simple and Fast Retrieval-Augmented Generation" (actualización incremental del grafo): https://arxiv.org/abs/2410.05779
- Rasmussen et al., "Zep: A Temporal Knowledge Graph Architecture for Agent Memory" (grafo que crece por episodios, con resolución de entidades al insertar): https://arxiv.org/abs/2501.13956
- GPTCache (caché semántica de consultas a LLM): https://github.com/zilliztech/GPTCache

La canonización ataca el problema antes de la llamada: normalizar el texto, resolver las entidades a un id y reducir la pregunta a una clave estable hace que todas las redacciones caigan en la misma consulta y la misma entrada de caché.

## 4. La solución: canonizador (`canonizador/`)

Diseño completo en `docs/internal/SPEC-canonizador.md`. Principio: **el LLM solo extrae la intención; la consulta la arma el código.**

| Paso | Módulo | Qué hace |
|---|---|---|
| 1 | `normalize.py` | Unicode NFC, espacios, quita `¿¡` y comillas tipográficas. Determinista. |
| 2 | `intent.py` | Un LLM chico convierte la pregunta en una intención estructurada: entidades, atributo (ronda, financiación total, inversores, fundadores, ejecutivos, adquisiciones, lista de empresas…) y filtros. Los filtros salen en inglés canónico: "España" → `Spain`, sector en un valor fijo en minúsculas, "10 millones" → `10000000`. |
| 3 | `resolve.py` | Resuelve cada entidad a su id con `GET /v1/entities` (que ya ignora acentos), con elección determinista entre candidatas. |
| 4 | `plan.py` | Arma la consulta de `knowledge_query` con una plantilla fija por atributo, con los campos de `return(...)` en orden fijo y el nombre canónico de la entidad. Misma intención → misma cadena, byte a byte. |
| 5 | `cache.py`, `client.py` | Caché en disco cuya clave es la consulta canónica; una sola llamada a la vez y espera ante un 429. |
| 6 | cruce | Para rondas, compara la respuesta de `knowledge_query` con el valor estructurado de la entidad (`transaction_value`, participantes con `is_lead`) y marca la discrepancia en `cross_check` en vez de elegir en silencio. |

## 5. Resultados medidos

| Prueba | Redacciones | Consultas a Cala | Resultado |
|---|---|---|---|
| 2 preguntas | 20 | 2 | Respuesta idéntica dentro de cada grupo |
| 7 tipos de pregunta | 21 | 7 | Respuesta idéntica dentro de cada grupo |

Los 7 tipos: fundadores de Glovo, adquisiciones de Mews, financiación total de Factorial, inversores de Wolt, ejecutivos de TravelPerk, lista de fintech en Finlandia con más de 5M y lista de climate tech en Alemania con más de 20M.

El cruce con entidades detecta la discrepancia de la Serie B de Amenitiz (3.000 M EUR en la entidad frente a €38.9M en `knowledge_query`).

Benchmark lado a lado (9 preguntas × 3 redacciones, directo contra canonizado, con ejemplos de cifras distintas en modo directo): `docs/BENCHMARK-CANONIZADOR.md`.

## 6. Límites

- Se verificó la **consistencia** (misma intención → misma respuesta), no la **veracidad** de cada respuesta.
- El canonizador depende de que el LLM extraiga la misma intención de cada redacción. En las 41 redacciones probadas lo hizo; no es una garantía general.
- Las preguntas fuera de los atributos conocidos usan un camino de respaldo con una pregunta canónica en inglés, menos controlado.
- El experimento de la sección 3 es una sola pregunta nueva con una paráfrasis. Alcanza para mostrar el mecanismo de caché y de ids, no para cuantificarlo.
- No vemos el interior de Cala: lo dicho sobre creación de nodos es hipótesis mientras Cala no lo confirme.

## 7. Recomendaciones para Cala

1. **Canonizar la consulta antes de la caché y de la recuperación**: normalizar Unicode y acentos, resolver entidades a su id y usar una clave por intención, no por texto exacto. El endpoint de entidades ya ignora acentos; los de conocimiento no.
2. **Ids de hechos estables**: que `context[].id` identifique el pasaje o hecho (por ejemplo, derivado del documento y el fragmento), para que los clientes puedan deduplicar y comparar respuestas.
3. **Fusionar entidades duplicadas**: "Leadwind" / "Kfund's Leadwind fund" / "Leadwind" (Product); "Point9" / "Point Nine Capital".
4. **Validar montos al extraer rondas**: la Serie B de Amenitiz figura con 3.000.000.000 EUR (cifra de reservas). Una comprobación de coherencia contra el título de la fuente lo habría detectado.
5. **Enlazar inversores y `is_lead` en la ronda**, ya que `knowledge_query` conoce al líder (Kfund) y la entidad no.
6. **Documentar** la caché, el límite de uso (cuántas llamadas por minuto; incluir `Retry-After` en el 429), la latencia esperada y si las consultas modifican el grafo.
7. **Orden y campos por defecto deterministas** en `knowledge_query` cuando la consulta no trae `return(...)` ni `order_by`.

## 8. Cómo reproducirlo

Requisitos: `CALA_API_KEY` en `backend/.env` (no se imprime ni se guarda en el repo). La API admite pocas llamadas seguidas: hacerlas de a una y esperar unos 15 s entre llamadas.

**Problema (texto directo a Cala).** Enviar cada redacción y comparar `context[].id`, las URLs de `context[].origins[].document.url` y `entities[].id`:

```sh
curl -s -X POST https://api.cala.ai/v1/knowledge/search \
  -H "X-API-KEY: $CALA_API_KEY" -H "Content-Type: application/json" \
  -d '{"input": "¿Cuánto levantó Amenitiz en su Serie B y quién lideró la ronda?"}'
```

Redacciones equivalentes para probar:

- "¿Cuánto levantó Amenitiz en su Serie B y quién lideró la ronda?"
- "quien lidero y de cuanto fue la serie b de amenitiz"
- "How much did Amenitiz raise in its Series B and who led the round?"
- "¿Qué startups españolas de tecnología hotelera levantaron más de 10 millones?"
- "mas de 10 millones levantados startups hoteleras tecnologia españa"
- "Which Spanish hotel tech startups have raised more than 10 million?"

Repetir una de ellas sin cambiar nada muestra la caché por texto exacto (respuesta en menos de 1 s, JSON idéntico).

**Entidades duplicadas.**

```sh
curl -s "https://api.cala.ai/v1/entities?name=Leadwind&limit=10" -H "X-API-KEY: $CALA_API_KEY"
```

**Solución (canonizador).**

```sh
cd canonizador && uv sync --extra dev
uv run python -m canonizador "¿Cuánto levantó Amenitiz en su Serie B y quién lideró la ronda?"
uv run python -m canonizador "quien lidero y de cuanto fue la serie b de amenitiz"
uv run python -m canonizador "How much did Amenitiz raise in its Series B and who led the round?"
```

Las tres salidas deben mostrar la misma consulta y el mismo resultado; la segunda y la tercera reutilizan la caché y no repiten la consulta de conocimiento. Los grupos completos de redacciones están en `canonizador/bench/questions.json` y se ejecutan con `uv run python bench.py`. Tests sin red: `uv run pytest`.
