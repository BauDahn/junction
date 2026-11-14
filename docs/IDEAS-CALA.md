# IDEAS-CALA: opciones para el reto de Cala

> Agente IDEAS · vie 2026-11-13 · Base: RETOS.md (sección 3) y CALA-VS-MARIADB.md. **Son propuestas: la elección es del usuario.**
> Criterios del jurado: necesidad real 25% · ejecución 25% · originalidad 25% · uso de Cala 25%. "Focus beats breadth". Tiene que poder usarse al día siguiente, en Slush.
> **[verificar]** = depende de qué datos tenga Cala realmente (preguntar en el stand: lead/follow, personas y roles, fechas, adquisiciones, cobertura europea).

## Por qué el grafo de Cala y no una búsqueda web (el argumento común)
La búsqueda web da **documentos**; Cala da **relaciones estructuradas con fuente**: quién invirtió en qué, cuándo, en qué rol, quién trabaja dónde. Las ideas de abajo dependen de **consultas sobre el grafo**: recorridos de varios saltos, agregados temporales, comparables y caminos entre nodos. Con Google eso implica leer 200 páginas a mano. Cada idea explica qué consulta del grafo es la que la hace imposible sin Cala.

---

## Para founders

### 1. ★ Radar de primeros clientes ("First 10 customers")
- **Usuario y dolor**: founder B2B en etapa seed que no sabe a quién venderle primero y prospecta en frío.
- **Qué hace**: lista las empresas de tu segmento que **acaban de levantar plata**, rankeadas por timing, fit y una persona de contacto, cada una con la ronda que funciona como señal.
- **Por qué Cala**: necesita el filtro "ronda en las últimas N semanas × sector × tamaño × país" + las personas de cada empresa + los inversores en común. Es un join sobre el grafo; con búsqueda web serían horas.
- **Wow**: escribís "vendo compliance para fintechs" y en 5 s aparecen "12 fintechs que levantaron en los últimos 60 días, quién decide la compra en cada una y qué inversor tenés en común con ellas".
- **En Slush**: "estas empresas recién financiadas están en Slush: buscalas hoy". Una lista exportable para el celular.
- **Riesgo**: la cobertura de datos de personas y roles **[verificar]**. **Dificultad**: media.

### 2. Who actually leads: quién lidera hoy rondas como la tuya
- **Usuario y dolor**: un founder que va a levantar su ronda y pierde meses con fondos que solo siguen, o que ya no invierten.
- **Qué hace**: un ranking de **leads activos** para tu perfil (etapa, sector, país), con el partner que hizo cada deal y la evidencia.
- **Por qué Cala**: necesita distinguir **lead vs follow** y la recencia por inversor y partner, que son agregados sobre rondas. **[verificar]** si existe el rol de lead.
- **Wow**: muestra "fondos que te dirían que sí pero nunca lideran", tachados en rojo, frente a los 5 que sí lideraron 3 rondas parecidas este año.
- **En Slush**: tu lista de 10 inversores para cazar en el evento, con el nombre del partner.
- **Riesgo**: es **la idea que más equipos van a hacer**. **Dificultad**: baja-media.

### 3. ★ Escalera de inversores ("Investor pathways")
- **Usuario y dolor**: un founder pre-seed que elige su inversor seed sin saber **qué puertas le abre para la Series A**.
- **Qué hace**: para cada inversor seed, muestra **qué pasó después con sus empresas**: qué porcentaje llegó a la Serie A, en cuánto tiempo y **qué fondos lideraron esa A**.
- **Por qué Cala**: es un recorrido de varios saltos (inversor seed → sus empresas → rondas siguientes → leads de esas rondas) con tiempos. No sale de una búsqueda web.
- **Wow**: un diagrama Sankey: "las empresas que levantaron seed con el fondo X llegaron a Serie A en el 41% de los casos, 70% de ellas con estos 3 fondos". Comparás dos term sheets por el camino que abren.
- **En Slush**: "¿con qué ángel o fondo me conviene cerrar la seed?". Sirve para decidir entre ofertas.
- **Riesgo**: requiere historial de varias rondas por empresa **[verificar la profundidad]**. **Dificultad**: media.

