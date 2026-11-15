# Pitch y guion de demo (issue #69)

Borrador de `bau`, 14/11 noche. El guion hablado está en inglés (se presenta en Espoo); las notas para el equipo, en español. **Regla: en el escenario solo se dice lo que ya está medido o funcionando.** Lo que depende de trabajo en curso va marcado **[CONFIRMAR]** y se ajusta antes de ensayar.

## 1. La idea en una frase
> **Cala Match: the funding marketplace that finds the right investor or startup for you, and shows its sources for every claim.**

Versión corta para el stand de Cala: *"We turned Cala's knowledge graph into a two-sided marketplace, and we fixed the one thing that stops agents from trusting it: the same question giving different answers."*

## 2. Pitch de 3 minutos
**0:00 – El problema (30 s)**
"Raising money is a search problem. Founders spend weeks figuring out which investors actually back companies like theirs. Investors do the opposite: they scroll through hundreds of decks. Both sides are guessing, and the data to stop guessing exists, in Cala's knowledge graph. But it's hard to use."

**0:30 – El hallazgo (40 s)**
"When we started, we hit a wall. We asked Cala the same question three ways: with accents, without, in another language. Out of nine questions, asking directly gave consistent answers at most once. Through MCP, even with Cala's official guide loaded, also at most once. Same question, different companies, different numbers. An agent can't build trust on that."
"So we built a canonizer. It turns any phrasing into one canonical query. 41 phrasings of 9 questions collapsed into 9 queries with identical answers. Nine out of nine."

**1:10 – El producto (50 s)**
"On top of that, Cala Match. One app, two sides. Switch between *Raising* and *Investing*. The feed shows cards: each investor or startup with an affinity score from 0 to 100 and one line on why it matches. Tap a card and you get everything Cala knows: rounds, lead investors, portfolio, people. Every fact carries its source and date. Ask the chatbot anything, by text or voice. Upload your pitch deck or record a voice note, and your matches get better."

**2:00 – Cómo es rápido (30 s)**
"Cala is a graph, so we treat it like one. We pre-load all 2,990 Slush 2026 attendees into a shared Aiven Valkey cache. Exploring the local graph takes 0.13 milliseconds. Cala is only called at the edges. The language model never writes a number or a name: those come only from Cala, always with sources."

**2:30 – Cierre (30 s)**
"Slush starts right after this hackathon. Tomorrow, a founder walking the floor can open this app and know in seconds who is worth a conversation, and why. Cala Match."

## 3. Demo en vivo (2 minutos, 5 pasos) — flujo Raiser
| Paso | Qué se hace | Qué se dice | Depende de |
|---|---|---|---|
| 1 | Registrarse eligiendo **Raiser** y cargar el contexto de la startup de la demo | "I sign up as a raiser: a hotel-software startup raising a Series A." | Nueva web **[CONFIRMAR]** |
| 2 | **Explorar eventos**: guardar Slush 2026 | "One tap and it is in My events." | Nueva web **[CONFIRMAR]** |
| 3 | **Mis eventos** → Slush 2026: investores recomendados con la carta de contacto; abrir uno: ficha simple y cómo conseguir la inversión, con fuentes | "Ranked for me, with a draft of how to approach each one. Every fact has its source." | Nueva web, feed y detalle (**ya en main** la API) **[CONFIRMAR]** |
| 4 | **Asistente (burbuja)**: por voz "Who led Amenitiz's Series B?" y una empresa que no está en el catálogo | "Same answer however I phrase it; and if it is not in the graph, it searches Cala live." | **Ya funciona** (chat, canonizador, respaldo y búsqueda) |
| 5 | Al asistente: "We now raise 2 million in seed" y "I want to go to Slush 2026" | "It edits my context and works as a shortcut." | Nueva web **[CONFIRMAR]** |
Si sobra tiempo: **Perfil** con favoritos y contexto (10 segundos).

**Plan B** (si Cala o la red fallan): recargar el catálogo desde el archivo de respaldo (`docs/ARQUITECTURA.md`, sección 2 punto 8) y hacer la demo con datos precargados. Tener un video grabado del recorrido completo de reserva. **Los pasos 4 y 5 deben funcionar aun sin red** gracias a la caché: precalentarlos antes.

## 4. Números que podemos decir (medidos el 14/11)
| Dato | Valor | Fuente |
|---|---|---|
| Consistencia sin canonizar | 0 de 9, 0 de 9, 1 de 9 y 0 de 9 (directo y por MCP, con y sin guía de Cala) | `docs/BENCHMARK-CANONIZADOR.md` |
| Consistencia con canonizador | 9 de 9; 41 redacciones → 9 consultas | `docs/INFORME-ERROR-CALA.md` |
| Respuesta repetida desde caché | 0,2–0,3 s contra 15–18 s la primera vez | `docs/INFORME-ERROR-CALA.md` |
| Slush 2026 completo | 2.990 asistentes traídos en 36 s | `docs/ARQUITECTURA.md` |
| Cargar un subgrafo de 185 nodos | ~14–18 s de trabajo real de Cala (19 llamadas, ~1 s cada una) | README |
| Explorar el subgrafo en local | 0,13 ms (BFS completo) | README |
| Valkey de Aiven | 200 lecturas en lote en 31 ms | `docs/ARQUITECTURA.md` |
| Codex | 12 tareas, 24 min y 8 M tokens de entrada en la máquina `bau` (más lo de las otras máquinas) | `docs/CODEX.md` |

