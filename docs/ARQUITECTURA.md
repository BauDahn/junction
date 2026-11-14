# Arquitectura: cómo montar Cala Match para que sea rápido

Complementa a `docs/SPEC-grafo-afinidad.md` (qué guardamos y cómo se calcula el afinidad). Esta es la parte de sistema: de dónde salen los datos, qué corre en segundo plano y cómo se mantiene la latencia baja con el límite de Cala y con Aiven. Todo lo medido es del 14/11 contra la API real; lo marcado *(estimado)* no se midió.

## 1. Lo medido que condiciona el diseño
| Hecho | Número |
|---|---|
| Llamada a entidades (`entity retrieval`) | 0,9–1,3 s |
| `knowledge/query` y `knowledge/search` | 16–60 s |
| Límite de uso en entidades | 10 llamadas en ~3 s dieron 429; 30 llamadas espaciadas 0,7 s no dieron ninguno (~1,4 llamadas/s sostenidas) |
| **Slush 2026 completo** | **2.990 asistentes** (2.982 `Company`, 7 `Organization`, 1 `EducationalInstitution`, ninguna `Person`; `role` siempre `ATTENDEE`), traídos en **36 s** con 30 páginas de 100 (`limit` y `offset` funcionan, sin solapes) |
| Retrieval **sin introspección** con una relación inexistente en la lista | funciona: Cala ignora la relación que no existe y no da error. Amenitiz: 1,3 s, 18 inversores, 3 fundadores y su ronda |
| Valkey de Aiven (versión 9.1.3) | RTT ~29 ms; **200 lecturas en pipeline: 31 ms**, una por una: ~28 ms cada una; memoria 6,5 MB usada de 2,43 GB; política `noeviction` |
| BFS sobre el subgrafo en memoria | 0,13 ms (185 nodos), 337 ms (100 mil nodos sintéticos) |

Dos consecuencias: **(a)** leer de a un nodo en Valkey cuesta 28 ms por nodo, así que hay que leer por lotes; **(b)** como `noeviction` no borra nada solo, todo lleva TTL y el catálogo tiene tope.

## 2. Decisiones
1. **Catálogo precalculado + capa viva por usuario.** El universo de la demo es finito: los 2.990 asistentes de Slush. Se calcula una vez, en segundo plano, y se comparte en Valkey. El feed sale de ahí sin llamar a Cala. Lo que el usuario hace en vivo (su perfil, sus preguntas, un nodo fuera del catálogo) es una capa pequeña encima.
2. **Una sola puerta a Cala (el gateway).** Todo pasa por un único componente con cola de prioridades, límite de tasa por tipo de endpoint, una sola petición en vuelo por clave (si dos usuarios piden lo mismo, una sola llamada) y ajuste automático ante 429. Es lo que da el #63.
3. **Valkey es el almacén del grafo; la memoria del proceso es solo una caché caliente.** Se lee por lotes, nivel por nivel; nunca nodo por nodo.
4. **Sin introspección.** Hoy cada expansión son 2 llamadas (introspección y retrieval). Como Cala ignora las relaciones que no existen, pedimos directo la lista blanca de relaciones: **la mitad de las llamadas** para el mismo resultado. *(Medido en dos entidades; hay que confirmarlo con personas y fondos.)*
5. **Gemini normaliza texto, Cala pone los hechos.** El sector y la etapa de cada startup se etiquetan con Gemini a partir de la `description` que ya trae Cala. Eso **no gasta cupo de Cala** y corre en paralelo. Las etiquetas se usan para el matching y se muestran como "AI-tagged from Cala's description" con la fuente de esa descripción; las cifras, rondas, inversores y personas siguen viniendo solo de Cala.
6. **Feed progresivo.** La pantalla nunca espera: muestra lo que haya y se completa sola (sección 5). El `confidence` del afinidad cuenta honestamente cuánto dato falta.
7. **Todo trabajo en segundo plano es reanudable y priorizado.** Si no termina antes de la demo, lo hecho se usa y lo que falta baja el `confidence`.
8. **Plan B de demo**: un archivo con el catálogo exportado, que se vuelve a cargar en Valkey con un comando si Cala o Aiven fallan.
9. **Métricas visibles** (`/api/stats`): llamadas a Cala por tipo, 429, aciertos por capa de caché, profundidad de la cola, tiempo hasta la primera tarjeta. Son los números del pitch.

