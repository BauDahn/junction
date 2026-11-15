# IDEAS-CALA: options for the Cala challenge

> IDEAS agent · Fri 2026-11-13 · Based on: RETOS.md (section 3) and CALA-VS-MARIADB.md. **These are proposals: the user makes the choice.**
> Jury criteria: real need 25% · execution 25% · originality 25% · use of Cala 25%. "Focus beats breadth." It must be usable the next day, at Slush.
> **[verify]** = depends on what data Cala actually has (ask at the booth: lead/follow, people and roles, dates, acquisitions, European coverage).

## Why Cala's graph instead of a web search (the common argument)
Web search returns **documents**; Cala provides **sourced structured relationships**: who invested in what, when, in what role, who works where. The ideas below depend on **queries over the graph**: multi-hop traversals, temporal aggregates, comparables, and paths between nodes. With Google, that means reading 200 pages by hand. Each idea explains which graph query makes it impossible without Cala.

---

## For founders

### 1. ★ First-customer radar ("First 10 customers")
- **User and pain point**: a seed-stage B2B founder who does not know whom to sell to first and is prospecting cold.
- **What it does**: lists companies in your segment that **have just raised money**, ranked by timing, fit, and a contact person, each with the round that serves as a signal.
- **Why Cala**: it needs the filter "round in the last N weeks × sector × size × country" + people at each company + investors in common. This is a graph join; doing it with web search would take hours.
- **Wow**: you type "I sell compliance for fintechs" and in 5 s see "12 fintechs that raised in the last 60 days, who makes the buying decision at each one, and which investor you have in common with them".
- **At Slush**: "these newly funded companies are at Slush: find them today". An exportable list for your phone.
- **Risk**: coverage of people and roles data **[verify]**. **Difficulty**: medium.

### 2. Who actually leads: who is leading rounds like yours today
- **User and pain point**: a founder about to raise a round who loses months with funds that only follow or no longer invest.
- **What it does**: ranks **active leads** for your profile (stage, sector, country), with the partner who made each deal and the evidence.
- **Why Cala**: it needs to distinguish **lead vs follow** and recency by investor and partner, which are aggregates over rounds. **[verify]** whether the lead role exists.
- **Wow**: shows "funds that would say yes to you but never lead", crossed out in red, alongside the 5 that led 3 similar rounds this year.
- **At Slush**: your list of 10 investors to track down at the event, with the partner's name.
- **Risk**: this is **the idea most teams will build**. **Difficulty**: low-medium.

### 3. ★ Investor pathways ("Investor pathways")
- **User and pain point**: a pre-seed founder choosing a seed investor without knowing **which doors they will open for Series A**.
- **What it does**: for each seed investor, shows **what happened next to its companies**: what percentage reached Series A, how long it took, and **which funds led that Series A**.
- **Why Cala**: it is a multi-hop traversal (seed investor → its companies → later rounds → leads of those rounds) with timing. A web search cannot provide it.
- **Wow**: a Sankey diagram: "companies that raised seed with fund X reached Series A in 41% of cases; 70% of them did so with these 3 funds." You compare two term sheets by the paths they open.
- **At Slush**: "which angel or fund should I close my seed with?" It helps decide between offers.
- **Risk**: requires a history of multiple rounds per company **[verify depth]**. **Difficulty**: medium.

### 4. Warm introduction path ("Warm intro path")
- **User and pain point**: a founder without a network; cold introductions do not work.
- **What it does**: finds the shortest and "warmest" path from your team (previous companies, current investors) to a target investor or customer.
- **Why Cala**: it is a shortest path in the graph of people, companies, and funds, with the source for each edge.
- **Wow**: "your CTO worked at Y with Z's partner: ask her for the introduction."
- **At Slush**: introductions to request that same night.
- **Risk**: depends on employment history data **[verify]** and is similar to LinkedIn. **Difficulty**: medium.

### 5. "Market thermometer": is it a good time to raise in my vertical?
- **User and pain point**: a founder who does not know whether their sector is "hot" or "cold" right now.
- **What it does**: shows the monthly flow of rounds in your vertical and country: count, size, funds entering, and funds that have stopped investing.
- **Why Cala**: time series over rounds, segmented by sector and investor.
- **Wow**: "3 funds that were active in your vertical have not invested at all in 9 months: do not waste time on them."
- **At Slush**: context for your pitch ("the market is growing X%").
- **Risk**: Dealroom/Crunchbase do this (not very original). **Difficulty**: low.