### 4. Camino de introducción ("Warm intro path")
- **Usuario y dolor**: un founder sin red de contactos; los intros en frío no funcionan.
- **Qué hace**: el camino más corto y "más cálido" desde tu equipo (empresas previas, inversores actuales) hasta un inversor o cliente objetivo.
- **Por qué Cala**: es un shortest path en el grafo de personas, empresas y fondos con la fuente de cada arista.
- **Wow**: "tu CTO trabajó en Y con la partner de Z: pedile el intro a ella".
- **En Slush**: los intros para pedir esa misma noche.
- **Riesgo**: depende de los datos de historial laboral **[verificar]** y es parecido a LinkedIn. **Dificultad**: media.

### 5. "Termómetro de mercado": ¿es buen momento para levantar en mi vertical?
- **Usuario y dolor**: un founder que no sabe si su sector está "caliente" o "frío" ahora.
- **Qué hace**: muestra el flujo de rondas por mes en tu vertical y país: cantidad, tamaño, fondos que entran y fondos que dejaron de invertir.
- **Por qué Cala**: series temporales sobre las rondas, segmentadas por sector e inversor.
- **Wow**: "3 fondos que eran activos en tu vertical no invirtieron nada en 9 meses: no pierdas tiempo con ellos".
- **En Slush**: el contexto para tu pitch ("el mercado está creciendo X%").
- **Riesgo**: es algo que hacen Dealroom/Crunchbase (poco original). **Dificultad**: baja.

---

## Para inversores

### 6. ★ Verificador de decks ("Deck fact-check")
- **Usuario y dolor**: un business angel o analista que recibe 50 decks en Slush y no tiene tiempo de verificar lo que dicen ("respaldados por X", "ex-Google", "levantamos €2M").
- **Qué hace**: subís el PDF del deck, el producto extrae las afirmaciones verificables y las contrasta con Cala: ✔ confirmada, ⚠ difiere o ? sin dato, cada una con su fuente.
- **Por qué Cala**: necesita datos **estructurados y con fuente** para confirmar o refutar rondas, inversores y trayectorias. La web da ruido; Cala da evidencia citable.
- **Wow**: subís un deck en vivo y en 10 segundos aparece "Inversor X en la ronda seed: ✔ (fuente). Ronda de €2M: ⚠, Cala registra €1.2M".
- **En Slush**: **es el caso perfecto**: el angel recibe un deck en el celular y lo verifica antes de la reunión.
- **Riesgo**: el tono de "acusar" al founder (mejor enmarcarlo como "due diligence rápida") y extraer afirmaciones de PDFs variados. **Dificultad**: media.

### 7. Radar de rondas atrasadas ("Overdue for a round")
- **Usuario y dolor**: un inversor de follow-on o de secundario, o un comprador corporativo, que busca empresas que **ya deberían haber levantado** según lo típico de su etapa y sector y no lo hicieron (puede ser una oportunidad o una alerta).
- **Qué hace**: el tiempo desde la última ronda contra la mediana de su cohorte; marca las que se pasaron del percentil 75.
- **Por qué Cala**: necesita cohortes (sector × etapa × año) y los tiempos entre rondas, agregados sobre todo el grafo.
- **Wow**: "estas 20 startups de Serie A no levantan hace 30 meses, cuando la mediana es 20: posibles bridge rounds o adquisiciones".
- **En Slush**: una lista de conversaciones "¿cómo están de runway?" para inversores de secundarios o M&A.
- **Riesgo**: que una ronda falte en los datos genera falsos positivos. **Dificultad**: media.

### 8. Armador de sindicatos ("Syndicate builder")
- **Usuario y dolor**: un fondo que lidera y tiene que **completar la ronda** con co-inversores compatibles.
- **Qué hace**: recomienda co-inversores según el historial de co-inversión con vos y la actividad reciente en el sector y la etapa.
- **Por qué Cala**: es un grafo de co-inversión (proyección inversor–inversor a través de las rondas compartidas).
- **Wow**: un grafo interactivo: "estos 4 fondos co-invirtieron con vos 3 veces y están activos en climate tech".
- **En Slush**: a quién buscar para cerrar la ronda.
- **Riesgo**: es un nicho (son pocos usuarios). **Dificultad**: baja-media.

