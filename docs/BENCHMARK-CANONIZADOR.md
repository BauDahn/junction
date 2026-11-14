# Benchmark: canonizador vs. preguntas directas a Cala

Junction 2026, reto de Cala. Corridas del 14/11/2026 contra la API real. Complementa a `docs/INFORME-ERROR-CALA.md` (qué es el error y qué sabemos del grafo); este documento solo trae los números del benchmark.

## Resumen

Cinco formas de preguntarle lo mismo a Cala:

| | Búsqueda directa | Consulta directa | Agente por MCP | Agente por MCP con la guía de Cala | Canonizador |
|---|---|---|---|---|---|
| Qué recibe Cala | La pregunta tal cual, en `POST /v1/knowledge/search` | La pregunta tal cual, en `POST /v1/knowledge/query` (sin guía ni plantilla) | Lo que decida un agente (Codex) conectado al servidor MCP de Cala | Lo mismo, con la guía oficial de Cala en el prompt | Una consulta armada con plantilla fija, en `POST /v1/knowledge/query` |
| Preguntas | 9 × 3 redacciones = 27 | las mismas 27 | las mismas 27 | las mismas 27 | las mismas 27 |
| Consultas distintas que llegan a Cala | 27 | 27 | 24 (el agente reescribe la pregunta) | 32 argumentos distintos en 35 llamadas | **9** |
| Preguntas con los mismos datos en sus 3 redacciones | **0 de 9** | **0 de 9** | **1 de 9** | **0 de 9** | **9 de 9** |
| Llamadas a Cala | 27 | 27 | 25 (en 2 no llamó a Cala) | 35 (en 2 no pudo conectarse) | 9 en frío (en esta corrida, 2: el resto ya estaba en caché) |
| Tiempo | 906 s; 33,6 s de media (máx. 61 s) | 939 s; 34,8 s de media (máx. 65 s) | 785 s; 29,1 s de media (máx. 66 s) | 917 s; 34,0 s de media (máx. 70 s) | ~21 s en esta corrida (casi todo caché) |

Mandar lenguaje natural sin canonizar es inconsistente en las dos APIs de conocimiento, y también por MCP, que es como la mayoría de los agentes van a usar Cala, **incluso con la guía oficial de Cala cargada**. Cambian datos, empresas y hasta el formato de la respuesta según cómo se escriba la pregunta.

## Qué se midió

- **9 preguntas** de 7 tipos: ronda concreta, fundadores, adquisiciones, financiación total, inversores, ejecutivos y 3 listas filtradas por país, sector y monto.
- **3 redacciones por pregunta**: español con acentos, español sin acentos o desordenado, e inglés.
- **Búsqueda directa**: el texto tal cual a `knowledge/search`.
- **Consulta directa**: el texto tal cual a `knowledge/query`, que según la documentación de Cala acepta lenguaje natural además de su lenguaje de consultas.
- **Agente por MCP**: Codex CLI (`gpt-6-luna`, esfuerzo bajo) conectado al servidor MCP de Cala (`https://api.cala.ai/mcp/`) como única herramienta, sin la guía de Cala. Recibe la pregunta tal cual y elige solo qué herramientas llamar. Se le pide responder en inglés y listar aparte nombres y cifras, para comparar datos y no idiomas. Script: `canonizador/bench_mcp.py`; resultados en `canonizador/bench/results_mcp.json`.
- **Agente por MCP con la guía de Cala**: el mismo agente y el mismo prompt, con la guía oficial de uso de Cala (`docs/CALA-SKILL.md`, copia de `github.com/cala-ai/cala-skill`) agregada al comienzo. Sin canonizador. `python3 bench_mcp.py --guia`; resultados en `canonizador/bench/results_mcp_guia.json`.
- **Canonizador**: `canonizador.api.answer()`, que reduce la pregunta a una intención y arma la consulta de `knowledge_query` con una plantilla fija.
- Todo secuencial, con caché y reanudable. Los resultados crudos quedan en `canonizador/bench/results.json`.

