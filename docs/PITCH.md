# Pitch and demo script (issue #69)

Draft by `bau`, evening of 14/11. The spoken script is in English (the presentation is in Espoo); the team notes too. **Rule: on stage, say only what has been measured or is working.** Anything that depends on work in progress is marked **[CONFIRM]** and should be updated before rehearsal.

## 1. The idea in one sentence
> **Cala Match: the funding marketplace that finds the right investor or startup for you, and shows its sources for every claim.**

Short version for the Cala booth: *"We turned Cala's knowledge graph into a two-sided marketplace, and we fixed the one thing that stops agents from trusting it: the same question giving different answers."*

## 2. Three-minute pitch
**0:00 – The problem (30 s)**
"Raising money is a search problem. Founders spend weeks figuring out which investors actually back companies like theirs. Investors do the opposite: they scroll through hundreds of decks. Both sides are guessing, and the data to stop guessing exists, in Cala's knowledge graph. But it's hard to use."

**0:30 – The finding (40 s)**
"When we started, we hit a wall. We asked Cala the same question three ways: with accents, without, in another language. Out of nine questions, asking directly gave consistent answers at most once. Through MCP, even with Cala's official guide loaded, also at most once. Same question, different companies, different numbers. An agent can't build trust on that."
"So we built a canonizer. It turns any phrasing into one canonical query. 41 phrasings of 9 questions collapsed into 9 queries with identical answers. Nine out of nine."

**1:10 – The product (50 s)**
"On top of that, Cala Match. One app, two sides. Switch between *Raising* and *Investing*. The feed shows cards: each investor or startup with an affinity score from 0 to 100 and one line on why it matches. Tap a card and you get everything Cala knows: rounds, lead investors, portfolio, people. Every fact carries its source and date. Ask the chatbot anything, by text or voice. Upload your pitch deck or record a voice note, and your matches get better."

**2:00 – How it stays fast (30 s)**
"Cala is a graph, so we treat it like one. We pre-load all 2,990 Slush 2026 attendees into a shared Aiven Valkey cache. Exploring the local graph takes 0.13 milliseconds. Cala is only called at the edges. The language model never writes a number or a name: those come only from Cala, always with sources."

**2:30 – Closing (30 s)**
"Slush starts right after this hackathon. Tomorrow, a founder walking the floor can open this app and know in seconds who is worth a conversation, and why. Cala Match."

## 3. Live demo (2 minutes, 5 steps) — Raiser flow
| Step | What to do | What to say | Depends on |
|---|---|---|---|
| 1 | Sign up as a **Raiser** and add the demo startup's context | "I sign up as a raiser: a hotel-software startup raising a Series A." | New website **[CONFIRM]** |
| 2 | **Explore events**: save Slush 2026 | "One tap and it is in My events." | New website **[CONFIRM]** |
| 3 | **My events** → Slush 2026: recommended investors with an outreach letter; open one for a simple profile and how to secure the investment, with sources | "Ranked for me, with a draft of how to approach each one. Every fact has its source." | New website, feed and detail (**API already in main**) **[CONFIRM]** |
| 4 | **Assistant (bubble)**: ask by voice "Who led Amenitiz's Series B?" and ask about a company not in the catalog | "Same answer however I phrase it; and if it is not in the graph, it searches Cala live." | **Already works** (chat, canonizer, fallback, and search) |
| 5 | Tell the assistant: "We now raise 2 million in seed" and "I want to go to Slush 2026" | "It edits my context and works as a shortcut." | New website **[CONFIRM]** |
If time permits: **Profile** with favorites and context (10 seconds). From favorites, download the **PDF report**: the saved companies, what Cala knows about each with its source, and an action plan proposed by Gemini (labeled as such) **[CONFIRM]** until its PR is merged.

**Plan B** (if Cala or the network fails): reload the catalog from the backup file (`docs/ARCHITECTURE.md`, section 2, item 8) and demo with preloaded data. Have a video recording of the complete booking flow. **Steps 4 and 5 must work offline** thanks to the cache: warm it up beforehand.