### 9. Mapa de compradores ("Acquirer map")
- **Usuario y dolor**: un founder o inversor que piensa en la salida: ¿quién compra empresas como esta?
- **Qué hace**: lista los adquirentes probables según sus compras previas de empresas parecidas, los inversores en común y el solapamiento de sector.
- **Por qué Cala**: depende de que Cala tenga **adquisiciones** como aristas **[verificar, es crítico]**.
- **Wow**: "3 de los últimos 5 compradores de startups de logística nórdicas comparten un inversor con vos".
- **Riesgo**: sin datos de adquisiciones, la idea no existe. **Dificultad**: media.

---

## Fuera del menú

### 10. Radar de carreras para estudiantes ("¿quién va a contratar?")
- **Usuario y dolor**: estudiantes (como nosotros) que buscan prácticas o un primer empleo en startups y no saben **cuáles tienen plata fresca y van a contratar**.
- **Qué hace**: muestra las startups que levantaron en los últimos 90 días en tu ciudad y tu área, con el tamaño de la ronda, los founders y su trayectoria (por ejemplo, "founders ex-Supercell").
- **Por qué Cala**: ronda reciente × ciudad × sector × personas.
- **Wow**: "Helsinki, ML, levantaron en los últimos 90 días: 14 startups. Este es el CTO de cada una".
- **En Slush**: Slush está lleno de estudiantes voluntarios y buscando trabajo: es una historia auténtica (somos el usuario).
- **Riesgo**: el jurado puede verlo fuera del público "founders o investors". Se puede reencuadrar como "founders que necesitan contratar se cruzan con talento". **Dificultad**: baja.

### 11. Pulso de ecosistemas para agencias públicas ("Ecosystem pulse")
- **Usuario y dolor**: agencias como ACCIÓ (Catalunya) o Business Finland que quieren medir qué capital extranjero entra a su ecosistema y qué fondos atraer.
- **Qué hace**: compara flujos de capital entre ecosistemas (por ejemplo, Barcelona vs. Helsinki): qué fondos extranjeros invierten en cada uno, en qué sectores, y las tendencias.
- **Por qué Cala**: agregados por geografía de la empresa × geografía del inversor a lo largo del tiempo.
- **Wow**: "los 10 fondos que invierten en Helsinki y nunca en Barcelona: ACCIÓ, estos son tus objetivos para Slush".
- **En Slush**: las agencias están ahí con stands. **Encaja con el ángulo catalán** y se puede validar con los fundadores de Cala.
- **Riesgo**: está fuera del público principal y es un nicho B2G. **Dificultad**: baja-media.

### 12. Planificador de agenda para Slush ("Slush planner")
- **Usuario y dolor**: un founder con 2 días de Slush y miles de asistentes; no sabe a quién priorizar.
- **Qué hace**: cruza la lista pública de oradores y expositores de Slush **[verificar que exista y se pueda usar]** con el grafo de Cala y arma una agenda priorizada ("estos 8 inversores que hablan o tienen stand lideraron rondas como la tuya").
- **Por qué Cala**: el valor está en enriquecer y rankear según el grafo; la lista sola no sirve.
- **Wow**: tu agenda de Slush personalizada en 30 segundos.
- **En Slush**: **es literalmente para el lunes**.
- **Riesgo**: depende de los datos de Slush y es efímero (sirve para un evento). Se puede combinar como "modo Slush" de las ideas 1 o 2. **Dificultad**: baja.

---

## Tabla de puntuación (1–5 por criterio; total ponderado sobre 5)