## Resultados por pregunta

"Entidades en común" es el Jaccard medio de los ids de entidad devueltos entre las 3 redacciones (1 = idénticos).

| Pregunta | Búsqueda directa: respuestas distintas | Búsqueda directa: entidades en común | Consulta directa: respuestas distintas | Consulta directa: entidades en común | Canonizador: consultas | Canonizador: respuestas distintas |
|---|---|---|---|---|---|---|
| Serie B de Amenitiz | 3 de 3 | 0,35 | 3 de 3 | 0,78 | 1 | 1 |
| Fundadores de Glovo | 3 de 3 | 0,38 | 3 de 3 | 0,40 | 1 | 1 |
| Adquisiciones de Mews | 3 de 3 | 0,32 | 3 de 3 | 0,41 | 1 | 1 |
| Financiación total de Factorial | 3 de 3 | 0,36 | 3 de 3 | 0,33 | 1 | 1 |
| Inversores de Wolt | 3 de 3 | 0,69 | 3 de 3 | 0,53 | 1 | 1 |
| Ejecutivos de TravelPerk | 3 de 3 | 0,26 | 3 de 3 | 0,67 | 1 | 1 |
| Tecnología hotelera en España, > 10M | 3 de 3 | 0,16 | 3 de 3 | 0,39 | 1 | 1 |
| Fintech en Finlandia, > 5M | 3 de 3 | 0,33 | 3 de 3 | 0,40 | 1 | 1 |
| Climate tech en Alemania, > 20M | 3 de 3 | 0,33 | 3 de 3 | 0,23 | 1 | 1 |

Consultas que genera el canonizador (siempre la misma cadena para las 3 redacciones):
```
Amenitiz.funding_round.series=B.return(amount, lead investor, investors, date)
Glovo.founders.return(name)
Mews.acquisitions.return(name, date, amount)
Factorial.return(total funding)
Wolt.investors.return(name, is_lead)
TravelPerk.executives.return(name, title)
startups.location=Spain.sector=hotel technology.funding>10M.return(name, funding, sector, location)
startups.location=Finland.sector=fintech.funding>5M.return(name, funding, sector, location)
startups.location=Germany.sector=climate tech.funding>20M.return(name, funding, sector, location)
```

## Agente conectado por MCP

| Pregunta | Mismos nombres en las 3 | Mismas cifras en las 3 | Qué cambió |
|---|---|---|---|
| Serie B de Amenitiz | no | no | Los datos coinciden (€38,9M / ~$45M, Kfund vía Leadwind); cambia cómo se escriben |
| Fundadores de Glovo | no | — | 3 fundadores (con Gerard Olivé) · 2 · 2 |
| Adquisiciones de Mews | no | — | 13 o 14 empresas; Planet Winner falta en una y otra incluye a la propia Mews |
| Financiación total de Factorial | sí | no | **€523M · $370–420M · $572M** |
| Inversores de Wolt | no | no | 17 o 18 inversores, distintos en cada versión (Inventure, Atomico, DoorDash, ángeles…) |
| Ejecutivos de TravelPerk | sí | sí | Avi Meir en las 3 (la única consistente) |
| Tecnología hotelera en España, > 10M | no | no | TravelPerk, Amenitiz y HolaCamp · solo Hotelverse (con ~€8,2M, por debajo del umbral) · Amenitiz, Lodgify y HolaCamp |
| Fintech en Finlandia, > 5M | no | no | 15, 13 o 10 empresas, con cifras distintas |
| Climate tech en Alemania, > 20M | no | no | 12 empresas · ninguna (sin herramientas, ver abajo) · 13 empresas, con otras cifras |

Lo que hizo el agente:

