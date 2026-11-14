# Spec: subgrafo local y puntaje de afinidad (Cala Match)

Issue #68. La leen `fabricio` (#64 grafo en Valkey, #65 API del feed), `adrian` (#62 app) y `gabriel` (#66 contexto). Es una **propuesta**: lo marcado *(a validar)* depende de datos que todavía no medimos.

## 1. Qué sabemos (medido el 14/11, semilla Amenitiz, 185 nodos y 246 aristas)
- Los endpoints de entidades responden en ~1 s; `knowledge/query` y `knowledge/search`, en 16–60 s. El límite de uso saltó con 10 llamadas seguidas.
- Recorrer el subgrafo en local: BFS completo en 0,13 ms. El tamaño no es un problema.
- **Cada arista trae sus fuentes**, pero dentro de `properties`, no en el elemento: `{id, name, entity_type, properties: {role, is_lead, valid_since, valid_until, event_date, sources: [...], id: <id de la arista>}}`. (Mi primer script leía mal esa ruta y contó cero fuentes; está corregido aquí.)
- Mucho ruido: 54 de 185 nodos eran `PrivateCompanyFundingRound` (registros sin inversores con el mismo nombre genérico), más productos, premios y países.
- Duplicados reales: el mismo fondo aparece como `Organization` y como `Company` ("Chalfen Ventures" y "CHALFEN VENTURES LLP", "Otium Capital" dos veces: 2 de 33 vecinos). Y "Amenitiz" existe como empresa y como producto, que **no** son lo mismo.

## 2. Modelo de datos
**Nodo** `{id, type, name, aliases[], props{}, loaded_at, expanded: {<conjunto de relaciones>: <fecha>}}`. `id` canónico = el de la `Company` si hay duplicados (sección 4).

**Arista** `{id, src, dst, rel, role?, is_lead?, valid_since?, valid_until?, event_date?, sources[], loaded_at}`.
- Se guarda siempre orientada como `src → dst` según el sentido semántico de Cala (`INVESTED_IN`: inversor → empresa), sin importar desde qué nodo se leyó. Así una arista leída desde las dos puntas es una sola.
- Sin `sources` no se muestra al usuario (regla del proyecto: todo dato con su fuente).

**Valkey** (prefijo `graph:v1:`, TTL 7 días, igual que la caché cruda):
| Clave | Valor |
|---|---|
| `node:<id>` | el nodo |
| `adj:<id>` | las aristas que tocan ese nodo (lista de ids de arista) |
| `edge:<id>` | la arista |
| `alias:<nombre normalizado>` | id canónico (para unir duplicados y resolver nombres) |
| `view:<usuario>:seeds` | ids de las semillas del usuario |
| `view:<usuario>:nodes` | conjunto de ids que le interesan |
Un solo grafo compartido; **el subgrafo de cada usuario es una vista** (lista de ids), no una copia. El nodo del usuario que aún no existe en Cala es **temporal y local**: no se escribe en `node:` compartido; se conecta a sus semillas en memoria.

## 3. Qué se recorre y qué no
Se recorren solo aristas con significado de negocio:
`INVESTED_IN`, `PARTICIPATES_IN_FUNDING_ROUND` (con `role` y `is_lead`), `FOUNDED`, `IS_CEO_OF`, `IS_CTO_OF`, `IS_BOARD_MEMBER_OF`, `WORKS_AT`, `IS_MEMBER_OF`, `PARTICIPATES_IN_CORPORATE_EVENT` solo si es M&A (`MNA_*`), `PARTICIPATES_IN_EVENT` (Slush 2026).

Se **leen como atributo pero no se recorren** (conectan todo con todo): `OPERATES_IN_INDUSTRY`, `HAS_HEADQUARTERS_IN`, `IS_REGISTERED_IN`, `HAS_DOMAIN_NAME`. Sirven para el sector y la región del afinidad.

Se **excluyen**: nodos `PrivateCompanyFundingRound` (se cuentan, no se guardan), `Product`, `Award`, `Country`, `Group`, `EducationalInstitution`. Excepción: guardar el producto solo si hace falta mostrarlo en el detalle.

Pedir `limit: 100` por relación. Si vuelve exactamente 100, marcar `truncated: true`: hay más y el nodo es un concentrador (Eight Roads dio 74 aristas con ese límite).

## 4. Unir duplicados
Clave de unión = nombre normalizado (minúsculas, sin acentos, sin sufijo legal: `LLP, Ltd, Inc, GmbH, AB, Oy, SA, SL, BV`) **+** tipo compatible (`Company` con `Organization` se unen; con `Product` o `Award`, nunca) **+** `website` si ambos lo tienen. Ante duda, no unir. El id canónico es el de la `Company`; el otro queda en `aliases` y en `alias:`. *(a validar con 20 fondos reales: cuántos falsos positivos da.)*