| # | Idea | Público | Necesidad | Ejecución (factib. ~36h) | Originalidad | Uso de Cala | **Total /5** | Competencia esperada |
|---|------|---------|-----------|--------------------------|--------------|-------------|--------------|----------------------|
| 1 | ★ Radar de primeros clientes | Founders | 5 | 4 | 4 | 5 | **4.50** | Media-baja |
| 3 | ★ Escalera de inversores | Founders | 4 | 4 | 5 | 5 | **4.50** | Baja |
| 6 | ★ Verificador de decks | Inversores | 5 | 3 | 5 | 4 | **4.25** | Baja |
| 2 | Who actually leads | Founders | 5 | 5 | 2 | 5 | 4.25 | **Muy alta** |
| 7 | Rondas atrasadas | Inversores | 4 | 4 | 4 | 5 | 4.25 | Baja |
| 12 | Slush planner | Founders | 4 | 4 | 4 | 3 | 3.75 | Media |
| 4 | Camino de introducción | Founders | 4 | 3 | 3 | 4 | 3.50 | Media |
| 8 | Armador de sindicatos | Inversores | 3 | 4 | 3 | 4 | 3.50 | Baja |
| 11 | Pulso de ecosistemas | Agencias | 3 | 4 | 4 | 4 | 3.75 | Muy baja |
| 10 | Radar de carreras | Estudiantes | 3 | 5 | 3 | 4 | 3.75 | Media |
| 9 | Mapa de compradores | Founders/inv. | 4 | 2 | 4 | 4 | 3.50 (si hay datos de M&A) | Baja |
| 5 | Termómetro de mercado | Founders | 3 | 5 | 1 | 4 | 3.25 | Alta |

Los puntajes son mi estimación. Dependen mucho de la cobertura de datos que confirme el stand.

**Mis 3 favoritas** (la decisión queda en manos del usuario):
1. **Radar de primeros clientes**: es la más útil al día siguiente, el uso de Cala es central y es un ángulo que los demás no van a tomar.
2. **Escalera de inversores**: es la más original. Responde una pregunta que nadie más puede responder sin un grafo de varios saltos.
3. **Verificador de decks**: es la demo más memorable y encaja perfecto con Slush, pero tiene el mayor riesgo de ejecución (parsear PDFs).

**Combinaciones posibles**: 1 + "modo Slush" (12) · 3 + 2 (la escalera con un ranking de leads activos como segunda pestaña) · 6 + 7 (una suite de due diligence). Ojo: el jurado pide **foco**, así que combinar solo si la segunda parte es una pestaña chica.

---

## Stitch (Google) en el flujo: ¿sirve?
**Sí, para la parte visual, no para la lógica.** Stitch genera pantallas a partir de un prompt o un boceto y exporta HTML/CSS o a Figma **[verificar el formato de exportación actual]**.
- **Para qué ideas**: pesa más en las que tienen una **UI vistosa como "wow"**: el verificador de decks (pantalla de carga + tarjetas ✔/⚠), la escalera de inversores (pantalla con Sankey y comparación de inversores) y el Slush planner (agenda mobile-first). En el radar de clientes también sirve para la tabla y la ficha de cada empresa.
- **Cómo encaja**: (1) el sábado a la mañana se generan 3–4 pantallas en Stitch (input, resultados, detalle con fuentes, versión móvil para Slush); (2) se exportan y Claude Code las convierte en componentes conectados a la API de Cala; (3) las mismas pantallas sirven como **mockups del deck** si alguna parte no llega a estar funcional.
- **No conviene**: depender de Stitch para gráficos interactivos (el Sankey y los grafos van con una librería de gráficos) ni tocar la UI generada a último momento. Hay que fijar el diseño temprano.
- **Ahorro estimado**: 2–4 horas de diseño y un look más profesional, que suma en "ejecución".

## Preguntas para el stand de Cala (para elegir entre las 3)
1. ¿Distinguen **lead vs follow** en las rondas? (es clave para las ideas 2 y 3)
2. ¿Qué profundidad tiene el historial de rondas por empresa (seed → A → B)? (idea 3)
3. ¿Hay **personas con roles** en las empresas, y su historial laboral? (ideas 1 y 4)
4. ¿Tienen **adquisiciones**? (idea 9)
5. ¿Cuánta cobertura tienen de Europa y los nórdicos en 2025–2026, y con qué frescura (cuántos días de retraso)?
6. Si les contamos las ideas 1, 3 y 6, ¿cuál les entusiasma más? **Esta es la validación del ángulo catalán**: usarla.
7. ¿Límites de la API, uso de MCP y créditos durante la hackatón?


---

## Ajuste según la API (sáb 2026-11-14, base: CALA-API.md)