- **Usó siempre la búsqueda en lenguaje natural.** Las 25 llamadas fueron a `knowledge_search`; nunca usó `knowledge_query` ni los endpoints de entidades, que son los que Cala recomienda para datos concretos.
- **Reescribió la pregunta antes de mandarla.** En 16 de las 25 llamadas no pasó el texto tal cual: la tradujo al inglés, la parafraseó o le agregó pedidos ("and how much did each invest?"). Hasta preguntas que ya estaban en inglés llegaron a Cala con otro texto. Las 25 llamadas usaron 24 textos distintos, así que casi cada versión es una consulta nueva para Cala.
- **En 2 de 27 no llamó a Cala.** En una respondió "no hay herramientas de Cala disponibles en esta sesión", así que la conexión al MCP falló en esa corrida. En la otra (fundadores de Glovo, sin acentos) respondió sin consultar nada, aunque se le pidió usar solo Cala: es una respuesta de memoria presentada como de Cala.

## Agente por MCP con la guía de Cala

La guía oficial le dice al agente qué herramienta usar en cada caso (consulta estructurada para filtros, entidades para datos concretos, búsqueda en lenguaje natural solo para preguntas abiertas) y que se detenga si falla, en vez de inventar.

| Pregunta | Herramientas usadas en las 3 redacciones | Resultado |
|---|---|---|
| Serie B de Amenitiz | búsqueda · búsqueda · búsqueda | Mismos datos (€38,9M, Kfund vía Leadwind); cambia cómo se escriben |
| Fundadores de Glovo | entidades · búsqueda · ninguna | 3 fundadores · 2 · sin respuesta (MCP no disponible) |
| Adquisiciones de Mews | entidades + búsqueda · búsqueda · búsqueda | Listas distintas |
| Financiación total de Factorial | entidades + búsqueda en las 3 | **€523M · €523M · $572M (y $420M)** |
| Inversores de Wolt | búsqueda en las 3 | Listas distintas |
| Ejecutivos de TravelPerk | búsqueda · búsqueda · ninguna | Avi Meir · Avi Meir · sin respuesta (MCP no disponible) |
| Tecnología hotelera en España, > 10M | consulta estructurada en las 3 | Amenitiz en las 3, con cifras distintas (€76–81M · ~€77M · ~€70M); las otras empresas cambian (Lodgify, The Hotels Network, Perk, BEONx, Civitatis) |
| Fintech en Finlandia, > 5M | consulta estructurada en las 3 | Listas y cifras distintas |
| Climate tech en Alemania, > 20M | consulta estructurada en las 3 | Listas y cifras distintas |

Comparado con el agente sin guía:

- **La guía cambia las herramientas, no la consistencia.** Sin guía, 25 de 25 llamadas fueron búsquedas en lenguaje natural. Con guía usó la consulta estructurada en las 9 preguntas de listas y las entidades en 3 preguntas, pero ninguna de las 9 preguntas dio los mismos datos en sus 3 redacciones (sin guía, 1 de 9).
- **El agente sigue escribiendo la consulta a su manera.** Con la consulta estructurada, cada redacción produjo una consulta distinta, y Cala devolvió empresas y cifras distintas. Es lo mismo que medimos al traducir con la guía de forma libre (`docs/INFORME-ERROR-CALA.md`, sección 2.3): la guía enseña el lenguaje de consultas, pero no fija una forma canónica.
- **Con la guía, no inventa cuando falla.** En la primera corrida 6 de 27 preguntas no pudieron conectarse al MCP, y en todas el agente respondió que las herramientas no estaban disponibles, como pide la guía. Al repetir esas 6, 4 funcionaron y 2 siguieron sin conexión; la tabla muestra la corrida repetida. Sin guía, en un caso respondió de memoria.
- **Las conexiones al MCP fallan con frecuencia**: 8 de 33 intentos en total sumando las dos corridas con guía. No sabemos si es el límite de uso de Cala o un problema del servidor MCP.

## Ejemplos de diferencias reales sin canonizar

No es solo redacción o idioma: cambian los datos.

