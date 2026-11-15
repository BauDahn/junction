# Junction 2026: proyecto del equipo

Hackathon Junction 2026, Espoo (Finlandia), del 13 al 15 de noviembre de 2026. Somos **cuatro personas (Bau, Fabricio, Gabriel y Adrian), cada una con su máquina y sus agentes**, trabajando en paralelo sobre este repo. Este archivo lo leen todos los agentes: Claude (`CLAUDE.md`), Codex (`AGENTS.md`) y los de Google (`GEMINI.md`); los tres nombres apuntan al mismo archivo. Respondé en español.

## Producto (forma final, 15/11: Cala Match)
**Marketplace de financiación alrededor de eventos, sobre el grafo de Cala. Toda la app en inglés.** El README tiene la versión pública. El prompt que se le dio a Gemini para la nueva web está resumido aquí.
1. **Registro:** al registrarse se elige **Raiser** (startup que busca financiación) o **Investor**; es requisito para entrar y decide lo que muestra cada pantalla. Solo el modo Raiser está especificado; el de Investor es el espejo (startups a las que ver).
2. **Eventos** (cuadrados con imagen, nombre, eslogan y fecha), dos pestañas:
   - **Explorar eventos:** todos los eventos; se guarda uno como "asisto" o no; si se guarda pasa a Mis eventos.
   - **Mis eventos:** al entrar en un evento, los **inversores recomendados** por el motor de afinidad y, por cada uno, una **carta de cómo plantear el contacto**. Al pinchar un inversor, una ficha muy simple con lo que da Cala (empresa, industria, factores importantes como los fondos) y **cómo conseguir la inversión**, según las inversiones previas, horarios y datos de Cala.
3. **Asistente:** no hay pestaña Ask. Una **mascota en burbuja** abajo a la derecha abre un panel superpuesto con chat por texto y voz: pregunta por empresas (Cala + canonizador), **modifica el contexto** (lo que usa el motor de recomendación) y hace **atajos** ("quiero ir a Slush 2026" lo agrega a favoritos).
4. **Perfil:** contexto, inversores favoritos y datos personales. Simple y minimalista.
5. **Respaldo si no está en el grafo:** el chat nunca falla (canonizador, entidad, búsqueda, `not_found` con lo intentado); el detalle se trae de Cala en vivo y se guarda; `GET /api/search` mira el catálogo y luego Cala.
6. **Subgrafo local sobre Cala y afinidad:** como en `docs/ARQUITECTURA.md` y `docs/SPEC-grafo-afinidad.md`. Datos de eventos: Slush 2026 tiene 2.990 empresas participantes con personas; Slush 2025 solo 8 speakers.

