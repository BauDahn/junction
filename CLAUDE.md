# Junction 2026: team project

Junction 2026 hackathon, Espoo (Finland), November 13–15, 2026. We are **four people (Bau, Fabricio, Gabriel, and Adrian), each with their own machine and agents**, working in parallel on this repo. This file is read by all agents: Claude (`CLAUDE.md`), Codex (`AGENTS.md`), and Google's agents (`GEMINI.md`); all three names point to the same file. Respond in Spanish.

## Product (final form, 15/11: Cala Match)
**A financing marketplace around events, built on Cala's graph. The entire app is in English.** The README has the public version. The prompt given to Gemini for the new web app is summarized here.
1. **Registration:** during sign-up, choose **Raiser** (a startup seeking funding) or **Investor**; this is required to enter and determines what each screen shows. Only Raiser mode is specified; Investor mode is its mirror (startups to browse).
2. **Events** (squares with an image, name, tagline, and date), two tabs:
   - **Explore events:** all events; save one as "attending" or not; saved events appear under My events.
   - **My events:** when entering an event, see the **investors recommended** by the affinity engine and, for each one, a **note on how to approach them**. Clicking an investor opens a very simple profile with the information Cala provides (company, industry, important factors such as funds) and **how to secure the investment**, based on previous investments, schedules, and Cala data.
3. **Assistant:** there is no Ask tab. A **mascot bubble** in the bottom-right opens an overlay panel with text and voice chat: ask about companies (Cala + canonicalizer), **modify the context** (what the recommendation engine uses), and perform **shortcuts** ("quiero ir a Slush 2026" ("I want to go to Slush 2026") adds it to favorites).
4. **Profile:** context, favorite investors, and personal details. Simple and minimal.
5. **Fallback when something is not in the graph:** chat never fails (canonicalizer, entity, search, `not_found` with what was tried); details are fetched live from Cala and saved; `GET /api/search` checks the catalog and then Cala.
6. **Local subgraph over Cala and affinity:** as in `docs/ARCHITECTURE.md` and `docs/SPEC-GRAPH-AFFINITY.md`. Event data: Slush 2026 has 2,990 participating companies with people; Slush 2025 has only 8 speakers.

Gemini (Antigravity) is building the new web app. **Product items NOT in that prompt** remain ideas: a meeting planner in a document, and a "20 minutes free" notice. Outside the product: the deck checker and the journal. Cala is the core; all Cala data is shown with its source.

## Challenges
- **Primary: Cala** (25% each: real need, end-to-end execution, originality, Cala as the core). Slush starts right after: usable the next day.
- **Google Gemini** (secondary, from 14/11): Gemini is the product's AI (router, audio, intent, judge). The challenge asks for a meaningful and innovative use and an explanation of why Gemini matters to the solution.
- **Aiven** (secondary): shared cache for Cala queries in Aiven Valkey (`VALKEY_URL`, see `canonizador/README.md`).
- NVIDIA Nemotron: ruled out as the primary model (the endpoint they gave us never responded); the provider remains in the code as an alternative.
- **OpenAI Codex** (secondary): we are building with Codex; evidence is in `docs/CODEX.md` (task log exported from `cx log` on each machine).
- Candidates not yet decided: Context.dev, CRACI. Ruled out: WhatsApp/Telegram bot (replaced by the in-app assistant).

## Team and coordination
| Machine | Person | Agents | Role |
|---|---|---|---|
| `bau` | Bau | Claude, Codex, Gemini | Member. The public demo backend and tunnel run on his laptop |
| `fabricio` | Fabricio | Claude (orchestrator), Codex, Gemini | **Leads since 15/11:** assigns, reviews, and merges everything |
| `gabriel` | Gabriel | Antigravity (Gemini) and Codex | Member: brand calado and interface |
| `adrian` | Adrian | Antigravity | Member: Vercel deployment, registration, and profile |

