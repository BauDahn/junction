# Built with Codex

**Claude plans and reviews, Codex writes the code, Gemini is the AI inside the product.** By team rule, the application code in this repository is written by OpenAI Codex from concrete tasks, and checked against the real Cala and Gemini services before it was merged. This page is the evidence: how we worked, what Codex built, and how much we used it.

## The numbers

| | |
|---|---|
| Codex tasks logged on the orchestrator machine (`bau`) | **19**, all finished successfully, in 10 separate conversations |
| Of those, follow-up corrections after a real test (`seguir`) | **9** |
| Codex time on that machine | **53 min** (14 Nov, 02:20 to 16:16) |
| Tokens on that machine | **14.4 M input** (**95% from cache**), **184 k output**, 28 k reasoning |
| Gabriel's machine (`gabriel`) | **4 tasks, 12 min, 5.2 M input** (96% cached), **115 k output** |
| Fabricio's machine (`fabricio`) | **30 tasks, 107 min, 34.9 M input** (96% cached), **371 k output** |
| Adrian's machine (`adrian`) | **10 tasks, 17 min, 8.9 M input** (95% cached), **120 k output** |
| **Team total (four machines)** | **63 tasks, about 189 min of Codex time, 63.4 M input tokens, 790 k output tokens** |
| Code in `main` | about **7,500 lines** of Python and TypeScript at the time of the first count, and growing (app, backend, canonizer, catalog, graph, feed API) |
| Tests | **206 passing** on the combined main (backend) plus the canonizer suite |

## 1. How we use Codex

```mermaid
flowchart LR
  C["Claude<br/>design, tasks, review"] -- "cx: one concrete task<br/>files, done-when, how to verify" --> X["Codex<br/>writes and fixes the code"]
  X -- "diff and 'LISTO' report" --> C
  C -- "runs it against real<br/>Cala and Gemini" --> T{"works?"}
  T -- "no: exact error and input" --> F["cx seguir: correction<br/>in the same thread"] --> X
  T -- yes --> M["commit, PR, squash merge"]
```

- **Roles with their own model and effort** (`cx roles`): `backend` and `frontend` use `gpt-6-luna` at medium effort; `orquestador` runs at high effort; `ideas`, `seguridad` and `revisor` are read-only roles for brainstorming, security and review; trivial tasks use `gpt-5.6-luna` at low effort.
- **One task = one precise brief.** Each task names the files to read, the done-when criterion and how to verify it. Codex runs in a sandbox with workspace-write and never commits, pushes or switches branches: the human side owns Git.
- **Corrections stay in the same thread** (`cx seguir <thread> "..."`) so the context is reused. Threads that grow long get expensive, so new work gets a new thread. This helps explain why 95% of input tokens come from cache.
- **Four people, four machines, one flow.** Everyone delegates to Codex with the same `cx` tool and the same issue, branch and pull request rules (`CLAUDE.md`).
- **A task that hangs is cut and relaunched** instead of waiting.

## 2. What Codex built

