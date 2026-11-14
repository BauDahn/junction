# Junction 2026: proyecto del equipo

Hackathon Junction 2026, Espoo (Finlandia), del 13 al 15 de noviembre de 2026. Somos **dos personas, cada una con su máquina, su Claude (Pro) y su Codex**, trabajando en paralelo sobre este repo. Lo leen los Claude de ambas máquinas (central, orquestador, subagentes) y Codex (este archivo es también `AGENTS.md`). Respondé en español.

## Producto (enfoque desde el 14/11: Cala en el centro)
**No es un chatbot: es una forma de usar Cala desde la voz.** Plan completo en `docs/PLAN-CALA-CENTRO.md`.
1. El usuario habla o escribe en la app (web y móvil, Expo). El audio se **transcribe** (Whisper local).
2. Un **router** divide el mensaje en partes y clasifica cada una: **consulta** (se busca en Cala), **afirmación** del usuario (se contrasta con Cala), **perfil/gustos** (se guarda) o charla.
3. Las consultas van por el **canonizador** (misma intención → misma consulta) y, si no hay datos, prueban las otras herramientas de Cala (entidades, búsqueda). Nunca "no hay información" sin haber probado todo.
4. Lo que se muestra son **datos de Cala tal cual**, como tablas con fuentes (`docs/API.md`, bloques). El modelo nunca escribe cifras ni nombres que no vengan de Cala.
5. **Journal diario** en la app: edición genérica del ecosistema y edición personalizada para founders, armadas solo con consultas a Cala.
6. Además: **verificador de pitch decks** (cada afirmación del PDF contra Cala) y recomendaciones de inversores, competidores y clientes.

Cala es el núcleo (no tocamos cómo funciona: mostramos para qué sirve). Todo dato de Cala se muestra con su fuente.

## Retos
- **Principal: Cala** (25% cada uno: necesidad real, ejecución end-to-end, originalidad, Cala como núcleo). Slush empieza justo después: usable al día siguiente.
- **Google Gemini** (secundario, desde el 14/11): Gemini es la IA del producto (router, audio, intención, juez, lectura de decks). El reto pide un uso significativo e innovador y explicar por qué Gemini importa en la solución.
- **Aiven** (secundario): caché compartida de consultas a Cala en Aiven Valkey (`VALKEY_URL`, ver `canonizador/README.md`).
- NVIDIA Nemotron: descartado como modelo principal (el endpoint que nos dieron nunca respondió); el proveedor queda en el código como alternativa.
- **OpenAI Codex** (secundario): construimos con Codex; evidencia en `docs/CODEX.md` (registro de tareas exportado de `cx log` de cada máquina) y `docs/PROCESO.md`.
- Candidatos sin decidir: Context.dev, CRACI. Descartado: bot de WhatsApp/Telegram con n8n (se reemplaza por el chat de la app).

## Equipo y coordinación
- Cada máquina tiene **claude-central** instalado (github.com/BauDahn/claude-central): agentes, `cx` (Codex) y `equipo` (coordinación entre máquinas vía GitHub).
- **Orquestador del equipo: el central de la máquina `bau`.** Ve el estado de todas las máquinas con `equipo ver`, reparte trabajo con `equipo asignar`, revisa PRs y vigila conflictos. La otra máquina es `miembro`: trabaja lo que le llega por `equipo mias` y avisa con `equipo avisar bau "..."`.
- Estado compartido en GitHub: issue fijo #1 "Estado del equipo" (cada máquina actualiza su comentario cada 10 min), issues con label `maquina:<nombre>` y PRs.

### Dueños de cada área (para no pisarse)
| Área | Dueño | Notas |
|---|---|---|
| `backend/cala_core/`, `backend/journal/` | máquina `bau` | Router, ejecución contra Cala, formato de bloques, verificación de afirmaciones y journal |
| `backend/verifier/`, `canonizador/` | máquina `bau` | Verificador de decks; canonizador de consultas y benchmarks |
| `backend/chat/`, `backend/app.py` | máquina `fabricio` | Sesiones, mensajes, audio, perfil, recomendaciones; conecta `cala_core` al chat |
| `app/` | máquina `fabricio` | Expo (web + iOS + Android), TypeScript |
| `docs/API.md` | compartido | contrato backend ↔ app; cambios fuera de *(borrador)* en un PR propio aprobado por el otro |
| resto de `docs/` | cualquiera | `PROCESO.md`: una línea por hito |

Si hace falta tocar el área del otro, se pide por `equipo avisar` o se hace en un PR que el dueño aprueba.

### Flujo de Git (obligatorio)
1. Toda tarea es un **issue** (`equipo asignar <maquina> "título" --cuerpo "qué, criterio de hecho"`).
2. Rama desde `main` actualizado: `git switch main && git pull && git switch -c <maquina>/<issue>-<slug>` (ej. `bau/12-chat-audio`).
3. Commits chicos. **Nunca commitear a `main` ni hacer force-push a ramas ajenas.**
4. Antes del PR: `git fetch && git rebase origin/main`, tests en verde.
5. PR con `gh pr create --fill --body "Closes #<issue>"`; avisar al otro (`equipo avisar <maquina> "PR #N"`). Revisa el otro o el orquestador; merge con **squash**. Apuntar a PRs de < 2 h de trabajo.
6. Después de cada merge en `main`, la otra máquina hace `git pull --rebase` en su rama.

