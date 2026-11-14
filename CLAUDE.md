# Junction 2026: proyecto del equipo

Hackathon Junction 2026, Espoo (Finlandia), del 13 al 15 de noviembre de 2026. Somos **dos personas, cada una con su máquina, su Claude (Pro) y su Codex**, trabajando en paralelo sobre este repo. Lo leen los Claude de ambas máquinas (central, orquestador, subagentes) y Codex (este archivo es también `AGENTS.md`). Respondé en español.

## Producto
App **web y móvil** (una sola base de código con Expo) con un **chat** al que el founder le habla (texto o **audio**):
1. el audio se **transcribe**;
2. el backend arma y actualiza el **perfil de su startup** (sector, etapa, ciudad, competidores, qué busca);
3. responde al momento usando la **caché de Cala**;
4. en **segundo plano** busca en Cala recomendaciones (inversores, competidores que acaban de levantar, clientes potenciales) y avisa en el chat cuando están listas;
5. puede **verificar su pitch deck**: cada afirmación contra Cala, con fuentes (ya implementado en `backend/verifier`).

Cala es el núcleo (no tocamos cómo funciona: mostramos para qué sirve). Todo dato de Cala se muestra con su fuente.

## Retos
- **Principal: Cala** (25% cada uno: necesidad real, ejecución end-to-end, originalidad, Cala como núcleo). Slush empieza justo después: usable al día siguiente.
- **NVIDIA Nemotron** (secundario): Nemotron 3.5 Super VL como modelo central. Entrega: texto con el modelo, qué hace, por qué importa y **cómo mejoramos sus respuestas** (el filtro anti-alucinación de URLs y las métricas cuentan). Mientras no haya clave, `LLM_PROVIDER=codex`.
- **OpenAI Codex** (secundario): construimos con Codex; evidencia con `cx log` en cada máquina y `docs/PROCESO.md`.
- Candidatos sin decidir: Context.dev, Aiven, CRACI. Descartado: bot de WhatsApp/Telegram con n8n (se reemplaza por el chat de la app).

## Equipo y coordinación
- Cada máquina tiene **claude-central** instalado (github.com/BauDahn/claude-central): agentes, `cx` (Codex) y `equipo` (coordinación entre máquinas vía GitHub).
- **Orquestador del equipo: el central de la máquina `bau`.** Ve el estado de todas las máquinas con `equipo ver`, reparte trabajo con `equipo asignar`, revisa PRs y vigila conflictos. La otra máquina es `miembro`: trabaja lo que le llega por `equipo mias` y avisa con `equipo avisar bau "..."`.
- Estado compartido en GitHub: issue fijo #1 "Estado del equipo" (cada máquina actualiza su comentario cada 10 min), issues con label `maquina:<nombre>` y PRs.

### Dueños de cada área (para no pisarse)
| Área | Dueño | Notas |
|---|---|---|
| `backend/` | máquina `bau` | FastAPI + verificador + chat/audio/perfil/recomendaciones |
| `app/` | la otra máquina | Expo (web + iOS + Android), TypeScript |
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

## Cómo trabajamos
- **Claude planifica y revisa; el código lo escribe Codex** con `cx` (ver `cx roles`): `cx <rol> -C ~/proyectos/junction -p junction "<tarea concreta con criterio de hecho y cómo verificar>"`. Correcciones con `cx seguir <hilo> "..."` (hilos largos se encarecen: para algo nuevo, hilo nuevo). Claude revisa leyendo solo lo que cambió (`git diff`).
- Codex no hace commits, push ni cambia de rama: eso lo hace Claude.
- **Tokens:** no leer docs enteros si no hace falta; `rg` y lecturas parciales.

## Cómo correr
- Backend: `cd backend && uv sync && uv run uvicorn app:app --port 8000` (UI de prueba del verificador en `/`). CLI: `LLM_PROVIDER=codex uv run python -m verifier examples/sample_deck.pdf`. Tests: `uv run pytest`.
- App: `cd app && npm install && npx expo start` (web: tecla `w`). *(se completa cuando exista `app/`)*

## Reglas técnicas
- **Secretos**: `CALA_API_KEY`, `NVIDIA_API_KEY` solo en `backend/.env` (ignorado por git; plantilla en `backend/.env.example`). Nunca leerlos, imprimirlos, loguearlos ni ponerlos en prompts o commits.
- **Cala**: `POST /v1/knowledge/search` (lenguaje natural → respuesta con fuentes) y `/v1/knowledge/query` (filas). **~16 s por llamada**: siempre en paralelo, con caché en disco (`backend/cache/`, ignorada) y pocas llamadas por pantalla. Detalle en `docs/CALA-API.md`.
- **LLM**: `LLM_PROVIDER` = `nvidia` | `codex` | `claude` (`backend/verifier/llm.py`). NVIDIA: API compatible con OpenAI en `https://integrate.api.nvidia.com/v1`, ~40 req/min por clave, reintentos con backoff.
- **Transcripción**: proveedor configurable (pendiente de decidir: NVIDIA ASR, Whisper local con faster-whisper, u OpenAI).
- No crear repos ni desplegar sin aprobación del usuario. Antes de dar algo por terminado, correr la app o los tests y decir qué se verificó.

## Documentos
- `docs/API.md`: contrato backend ↔ app.
- `docs/SPEC-verificador.md`: diseño del verificador. `docs/CALA-API.md`: qué permite Cala. `docs/IDEAS-CALA.md`: ideas evaluadas. `docs/PROCESO.md`: diario.

## Pendientes
- [ ] Usuario de GitHub del compañero (acceso al repo) y nombre de su máquina para `equipo init`.
- [ ] Clave de NVIDIA (mañana) → probar Nemotron y fijar el ID exacto del modelo.
- [ ] Elegir proveedor de transcripción.
- [ ] Preguntas al stand de Cala (costo y latencia, cobertura nórdica y española, lead/follow).
- [ ] Confirmar hora límite de entrega y formularios de cada reto secundario.
