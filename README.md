# Junction 2026 · Cala

Chat (web y móvil) que entiende tu startup por audio, verifica tu pitch deck con datos de [Cala](https://cala.ai) y te recomienda inversores y clientes, siempre con fuentes. Las reglas para humanos y agentes están en [CLAUDE.md](CLAUDE.md).

## Puesta en marcha (cada persona, una vez)
1. Instalar [claude-central](https://github.com/BauDahn/claude-central) (`git pull && ./install.sh` si ya lo tenés). Requiere Claude Code, `gh` autenticado y Codex (`npm i -g @openai/codex && codex login`).
2. Clonar: `gh repo clone BauDahn/junction ~/proyectos/junction`.
3. Claves: `cp backend/.env.example backend/.env` y completar `CALA_API_KEY` (la misma para los dos) y `NVIDIA_API_KEY`. Nunca se commitean.
4. Registrar la máquina en el equipo:
   - orquestador: `equipo init --maquina bau --rol orquestador --repo BauDahn/junction --dir ~/proyectos/junction`
   - compañero: `equipo init --maquina <tu-nombre> --rol miembro --repo BauDahn/junction --dir ~/proyectos/junction`
5. Backend: `cd backend && uv sync && uv run pytest`.
6. Abrí `central` y decile "¿qué tengo asignado?".

## Correr
- Backend: `cd backend && uv run uvicorn app:app --port 8000` → http://localhost:8000
- App: `cd app && npm install && npx expo start` *(cuando exista)*