### Qué cambia con lo que sabemos de la API
- **A favor**: (a) `knowledge/search` ya devuelve **respuestas con fuentes** (explainability + origins con URL), así que la verificación con citas viene "de fábrica"; (b) `knowledge/query` devuelve **filas estructuradas** que se pueden filtrar y ordenar (sirve para rankear); (c) existen **Person con rol** y **relaciones con `valid_since`/`valid_until`** (historial laboral con fechas); (d) existe **CorporateEvent (M&A)**, así que el mapa de compradores deja de ser hipotético.
- **En contra**: (a) **no hay tipo Investor** y **no está documentado lead vs follow**; (b) no se sabe el costo por llamada, la latencia ni los límites (solo un 429), así que hay que diseñar con **caché y pocas llamadas por pantalla**; (c) no se sabe la cobertura nórdica ni española ni la frescura de los datos.
- **Encaje con la postura del usuario** ("no tocar Cala, mostrar para qué sirve"): las ideas que **ponen a Cala en un flujo de trabajo concreto** (preparar ventas, revisar un deck) se lucen más que las que exigen análisis profundos del grafo, que la API puede no soportar bien.

### Revisión de las 12 ideas

| # | Idea | Estado | Por qué | Nuevo total /5 (antes) |
|---|------|--------|---------|------------------------|
| 1 | Radar de primeros clientes | ✅ **Mejora** | Solo necesita rondas recientes + sector + personas con rol, todo documentado. `query` da filas para rankear | **4.50** (4.50) |
| 6 | Verificador de decks | ✅ **Mejora mucho** | Nemotron VL lee el PDF y `search` con explainability devuelve evidencia citada: es exactamente para lo que Cala está hecha | **4.50** (4.25) |
| 9 | Mapa de compradores | ⬆ **Sube** | CorporateEvent (M&A) existe. Falta ver su cobertura | **3.75** (3.50) |
| 4 | Camino de introducción | ⬆ Sube un poco | Las relaciones persona–empresa con fechas permiten "trabajaron juntos en X entre tal y tal año" | 3.75 (3.50) |
| 10 | Radar de carreras | = | Igual que la 1, pero con un público fuera del foco | 3.75 |
| 12 | Slush planner | = | Cala aporta el enriquecimiento, pero la lista de asistentes de Slush es externa | 3.75 |
| 11 | Pulso de ecosistemas | ⚠ Baja un poco | Necesita la geografía del inversor: sin el tipo Investor, se infiere a partir de Company | 3.50 (3.75) |
| 7 | Rondas atrasadas | ⚠ Riesgo | Depende de fechas exactas de las rondas (`year` en las filas puede quedarse corto) y de la completitud | 3.75 (4.25) |
| 3 | Escalera de inversores | ⚠ **Riesgo** | Sin lead/follow, se convierte en "qué fondos aparecen en la Serie A de las empresas de este fondo" (participantes, no leads). Pierde precisión, sigue siendo original | **3.75** (4.50) |
| 8 | Armador de sindicatos | ⚠ Riesgo | Co-inversión vía `investors=A AND B`: funciona, pero sin el tipo Investor el grafo es más pobre | 3.25 (3.50) |
| 2 | Who actually leads | ❌ **En riesgo alto** | Toda la idea depende de lead/follow. Si no está, se vuelve "inversores activos" genérico (lo que hace todo el mundo) | **3.00** (4.25) |
| 5 | Termómetro de mercado | = | Factible, poco original | 3.25 |

### Top 3 actualizado (el usuario decide)
1. **★ Verificador de decks**: sube al 1°. Es el uso más "Cala tal cual" (preguntas con respuesta citada) en un contexto concreto (el angel en Slush), con la demo más memorable y el modelo VL justificado.
2. **★ Radar de primeros clientes**: es la más sólida en datos y útil al día siguiente.
3. **★ Mapa de compradores** (reemplaza a la escalera **si** el stand confirma que hay buena cobertura de CorporateEvent). Si no, queda la **escalera de inversores en versión "participantes"**.

### Consultas concretas y papel de Nemotron