## 3. Componentes
```
 Expo app ──REST/polling──► FastAPI (un proceso, asyncio)
                              │
        ┌─────────────────────┼─────────────────────────┐
   feed / detalle        chat (router + canonizador)   contexto (PDF, voz → Gemini)
        │                     │                          │
        └──────────► Graph store (lotes, vistas) ◄───────┘
                              │         ▲
                   hit        │         │ escribe nodos y aristas
              ┌───────────────┘         │
         memoria (LRU) → Valkey (Aiven) │
                              │ miss    │
                              ▼         │
                        Cala gateway ───┘   límite por endpoint, prioridad,
                   (interactivo > prefetch > lote)  una petición por clave, AIMD ante 429
                              │
                          Cala API          Gemini (etiquetas, router, audio, PDF)

 Trabajos en segundo plano (mismo proceso, tareas asyncio, estado en Valkey):
   catalog-sync  → asistentes de Slush, perfil de cada uno, etiquetas de Gemini
   frontier      → expansiones por usuario y precarga de lo que se muestra
```
**Por qué un solo proceso y no colas externas:** son cuatro personas y una noche. Un proceso asyncio con el estado en Valkey alcanza; si hay dos máquinas corriendo, el límite de tasa se comparte en Valkey (contador por segundo con `INCR` y expiración de 2 s) para que no sumen sus llamadas contra la misma clave de Cala.

## 4. El catálogo (el cambio grande)
**Etapa 1, la lista (36 s, ya probada).** `PARTICIPATES_IN_EVENT` entrante de Slush, 30 páginas. Da 2.990 ids y nombres.