---

## For investors

### 6. ★ Deck fact-checker ("Deck fact-check")
- **User and pain point**: an angel investor or analyst who receives 50 decks at Slush and has no time to verify their claims ("backed by X", "ex-Google", "we raised €2M").
- **What it does**: you upload the deck PDF; the product extracts verifiable claims and checks them against Cala: ✔ confirmed, ⚠ differs, or ? no data, each with its source.
- **Why Cala**: it needs **structured, sourced data** to confirm or refute rounds, investors, and career histories. The web is noisy; Cala provides citable evidence.
- **Wow**: you upload a deck live and in 10 seconds see "Investor X in the seed round: ✔ (source). €2M round: ⚠, Cala records €1.2M".
- **At Slush**: **it is the perfect use case**: an angel receives a deck on their phone and checks it before the meeting.
- **Risk**: the tone of "accusing" the founder (better framed as "quick due diligence") and extracting claims from varied PDFs. **Difficulty**: medium.

### 7. Overdue-round radar ("Overdue for a round")
- **User and pain point**: a follow-on or secondary investor, or a corporate buyer, looking for companies that **should already have raised** based on what is typical for their stage and sector but have not (this could be an opportunity or a warning).
- **What it does**: compares time since the last round against the cohort median; flags companies past the 75th percentile.
- **Why Cala**: it needs cohorts (sector × stage × year) and the time between rounds, aggregated across the whole graph.
- **Wow**: "these 20 Series A startups have not raised in 30 months, while the median is 20: possible bridge rounds or acquisitions".
- **At Slush**: a list of "how is your runway?" conversations for secondary or M&A investors.
- **Risk**: a missing round in the data creates false positives. **Difficulty**: medium.

### 8. Syndicate builder ("Syndicate builder")
- **User and pain point**: a lead fund that needs to **fill out the round** with compatible co-investors.
- **What it does**: recommends co-investors based on your co-investment history and recent activity in the sector and stage.
- **Why Cala**: it is a co-investment graph (an investor–investor projection through shared rounds).
- **Wow**: an interactive graph: "these 4 funds co-invested with you 3 times and are active in climate tech".
- **At Slush**: whom to find to close the round.
- **Risk**: it is a niche (few users). **Difficulty**: low-medium.

### 9. Acquirer map ("Acquirer map")
- **User and pain point**: a founder or investor thinking about an exit: who buys companies like this?
- **What it does**: lists likely acquirers based on their past purchases of similar companies, shared investors, and sector overlap.
- **Why Cala**: it depends on Cala having **acquisitions** as edges **[verify, critical]**.
- **Wow**: "3 of the last 5 buyers of Nordic logistics startups share an investor with you".
- **Risk**: without acquisition data, the idea does not exist. **Difficulty**: medium.

---

## Off the shortlist

### 10. Student career radar ("Who's hiring?")
- **User and pain point**: students (like us) looking for internships or a first job at startups who do not know **which ones have fresh funding and are about to hire**.
- **What it does**: shows startups that raised in the last 90 days in your city and field, with round size, founders, and their background (for example, "founders ex-Supercell").
- **Why Cala**: recent round × city × sector × people.
- **Wow**: "Helsinki, ML, raised in the last 90 days: 14 startups. Here is each one's CTO."
- **At Slush**: Slush is full of student volunteers looking for work: it is an authentic story (we are the user).
- **Risk**: the jury may see it as outside the "founders or investors" audience. It can be reframed as "founders who need to hire meet talent". **Difficulty**: low.

### 11. Ecosystem pulse for public agencies ("Ecosystem pulse")
- **User and pain point**: agencies such as ACCIÓ (Catalonia) or Business Finland that want to measure what foreign capital enters their ecosystem and which funds to attract.
- **What it does**: compares capital flows between ecosystems (for example, Barcelona vs. Helsinki): which foreign funds invest in each, in what sectors, and the trends.
- **Why Cala**: aggregates by company geography × investor geography over time.
- **Wow**: "the 10 funds that invest in Helsinki and never in Barcelona: ACCIÓ, these are your targets for Slush".
- **At Slush**: the agencies are there with booths. **It fits the Catalan angle** and can be validated with Cala's founders.
- **Risk**: outside the main audience and a B2G niche. **Difficulty**: low-medium.

