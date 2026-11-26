# Design System

Dark-first command-centre aesthetic: dense, quiet, numerically precise. No light theme is implemented (stated in Settings).

## Tokens (`src/styles/index.css`, surfaced in `tailwind.config.ts`)

Colours are RGB-channel CSS variables so `bg-accent/10` alpha utilities work.

| Role | Token | Value (rgb) |
| --- | --- | --- |
| Page background | `canvas` | 7 11 24 |
| Sidebar | `sidebar` | 10 16 32 |
| Surfaces (layered) | `surface` / `surface-raised` / `surface-overlay` | 14 21 38 / 19 28 49 / 27 38 63 |
| Borders | `line` / `line-strong` | 33 45 72 / 52 68 102 |
| Text | `ink` / `ink-muted` / `ink-faint` | 230 236 246 / 139 153 179 / 95 109 136 |
| Primary accent | `accent` (electric cyan) | 34 211 238 |
| Secondary accent | `brand` (blue) | 59 130 246 |
| Success / Warning / Danger | `success` / `warning` / `danger` | 74 190 134 / 240 172 40 / 240 90 90 |
| Simulation | `simulation` (violet) | 167 139 250 — **reserved for simulation-origin data only** |

Status colours are never the only signal: badges carry text, bars carry numbers.

## Type, spacing, shape

- Inter (UI) + JetBrains Mono (identifiers, references). Tabular figures (`.num`) wherever numbers are compared.
- Scale: 11 / 12 / 13 / 14 px body range; page title 20 px; KPI 24 px. Eyebrow labels 11 px uppercase.
- Spacing on Tailwind's 4 px grid; panels use 16 px padding, 12–16 px gaps.
- Radius 4 px (6–8 px for panels/overlays). Elevation: one subtle inset + shadow for panels, a stronger shadow for overlays only.
- Motion: sidebar width, drawer slide, command palette fade (≤180 ms). `prefers-reduced-motion` disables transitions.

## Components

- **Button** — `primary` (one per view), `secondary`, `ghost`, `danger`; `sm`/`md`; `loading` state.
- **Badge / StatusBadge / OriginBadge** — status maps known values to tones, unknown values stay neutral. OriginBadge shows Real / Imported / Manual / Simulation (flask icon) / "Origin unknown".
- **Panel (+Header/Body)**, **PageHeader**, **DetailList** (null → `—`).
- **StatTile** — value | loading | error | unavailable.
- **DataTable / ResourceTable** — sticky-less compact table, sortable headers (`aria-sort`), keyboard-activatable rows, mobile column hiding, built-in skeleton/empty/error/awaiting states, search + filters + pagination.
- **Charts** — `TimeSeriesChart`, `BreakdownBar`, themed through `chartTheme.ts`; always inside `ChartPanel`, which owns state handling and shows reporting period + origin.
- **States** — `EmptyState`, `ErrorState`, `UnavailableState`, `AwaitingContractState`.
- **Form** — `FormField` wires label, hint, error, `aria-invalid`, `aria-describedby`.

## Data-origin conventions

1. Every table/detail with records shows an origin marker.
2. Simulation data uses the violet token and a flask icon, is confined to the Concurrency Lab, and carries a persistent banner.
3. Imported data is "Imported" and shown as user-supplied/unverified on import detail.
4. A missing origin is "Origin unknown" — never assumed real.

## Accessibility

Skip link, landmark navigation, `aria-current` breadcrumbs, focus-visible ring, labelled icon buttons, `role=status/alert` on states, dialog semantics + Escape on palette/popovers, keyboard sidebar/table/palette, WCAG-minded contrast (ink on canvas ≈ 15:1; `ink-faint` is for non-essential metadata only). Not yet audited with a screen reader or automated tool.