La nueva web la construye Gemini (Antigravity). **Pendientes de producto que NO están en ese prompt** y quedan como ideas: planificador de reuniones en documento, aviso de "20 minutos libres". Fuera del producto: el verificador de decks y el journal. Cala es el núcleo; todo dato de Cala se muestra con su fuente.

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
| `bau` | Bau | Claude (orquestador), Codex, Gemini | **Activo:** revisa y mergea todo, limpia el repo, mantiene la documentación, el pitch y la coordinación |
| `fabricio` | Fabricio | Claude, Codex, Gemini | **En pausa** (decisión del 14/11 noche): su trabajo (feed, grafo, optimizador) ya está en `main` |
| `gabriel` | Gabriel | Antigravity y Codex | **Activo:** la interfaz de la app (#80), el catálogo de Slush y el contexto (PDF y voz) |
| `adrian` | Adrian | Antigravity | **En pausa** (decisión del 14/11 noche) |

- **Todo se coordina por GitHub**, que es lo único que ven las cuatro máquinas: issue fijo #1 "Estado del equipo" (estado de cada máquina y mensajes), issues con label `maquina:<nombre>` (tareas) y PRs.
- Con [claude-central](https://github.com/BauDahn/claude-central) instalado se usa el comando `equipo` (`equipo mias`, `equipo mensajes`, `equipo avisar bau "..."`, `equipo publicar`). **Sin claude-central** (por ejemplo, con un agente de Google) se hace lo mismo con `gh`: `gh issue list --label maquina:<nombre>` para ver tus tareas, y un comentario en el issue #1 que empiece con `**<nombre> → bau:**` para avisar. El script `equipo` es un solo archivo de Python que solo necesita `gh`; se puede usar suelto.
- **Antes de empezar algo que no te asignaron, avisá al orquestador** (comentario en #1 o `equipo avisar bau`), para no duplicar trabajo. Ya pasó.
- El orquestador responde y reparte por el mismo canal. Las claves (`CALA_API_KEY`, `GEMINI_API_KEY`, `VALKEY_URL`) se pasan por privado, nunca por GitHub.

### Dueños de cada área (desde el 14/11 noche: solo `bau` y `gabriel` están activos)
| Área | Dueño |
|---|---|
| `app/` (la interfaz) | `gabriel` |
| `backend/catalog/` y `backend/context/` | `gabriel` |
| Todo lo demás (`backend/`, `canonizador/`, `docs/`, `CLAUDE.md`, `README.md`) | `bau`, con Codex |

**Quién mergea:** `bau` revisa y mergea todos los PRs (squash), después de correr los tests. `gabriel` abre PRs chicos, uno por pantalla, con capturas a 390 px. Al mergear, `bau` avisa en el issue #1.

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
- **Fuera de la app y del repo:** Deck, Journal y la pantalla de estado. Los archivos de esas pantallas se borran, no se esconden.
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
- **LLM**: `LLM_PROVIDER` = `gemini` (por defecto si hay `GEMINI_API_KEY`) | `nvidia` | `codex` | `claude` (`backend/core/llm.py`). Claves solo en `backend/.env`.
- **Transcripción**: Gemini por defecto si hay `GEMINI_API_KEY` (una llamada para transcripción literal e intención limpia, con respaldo a faster-whisper local, modelo `WHISPER_MODEL`, por defecto `small`); si no, whisper si está instalado, o `none`. `TRANSCRIPTION_PROVIDER` permite elegir `gemini` | `whisper` | `nvidia` | `none`. Ver `backend/chat/transcribe.py`.
- No crear repos ni desplegar sin aprobación del usuario. Antes de dar algo por terminado, correr la app o los tests y decir qué se verificó.

## Documentos
| Documento | Qué tiene |
|---|---|
| `docs/PLAN-CALA-CENTRO.md` | El motor: router de mensajes, consultas a Cala, bloques y reparto |
| `docs/API.md` | Contrato backend ↔ app |
| `docs/CALA-CAMPOS.md` | Guía oficial de campos de Cala (entidades, rondas, `is_lead`, Slush 2026) |
| `docs/CALA-SKILL.md` | Guía oficial para que un LLM use Cala (lenguaje de consultas) |
| `docs/CALA-API.md` | Primer resumen de la API de Cala |
| `docs/SPEC-canonizador.md` | Diseño del canonizador de consultas |
| `docs/BENCHMARK-CANONIZADOR.md` | Benchmark: 5 formas de preguntarle a Cala (0–1 de 9 consistentes contra 9 de 9) |
| `docs/INFORME-ERROR-CALA.md` | El error de consistencia de Cala, evidencia y recomendaciones para Cala |
| `docs/design/` | Prototipo de Stitch (pantallas y sistema de diseño) |
| `docs/IDEAS-CALA.md` | Ideas evaluadas al elegir el proyecto |
| `docs/CODEX.md` | Registro de lo que construyó Codex (reto de Codex) |
| `docs/PROCESO.md` | Diario de decisiones |

## Estado (14/11, noche)
- En `main`: canonizador con límite de tasa compartido en Valkey, grafo compartido (`backend/graph/`), catálogo de Slush (`backend/catalog/`), feed y detalle con afinidad (`backend/api/`), chat con audio de Gemini y las páginas de cada reto (`docs/AIVEN.md`, `docs/CODEX.md`, `docs/GOOGLE-GEMINI.md`, `docs/PITCH.md`).
- En revisión: la interfaz minimalista de `gabriel` (#90 a #93) y el contexto por PDF y voz (#73).
- Equipo activo: `bau` y `gabriel`. `fabricio` y `adrian` en pausa.

## Pendientes
- [ ] Interfaz (#80): mergear #90 a #93 tras revisar capturas; sacar los archivos de las pantallas viejas (Deck, Journal, Estado, Perfil como pestaña).
- [ ] Contexto (#66, PR #73): sacar su cambio de `docs/CODEX.md`, rebasar y mergear.
- [ ] Correr el catálogo de Slush completo contra Valkey (~55 min) y exportar el respaldo.
- [ ] Textos del backend en inglés y no perder nombres en las notas de voz (#83).
- [ ] Prueba de punta a punta de la app contra el backend en vivo (#53).
- [ ] Preguntas al stand de Cala (`is_lead`, límite de uso, costo, otros eventos).
- [ ] Confirmar hora límite de entrega y formularios de cada reto.
- [ ] Slides y video del pitch (#69).