### 12. Slush schedule planner ("Slush planner")
- **User and pain point**: a founder with 2 days at Slush and thousands of attendees who does not know whom to prioritize.
- **What it does**: cross-references Slush's public list of speakers and exhibitors **[verify that it exists and can be used]** with Cala's graph and builds a prioritized schedule ("these 8 investors who speak or have a booth led rounds like yours").
- **Why Cala**: the value is in enriching and ranking according to the graph; the list alone is not useful.
- **Wow**: your personalized Slush schedule in 30 seconds.
- **At Slush**: **it is literally for Monday**.
- **Risk**: depends on Slush data and is temporary (useful for one event). It can be combined as "Slush mode" for ideas 1 or 2. **Difficulty**: low.

---

## Scoring table (1–5 per criterion; weighted total out of 5)

| # | Idea | Audience | Need | Execution (feasibility ~36h) | Originality | Use of Cala | **Total /5** | Expected competition |
|---|------|---------|-----------|--------------------------|--------------|-------------|--------------|----------------------|
| 1 | ★ First-customer radar | Founders | 5 | 4 | 4 | 5 | **4.50** | Medium-low |
| 3 | ★ Investor pathways | Founders | 4 | 4 | 5 | 5 | **4.50** | Low |
| 6 | ★ Deck fact-checker | Investors | 5 | 3 | 5 | 4 | **4.25** | Low |
| 2 | Who actually leads | Founders | 5 | 5 | 2 | 5 | 4.25 | **Very high** |
| 7 | Overdue rounds | Investors | 4 | 4 | 4 | 5 | 4.25 | Low |
| 12 | Slush planner | Founders | 4 | 4 | 4 | 3 | 3.75 | Medium |
| 4 | Warm introduction path | Founders | 4 | 3 | 3 | 4 | 3.50 | Medium |
| 8 | Syndicate builder | Investors | 3 | 4 | 3 | 4 | 3.50 | Low |
| 11 | Ecosystem pulse | Agencies | 3 | 4 | 4 | 4 | 3.75 | Very low |
| 10 | Career radar | Students | 3 | 5 | 3 | 4 | 3.75 | Medium |
| 9 | Acquirer map | Founders/inv. | 4 | 2 | 4 | 4 | 3.50 (if M&A data exists) | Low |
| 5 | Market thermometer | Founders | 3 | 5 | 1 | 4 | 3.25 | High |

These scores are my estimate. They depend heavily on the data coverage confirmed at the booth.

**My 3 favorites** (the user makes the decision):
1. **First-customer radar**: the most useful the next day, Cala is central to it, and it is an angle other teams are unlikely to take.
2. **Investor pathways**: the most original. It answers a question no one else can answer without a multi-hop graph.
3. **Deck fact-checker**: the most memorable demo and a perfect fit for Slush, but it has the greatest execution risk (parsing PDFs).

**Possible combinations**: 1 + "Slush mode" (12) · 3 + 2 (pathways with a ranking of active leads as a second tab) · 6 + 7 (a due diligence suite). Note: the jury asks for **focus**, so combine only if the second part is a small tab.

---

## Stitch (Google) in the workflow: is it useful?
**Yes, for the visuals, not the logic.** Stitch generates screens from a prompt or sketch and exports HTML/CSS or to Figma **[verify current export format]**.
- **Best ideas for it**: it matters most for ideas with a **visually striking "wow" UI**: the deck fact-checker (loading screen + ✔/⚠ cards), investor pathways (screen with a Sankey and investor comparison), and Slush planner (mobile-first schedule). It also helps with the table and company profile for the customer radar.
- **How it fits**: (1) on Saturday morning, generate 3–4 screens in Stitch (input, results, detail with sources, mobile version for Slush); (2) export them and have Claude Code turn them into components connected to the Cala API; (3) the same screens serve as **deck mockups** if any part is not fully functional in time.
- **Not recommended**: relying on Stitch for interactive charts (the Sankey and graphs need a charting library) or changing the generated UI at the last minute. The design needs to be settled early.
- **Estimated savings**: 2–4 hours of design and a more professional look, which adds to "execution".