## 5. Recorrido (BFS con cupo por nivel)
1. **Semillas**: Gemini saca del perfil y del contexto las entidades nombradas (su startup, sus inversores, competidores) y se resuelven con `entity_search`. Sector, etapa, región y ticket **no son nodos**: son restricciones (sección 6).
2. **Nivel 0 → 1**: introspección + retrieval de cada semilla con la lista blanca de la sección 3. Para perfilar a cada inversor candidato, **una** consulta `knowledge/query` (`startups.investors=<fondo> return(company, round_type, funding_amount, year, sector, location)`) trae todas sus rondas de una vez; es lenta pero es una llamada, no cuarenta.
3. **Niveles siguientes**: se expande por prioridad, no por orden de llegada: primero los nodos que mejor cumplen las restricciones. **Cupo por nivel: 15 expansiones** (con ~1 s por llamada son ~15–30 s; ajustar cuando #63 mida el límite real). Profundidad máxima 2, tercer nivel solo en segundo plano.
4. Cada llamada respeta la pausa por endpoint de #63. Mientras no esté, usar 1 s para entidades.
5. **Segundo plano**: al mostrar una respuesta o una tarjeta, se encolan las expansiones de los nodos que aparecen en ella (precarga). Lo que el usuario descarta no se expande.

**Distancia** = nivel BFS sobre el grafo sin dirección, con todas las aristas valiendo 1 (equivale a Dijkstra). Es el camino mínimo **dentro de lo explorado**, no en todo Cala; no presentarlo como "el camino más corto que existe". Si algún día hay pesos (cofundador < mismo empleador, vigente < histórico), la cola pasa a prioridad.

## 6. Puntaje de afinidad (v1)
Entrada: perfil del usuario `{sector[], stage, region[], ticket {min,max}, seeds[]}` y una entidad candidata. Es el mismo cálculo en los dos modos; cambia quién es el candidato.

| Señal | Peso | Cómo se calcula (0 a 1) | Dato de Cala |
|---|---|---|---|
| Sector | 0,30 | Raising: porcentaje de las rondas del inversor en el sector del usuario. Investing: la startup está en un sector de la tesis del inversor | `knowledge/query` del inversor (columna sector), `OPERATES_IN_INDUSTRY` |
| Etapa | 0,20 | Porcentaje de rondas del inversor en la etapa que busca la startup (`round_type`) | `knowledge/query` |
| Región | 0,15 | 1 mismo país, 0,6 misma región (Nordics, DACH, Iberia), 0 el resto | `location`, `HAS_HEADQUARTERS_IN` |
| Ticket | 0,15 | 1 si el monto buscado cae en el rango habitual del inversor (mediana ± un cuartil), decae fuera | `funding_amount` de sus rondas |
| Actividad | 0,10 | Rondas lideradas o seguidas en los últimos 24 meses (saturar en 5) | `year`, `is_lead` |
| Cercanía en el grafo | 0,10 | 1 inversor ya en común, 0,6 a distancia 2, 0,3 a distancia 3, 0 si no hay camino | el subgrafo local |

- `score = round(100 × Σ wᵢ·sᵢ / Σ wᵢ)` **solo sobre las señales con dato**. Una señal sin dato no cuenta como cero: se omite y baja la `confidence`.
- `confidence` = suma de pesos con dato (0 a 1). La tarjeta muestra el puntaje; `confidence < 0,5` se marca como "partial data".
- Colores de la tarjeta (coinciden con el diseño de Stitch): verde ≥ 80, ámbar 60–79, gris < 60.
- **Explicable siempre**: cada señal devuelve una frase con su dato y sus fuentes ("Led 3 similar rounds in 2025"). `why_match` en la tarjeta son las dos señales con mayor aporte.
- Los pesos son una primera propuesta, **no calibrados**. Calibrar con 10 pares conocidos (por ejemplo Amenitiz con Eight Roads y Chalfen debería dar un puntaje alto) antes de la demo.
- Orden del feed: puntaje descendente; a igual puntaje, mayor `confidence`.

## 7. Contrato (borrador, en `docs/API.md`)
Quedó agregado como *(borrador)*: `GET /api/feed`, `GET /api/entities/{id}` y `FeedCard`. `fabricio` y `adrian` coordinan cambios entre ellos y avisan a `bau` si se rompe algo ya marcado como estable.

## 8. Preguntas abiertas
1. ¿`is_lead` viene siempre? Es clave para "actividad" y "who actually leads". *(pregunta al stand de Cala)*
2. ¿Un fondo es `Organization` o `Company`? En la muestra hubo de los dos; confirmar con más fondos.
3. ¿Cuántas llamadas seguidas aguantan las entidades? Lo mide #63; define el cupo de la sección 5.
4. ¿Cobertura de startups nórdicas y españolas? Sin eso el modo Investing puede quedar flaco.
5. La startup del usuario puede no estar en Cala: el afinidad debe funcionar con el nodo temporal y solo con las restricciones del perfil.

## 9. Criterios de hecho de esta spec
- Con la semilla Amenitiz, el grafo guardado no tiene `PrivateCompanyFundingRound` ni productos, y "Chalfen" y "Otium" quedan como un solo nodo cada uno.
- Una búsqueda repetida del mismo usuario no hace ninguna llamada a Cala.
- Cada tarjeta del feed trae `score`, `confidence`, `why_match` y `sources`.
