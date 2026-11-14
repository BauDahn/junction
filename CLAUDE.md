# Junction 2026: proyecto del equipo

Hackathon Junction 2026, Espoo (Finlandia), del 13 al 15 de noviembre de 2026. Este repo concentra todo lo del equipo para la hackathon. Lo leen Claude (central, orquestador, subagentes) y Codex (este archivo es también `AGENTS.md`). Respondé en español.

## Decisiones (no reabrirlas sin que lo pida el usuario)
- **Reto principal: Cala.** Producto para founders o inversores sobre los datos públicos de Cala. No se toca cómo funciona Cala: se muestra para qué sirve en un contexto concreto. Jurado (25% cada uno): necesidad real, ejecución end-to-end, originalidad, uso de Cala como núcleo. Slush empieza justo después: tiene que ser usable al día siguiente.
- **Retos secundarios ("pasivos") confirmados:**
  - **NVIDIA Nemotron**: Nemotron 3.5 Super VL es el modelo central (consulta a Cala, cruza, rankea, explica; lee PDFs e imágenes). Entrega: texto en el formulario con el modelo usado, qué hace, por qué importa y **cómo mejoramos sus respuestas** (evaluación, prompts). Criterios: uso significativo, ejecución, calidad de las respuestas, creatividad. Premio: 2 × RTX 5080.
  - **OpenAI Codex**: construimos con Codex y hay que mostrar cómo aceleró el desarrollo. Evidencia: `cx log` (ver abajo) y notas en `docs/PROCESO.md`.
- **Secundarios candidatos (sin decidir):** Context.dev (señales web en vivo), Aiven (PostgreSQL/Valkey como caché), CRACI (CI con `runs-on: craci`). Descartados: Verda, Modal, Gemma, Cloudinary, Gemini (elegimos Nemotron).
- **Idea: PENDIENTE de elección del usuario.** Finalistas: **verificador de decks** (Nemotron VL lee el PDF y Cala verifica cada afirmación con fuente) y **radar de primeros clientes** (empresas recién financiadas en tu segmento, con la persona a contactar y el motivo, todo con fuente). Detalle y puntajes en `docs/IDEAS-CALA.md`.

## Estructura
- `docs/IDEAS-CALA.md`: las 12 ideas, puntajes, consultas a Cala por idea, preguntas para el stand.
- `docs/CALA-API.md`: qué permite la API de Cala y qué no está documentado.
- `docs/PROCESO.md`: diario de decisiones y uso de Codex/Nemotron (material para las entregas y el pitch). Agregá una línea por hito.
- `demo/`: prototipo funcional. Las claves van en `demo/.env` (ver `demo/.env.example`).

## Cómo trabajamos
- **Central** coordina y habla con el usuario por voz. **Orquestador** (si está abierto) reparte el trabajo. Nadie arranca una tarea grande sin que central o el usuario la haya pedido.
- **El código lo escribe Codex** con `cx` (perfiles baratos por rol, ver `cx roles`): `cx <rol> -C ~/proyectos/junction -p junction -t <ID> "<tarea concreta con criterio de hecho y cómo verificar>"`. Correcciones: `cx seguir <hilo> "..."`. Claude revisa leyendo solo los archivos que cambiaron.
- **Tablero**: proyecto `junction` (`tareas ls -p junction`). **Bloqueos de archivo** con `bloqueo` si dos agentes tocan lo mismo.
- **Tokens**: no leas docs enteros si no hace falta; usá `rg` y lecturas parciales. Las respuestas de Cala se cachean en disco (ver reglas técnicas).

## Reglas técnicas
- **Secretos**: `CALA_API_KEY` y `NVIDIA_API_KEY` solo en `demo/.env` (está en `.gitignore`). Nunca los imprimas, loguees, copies a otro archivo ni los pongas en prompts. El código los carga del entorno.
- **Cala**: base `https://api.cala.ai`, header `X-API-KEY`. Endpoints clave: `POST /v1/knowledge/search` (lenguaje natural → respuesta con fuentes), `POST /v1/knowledge/query` (filas estructuradas), `GET /v1/entities?name=`, `POST /v1/entities/{id}`. Costo por llamada y límites no documentados: **cachear todas las respuestas en disco** (clave = endpoint + input) y minimizar llamadas por pantalla. Siempre mostrar la fuente (`origins`) de cada dato en la UI.
- **NVIDIA**: API compatible con OpenAI, base `https://integrate.api.nvidia.com/v1`. Modelo: Nemotron 3.5 Super VL (verificar el ID exacto en build.nvidia.com). Free tier ~40 req/min por clave: reintentos con backoff, pocas llamadas por acción. Dejar el modelo configurable por variable de entorno para tener un respaldo.
- No hagas `git push`, no crees repos remotos ni despliegues sin aprobación del usuario.
- Antes de dar algo por terminado, corré la demo o los tests y decí qué verificaste.

## Pendientes
- [ ] El usuario elige la idea (verificador de decks vs radar de clientes).
- [ ] Preguntas al stand de Cala: costo por llamada y latencia, cobertura nórdica y española, M&A, lead/follow, personas con rol (ver `docs/IDEAS-CALA.md`).
- [ ] Confirmar el ID exacto de Nemotron 3.5 Super VL y el límite real de la API gratis.
- [ ] Confirmar la hora límite de entrega de Junction y si cada reto secundario pide formulario aparte.
- [ ] Demo funcional en `demo/`.