## Questions for the Cala booth (to choose among the 3)
1. Do you distinguish **lead vs follow** in rounds? (key for ideas 2 and 3)
2. How deep is the round history for each company (seed → A → B)? (idea 3)
3. Are there **people with roles** at companies, and do you have their employment history? (ideas 1 and 4)
4. Do you have **acquisitions**? (idea 9)
5. How much coverage do you have for Europe and the Nordics in 2025–2026, and how fresh is it (how many days of delay)?
6. If we tell you about ideas 1, 3, and 6, which excites you most? **This validates the Catalan angle**: use it.
7. What are the API limits, MCP usage rules, and hackathon credits?

---

## Adjustment based on the API (Sat 2026-11-14, based on: CALA-API.md)

### What changes based on what we know about the API
- **In favor**: (a) `knowledge/search` already returns **answers with sources** (explainability + origins with URL), so cited verification comes "out of the box"; (b) `knowledge/query` returns **structured rows** that can be filtered and sorted (useful for ranking); (c) **Person with role** exists, as do relationships with `valid_since`/`valid_until` (employment history with dates); (d) **CorporateEvent (M&A)** exists, so the acquirer map is no longer hypothetical.
- **Against**: (a) there is **no Investor type** and **lead vs follow is not documented**; (b) call cost, latency, and limits are unknown (only a 429 is known), so the design needs **caching and few calls per screen**; (c) Nordic and Spanish coverage and data freshness are unknown.
- **Fit with the user's position** ("don't change Cala, show what it can do"): ideas that **put Cala in a concrete workflow** (preparing sales, reviewing a deck) stand out more than those requiring deep graph analysis, which the API may not support well.

### Review of the 12 ideas

| # | Idea | Status | Why | New total /5 (before) |
|---|------|--------|---------|------------------------|
| 1 | First-customer radar | ✅ **Improves** | It only needs recent rounds + sector + people with roles, all documented. `query` returns rows for ranking | **4.50** (4.50) |
| 6 | Deck fact-checker | ✅ **Improves a lot** | Nemotron VL reads the PDF and `search` with explainability returns cited evidence: this is exactly what Cala is built for | **4.50** (4.25) |
| 9 | Acquirer map | ⬆ **Moves up** | CorporateEvent (M&A) exists. Its coverage still needs checking | **3.75** (3.50) |
| 4 | Warm introduction path | ⬆ Moves up slightly | Person–company relationships with dates allow "worked together at X between these years" | 3.75 (3.50) |
| 10 | Career radar | = | Same as 1, but for an audience outside the focus | 3.75 |
| 12 | Slush planner | = | Cala provides enrichment, but Slush's attendee list is external | 3.75 |
| 11 | Ecosystem pulse | ⚠ Moves down slightly | It needs investor geography: without the Investor type, it must be inferred from Company | 3.50 (3.75) |
| 7 | Overdue rounds | ⚠ Risk | It depends on exact round dates (`year` in the rows may not be precise enough) and completeness | 3.75 (4.25) |
| 3 | Investor pathways | ⚠ **Risk** | Without lead/follow, it becomes "which funds appear in Series A rounds for this fund's companies" (participants, not leads). It loses precision but remains original | **3.75** (4.50) |
| 8 | Syndicate builder | ⚠ Risk | Co-investment via `investors=A AND B`: it works, but without the Investor type the graph is poorer | 3.25 (3.50) |
| 2 | Who actually leads | ❌ **High risk** | The whole idea depends on lead/follow. Without it, it becomes generic "active investors" (what everyone does) | **3.00** (4.25) |
| 5 | Market thermometer | = | Feasible, not very original | 3.25 |

### Updated top 3 (the user decides)
1. **★ Deck fact-checker**: moves up to #1. It is the most "Cala as-is" use (questions with cited answers) in a concrete context (the angel at Slush), with the most memorable demo and a justified VL model.
2. **★ First-customer radar**: the strongest on data and useful the next day.
3. **★ Acquirer map** (replaces investor pathways **if** the booth confirms good CorporateEvent coverage). Otherwise, use **investor pathways in a "participants" version**.

