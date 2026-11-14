# Benchmark: canonizador vs. preguntas directas a Cala

Junction 2026, reto de Cala. Corrida del 14/11/2026 contra la API real. Complementa a `docs/INFORME-ERROR-CALA.md` (qué es el error y qué sabemos del grafo); este documento solo trae los números del benchmark.

## Resumen

| | Directo (`knowledge/search` con el texto tal cual) | Canonizado (`canonizador/`) |
|---|---|---|
| Preguntas | 9 preguntas × 3 redacciones = 27 | las mismas 27 |
| Consultas distintas que llegan a Cala | 27 (una por redacción) | **9 (una por pregunta)** |
| Grupos donde las 3 redacciones dan la misma respuesta | **0 de 9** | **9 de 9** |
| Llamadas a Cala | 27 | 9 en frío (en esta corrida, 2: el resto ya estaba en caché por pruebas anteriores) |
| Tiempo | 906 s en total, 33,6 s de media por pregunta (máx. 61 s) | ~21 s en total en esta corrida (casi todo caché) |

## Qué se midió

- **9 preguntas** de 7 tipos: ronda concreta, fundadores, adquisiciones, financiación total, inversores, ejecutivos y 3 listas filtradas por país, sector y monto.
- **3 redacciones por pregunta**: español con acentos, español sin acentos o desordenado, e inglés.
- **Modo directo**: el texto tal cual a `POST /v1/knowledge/search`.
- **Modo canonizado**: `canonizador.api.answer()`, que reduce la pregunta a una intención y arma la consulta de `knowledge_query` con una plantilla fija.
- Todo secuencial, con caché y reanudable. Los resultados crudos quedan en `canonizador/bench/results.json`.

## Resultados por pregunta

| Pregunta | Directo: respuestas distintas | Directo: entidades en común entre redacciones (Jaccard medio) | Canonizado: consultas | Canonizado: respuestas distintas |
|---|---|---|---|---|
| Serie B de Amenitiz | 3 de 3 | 0,35 | 1 | 1 |
| Fundadores de Glovo | 3 de 3 | 0,38 | 1 | 1 |
| Adquisiciones de Mews | 3 de 3 | 0,32 | 1 | 1 |
| Financiación total de Factorial | 3 de 3 | 0,36 | 1 | 1 |
| Inversores de Wolt | 3 de 3 | 0,69 | 1 | 1 |
| Ejecutivos de TravelPerk | 3 de 3 | 0,26 | 1 | 1 |
| Tecnología hotelera en España, > 10M | 3 de 3 | 0,16 | 1 | 1 |
| Fintech en Finlandia, > 5M | 3 de 3 | 0,33 | 1 | 1 |
| Climate tech en Alemania, > 20M | 3 de 3 | 0,33 | 1 | 1 |

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

## Ejemplos de diferencias reales en modo directo

No es solo redacción o idioma: cambian los datos.

| Pregunta | Redacción 1 | Redacción 2 | Redacción 3 (inglés) | Canonizado |
|---|---|---|---|---|
| Financiación total de Factorial | $420M y €523M | €523M y $570M | $572M | $572M |
| Fundadores de Glovo | Oscar Pierre, Sacha Michaud, Gerard Olivé | Oscar Pierre, Sacha Michaud, Gerard Olivé | Óscar Pierre, Sacha Michaud | Oscar Pierre, Sacha Michaud |
| Tecnología hotelera en España, > 10M | destaca TravelPerk | sin empresas destacadas | destaca Amenitiz | Amenitiz y Room00, siempre |

Las cifras y nombres de esta tabla se extrajeron automáticamente del comienzo de cada respuesta (montos y textos en negrita), así que muestran lo que la respuesta pone en primer plano, no todo su contenido.

## Cómo leer estos números (límites)

- **Hechos en común.** El modo directo comparte 0 hechos entre redacciones en las 9 preguntas, pero según `INFORME-ERROR-CALA.md` los ids de `context` se generan por respuesta. Por eso ese 0 no prueba nada por sí solo y no lo usamos como métrica. Usamos las entidades devueltas (que sí son ids estables) y los datos de la respuesta.
- **Respuestas distintas.** En modo directo el texto cambia también por el idioma de la respuesta. Por eso la tabla de ejemplos compara cifras y nombres, no el texto.
- **Llamadas.** En esta corrida el modo canonizado hizo solo 2 llamadas porque las demás consultas ya estaban en caché por las pruebas anteriores. En frío serían 9: una por pregunta en vez de una por redacción.
- **Consistencia no es exactitud.** El canonizador garantiza la misma respuesta para la misma intención, no que sea correcta. Dos casos a mirar:
  - Glovo: el canonizado devuelve 2 fundadores; dos respuestas directas nombran a un tercero (Gerard Olivé). No verificamos cuál es el dato correcto.
  - Amenitiz: el cruce con los endpoints de entidades marca discrepancia: la ronda figura con 3.000 M EUR en el dato estructurado y con €38,9 M en la consulta. El canonizador la señala en vez de elegir en silencio.
- **Muestra chica.** 9 preguntas, 3 redacciones cada una, una sola corrida. El sector depende de una lista cerrada de etiquetas, y un sector fuera de la lista cae en "other".

## Cómo reproducirlo

```bash
cd canonizador
uv sync
uv run python bench.py          # reanudable; escribe bench/results.json
```
Requiere `CALA_API_KEY` en `backend/.env` y el CLI de Codex logueado (el LLM que extrae la intención). Las preguntas están en `bench/questions.json`. Para una corrida en frío, borrar `canonizador/cache/` y `bench/results.json`.