#### 1. Verificador de decks
**Nemotron (VL)**: lee el PDF/imágenes del deck → extrae las **afirmaciones verificables** como una lista estructurada (empresa, founders, rondas pasadas, inversores mencionados, clientes o logos, métricas de tracción) → genera una consulta por afirmación → al final clasifica cada una como ✔ confirmada / ⚠ difiere / ? sin dato, con explicación y fuente. **Cala**: es la fuente de verdad citada.
- `entities?name=Acme Robotics&entity_types=Company` → id → `entities/{id}` con relaciones de rondas y personas (una sola llamada por perfil).
- `knowledge/query`: `startups.name=Acme Robotics.funding_rounds return(round_type, funding_amount, year, investors)`
- `knowledge/search`: "Did Lifeline Ventures invest in Acme Robotics? In which round and when?" (con explainability → URL de la fuente)
- `knowledge/search`: "Did Jane Doe previously work at Google, and in what role and years?"
- `knowledge/search`: "Is Kesko a customer or partner of Acme Robotics?" (los logos de clientes del deck)
- **Wow**: el PDF a la izquierda con cada afirmación resaltada; a la derecha, las tarjetas ✔/⚠/? con el link a la fuente.

#### 2. Radar de primeros clientes
**Nemotron**: convierte la descripción del producto ("compliance para fintechs de 20–200 personas en el norte de Europa") en filtros (sector, país, tamaño, etapa) → arma las consultas → **rankea** las filas según timing, fit y acceso → escribe un "por qué ahora" de una línea y un primer mensaje de contacto por empresa. **Cala**: las filas de empresas con rondas recientes y las personas con rol.
- `knowledge/query`: `startups.industry=Fintech.location=Finland.funding>1M order_by=funding_date limit=50 return(company, round_type, funding_amount, year, investors)`. Repetir para Sweden, Norway y Denmark, o en lenguaje natural: "Fintech startups in the Nordics that raised a funding round in the last 3 months".
- `knowledge/query`: `people.role=Head of Compliance.company.name=<empresa>` (y CFO o COO como fallback) → la persona que decide la compra.
- `knowledge/search`: "Which investors does <mi startup> share with <empresa>?" o `investors=<inv1> AND <inv2>` → un intro en común.
- **Wow**: 5 segundos desde la descripción del producto hasta "12 empresas, la persona que decide y el intro en común", cada una con la ronda citada.

#### 3a. Mapa de compradores (si hay datos de M&A)
**Nemotron**: define "empresas parecidas" a partir de la descripción, agrupa los compradores y explica el patrón ("compra startups de logística nórdicas en etapa Serie A"). **Cala**: los CorporateEvent con comprador, objetivo y fecha.
- `knowledge/search`: "Acquisitions of Nordic logistics software startups since 2020: acquirer, target, date"
- `entities/{id_comprador}` → relaciones CorporateEvent salientes (todas sus compras).
- `knowledge/query`: `investors=<inversor del founder> AND <comprador>` → un camino de acceso.

#### 3b. Escalera de inversores en versión "participantes" (alternativa)
- `knowledge/query`: `startups.investors=Lifeline Ventures.round_type=Seed return(company, year)` → la cohorte.
- Por cada empresa: `knowledge/query`: `startups.name=<empresa>.funding_rounds.round_type=Series A return(investors, year)`
- **Nemotron**: agrega, calcula porcentajes y tiempos y redacta la comparación entre dos fondos. **Costo**: 1 + N llamadas por fondo → hace falta caché.

### Preguntas para el stand de Cala (ordenadas por cuánto cambian la decisión)
1. **¿Cuántas llamadas y créditos tenemos, y con qué latencia?** Define si las ideas de "1 + N consultas" (escalera, radar) son viables en vivo.
2. **¿Qué cobertura tienen de rondas 2025–2026 en los nórdicos y en España, y con qué frescura?** Si es floja, el radar de clientes y el verificador se ven vacíos con startups locales (mitigación: usar startups conocidas de la UE o de EE. UU.).
3. **¿Qué tan completos están los CorporateEvent (M&A)?** Decide entre el mapa de compradores y la escalera para el 3° lugar.
4. **¿Se puede distinguir el lead de una ronda (en alguna propiedad o relación de FundingRound)?** Si sí, "who actually leads" y la escalera vuelven al nivel ~4.5.
5. **¿Las fechas de las rondas son exactas (día/mes) o solo el año?** Afecta el "levantó hace N semanas" (radar) y las rondas atrasadas.
6. **¿Hay personas con rol para empresas medianas, no solo founders o el CEO?** Afecta "la persona que decide" en el radar.
7. **De las ideas verificador / radar / compradores, ¿cuál les entusiasma más?** Es la validación con los fundadores (el ángulo catalán).