### Specific queries and Nemotron's role

#### 1. Deck fact-checker
**Nemotron (VL)**: reads the PDF/images of the deck → extracts **verifiable claims** as a structured list (company, founders, past rounds, named investors, customers or logos, traction metrics) → generates one query per claim → finally classifies each as ✔ confirmed / ⚠ differs / ? no data, with an explanation and source. **Cala**: the cited source of truth.
- `entities?name=Acme Robotics&entity_types=Company` → id → `entities/{id}` with round and people relationships (one call per profile).
- `knowledge/query`: `startups.name=Acme Robotics.funding_rounds return(round_type, funding_amount, year, investors)`
- `knowledge/search`: "Did Lifeline Ventures invest in Acme Robotics? In which round and when?" (with explainability → source URL)
- `knowledge/search`: "Did Jane Doe previously work at Google, and in what role and years?"
- `knowledge/search`: "Is Kesko a customer or partner of Acme Robotics?" (deck customer logos)
- **Wow**: the PDF on the left with each claim highlighted; on the right, ✔/⚠/? cards with a link to the source.

#### 2. First-customer radar
**Nemotron**: turns the product description ("compliance for fintechs with 20–200 people in Northern Europe") into filters (sector, country, size, stage) → builds the queries → **ranks** rows by timing, fit, and access → writes a one-line "why now" and an initial outreach message for each company. **Cala**: company rows with recent rounds and people with roles.
- `knowledge/query`: `startups.industry=Fintech.location=Finland.funding>1M order_by=funding_date limit=50 return(company, round_type, funding_amount, year, investors)`. Repeat for Sweden, Norway, and Denmark, or in natural language: "Fintech startups in the Nordics that raised a funding round in the last 3 months".
- `knowledge/query`: `people.role=Head of Compliance.company.name=<empresa>` (and CFO or COO as fallback) → the person who makes the buying decision.
- `knowledge/search`: "Which investors does <mi startup> share with <empresa>?" or `investors=<inv1> AND <inv2>` → a shared introduction.
- **Wow**: 5 seconds from product description to "12 companies, the decision-maker, and a shared introduction", each with its round cited.

#### 3a. Acquirer map (if M&A data exists)
**Nemotron**: defines "similar companies" based on the description, groups buyers, and explains the pattern ("buys Nordic logistics startups at Series A stage"). **Cala**: CorporateEvents with buyer, target, and date.
- `knowledge/search`: "Acquisitions of Nordic logistics software startups since 2020: acquirer, target, date"
- `entities/{id_comprador}` → outgoing CorporateEvent relationships (all its acquisitions).
- `knowledge/query`: `investors=<founder's investor> AND <buyer>` → a path of access.

#### 3b. Investor pathways in a "participants" version (alternative)
- `knowledge/query`: `startups.investors=Lifeline Ventures.round_type=Seed return(company, year)` → the cohort.
- For each company: `knowledge/query`: `startups.name=<empresa>.funding_rounds.round_type=Series A return(investors, year)`
- **Nemotron**: aggregates, calculates percentages and timing, and writes the comparison between two funds. **Cost**: 1 + N calls per fund → caching is needed.

### Questions for the Cala booth (ordered by how much they affect the decision)
1. **How many calls and credits do we have, and what is the latency?** This determines whether ideas with "1 + N queries" (pathways, radar) are viable live.
2. **What coverage do you have for 2025–2026 rounds in the Nordics and Spain, and how fresh is it?** If coverage is weak, the customer radar and fact-checker will look empty with local startups (mitigation: use known EU or US startups).
3. **How complete is CorporateEvent (M&A) data?** This decides between the acquirer map and investor pathways for third place.
4. **Can a round's lead be distinguished (in any FundingRound property or relationship)?** If so, "who actually leads" and investor pathways return to around 4.5.
5. **Are round dates exact (day/month) or only the year?** This affects "raised N weeks ago" (radar) and overdue rounds.
6. **Are people with roles available for mid-sized companies, not just founders or the CEO?** This affects "the decision-maker" in the radar.
7. **Of the fact-checker / radar / acquirer ideas, which excites you most?** This is validation with the founders (the Catalan angle).
