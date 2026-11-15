# Brand References — Cala Match

Visual and structural benchmarks for **Cala Match** (B2B Event & Deal-Flow), aligned with its Anti-AI-slop aesthetic:
- **Surfaces & Neutrals**: Slate `#f8f9fc` (canvas) / `#0f172a` (ink)
- **Accent**: Indigo `#3730A3`
- **Geometry**: `1px` hairline borders, zero decorative gradients or drop shadows
- **Typography**: `tabular-nums` for metrics/dates/amounts, sober & factual English copy

## Comparative Index (5 Host-Verified Live DOM References)

| # | Brand | Exact URL | Live Typography | Live Palette & CSS Tokens | CTA & Geometry | Verified `img.src` Assets | Fit with Cala Match |
|---|---|---|---|---|---|---|---|
| 1 | **Attio** | `https://attio.com` | `Inter` / `Inter Tight` (`clamp(64px, 16px + 5.333svh, 80px)`) | `--gray1`..`--gray12` neutral scale | CTA `#18181b`, `radius: 10px` | `_next/image`: `granola-cover...webp`, `attio-app-layout-sidebar-header-avatar...png` | Deal-flow pipelines, neutral gray scale, restrained CTA geometry |
| 2 | **Mercury** | `https://mercury.com` | `Arcadia Sans` / `arcadia-display-3` | `#0B0C0E`, `--surface-primary: #4361EE` | CTA `--surface-primary: #4361EE`, `radius: 9999px` | `hero_start_frame_sm...jpg`, `hero_end_frame_sm...jpg` | Indigo-adjacent `#4361EE` restraint, `tabular-nums` financial legibility |
| 3 | **Midday** | `https://midday.ai` | `hedvig_letters_sans` / `hedvig_letters_serif` | `--background: 0 0% 5%` (`#0c0c0c`), `--primary: 0 0% 98%` (`#ffffff`), `--border: 0 0% 15%` | High-contrast monochrome surfaces, `1px` hairline borders | `dashboard-dark.svg`, `accounting-dark.png`, `gmail.svg` | Strict `1px` hairline borders, editorial sans/serif pairing, ledger density |
| 4 | **Twenty** | `https://twenty.com` | `Instrument Serif` + system sans | `#161616` | Beveled button with `clip-path` | `https://twenty.com/images/shared/companies/logos/anthropic.webp`, `linkedin.webp`, `dario-amodei.webp`, `reid-hoffman.webp` | Dense B2B entity grids (`Companies`, `Opportunities`), crisp `1px` cells |
| 5 | **Luma** | `https://luma.com` | System/UI sans | `#0F0F11`, `--primary-color: #2e66ff`, `--cranberry-content: #f43f5e` | `--city-column: min(12.75rem, calc((100vw - 3rem) / 3))` | `images.lumacdn.com/...` (Junction Afterparty, Techstars Slush Pullakahvit, PRE-SLUSH 2026 Helsinki) | Direct B2B/Slush/Junction event discovery, host/attendee cards, frictionless RSVP |

## Extracted Artifacts & Captures

- [captured-styles.css](captured-styles.css) — Unified `:root` host-verified live DOM tokens from all 5 sites + direct **Cala Match** token mapping (`#3730A3`, `#f8f9fc`, `#0f172a`, `1px` borders, `box-shadow: none`).
- [luma-latest.png](captures/luma-latest.png) — Host-verified browser screenshot capture (`final_step_22.png`) of `https://luma.com`.
- [attio-tokens.css](attio-tokens.css) — Extended Attio typography & card tokens.
- [mercury-tokens.css](mercury-tokens.css) — Extended Mercury dual-mode tokens & layout gutters.
- [midday-ledger-pattern.html](midday-ledger-pattern.html) — 4-column `tabular-nums` ledger HTML/CSS pattern.
- [twenty-grid-pattern.html](twenty-grid-pattern.html) — CRM entity table HTML/CSS pattern.
- [luma-event-pattern.md](luma-event-pattern.md) — `https://luma.com` event card HTML/CSS snippet and Helsinki/Slush/Junction reference notes.