## 4. Numbers we can share (measured on 14/11)
| Metric | Value | Source |
|---|---|---|
| Consistency without canonization | 0 out of 9, 0 out of 9, 1 out of 9, and 0 out of 9 (direct and through MCP, with and without Cala's guide) | `docs/BENCHMARK-CANONIZER.md` |
| Consistency with canonizer | 9 out of 9; 41 phrasings → 9 queries | `docs/CALA-CONSISTENCY-REPORT.md` |
| Repeated response from cache | 0.2–0.3 s versus 15–18 s the first time | `docs/CALA-CONSISTENCY-REPORT.md` |
| Complete Slush 2026 | 2,990 attendees fetched in 36 s | `docs/ARCHITECTURE.md` |
| Load a 185-node subgraph | ~14–18 s of actual Cala work (19 calls, ~1 s each) | README |
| Explore the subgraph locally | 0.13 ms (complete BFS) | README |
| Aiven Valkey | 200 batch reads in 31 ms | `docs/ARCHITECTURE.md` |
| Codex | 12 tasks, 24 min, and 8 M input tokens on the `bau` machine (plus the other machines) | `docs/CODEX.md` |

**Do not say** (not measured yet or does not exist): how many attendees are investors, the catalog's total processing time, affinity score quality, "the shortest path in all of Cala" (it is only the minimum within the explored graph), or anything about the pitch-deck verifier.

## 5. What to say about each challenge
**Cala (main): "Cala at the core"**
- Every card, table, and score comes from Cala and shows its source. The model does not write data.
- We use more than search: entities with typed relationships (`INVESTED_IN`, `is_lead`, dates), structured queries, and search as a last resort.
- We give something back to Cala: a report with evidence of the consistency error and a way to address it (`docs/CALA-CONSISTENCY-REPORT.md`).
- At the booth: ask about `is_lead`, the usage limit, the cost per call, and whether there will be events besides Slush 2026.

**Google Gemini: "why Gemini matters here"**
- It is the product's AI wherever language is involved: the router that separates queries, claims, and profile updates; the intent behind each question; audio; PDF context; and catalog sector and stage labels derived from Cala descriptions.
- Two models: a fast one (`gemini-3.5-flash-lite`, ~1 s per call, 3 out of 3 in the router test) for the live flow, and a stronger one for harder tasks. **[CONFIRM]** the figures when Gemini audio is finished (#50).
- Gemini normalizes text; Cala supplies the facts. That separation is the trust argument.

**Aiven: "Valkey as the product's memory"**
- A cache shared across machines and users, plus the graph: nodes and edges with sources, one graph that grows with use, and each user's subgraph as a view.
- It protects Cala's usage limit and makes previously queried information instant.
- Data: batch reads (200 in 31 ms), TTL everywhere, and a backup file that can be reloaded with one command.

**OpenAI Codex: "built with Codex, directed by Claude"**
- Claude designs, reviews, and tests; Codex writes the code; Gemini is the AI inside the product. Full log in `docs/CODEX.md` and `docs/PROCESS.md`.
- Each machine exports its `cx log` (tasks, model, minutes, tokens). bau, gabriel, and fabricio are included; adrian works with Antigravity and has no Codex log.

## 6. Questions we'll be asked
| Question | Answer |
|---|---|
| What if Cala does not have the data? | We try Cala's other tools and, if none has it, the card says "no data" and shows what was searched. Nothing is made up. |
| How is affinity calculated? | Six weighted signals (sector, stage, region, ticket size, recent activity, and graph proximity); each is explained with its data and source. A missing signal does not count as zero: confidence goes down. `docs/SPEC-GRAPH-AFFINITY.md`. **[CONFIRM]** during calibration. |
| Why not use Google? | Google gives documents; Cala gives relationships with sources, dates, and roles. A path like "this fund co-invested with your investor" does not come from a search engine. |
| Is the data up to date? | Each node stores when it was loaded, and the app shows it. Cala returns the date for each source. |
| Does it work beyond Slush? | The catalog is limited to Slush for the demo; chat and detail query Cala live for any company. |
| What about Cala's usage limit? | We measured around 1.4 sustained calls per second. That is why the catalog is precomputed and shared. |
| What would you do with more time? | Build an introduction path between people, alerts for new rounds, and affinity weights learned from real data. |

## 7. Checklist before presenting (owner: `bau`)
- [ ] Catalog loaded in Valkey and backup file exported.
- [ ] Demo profile (Stayflow) created and tested in both tabs.
- [ ] Steps 4 and 5 warmed in the cache; tested offline.
- [ ] Video of the complete booking flow (1 to 2 min).
- [ ] All **[CONFIRM]** items in this document resolved and timed rehearsal completed (3:00 pitch plus 2:00 demo).
- [ ] Photos or screenshots of the screens for the slides (taken from the new website running).
- [ ] Cala, Gemini, Aiven, and Codex submission deadline and forms confirmed (still pending).
- [ ] Fabricio and Adrian's Codex logs added to `docs/CODEX.md`.