## Cómo trabajamos: tres roles (decisión del 14/11)
| Quién | Rol | Qué hace | Qué no hace |
|---|---|---|---|
| **Claude** | Orquestador y arquitecto | Diseña (specs, contrato de la API, planes), reparte tareas, revisa diffs y PRs, prueba contra los servicios reales, coordina las máquinas y mantiene la documentación | **No escribe código de la aplicación.** Ni arreglos chicos: todo cambio de código se le pide a Codex |
| **Codex** | Programador | Escribe y corrige todo el código (backend, app, canonizador, tests) a partir de tareas concretas | No decide arquitectura ni hace commits, push o cambios de rama |
| **Gemini** | IA dentro del producto | Todos los servicios de IA en tiempo de ejecución: clasificar mensajes (router), extraer intenciones, transcribir y entender audio, elegir filas, juzgar afirmaciones y leer decks | No se usa Codex ni Claude como modelo del producto (quedan solo como respaldo) |

- Delegar a Codex con `cx` (ver `cx roles`): `cx <rol> -C ~/proyectos/junction -p junction "<tarea concreta con criterio de hecho y cómo verificar>"`. Correcciones con `cx seguir <hilo> "..."` (hilos largos se encarecen: para algo nuevo, hilo nuevo). Si Codex queda colgado sin tocar archivos, cortarlo y relanzar.
- Claude revisa leyendo solo lo que cambió (`git diff`), corre los tests y las pruebas reales, y hace los commits, push y PRs.
- **Gemini**: modelo rápido (`GEMINI_FAST_MODEL`, por defecto `gemini-3.5-flash-lite`: ~1 s por llamada, 3/3 en la prueba del router) para router, intención y foco; modelo fuerte (`GEMINI_MODEL`, por defecto `gemini-flash-latest`) para verificador y juez. Medido el 14/11 con la clave del equipo.
- **Tokens:** no leer docs enteros si no hace falta; `rg` y lecturas parciales.

## Cómo correr
- Backend: `cd backend && uv sync && uv run uvicorn app:app --port 8000` (UI de prueba del verificador en `/`). CLI: `LLM_PROVIDER=codex uv run python -m verifier examples/sample_deck.pdf`. Tests: `uv run pytest`.
- App: `cd app && npm install && npx expo start` (web: tecla `w`; en Expo Go, `EXPO_PUBLIC_API_URL` con la IP del PC). La app tiene modo simulado si el backend no responde.
- Todo junto: backend en `:8000` y app web; el chat completo (texto, audio, perfil, recomendaciones con fuentes) ya está en `main`.

## Reglas técnicas
- **Secretos**: `CALA_API_KEY`, `NVIDIA_API_KEY` solo en `backend/.env` (ignorado por git; plantilla en `backend/.env.example`). Nunca leerlos, imprimirlos, loguearlos ni ponerlos en prompts o commits.
- **Cala**: el código nuevo consulta Cala **a través del canonizador** (`canonizador/`), nunca mandando el texto del usuario directo: el texto libre da respuestas distintas para la misma pregunta (`docs/BENCHMARK-CANONIZADOR.md`). Endpoints: `knowledge/query` (filas), entidades (datos con fuentes y `is_lead`), `knowledge/search` (respuesta con fuentes, último recurso). **16–60 s por llamada** y HTTP 429 tras ~7 llamadas seguidas: caché en disco (`backend/cache/`, ignorada), pocas llamadas a la vez y reintentos con espera. Detalle en `docs/CALA-CAMPOS.md` y `docs/CALA-API.md`.
- **LLM**: `LLM_PROVIDER` = `gemini` (por defecto si hay `GEMINI_API_KEY`) | `nvidia` | `codex` | `claude` (`backend/verifier/llm.py`). Claves solo en `backend/.env`.
- **Transcripción**: `TRANSCRIPTION_PROVIDER` = `whisper` (por defecto: faster-whisper local, modelo `WHISPER_MODEL`, por defecto `small`) | `nvidia` (sin probar) | `none`. Ver `backend/chat/transcribe.py`.
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
| `docs/SPEC-verificador.md` | Diseño del verificador de decks |
| `docs/IDEAS-CALA.md` | Ideas evaluadas al elegir el proyecto |
| `docs/CODEX.md` | Registro de lo que construyó Codex (reto de Codex) |
| `docs/PROCESO.md` | Diario de decisiones |

## Estado (14/11, tarde)
- En `main`: verificador de decks, canonizador + benchmarks, app Expo (#6, #7, #8) y chat del backend: sesiones, texto, audio y recomendaciones (#3, #4, #5).
- En curso: enfoque "Cala en el centro" (`docs/PLAN-CALA-CENTRO.md`): router y bloques (bau), journal (bau), conexión al chat y app (fabricio).
- Equipo: `bau` (orquestador), `fabricio` (miembro). Gabriel está en el equipo, por ahora en otra tarea.

## Pendientes
- [ ] Enfoque Cala en el centro: tareas A–F de `docs/PLAN-CALA-CENTRO.md`.
- [ ] Gemini: proveedor en backend y canonizador (#43), transcripción con Gemini (fabricio) y medir el tiempo por mensaje.
- [ ] Aiven: crear el servicio Valkey y poner `VALKEY_URL` en `backend/.env` de las dos máquinas.
- [ ] Prueba de punta a punta de la app contra el backend en vivo (web y Expo Go).
- [ ] Preguntas al stand de Cala (límite de uso, costo, latencia, lead/follow, Slush 2026).
- [ ] Confirmar hora límite de entrega y formularios de cada reto secundario.
- [ ] Pitch y video de demo.