| Component | What it is | Tasks |
|---|---|---|
| **Query canonizer** (`canonizador/`) | Turns any phrasing of a question into one canonical Cala query: intent extraction, entity resolution, fixed query templates, two cache layers. Takes consistency from 0 to 1 out of 9 up to **9 out of 9** | 6 |
| **Cala core** (`backend/cala_core/`) | Message router (query, claim, profile, chat), executor with fallbacks across Cala's tools, source normalization | 4 |
| **Gemini provider** | Gemini as an LLM provider for text, images and audio, with strict JSON schemas | 2 |
| **Chat backend** and **voice** | Sessions, text and audio messages, profile, recommendations; Gemini transcription that returns the literal transcript plus a clean intent in one call | Fabricio's machine |
| **Cala client optimizer** (#63) | Per-endpoint pacing, `Retry-After`, one request in flight per key; measured up to 1.89 calls/s with zero 429 | Fabricio's machine |
| **Expo app** (`app/`) | Chat with audio, profile, design system | Fabricio's machine |
| **Context ingestion** (#66) | PDF and voice notes into the profile with Gemini | In main |
| **n8n flows** (#47, in review) | Daily journal and Cala query workflows, validated against the n8n schema | Gabriel's machine |
| **Shared graph store** (#64) and **feed API** (#65) | Shared graph and feed API | In main |
| **Accounts, context and voice** (#112/#121) | Email authentication, fixed role, raw context and voice preview | In main |
| **Favorites PDF report** (#131/#137) | Cala-backed report and action plan | In main |
| **Abuse protection** (#134) | Shared limits and negative cache | In main |
| **Vercel SPA** (#133) | Static web export configuration | In main |
| First prototype: **pitch-deck verifier** | Built end to end in the first hours (backend, CLI, API and UI). We later dropped it from the product, but it is where we learned the pipeline and the rules Cala needs | 6 |

## 3. Why Codex worked well here

The pattern that paid off is **test against the real services, then hand Codex the exact failure**. Nine of the 19 tasks are corrections like these, taken from the log:

| What the real test showed | What Codex did |
|---|---|
| Gemini returned HTTP 400 `Unknown name "type"` | Normalized the schema converters to handle type lists and nested `properties` and `items` |
| The deck run failed with "Codex exceeded the 180 s timeout" | Made the timeout configurable (`CODEX_TIMEOUT`) |
| The retrieval step returned 422 from Cala | Switched round retrieval to filter locally |
| The judge marked "I was unable to find any evidence" as a contradiction | Taught it that absence of evidence is not contradiction |
| Filters failed to normalize with the real LLM | Made them deterministic |
| Open questions should go to the search tool, with sources | Extracted sources from `context[].origins[]` and named the block correctly |

Each correction was a short task with the failing input attached. The nine follow-ups took a median of 103 seconds of Codex time (from 34 s to 7.8 min).

## 4. Task log, `bau` machine (from `cx log`)

| Date | Role | Model | Task (summary) | Result | Min |
|---|---|---|---|---|---|
| 14/11 02:20 | backend | gpt-6-luna | Implementá la parte backend del verificador de decks según docs/SPEC-verificador.md: secciones Stack, Módulos… | LISTO: Backend del verificador, deck de ejemplo, CLI y tests implementados; no incluye `app.py… | 3.2 |
| 14/11 02:25 | backend | gpt-6-luna | (seguir) Probé la CLI real con Cala + Codex: funciona (59 s), pero corregí esto en pipeline.py y el deck de e… | LISTO: Ajusté la extracción para excluir marketing, forcé la consulta de afirmaciones públicas… | 1.5 |
| 14/11 02:25 | frontend | gpt-6-luna | Implementá app.py (en demo/) y la UI demo/static/index.html del verificador de decks según docs/SPEC-verifica… | LISTO: Implementé la API de jobs y la UI responsive del verificador. | 1.9 |
| 14/11 02:29 | backend | gpt-6-luna | (seguir) La corrida real falló: 'Codex excedió el timeout de 180 segundos' (ahora hay más claims). Cambios: 1… | LISTO: `CODEX_TIMEOUT` configura el timeout de Codex (default 420 s); los errores indican si f… | 1.6 |
| 14/11 02:31 | frontend | gpt-6-luna | (seguir) El pipeline ya expone progreso: verify_pdf acepta on_progress(stage, done, total) (leé demo/verifier… | LISTO: Conecté el progreso por etapas y el tiempo transcurrido. | 1.0 |
| 14/11 02:32 | backend | gpt-6-luna | En demo/verifier/pipeline.py, el prompt del juez marca 'contradicted' cuando Cala dice 'I was unable to find … | LISTO: el juez distingue ausencia de evidencia de una contradicción y extrae métricas internas… | 0.8 |
| 14/11 03:13 | backend | gpt-6-luna | Implementá el canonizador de consultas a Cala según docs/internal/SPEC-canonizador.md (leé también docs/internal/CALA-CAMPOS.md… | LISTO: Implementé el paquete independiente en `canonizador/`, con normalización, proveedor LLM… | 3.2 |
| 14/11 03:27 | backend | gpt-6-luna | (seguir) La corrida real falló en canonizador/canonizador/intent.py (CodexProvider). Dos arreglos: (1) el sch… | LISTO: CodexProvider ahora genera schemas estrictos, cierra stdin, usa timeout de 120 s con st… | 0.6 |
| 14/11 03:28 | backend | gpt-6-luna | (seguir) El intent ya funciona (las 3 variantes resuelven a Amenitiz db95edaa-058f-494d-a4f4-5f56bf81afd9), p… | LISTO: El retrieval de rondas filtra localmente, envía a Cala solo claves admitidas y pide pro… | 2.6 |
| 14/11 03:49 | backend | gpt-6-luna | Implementá la 'Fase 2' de docs/internal/SPEC-canonizador.md en canonizador/ (leé esa sección, docs/internal/CALA-SKILL.md y el … | LISTO: Fase 2 implementada en `canonizador/`; la consulta de Amenitiz marcó la discrepancia en… | 3.6 |
| 14/11 03:54 | backend | gpt-6-luna | (seguir) Probé con el LLM real. Amenitiz: las 4 variantes dan la misma cadena y la misma respuesta (bien). Fi… | LISTO: filtros normalizados de forma determinista; ambos casos generan la misma consulta y el … | 1.7 |
| 14/11 04:04 | backend | gpt-6-luna | Bug en canonizador/ (leé canonizador/canonizador/api.py, plan.py, client.py). Con el LLM real, las listas (co… | LISTO: separé la respuesta principal del enriquecimiento y ajusté el cuerpo de retrieval al co… | 2.2 |
| 14/11 13:48 | backend | gpt-6-luna | Issue #30: implementá backend/cala_core/ según docs/internal/PLAN-CALA-CENTRO.md (secciones 1–5) y el contrato de bloq… | LISTO: Implementé `backend/cala_core/` y la dependencia editable local de Cala Canonizador. Aj… | 5.8 |
| 14/11 14:00 | backend | gpt-6-luna | (seguir) Probé cala_core con Codex y Cala reales: anda bien (consulta, claim contradicted, mensaje mixto). Co… | LISTO: Normalicé las fuentes, limpié los parches de perfil, canonizé intereses y generé título… | 2.8 |
| 14/11 15:59 | rapido | gpt-5.6-luna | Respondé solo: LISTO: ok | LISTO: ok | 0.7 |
| 14/11 15:59 | backend | gpt-6-luna | Issue #43: agregá Gemini como proveedor de LLM. Leé backend/verifier/llm.py (proveedores con complete_json(sy… | LISTO: Gemini agregado como proveedor de LLM, con soporte de texto, imágenes y audio en el bac… | 5.2 |
| 14/11 16:05 | backend | gpt-6-luna | (seguir) Probé con la clave real: Gemini devuelve HTTP 400 'Unknown name "type" … Proto field is not repeatin… | LISTO: Ambos conversores normalizan listas de tipos y recorren `properties`, `items`, `anyOf` … | 2.5 |
| 14/11 16:10 | backend | gpt-6-luna | Issue #49 (rama actual). Leé backend/cala_core/router.py y executor.py (ya en main con los arreglos de respal… | LISTO: Router, executor y fusión de perfiles actualizados para Issue #49. | 4.6 |
| 14/11 16:16 | backend | gpt-6-luna | (seguir) Probé con Gemini y Cala reales. Las preguntas abiertas ya van a knowledge_search (bien). Dos fallas:… | LISTO: fuentes de búsqueda extraídas de `context[].origins[]`, título de `cala_answer` basado … | 7.8 |

## 5. Other machines

- **`gabriel`:** 4 tasks, 12 min, 5,177,047 input tokens (96% cached), 115,061 output, model `gpt-6-luna`. They built the three n8n workflows (#47), validated with `n8n-mcp`, and the context module (#66).
- **`fabricio`:** 30 tasks, 107 min, 34.9 M input tokens (96% cached), 371 k output. Cala client optimizer and shared rate limit, Gemini audio, feed and detail API with the affinity score, shared graph store on Valkey, journal and chat integration, design system, router fixes, Valkey connection.
- **`adrian`:** 10 tasks, 17 min, 8.9 M input tokens (95% cached), 120 k output. Context adaptation; #112/#121 email authentication, fixed role, raw context and voice preview; #133 Vercel SPA configuration.

## 6. How to regenerate

Each machine keeps its log in `~/agentes/estado/codex.jsonl`; `cx log` summarizes it. Per machine, add a section with the totals (tasks, minutes, input, cached and output tokens) and the table, as in section 4. The totals at the top of this page are updated from those sections.
