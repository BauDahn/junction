# Benchmark: canonizador vs. preguntas directas a Cala

Junction 2026, reto de Cala. Corridas del 14/11/2026 contra la API real. Complementa a `docs/INFORME-ERROR-CALA.md` (qué es el error y qué sabemos del grafo); este documento solo trae los números del benchmark.

## Resumen

Tres formas de preguntarle lo mismo a Cala:

| | Búsqueda directa | Consulta directa | Canonizador |
|---|---|---|---|
| Qué recibe Cala | La pregunta tal cual, en `POST /v1/knowledge/search` | La pregunta tal cual, en `POST /v1/knowledge/query` (sin guía ni plantilla) | Una consulta armada con plantilla fija, en `POST /v1/knowledge/query` |
| Preguntas | 9 × 3 redacciones = 27 | las mismas 27 | las mismas 27 |
| Consultas distintas que llegan a Cala | 27 | 27 | **9** |
| Preguntas con la misma respuesta en sus 3 redacciones | **0 de 9** | **0 de 9** | **9 de 9** |
| Llamadas a Cala | 27 | 27 | 9 en frío (en esta corrida, 2: el resto ya estaba en caché) |
| Tiempo | 906 s; 33,6 s de media (máx. 61 s) | 939 s; 34,8 s de media (máx. 65 s) | ~21 s en esta corrida (casi todo caché) |

Mandar lenguaje natural sin canonizar es inconsistente en las dos APIs de conocimiento. La consulta directa no corrige el problema: también cambia datos, empresas y hasta el formato de la respuesta según cómo se escriba la pregunta.

## Qué se midió

- **9 preguntas** de 7 tipos: ronda concreta, fundadores, adquisiciones, financiación total, inversores, ejecutivos y 3 listas filtradas por país, sector y monto.
- **3 redacciones por pregunta**: español con acentos, español sin acentos o desordenado, e inglés.
- **Búsqueda directa**: el texto tal cual a `knowledge/search`.
- **Consulta directa**: el texto tal cual a `knowledge/query`, que según la documentación de Cala acepta lenguaje natural además de su lenguaje de consultas.
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
- **Muestra chica.** 9 preguntas, 3 redacciones cada una, una sola corrida por modo. El sector depende de una lista cerrada de etiquetas, y un sector fuera de la lista cae en "other".

## Cómo reproducirlo

```bash
cd canonizador
uv sync --extra dev
uv run python bench.py          # reanudable; escribe bench/results.json
```
Requiere `CALA_API_KEY` en `backend/.env` y el CLI de Codex logueado (el LLM que extrae la intención). Las preguntas están en `bench/questions.json`. Para una corrida en frío, borrar `canonizador/cache/` y `bench/results.json`.
