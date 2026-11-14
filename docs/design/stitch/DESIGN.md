---
name: Cala Match Design System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#464553'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#777584'
  outline-variant: '#c8c4d5'
  surface-tint: '#544fc0'
  primary: '#1f108e'
  on-primary: '#ffffff'
  primary-container: '#3730a3'
  on-primary-container: '#a9a7ff'
  inverse-primary: '#c3c0ff'
  secondary: '#006c49'
  on-secondary: '#ffffff'
  secondary-container: '#6cf8bb'
  on-secondary-container: '#00714d'
  tertiary: '#422700'
  on-tertiary: '#ffffff'
  tertiary-container: '#603b00'
  on-tertiary-container: '#f49d09'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e2dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#0f0069'
  on-primary-fixed-variant: '#3b35a7'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffddb8'
  tertiary-fixed-dim: '#ffb95f'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: '700'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 30px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.015em
  headline-lg-mobile:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-md:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0em
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  metric-display:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  metric-table:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system powers a high-velocity, dual-sided venture marketplace connecting early-to-growth stage founders with institutional and angel capital. It must inspire absolute fiduciary trust while delivering the frictionless speed of modern consumer matching platforms. 

The aesthetic is **Precision Corporate Modern**: confident, airy, restrained, and data-dense without visual clutter. It prioritizes clarity over ornamentation, balancing deep institutional authority with dynamic marketplace momentum. Founders experience an interface that feels serious, validating, and empowering; investors navigate an environment optimized for deal triage, rigorous signal-to-noise ratio, and rapid cognitive parsing.

Key design principles:
- **Structural Legibility:** Generous negative space balances high-density cap-table and valuation metrics.
- **Bi-Modal Fluidity:** Unambiguous visual anchors signify dynamic contextual switching between "Raising" (founder cockpit) and "Investing" (allocator pipeline).
- **Quantified Trust:** Visual badges, data attribution pills ("Source: Cala"), and transparent affinity scoring establish immediate credibility.

## Colors

The palette is engineered around an institutional, deep indigo foundation paired with a refined cool-slate neutral scale and calibrated semantic feedback tokens.

- **Primary (`#3730A3` / Indigo-800):** Anchors brand authority, primary calls-to-action, active segmented toggles, and primary navigation focus states. Represents calculated execution and institutional confidence.
- **Secondary (`#10B981` / Emerald-500):** Designates top-tier affinity matches (>80%), positive growth deltas, and verified deployment actions. Paired with an ultra-light tint (`#ECFDF5` / Emerald-50) and deep forest text (`#047857` / Emerald-700).
- **Tertiary (`#F59E0B` / Amber-500):** Flags moderate affinity matches (60–80%), syndication holds, and pending diligence. Paired with soft tint (`#FFFBEB` / Amber-50) and rich amber text (`#B45309` / Amber-700).
- **Neutral (`#64748B` / Slate-500):** Anchors secondary metadata, subtle borders (`#E2E8F0` / Slate-200), background tiers (`#F8FAFC` to `#FFFFFF`), and low affinity matches (<60%) via muted badges (`#F1F5F9` background with `#475569` text).
- **Surface Foundations:** Canvas relies on crisp `#FFFFFF` for interactive cards, layering over a subtle `#F8FAFC` (Slate-50) ambient canvas wash.

## Typography

Inter serves as the primary typographic driver across all tiers, chosen for its micro-structural legibility and neutral, systematic tone.

- **Tabular Figures & Metrics:** For all numerical representations—including run rates, round sizes, ownership percentages, valuations, and affinity scores—the OpenType feature `tnum` (tabular numbers) and `cv05` must be forced. This preserves vertical column alignment in deal sheets and comparison grids.
- **Hierarchy Enforcement:** Headline tracking tightens progressively (`-0.02em` to `-0.005em`) to retain punchiness at scale, while micro labels (`label-sm`) leverage slight positive tracking (`+0.04em`) with uppercase transforms to ensure legibility on card headers and verification tags.

## Layout & Spacing

The layout model is anchored strictly on an 8px spatial rhythm, ensuring mathematical predictability across micro and macro layouts.

- **Desktop (1024px+):** 12-column responsive fluid grid constrained to a 1280px max-width container, 24px (`1.5rem`) gutters, and 32px (`2rem`) outer margins.
- **Tablet (768px - 1023px):** 8-column layout, 16px (`1rem`) gutters, and 24px (`1.5rem`) outer margins.
- **Mobile (<768px):** 4-column layout with 16px (`1rem`) gutters and 16px (`1rem`) outer canvas margins. Full-width swipe cards deduct outer margin space.
- **Vertical Rhythm:** Components stack using strictly mapped spacing tokens: internal micro gaps (`space-xs` = 4px, `space-sm` = 8px), standard intra-card padding (`space-md` = 16px, `space-lg` = 24px), and inter-card orchestration (`space-xl` = 32px).

## Elevation & Depth

Visual hierarchy leverages a hybrid model of **tonal layers** bolstered by **ambient, diffused shadows** and **crisp 1px borders**. Hard drop shadows are strictly prohibited; depth must convey calm institutional precision.

