# Junction 2026: proyecto del equipo

Hackathon Junction 2026, Espoo (Finlandia), del 13 al 15 de noviembre de 2026. Somos **cuatro personas (Bau, Fabricio, Gabriel y Adrian), cada una con su máquina y sus agentes**, trabajando en paralelo sobre este repo. Este archivo lo leen todos los agentes: Claude (`CLAUDE.md`), Codex (`AGENTS.md`) y los de Google (`GEMINI.md`); los tres nombres apuntan al mismo archivo. Respondé en español.

## Producto (enfoque desde el 14/11 por la noche: Cala Match)
**Marketplace de financiación de doble interfaz, construido sobre el grafo de Cala. Toda la app en inglés.** El README tiene la versión pública; el diseño demo está en `docs/design/stitch/` (hecho con Stitch).
1. **Dos modos** con un interruptor arriba: *Raising* (startup que busca financiación, el feed muestra inversores) e *Investing* (inversor que busca startups, el feed muestra startups).
2. **Feed**: cuadraditos, uno por inversor o startup, con **puntaje de afinidad** (0–100) y una línea "por qué encaja". Al entrar, el detalle con todo lo que Cala recolecta (rondas, líderes, portfolio, personas, cifras), cada dato con su fuente.
3. **Chat**: el usuario pregunta por texto o voz; las consultas van por el **canonizador** y se muestran como tablas de datos de Cala con fuentes. El modelo nunca escribe cifras ni nombres que no vengan de Cala.
4. **Contexto**: el usuario sube PDFs (por ejemplo el pitch), notas de voz o texto; Gemini extrae sector, etapa, región y ticket, y eso mejora el afinidad. **No es el verificador de decks** (ese sigue fuera del producto): el PDF solo alimenta el perfil.
5. **Subgrafo local sobre Cala**: el vecindario de cada usuario se carga en local (nodos y aristas con fuente) y se explora con BFS; Cala solo se llama en el borde. Medido el 14/11 (semilla Amenitiz, 185 nodos): la carga son unos 14–18 s de trabajo real de Cala, el BFS local tarda 0,13 ms y el límite de uso salta con unas 10 llamadas seguidas. Los endpoints de entidades responden en ~1 s; los 16–60 s son de `knowledge/query` y `knowledge/search`.
6. **Puntaje de afinidad (propuesta de `bau`, a validar)**: coincidencia con las restricciones del perfil (sector, etapa, región, ticket) + distancia en el grafo + rondas parecidas compartidas. Siempre explicable: cada punto se justifica con datos de Cala.

El motor (router de mensajes, canonizador, bloques, journal) sigue en `docs/PLAN-CALA-CENTRO.md`. **Fuera del producto (decisión del 14/11): el verificador de pitch decks.** `backend/verifier/` se queda porque el chat usa sus módulos compartidos (`llm.py`, `config.py`, `cala.py`).

Cala es el núcleo (no tocamos cómo funciona: mostramos para qué sirve). Todo dato de Cala se muestra con su fuente.

## Retos
- **Principal: Cala** (25% cada uno: necesidad real, ejecución end-to-end, originalidad, Cala como núcleo). Slush empieza justo después: usable al día siguiente.
- **Google Gemini** (secundario, desde el 14/11): Gemini es la IA del producto (router, audio, intención, juez). El reto pide un uso significativo e innovador y explicar por qué Gemini importa en la solución.
- **Aiven** (secundario): caché compartida de consultas a Cala en Aiven Valkey (`VALKEY_URL`, ver `canonizador/README.md`).
- NVIDIA Nemotron: descartado como modelo principal (el endpoint que nos dieron nunca respondió); el proveedor queda en el código como alternativa.
- **OpenAI Codex** (secundario): construimos con Codex; evidencia en `docs/CODEX.md` (registro de tareas exportado de `cx log` de cada máquina) y `docs/PROCESO.md`.
- Candidatos sin decidir: Context.dev, CRACI. Descartado: bot de WhatsApp/Telegram con n8n (se reemplaza por el chat de la app).

## Equipo y coordinación
| Máquina | Persona | Agentes | Rol |
|---|---|---|---|
| `bau` | Bau | Claude (orquestador), Codex, Gemini | **Coordina a todo el equipo**: reparte tareas, revisa y mergea PRs, vigila conflictos y comunica las novedades. Arquitectura, pitch y documentación |
| `fabricio` | Fabricio | Claude, Codex, Gemini | Miembro: API del backend, optimizador y Aiven |
| `gabriel` | Gabriel | Agente de Google (Gemini) como principal | Miembro: contexto (PDF y voz), n8n y herramientas extra |
| `adrian` | Adrian | Agente propio (a confirmar) | Miembro: diseño y app (el prototipo de Stitch llevado a Expo) |