- **Everything is coordinated through GitHub**, the only thing all four machines can see: fixed issue #1 "Team status" (each machine's status and messages), issues labeled `maquina:<nombre>` (tasks), and PRs.
- With [claude-central](https://github.com/BauDahn/claude-central) installed, use the `equipo` command (`equipo mias`, `equipo mensajes`, `equipo avisar bau "..."`, `equipo publicar`). **Without claude-central** (for example, with a Google agent), do the same with `gh`: `gh issue list --label maquina:<nombre>` to see your tasks, and a comment on issue #1 starting with `**<nombre> → bau:**` to send a message. The `equipo` script is a single Python file that only needs `gh`; it can be used standalone.
- **Before starting work that was not assigned to you, notify the orchestrator** (comment on #1 or `equipo avisar bau`) to avoid duplication. This has happened before.
- The orchestrator replies and assigns work in the same channel. Keys (`CALA_API_KEY`, `GEMINI_API_KEY`, `VALKEY_URL`) are shared privately, never through GitHub.

### Area owners (15/11, all four active)
| Area | Owner |
|---|---|
| `app/`: theme, navigation, events, investors, assistant | `fabricio` |
| `app/`: registration, text profile, voice with preview | `adrian` |
| `backend/catalog/`, `backend/graph/`, `backend/api/`, `backend/accounts/`, `backend/context/`, `backend/chat/`, `canonizador/`, `docs/`, `CLAUDE.md`, `README.md` | `bau` with Codex |

**Who merges:** `fabricio` reviews and merges all PRs (squash), after running the tests. `gabriel` opens small PRs, one per screen, with screenshots at 390 px. After merging, `bau` posts in issue #1.

### Git workflow (required)
1. Every task is an **issue** (`equipo asignar <machine> "title" --cuerpo "what, definition of done"`).
2. Branch from an up-to-date `main`: `git switch main && git pull && git switch -c <maquina>/<issue>-<slug>` (e.g. `bau/12-chat-audio`).
3. Small commits. **Never commit to `main` or force-push to someone else's branch.**
4. Before the PR: `git fetch && git rebase origin/main`, with tests passing.
5. PR with `gh pr create --fill --body "Closes #<issue>"`; notify the other person (`equipo avisar <maquina> "PR #N"`). The other person or orchestrator reviews it; merge with **squash**. Aim for PRs requiring less than 2 hours of work.
6. After each merge into `main`, the other machine runs `git pull --rebase` on its branch.

## Workstreams
Current workstreams (15/11).

| Workstream | What it is | Who |
|---|---|---|
| **Interface** | Dark mode, #006CFF color, icon bar, events, investors, empty assistant with icon only, and blockers from PR #104 | `fabricio` (#107) |
| **Accounts and context in the interface** | Email registration with a fixed role, profile with context as text, voice with preview and 'Add to context' | `adrian` (#112) |
| **Data** | Cala 402 errors in the catalog, Slush investors from the graph, real events and per-user saved events | `bau` with Codex (#111) |
| **Central** | Review and merge, accounts and context backend (done: #109, #110), documentation, presentation | `bau` |

## Quality principles (decision on the night of 14/11)
**Less quantity, more quality. A simple app that looks and feels good is worth more than many half-finished features.**
- The app has a **bottom bar with three tabs**: My events, Explore events, and Profile (context lives inside the profile). The assistant is a floating bubble (icon only) that opens the chat. Plus the event page and company profile.
- **Out of the app and repo:** Deck, Journal, and the status screen. The files for those screens are deleted, not hidden.
- Before adding a feature, ask whether it improves the demo's first screen. If not, it does not go in; it goes on a later list.
- A screen is finished when it looks good on a phone, has empty, loading, and error states with human-friendly text, and has been tested with real data. A half-finished screen is not merged even if it "already works."
- **Minimal, human design.** The rules are in the app redesign issue (one accent color, no gradients or glow, minimal shadow, specific text instead of slogans, no cards inside cards). Interface PRs include screenshots at 390 px wide, and Claude reviews them before merging.

## How we work: three roles (decision on 14/11)
| Who | Role | What they do | What they don't do |
|---|---|---|---|
| **Claude** | Orchestrator and architect | Designs (specs, API contract, plans), assigns tasks, reviews diffs and PRs, tests against real services, coordinates the machines, and maintains documentation | **Does not write application code.** Not even small fixes: all code changes are assigned to Codex |
| **Codex** | Programmer | Writes and fixes all code (backend, app, canonicalizer, tests) from concrete tasks | Does not decide architecture or make commits, push, or branch changes |
| **Gemini** | AI inside the product | All runtime AI services: classify messages (router), extract intents, transcribe and understand audio, select rows, and judge claims | Codex or Claude are not used as the product model (they remain only as fallback) |

- Delegate to Codex with `cx` (see `cx roles`): `cx <role> -C ~/proyectos/junction -p junction "<concrete task with definition of done and how to verify>"`. Corrections with `cx seguir <hilo> "..."` (long threads get expensive: use a new thread for new work). If Codex hangs without touching files, stop it and relaunch.
- Claude reviews by reading only what changed (`git diff`), runs tests and real-world checks, and makes commits, pushes, and PRs.
- **Gemini**: fast model (`GEMINI_FAST_MODEL`, default `gemini-3.5-flash-lite`: ~1 s per call, 3/3 in the router test) for router, intent, and focus; stronger model (`GEMINI_MODEL`, default `gemini-flash-latest`) for the judge. Measured on 14/11 with the team's key.
- **Tokens:** don't read entire docs unless needed; use `rg` and partial reads.

## How to run
- Backend: `cd backend && uv sync && uv run uvicorn app:app --port 8000` Tests: `uv run pytest`.
- App: `cd app && npm install && npx expo start` (web: press `w`; in Expo Go, set `EXPO_PUBLIC_API_URL` to the PC's IP). The app has a mock mode if the backend does not respond.
- Everything together: backend on `:8000` and web app; the complete chat (text, audio, profile, recommendations with sources) is already on `main`.

## Technical rules
- **Secrets**: `CALA_API_KEY`, `NVIDIA_API_KEY` only in `backend/.env` (ignored by git; template in `backend/.env.example`). Never read, print, log, or put them in prompts or commits.
- **Cala**: new code queries Cala **through the canonicalizer** (`canonizador/`), never by sending the user's raw text directly: free text gives different answers for the same question (`docs/BENCHMARK-CANONIZER.md`). Endpoints: `knowledge/query` (rows), entities (data with sources and `is_lead`), `knowledge/search` (answer with sources, last resort). **16–60 s per call** and HTTP 429 after ~7 consecutive calls: disk cache (`backend/cache/`, ignored), few concurrent calls, and retries with a delay. Details in `docs/internal/CALA-CAMPOS.md` and `docs/internal/CALA-API.md`.
- **LLM**: `LLM_PROVIDER` = `gemini` (default if `GEMINI_API_KEY` is set) | `nvidia` | `codex` | `claude` (`backend/core/llm.py`). Keys only in `backend/.env`.
- **Transcription**: Gemini by default if `GEMINI_API_KEY` is set (one call for literal transcription and clean intent, with fallback to local faster-whisper, model `WHISPER_MODEL`, default `small`); otherwise whisper if installed, or `none`. `TRANSCRIPTION_PROVIDER` lets you choose `gemini` | `whisper` | `nvidia` | `none`. See `backend/chat/transcribe.py`.
- Do not create repos or deploy without the user's approval. Before calling something finished, run the app or tests and say what was verified.

## Documents
| Document | Contents |
|---|---|
| `docs/internal/PLAN-CALA-CENTRO.md` | The engine: message router, Cala queries, blocks, and distribution |
| `docs/API.md` | Backend ↔ app contract |
| `docs/internal/CALA-CAMPOS.md` | Official guide to Cala fields (entities, rounds, `is_lead`, Slush 2026) |
| `docs/internal/CALA-SKILL.md` | Official guide for an LLM to use Cala (query language) |
| `docs/internal/CALA-API.md` | Initial summary of the Cala API |
| `docs/internal/SPEC-canonizador.md` | Canonicalizer query design |
| `docs/BENCHMARK-CANONIZER.md` | Benchmark: 5 ways of asking Cala (0–1 of 9 consistent versus 9 of 9) |
| `docs/CALA-CONSISTENCY-REPORT.md` | Cala's consistency error, evidence, and recommendations for Cala |
| `docs/design/` | Stitch prototype (screens and design system) |
| `docs/internal/IDEAS-CALA.md` | Ideas evaluated when choosing the project |
| `docs/CODEX.md` | Record of what Codex built (Codex challenge) |

## Status and handoff (15/11, morning)
**Fabricio is leading.** `bau` handed him coordination; this section is the handoff.
- **On `main` (272 backend tests):** interface with calado branding, light and dark modes, email registration with a fixed role, events, real investors from the catalog, company profile that queries Cala only when opened, bubble assistant, text and voice context, redesigned favorites report in PDF, shared accounts, protection against Cala abuse, and call counter.
- **Deployment:** the app is on Vercel (project `junction-app`, repo `BauDahn/junction`, folder `app`, variable `EXPO_PUBLIC_API_URL`). The backend runs on `bau`'s laptop (port 8000), exposed through a quick Cloudflare tunnel; **the URL changes if the tunnel or laptop is restarted**, so the variable in Vercel must then be updated and redeployed.
- **Public backend configuration** (`bau`'s `backend/.env`, not in git): `CALA_REQUIRE_AUTH=1`, `TRUST_PROXY=1`, `ACCOUNTS_STORE=postgres` (accounts are stored in Aiven PostgreSQL), `ADMIN_TOKEN` set. Default daily Cala limit: 2000 calls.
- **Cala:** one catalog load used about 3,000 calls; it ended at 2,110 of 2,990 attendees (47 investors, 1,060 startups, pool of ~923 investors). **Do not relaunch long loads without the user's permission**; `python -m catalog run` stops at 150 calls unless `--max-calls` is provided.
- **Demo accounts:** `demo@calamatch.test`, `demo.raiser@calamatch.test`, `demo.investor@calamatch.test` (the team has the passwords privately).

## Pending
- [ ] Confirm that Vercel deployed the latest `main` and test end to end on the published site: sign in, open an investor, a company in their portfolio, 'Open dossier' from the profile, chat, and PDF (#53).
- [ ] Backend for real events: list, save per user, and feed by event (#119, contract in `docs/API.md`).
- [ ] Data: BSV Ventures combines two different funds (description from India, headquarters in Lithuania): review merging duplicates by name (#111).
- [ ] Raiser feed relevance: confidence 0.1 and poorly matched top results; use the portfolio companies' sector tags (#111).
- [ ] Interface: source links overflow the width on mobile in the profile; 'View dossier' is covered by the bubble (#107).
- [ ] PDF: the action plan box may split across two pages.
- [ ] Slides and video (#69).
- [ ] Questions for the Cala booth (credits per call, `is_lead`) and submission deadline.