- **Level 0 (Flat/Base):** Pure `#F8FAFC` canvas. No shadow.
- **Level 1 (Default Card State):** Pure `#FFFFFF` surface bounded by a continuous 1px `#E2E8F0` border. Shadow: `0px 1px 3px 0px rgba(15, 23, 42, 0.04), 0px 1px 2px -1px rgba(15, 23, 42, 0.02)`.
- **Level 2 (Hover & Active Match Cards):** Pure `#FFFFFF` surface bounded by 1px `#CBD5E1`. Shadow: `0px 8px 16px -4px rgba(15, 23, 42, 0.06), 0px 4px 6px -2px rgba(15, 23, 42, 0.03)`.
- **Level 3 (Overlays & Modals):** Pure `#FFFFFF` surface bounded by 1px `#CBD5E1`. Shadow: `0px 20px 24px -4px rgba(15, 23, 42, 0.08), 0px 8px 8px -4px rgba(15, 23, 42, 0.03)`.
- **Level 4 (Floating Mobile Navigation Bar):** Pure `#FFFFFF` surface with `backdrop-filter: blur(12px)` and 85% opacity, bounded by a 1px `#E2E8F0` top edge border. Ambient shadow: `0px -4px 12px rgba(15, 23, 42, 0.04)`.

## Shapes

The geometric signature balances modern consumer friendliness with institutional restraint using a base 16px rounded structure for structural framing.

- **Cards & Surfaces (`rounded-lg`):** Strict 16px (`1rem`) border radius. This geometry defines all marketplace deal cards, analytics panels, and contextual modals.
- **Interactive Controls (`base`):** Form inputs, standard buttons, and alert modules adopt an 8px (`0.5rem`) radius.
- **Micro Tags & Trust Badges (`pill`):** Affinity score indicators, source citations ("Source: Cala"), status chips, and the primary dual-mode segment toggle adopt a fully circular / pill curvature (`9999px`).

## Components

### Mode Switcher (Segmented Pill Toggle)
- **Container:** Rounded pill container with `#F1F5F9` background, 4px internal padding, and an inline layout containing two options: "Raising" and "Investing".
- **States:** Active option features a full-pill white background (`#FFFFFF`), 1px subtle border (`#E2E8F0`), deep `#3730A3` text (`label-md`), and a micro ambient shadow. Inactive state features `#64748B` text with transparent background.

### Deal Cards
- **Geometry & Border:** Strict 16px corner radius, `#FFFFFF` background, 1px `#E2E8F0` border.
- **Padding:** 24px internal padding on desktop, 16px on mobile.
- **Header Structure:** Top row reserves the left for the startup/investor avatar with verified lockup, and the right for the prominent Affinity Badge.
- **Metrics Grid:** Interior 2-column or 3-column metric display with subtle `#F8FAFC` recessed backgrounds, 8px rounded corners, tabular figures for round size, ARR, and valuation multiples.

### Affinity Badges
- **Pill Badges:** 24px total height, 8px horizontal padding, pill border radius, bold tabular text (`label-sm`).
  - **High (>80%):** `#ECFDF5` background, `#047857` text, left dot indicator in `#10B981`.
  - **Medium (60–80%):** `#FFFBEB` background, `#B45309` text, left dot indicator in `#F59E0B`.
  - **Low (<60%):** `#F1F5F9` background, `#475569` text, left dot indicator in `#94A3B8`.

### Trust Elements ("Source: Cala" Pills)
- Micro pill badge: 20px height, 6px horizontal padding.
- Neutral light styling: `#F8FAFC` background, 1px `#E2E8F0` border, `#64748B` font (`label-sm`), prepended with an official monoline shield or verification node icon.

### Buttons
- **Primary:** `#3730A3` background, `#FFFFFF` text, 8px radius, height: 40px (desktop), 44px (touch mobile). Hover state: `#312E81`.
- **Secondary / Outline:** `#FFFFFF` background, 1px `#CBD5E1` border, `#1E293B` text. Hover state: `#F8FAFC` background with `#0F172A` text.
- **Destructive:** `#FEF2F2` background, 1px `#FEE2E2` border, `#B91C1C` text.

### Input Fields
- Height 40px, 8px radius, `#FFFFFF` background, 1px `#CBD5E1` border.
- Focus: 1px `#3730A3` border with `0 0 0 3px rgba(55, 48, 163, 0.12)` halo ring.
- Placeholder: `#94A3B8`. Label: `#334155` (`label-md`).

### Mobile Bottom Navigation Bar
- Fixed bottom container: 64px height + device safe-area inset, `#FFFFFF` with 90% opacity and 12px blur backdrop.
- Fixed 4-tab symmetric layout: **Feed**, **Chat**, **Context**, **Profile**.
- Icons: 20px monoline SVG. Active state: `#3730A3` icon and text (`label-sm`). Inactive state: `#64748B`.
- Active notification pip: 6px absolute dot in `#10B981` positioned top-right of the icon.