- **Todo se coordina por GitHub**, que es lo único que ven las cuatro máquinas: issue fijo #1 "Estado del equipo" (estado de cada máquina y mensajes), issues con label `maquina:<nombre>` (tareas) y PRs.
- Con [claude-central](https://github.com/BauDahn/claude-central) instalado se usa el comando `equipo` (`equipo mias`, `equipo mensajes`, `equipo avisar bau "..."`, `equipo publicar`). **Sin claude-central** (por ejemplo, con un agente de Google) se hace lo mismo con `gh`: `gh issue list --label maquina:<nombre>` para ver tus tareas, y un comentario en el issue #1 que empiece con `**<nombre> → bau:**` para avisar. El script `equipo` es un solo archivo de Python que solo necesita `gh`; se puede usar suelto.
- **Antes de empezar algo que no te asignaron, avisá al orquestador** (comentario en #1 o `equipo avisar bau`), para no duplicar trabajo. Ya pasó.
- El orquestador responde y reparte por el mismo canal. Las claves (`CALA_API_KEY`, `GEMINI_API_KEY`, `VALKEY_URL`) se pasan por privado, nunca por GitHub.

### Dueños de cada área (para no pisarse; reparto del 14/11 por la noche)
| Área | Dueño | Notas |
|---|---|---|
| `app/` | máquina `adrian` | Expo (web + iOS + Android), TypeScript, todo en inglés; sigue `docs/design/stitch/` |
| `backend/api/` (feed, afinidad, detalle) y `backend/chat/`, `app.py` | máquina `fabricio` | Endpoints nuevos del feed y del detalle; el chat existente |
| `canonizador/` (cliente de Cala, caché, límites) | máquina `fabricio` | Optimizador: pausa por endpoint, reintentos, Aiven Valkey |
| `backend/graph/` (subgrafo local) y `backend/cala_core/`, `journal/` | máquina `bau` (diseño) con Codex | Arquitectura del grafo y del puntaje de afinidad |
| `backend/context/` y `n8n/` | máquina `gabriel` | Ingesta de PDF y voz, flujos y herramientas extra |
| `docs/API.md` | compartido | Contrato; los cambios fuera de *(borrador)* los revisa `bau` |
| `CLAUDE.md`, `README.md`, `docs/` (salvo `docs/design/`) | máquina `bau` | Coordinación, plan, informes, pitch; `PROCESO.md`: una línea por hito |
| `docs/SPEC-grafo-afinidad.md` | Subgrafo local y puntaje de afinidad (qué se guarda y cómo se calcula) |
| `docs/ARQUITECTURA.md` | Cómo se monta el sistema: catálogo de Slush precalculado, gateway a Cala, grafo en Valkey, presupuesto de latencia |
| `docs/design/` | máquina `adrian` | Prototipos y sistema de diseño |

**Quién mergea:** cada máquina mergea sus propios PRs cuando sus tests pasan y solo tocan su área. `bau` revisa únicamente lo que cambia `docs/API.md` o cruza áreas. `fabricio` revisa los PRs de `gabriel` y `adrian` que toquen el backend; `adrian` revisa los de la app. Al mergear, avisar en el issue #1.

Si hace falta tocar el área del otro, se pide por `equipo avisar` o se hace en un PR que el dueño aprueba.

### Flujo de Git (obligatorio)
1. Toda tarea es un **issue** (`equipo asignar <maquina> "título" --cuerpo "qué, criterio de hecho"`).
2. Rama desde `main` actualizado: `git switch main && git pull && git switch -c <maquina>/<issue>-<slug>` (ej. `bau/12-chat-audio`).
3. Commits chicos. **Nunca commitear a `main` ni hacer force-push a ramas ajenas.**
4. Antes del PR: `git fetch && git rebase origin/main`, tests en verde.
5. PR con `gh pr create --fill --body "Closes #<issue>"`; avisar al otro (`equipo avisar <maquina> "PR #N"`). Revisa el otro o el orquestador; merge con **squash**. Apuntar a PRs de < 2 h de trabajo.
6. Después de cada merge en `main`, la otra máquina hace `git pull --rebase` en su rama.

## Workstreams
Una tarea por persona para cada eje; cada una es un issue con label `maquina:<nombre>`.

| Eje | Qué es | Dueño |
|---|---|---|
| **Arquitectura** | Subgrafo local (nodos y aristas con fuente, BFS con cupo por nivel, filtro de nodos concentradores, unir duplicados como "Chalfen Ventures" y "CHALFEN VENTURES LLP"), definición del puntaje de afinidad | `bau` |
| **Diseño y app** | Pasar el prototipo de Stitch a la app Expo: feed, detalle, chat, contexto y perfil, en inglés, con modo claro y oscuro | `adrian` |
| **Optimizador** | Pausa por endpoint (8 s para query y search, ~0,5–1 s para entidades), espera corta tras un 429, concurrencia, medir y publicar los números | `fabricio` |
| **Integración con Aiven** | Valkey como grafo compartido (nodos y aristas, no solo respuestas), vistas por usuario, precarga de la demo | `fabricio` |
| **Contexto** | Subir PDF (pitch) y notas de voz; Gemini extrae sector, etapa, región y ticket; actualiza el perfil y el afinidad | `gabriel` |
| **Otras herramientas y utilidades nuevas** | n8n: avisos de nuevas rondas y matches, resumen semanal; evaluar Context.dev y otras APIs; ideas de `docs/IDEAS-CALA.md` (camino de introducción, escalera de inversores) | `gabriel` |
| **Presentación** | Pitch, guion de la demo, video, números del benchmark, slides del reto de Cala, Gemini, Aiven y Codex | `bau` con aporte de todos |

## Principios de calidad (decisión del 14/11 noche)
**Menos cantidad, más calidad. Una app simple que se vea y se sienta bien vale más que muchas funciones a medias.**
- La app tiene **tres pestañas**: Feed, Ask (el chat) y Context. El perfil es una hoja que se abre desde el avatar, no una pestaña. Más el detalle de una tarjeta.
- **Fuera de la app:** Deck, Journal y la pantalla de estado. Si el código queda, no se muestra.
- Antes de sumar una función, preguntarse si mejora la primera pantalla de la demo. Si no, no entra; va a la lista "después" de `docs/PITCH.md`.
- Terminar una pantalla es que se vea bien en teléfono, tenga estados vacío, de carga y de error con texto humano, y esté probada con datos reales. No se mergea una pantalla a medias aunque "ya funcione".
- **Diseño minimalista y humano.** Las reglas están en el issue de rediseño de la app (un solo acento de color, sin degradados ni brillos, poca sombra, texto específico en lugar de eslóganes, nada de tarjetas dentro de tarjetas). Los PRs de interfaz llevan capturas a 390 px de ancho y Claude las revisa antes de mergear.

## Cómo trabajamos: tres roles (decisión del 14/11)
| Quién | Rol | Qué hace | Qué no hace |
|---|---|---|---|
| **Claude** | Orquestador y arquitecto | Diseña (specs, contrato de la API, planes), reparte tareas, revisa diffs y PRs, prueba contra los servicios reales, coordina las máquinas y mantiene la documentación | **No escribe código de la aplicación.** Ni arreglos chicos: todo cambio de código se le pide a Codex |
| **Codex** | Programador | Escribe y corrige todo el código (backend, app, canonizador, tests) a partir de tareas concretas | No decide arquitectura ni hace commits, push o cambios de rama |
| **Gemini** | IA dentro del producto | Todos los servicios de IA en tiempo de ejecución: clasificar mensajes (router), extraer intenciones, transcribir y entender audio, elegir filas y juzgar afirmaciones | No se usa Codex ni Claude como modelo del producto (quedan solo como respaldo) |

- Delegar a Codex con `cx` (ver `cx roles`): `cx <rol> -C ~/proyectos/junction -p junction "<tarea concreta con criterio de hecho y cómo verificar>"`. Correcciones con `cx seguir <hilo> "..."` (hilos largos se encarecen: para algo nuevo, hilo nuevo). Si Codex queda colgado sin tocar archivos, cortarlo y relanzar.
- Claude revisa leyendo solo lo que cambió (`git diff`), corre los tests y las pruebas reales, y hace los commits, push y PRs.
- **Gemini**: modelo rápido (`GEMINI_FAST_MODEL`, por defecto `gemini-3.5-flash-lite`: ~1 s por llamada, 3/3 en la prueba del router) para router, intención y foco; modelo fuerte (`GEMINI_MODEL`, por defecto `gemini-flash-latest`) para el juez. Medido el 14/11 con la clave del equipo.
- **Tokens:** no leer docs enteros si no hace falta; `rg` y lecturas parciales.

## Cómo correr
- Backend: `cd backend && uv sync && uv run uvicorn app:app --port 8000` Tests: `uv run pytest`.
- App: `cd app && npm install && npx expo start` (web: tecla `w`; en Expo Go, `EXPO_PUBLIC_API_URL` con la IP del PC). La app tiene modo simulado si el backend no responde.
- Todo junto: backend en `:8000` y app web; el chat completo (texto, audio, perfil, recomendaciones con fuentes) ya está en `main`.

## Reglas técnicas
- **Secretos**: `CALA_API_KEY`, `NVIDIA_API_KEY` solo en `backend/.env` (ignorado por git; plantilla en `backend/.env.example`). Nunca leerlos, imprimirlos, loguearlos ni ponerlos en prompts o commits.
- **Cala**: el código nuevo consulta Cala **a través del canonizador** (`canonizador/`), nunca mandando el texto del usuario directo: el texto libre da respuestas distintas para la misma pregunta (`docs/BENCHMARK-CANONIZADOR.md`). Endpoints: `knowledge/query` (filas), entidades (datos con fuentes y `is_lead`), `knowledge/search` (respuesta con fuentes, último recurso). **16–60 s por llamada** y HTTP 429 tras ~7 llamadas seguidas: caché en disco (`backend/cache/`, ignorada), pocas llamadas a la vez y reintentos con espera. Detalle en `docs/CALA-CAMPOS.md` y `docs/CALA-API.md`.
- **LLM**: `LLM_PROVIDER` = `gemini` (por defecto si hay `GEMINI_API_KEY`) | `nvidia` | `codex` | `claude` (`backend/verifier/llm.py`). Claves solo en `backend/.env`.
- **Transcripción**: Gemini por defecto si hay `GEMINI_API_KEY` (una llamada para transcripción literal e intención limpia, con respaldo a faster-whisper local, modelo `WHISPER_MODEL`, por defecto `small`); si no, whisper si está instalado, o `none`. `TRANSCRIPTION_PROVIDER` permite elegir `gemini` | `whisper` | `nvidia` | `none`. Ver `backend/chat/transcribe.py`.
- No crear repos ni desplegar sin aprobación del usuario. Antes de dar algo por terminado, correr la app o los tests y decir qué se verificó.

## Documentos
| Documento | Qué tiene |
|---|---|
| `docs/PLAN-CALA-CENTRO.md` | El enfoque actual: router, consultas, bloques, journal y reparto |
| `docs/API.md` | Contrato backend ↔ app |
| `docs/CALA-CAMPOS.md` | Guía oficial de campos de Cala (entidades, rondas, `is_lead`, Slush 2026) |
| `docs/CALA-SKILL.md` | Guía oficial para que un LLM use Cala (lenguaje de consultas) |
| `docs/CALA-API.md` | Primer resumen de la API de Cala |
| `docs/SPEC-canonizador.md` | Diseño del canonizador de consultas |
| `docs/BENCHMARK-CANONIZADOR.md` | Benchmark: 5 formas de preguntarle a Cala (0–1 de 9 consistentes contra 9 de 9) |
| `docs/INFORME-ERROR-CALA.md` | El error de consistencia de Cala, evidencia y recomendaciones para Cala |
| `docs/design/` | Prototipo de Stitch (pantallas y sistema de diseño) |
| `docs/SPEC-verificador.md` | Diseño del verificador de decks (fuera del producto desde el 14/11) |
| `docs/IDEAS-CALA.md` | Ideas evaluadas al elegir el proyecto |
| `docs/CODEX.md` | Registro de lo que construyó Codex (reto de Codex) |
| `docs/PROCESO.md` | Diario de decisiones |

## Estado (14/11, noche)
- En `main`: canonizador + benchmarks, caché Valkey, app Expo (chat, journal, perfil) y chat del backend (sesiones, texto, audio, recomendaciones).
- Cambio de enfoque: de "chatbot con Cala en el centro" a **Cala Match** (feed con afinidad, detalle, chat, contexto). El diseño demo ya está en `docs/design/stitch/`.
- Equipo: `bau` (orquestador), `fabricio`, `gabriel` y `adrian` (miembros).

## Pendientes
- [ ] Un issue por eje de la sección Workstreams (arquitectura, diseño y app, optimizador, Aiven, contexto, utilidades, presentación).
- [ ] Quitar la pestaña Deck de la app (el contrato y el verificador quedan sin uso).
- [ ] App en inglés.
- [ ] Contrato nuevo en `docs/API.md`: feed, detalle de una entidad, afinidad y contexto.
- [ ] Optimizador del cliente de Cala: pausa por endpoint y espera tras 429 (ver README para los números medidos).
- [ ] Aiven: grafo compartido en Valkey y precarga de la demo.
- [ ] Prueba de punta a punta de la app contra el backend en vivo (web y Expo Go).
- [ ] Preguntas al stand de Cala (límite de uso, costo, latencia, lead/follow, Slush 2026).
- [ ] Confirmar hora límite de entrega y formularios de cada reto secundario.
- [ ] Pitch y video de demo.