**Etapa 2, el perfil de cada uno (1 llamada por entidad).** Retrieval directo con `properties` (descripción, `funding_stage`, `total_funding`, rango de empleados, sede, web) y relaciones: `INVESTED_IN` entrante y saliente, `PARTICIPATES_IN_FUNDING_ROUND` saliente, `FOUNDED` entrante, todas con `limit` 100. De esa sola respuesta salen:
- **Quién es inversor y quién es startup.** Slush no los distingue (casi todo es `Company`): quien tiene `INVESTED_IN` saliente es inversor; quien tiene rondas con `role: ISSUER` es startup. Algunos son los dos.
- Las aristas del subgrafo (rondas, inversores, fundadores) con sus fuentes.
Costo: 2.990 × ~1,3 s ≈ **65 min en secuencial; unos 22 min con 3 en paralelo** *(estimado; depende del límite real que mida #63)*. Es el trabajo para dejar corriendo esta noche, reanudable.

**Etapa 3, etiquetas con Gemini.** Con la descripción de cada empresa: sector, etapa, tipo de cliente y región. En paralelo con la etapa 2, sin tocar el cupo de Cala. ~3.000 llamadas cortas al modelo rápido.

**Etapa 4, enriquecimiento (mejor esfuerzo).** Portfolio de los inversores más relevantes para el perfil de la demo: sector y etapa de sus participadas. Se hace por prioridad (los inversores que más coinciden con el usuario de la demo primero) y se corta cuando se acaba el tiempo. `knowledge/query` por inversor (16–60 s) solo para los 20–30 más relevantes, en paralelo con el resto porque usa otro endpoint.

**Claves**: las de `SPEC-grafo-afinidad.md`, más `cat:v1:status` (etapa y progreso), `cat:v1:todo` (conjunto de ids pendientes por etapa) y `cat:v1:feat:<id>` (características ya extraídas para calcular el afinidad: sector, etapa, región, rango de monto, actividad).

**Tamaño**: ~3.000 nodos de catálogo y unos 15–25 mil nodos y aristas vecinos a ~0,4 KB cada uno son **del orden de 10 MB**, contra los 2,43 GB disponibles. No es un problema de memoria; sí hay que ponerle TTL a todo por la política `noeviction`.

## 5. Presupuesto de latencia
| Acción | Objetivo | Cómo se logra |
|---|---|---|
| Abrir el feed | primera tarjeta en < 1,5 s, feed completo en < 3 s | Afinidad calculado sobre las características ya extraídas del catálogo (cálculo en memoria, milisegundos) + una lectura por lotes de Valkey (~30 ms) |
| Cambiar de modo (Raising / Investing) | < 500 ms | Mismo catálogo, otro filtro: ya está en memoria |
| Perfil recién creado | feed con `confidence` baja de inmediato; sube en 10–30 s | Con las restricciones del perfil (sector, etapa, región, ticket) se rankea el catálogo al instante; las señales del grafo (cercanía) llegan después |
| Abrir el detalle | < 500 ms si está en el catálogo; < 3 s si no | Aristas ya guardadas con fuentes; si falta algo, 1 retrieval directo con prioridad interactiva |
| Pregunta en el chat que Cala debe resolver (canonizador) | 16–60 s, no se puede evitar | Se responde primero desde el grafo si está (ms) y se avisa "looking it up in Cala"; la respuesta de Cala completa la tarjeta cuando llega |
| Pregunta sobre algo que ya está en el grafo (por ejemplo "who led Amenitiz's Series B?") | < 1 s | Sale del grafo con `is_lead` y fuentes, sin llamar a Cala |

**Actualización de la pantalla**: polling cada 2 s mientras haya trabajo pendiente (igual que el journal); cada tarjeta trae `score` y `confidence` y se actualiza en su lugar. Si sobra tiempo, SSE.

## 6. Orden de construcción
**Esta noche (lo que desbloquea todo)**
1. Gateway con límite por endpoint, una petición por clave y espera corta ante 429 (#63, `fabricio`). Valor inicial: 1,4 llamadas/s para entidades.
2. Almacén del grafo en Valkey con lectura por lotes y TTL (#64, `fabricio`). Publica primero la interfaz (`get_nodes(ids)`, `neighbors(ids)`, `put_expansion(...)`) para que los demás programen contra ella.
3. Trabajo del catálogo, etapas 1 a 3, reanudable (issue nuevo, `gabriel`). Se lanza apenas exista la interfaz del punto 2 y corre toda la noche.

**Mañana temprano**
4. Endpoints del feed y del detalle sobre el catálogo (#65, `fabricio`).
5. App con el feed y el detalle sobre datos reales (#62, `adrian`).
6. Calibrar los pesos del afinidad con 10 pares conocidos (`bau`).
7. Etapa 4 y la cola de precarga por usuario.

**Si sobra tiempo**: camino de introducción entre personas (hace falta ampliar a `Person`: el catálogo de Slush no trae personas, habría que sumarlas desde `FOUNDED` e `IS_CEO_OF`), SSE y pesos aprendidos.

## 7. Riesgos
| Riesgo | Qué hacemos |
|---|---|
| El límite real es más bajo que 1,4 llamadas/s en horas pico o con varias máquinas | Límite compartido en Valkey y ajuste automático; el catálogo se reanuda solo y se usa lo que haya |
| El catálogo no termina antes de la demo | Etapas por prioridad; el feed funciona con lo hecho y el `confidence` lo dice. Antes de la demo, congelar un archivo de respaldo |
| Gemini etiqueta mal un sector | Las etiquetas solo ordenan el feed; nunca se muestran como dato de Cala. Si hay dudas, se omite esa señal |
| Aiven cae o se llena | Se sigue con memoria y disco; todo tiene TTL por `noeviction`; el respaldo en archivo vuelve a cargar el catálogo |
| Dos máquinas llenando el catálogo a la vez | Un solo dueño del trabajo (marcado con `SET NX` en Valkey); la otra solo lee |
| Datos viejos | Cada nodo y arista guarda `loaded_at`; el detalle lo muestra ("loaded Nov 14") |

## 8. Preguntas abiertas
- ¿El límite de 429 es por clave, por IP o por endpoint? Cambia cuánta paralelización se puede usar. Lo mide #63.
- ¿Cuántos de los 2.990 son inversores? Lo dice la etapa 2; si son pocos, el modo Raising tiene un catálogo corto y conviene sumar los fondos vecinos (los inversores de las rondas de los asistentes).
- ¿`is_lead` viene siempre en las rondas? Lo pregunta `bau` en el stand de Cala.