**No decir** (todavía no está medido o no existe): cuántos de los asistentes son inversores, el tiempo total del catálogo, la calidad del puntaje de afinidad, "el camino más corto de todo Cala" (solo es el mínimo dentro de lo explorado) ni nada sobre el verificador de decks.

## 5. Qué decir para cada reto
**Cala (principal): "Cala at the core"**
- Cada tarjeta, tabla y puntaje sale de Cala y muestra su fuente. El modelo no escribe datos.
- Usamos más que la búsqueda: entidades con relaciones tipadas (`INVESTED_IN`, `is_lead`, fechas), consultas estructuradas y la búsqueda como último recurso.
- Le devolvemos algo a Cala: un informe con evidencia del error de consistencia y una forma de resolverlo (`docs/INFORME-ERROR-CALA.md`).
- Para el stand: preguntar por `is_lead`, el límite de uso, el costo por llamada y si habrá otros eventos además de Slush 2026.

**Google Gemini: "why Gemini matters here"**
- Es la IA del producto en todos los puntos donde hay lenguaje: el router que separa consulta, afirmación y perfil; la intención de cada pregunta; el audio; el contexto de los PDF; y las etiquetas de sector y etapa del catálogo a partir de las descripciones de Cala.
- Dos modelos: uno rápido (`gemini-3.5-flash-lite`, ~1 s por llamada, 3 de 3 en la prueba del router) para el flujo en vivo y uno fuerte para lo difícil. **[CONFIRMAR]** los números cuando termine el audio con Gemini (#50).
- Lo que hace Gemini es normalizar texto; los hechos los pone Cala. Esa separación es el argumento de confianza.

**Aiven: "Valkey as the product's memory"**
- Una caché compartida entre máquinas y usuarios, y además el grafo: nodos y aristas con fuente, un solo grafo que crece con el uso, y el subgrafo de cada usuario como una vista.
- Protege el límite de uso de Cala y hace instantáneo lo que ya se preguntó.
- Datos: lecturas en lote (200 en 31 ms), TTL en todo, y un archivo de respaldo que se recarga con un comando.

**OpenAI Codex: "built with Codex, directed by Claude"**
- Claude diseña, revisa y prueba; Codex escribe el código; Gemini es la IA dentro del producto. Registro completo en `docs/CODEX.md` y `docs/PROCESO.md`.
- Cada máquina exporta su `cx log` (tareas, modelo, minutos, tokens). Ya están bau, gabriel y fabricio; adrian trabaja con Antigravity y no tiene registro de Codex.

## 6. Preguntas que nos van a hacer
| Pregunta | Respuesta |
|---|---|
| ¿Qué pasa si Cala no tiene el dato? | Se prueban las otras herramientas de Cala y, si no hay, la tarjeta dice "no data" con lo que se buscó. Nunca se inventa. |
| ¿Cómo se calcula el afinidad? | Seis señales con pesos (sector, etapa, región, ticket, actividad reciente y cercanía en el grafo); cada una se explica con su dato y su fuente. Si falta una señal no cuenta como cero: baja la confianza. `docs/SPEC-grafo-afinidad.md`. **[CONFIRMAR]** al calibrar. |
| ¿Por qué no usar Google? | Google da documentos; Cala da relaciones con fuente, fechas y roles. Un camino como "este fondo coinvirtió con tu inversor" no sale de un buscador. |
| ¿Los datos están actualizados? | Cada nodo guarda cuándo se cargó y la app lo muestra. Cala devuelve la fecha de cada fuente. |
| ¿Funciona fuera de Slush? | El catálogo es de Slush por ser finito para la demo; el chat y el detalle consultan Cala en vivo para cualquier empresa. |
| ¿Y el límite de uso de Cala? | Lo medimos: unas 1,4 llamadas por segundo sostenidas. Por eso el catálogo es precalculado y compartido. |
| ¿Qué harían con más tiempo? | Camino de introducción entre personas, alertas de nuevas rondas, y pesos del afinidad aprendidos con datos reales. |

## 7. Lista antes de presentar (propietario: `bau`)
- [ ] Catálogo cargado en Valkey y archivo de respaldo exportado.
- [ ] Perfil de la demo (Stayflow) creado y probado en las dos pestañas.
- [ ] Pasos 4 y 5 precalentados en caché; probados sin red.
- [ ] Video de reserva del recorrido completo (1 a 2 min).
- [ ] Los **[CONFIRMAR]** de este documento resueltos y ensayo con cronómetro (3:00 de pitch más 2:00 de demo).
- [ ] Fotos o capturas de las pantallas para las slides (salen de la web nueva ya corriendo).
- [ ] Hora límite de entrega y formularios de Cala, Gemini, Aiven y Codex confirmados (sigue pendiente).
- [ ] Registro de Codex de Fabricio y de Adrian en `docs/CODEX.md`.
