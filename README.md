# Junction 2026 · Cala por voz

**Un copiloto para founders e inversores construido sobre [Cala](https://cala.ai).** Le hablás (o escribís) y convierte lo que decís en consultas a Cala: muestra los datos tal cual, como tablas con fuentes, contrasta los datos que vos afirmás y arma un journal diario del ecosistema con lo que encuentra en Cala.

Hecho en Junction 2026 (Espoo, 13–15 de noviembre de 2026) para el reto de Cala, con Codex como ejecutor y Nemotron 3.5 Super VL de NVIDIA como modelo.

## Qué hace

| Función | Cómo |
|---|---|
| **Preguntar por voz** | "¿Quién lideró la Serie B de Amenitiz?" → consulta canónica a Cala → tabla con monto, líder, inversores y fuentes |
| **Contrastar lo que decís** | "Mews levantó 50 millones" → se busca en Cala → confirmado, contradicho o sin datos, con la evidencia |
| **Perfil y gustos** | "Somos Stayflow, software para hoteles en Barcelona; nos interesan las fintech nórdicas" → se guarda para personalizar |
| **Journal diario** | Edición del ecosistema y edición personalizada, armadas solo con consultas a Cala |
| **Verificador de decks** | Subís el PDF del pitch y cada afirmación se contrasta con Cala |
| **Recomendaciones** | Inversores, competidores y clientes potenciales, cada uno con su fuente |

**Lo que lo hace distinto:** descubrimos que Cala responde distinto a la misma pregunta según cómo se escriba (acentos, idioma, orden) y construimos un **canonizador** que convierte cualquier redacción en la misma consulta. Preguntando directo, por MCP o con la guía oficial de Cala, como mucho 1 de 9 preguntas fue consistente; con el canonizador, 9 de 9. Ver [docs/BENCHMARK-CANONIZADOR.md](docs/BENCHMARK-CANONIZADOR.md) y [docs/INFORME-ERROR-CALA.md](docs/INFORME-ERROR-CALA.md).

## Cómo funciona

```
voz / texto ──► transcripción (Whisper) ──► router ──┬─ consulta ──► canonizador ──► Cala ──► tabla con fuentes
                                                     ├─ afirmación ─► canonizador ──► Cala ──► veredicto + evidencia
                                                     ├─ perfil ─────► perfil y gustos ──► journal personalizado
                                                     └─ charla ─────► respuesta corta
```

Si la consulta canónica no trae datos, se prueban las otras herramientas de Cala (entidades y búsqueda) antes de decir que no hay nada. El modelo de lenguaje solo interpreta el pedido: **nunca escribe cifras ni nombres que no vengan de Cala**. Diseño completo en [docs/PLAN-CALA-CENTRO.md](docs/PLAN-CALA-CENTRO.md).

## Estructura del repo

| Carpeta | Qué hay |
|---|---|
| `app/` | App web y móvil (Expo + React Native + TypeScript): chat con audio, perfil, verificador, journal |
| `backend/` | API (FastAPI + SQLite). `chat/`: sesiones, mensajes, audio, perfil, recomendaciones. `cala_core/`: router y consultas a Cala. `journal/`: journal diario. `verifier/`: verificador de decks. Ver [backend/README.md](backend/README.md) |
| `canonizador/` | Canonizador de consultas a Cala, con sus benchmarks. Ver [canonizador/README.md](canonizador/README.md) |
| `docs/` | Plan, contrato de la API, guías de Cala, benchmarks e informe del error (índice en [CLAUDE.md](CLAUDE.md#documentos)) |

## Correr

Requisitos: Python 3.11+ con [uv](https://docs.astral.sh/uv/), Node 20+, y una clave de Cala.

```bash
# claves (nunca se commitean)
cp backend/.env.example backend/.env      # completar CALA_API_KEY y, si hay, NVIDIA_API_KEY

# backend → http://localhost:8000
cd backend && uv sync && uv run uvicorn app:app --port 8000
uv run pytest                             # tests

# app → tecla w para la versión web
cd app && npm install && npx expo start   # en el celular (Expo Go): EXPO_PUBLIC_API_URL=http://<IP del PC>:8000
```

Sin `NVIDIA_API_KEY`, el backend usa Codex como modelo (`LLM_PROVIDER=codex`). La app tiene un modo simulado si el backend no responde.

## Cómo trabajamos

Dos personas, cada una con su máquina, Claude Code y Codex. Claude planifica y revisa, y **el código lo escribe Codex** (registro en [docs/CODEX.md](docs/CODEX.md)). Las máquinas se coordinan con [claude-central](https://github.com/BauDahn/claude-central) (`equipo`), usando issues y PRs en este repo. Las reglas del repo, el reparto de áreas y el flujo de Git están en [CLAUDE.md](CLAUDE.md).

### Puesta en marcha para el equipo (una vez por máquina)
1. Instalar [claude-central](https://github.com/BauDahn/claude-central) (`git pull && ./install.sh`). Requiere Claude Code, `gh` autenticado y Codex (`npm i -g @openai/codex && codex login`).
2. `gh repo clone BauDahn/junction ~/proyectos/junction` y crear `backend/.env`.
3. Registrar la máquina: `equipo init --maquina <nombre> --rol miembro --repo BauDahn/junction --dir ~/proyectos/junction` (la máquina `bau` es la orquestadora).
4. Abrir `central` y preguntarle "¿qué tengo asignado?".