| Pregunta | Búsqueda directa (3 redacciones) | Consulta directa (3 redacciones) | Canonizador |
|---|---|---|---|
| Financiación total de Factorial | $420M y €523M · €523M y $570M · $572M | $420M · $572M / €523M · €523M (~$570M+) | $572M |
| Fundadores de Glovo | 3 fundadores · 3 · 2 (sin Gerard Olivé) | 2 · 3 (con Gerard Olivé) · 2 | 2 (Oscar Pierre, Sacha Michaud) |
| Tecnología hotelera en España, > 10M | destaca TravelPerk · sin empresas destacadas · destaca Amenitiz | TravelPerk, Civitatis, Amenitiz… · TravelPerk, Amenitiz… · TravelPerk, Amenitiz… | Amenitiz y Room00, siempre |
| Climate tech en Alemania, > 20M | destaca Enpal en dos, ninguna en la tercera | empieza por 1KOMMA5° y Flix · empieza por Enpal · empieza por Enpal | Enpal, 1KOMMA5°, Sunfire…, siempre |

En la búsqueda directa, las cifras y nombres se extrajeron automáticamente del comienzo de cada respuesta (montos y textos en negrita), así que muestran lo que la respuesta pone en primer plano.

**La consulta directa también cambia el formato de las filas.** Para la misma pregunta, los campos se llaman `company`, `name`, `empresa`, `investor` o `startup`, y el líder de la ronda `lead_investor` o `leader`. Las filas pueden venir en español o en inglés según la pregunta. Un programa que consuma estas filas no puede depender de los nombres de campo. En la Serie B de Amenitiz los datos coinciden (€38,9M, Kfund) aunque las tres filas tienen formatos distintos.

## Cómo leer estos números (límites)

- **Hechos en común.** La búsqueda directa comparte 0 hechos entre redacciones en las 9 preguntas, pero según `INFORME-ERROR-CALA.md` los ids de `context` se generan por respuesta. Por eso ese 0 no prueba nada por sí solo y no lo usamos como métrica. Usamos los ids de entidad devueltos (que sí son estables) y los datos de la respuesta.
- **Respuestas distintas.** En los dos modos directos el texto y el formato cambian también por el idioma. Por eso la tabla de ejemplos compara cifras y nombres, no el texto.
- **Llamadas.** En esta corrida el canonizador hizo solo 2 llamadas porque las demás consultas ya estaban en caché por las pruebas anteriores. En frío serían 9: una por pregunta en vez de una por redacción.
- **Consistencia no es exactitud.** El canonizador garantiza la misma respuesta para la misma intención, no que sea correcta. Dos casos a mirar:
  - Glovo: el canonizado devuelve 2 fundadores; varias respuestas directas nombran a un tercero (Gerard Olivé). No verificamos cuál es el dato correcto.
  - Amenitiz: el cruce con los endpoints de entidades marca discrepancia: la ronda figura con 3.000 M EUR en el dato estructurado y con €38,9 M en la consulta. El canonizador la señala en vez de elegir en silencio.
- **Agente por MCP.** Es un solo agente (Codex con un modelo chico y esfuerzo bajo), con y sin la guía de Cala. Un modelo más grande podría elegir mejor las herramientas, pero el problema de fondo (cada redacción produce otra consulta) no depende de la herramienta elegida. La comparación de "mismos nombres" usa la lista que el propio agente extrajo de su respuesta.
- **Muestra chica.** 9 preguntas, 3 redacciones cada una, una sola corrida por modo. El sector depende de una lista cerrada de etiquetas, y un sector fuera de la lista cae en "other".

## Cómo reproducirlo

```bash
cd canonizador
uv sync --extra dev
uv run python bench.py          # reanudable; escribe bench/results.json
python3 bench_mcp.py            # agente por MCP; reanudable; escribe bench/results_mcp.json
python3 bench_mcp.py --guia     # lo mismo con la guía de Cala; escribe bench/results_mcp_guia.json
```
Requiere `CALA_API_KEY` en `backend/.env` y el CLI de Codex logueado (el LLM que extrae la intención). Las preguntas están en `bench/questions.json`. Para una corrida en frío, borrar `canonizador/cache/` y `bench/results.json`.
