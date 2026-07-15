# PRD: Financial Planner (fplan_v2)

- **Status:** active · **Updated:** 2026-07-14

## Vision
A personal financial planning tool that projects long-term net worth and cash flow from a
household's assets, loans, income and expenses — fast enough to explore what-ifs
interactively. The owner edits a portfolio (assets, loans, revenue streams, cash flows,
dated historical measurements) and immediately sees a 30-year net-worth and cash-flow
projection update, so decisions (buy/sell, refinance, change a lease) can be reasoned
about with numbers instead of guesswork.

## Problem
Household financial decisions span decades and interact (a loan against an appreciating
asset, a lease with annual steps, a pension that annuitizes). Spreadsheets go stale, don't
model Israeli instruments (prime/CPI-pegged loans, stepped rent), and can't be explored
interactively. This tool holds the whole household picture in one model, anchors it to
real dated measurements, and recomputes the full projection fast enough to feel live.

## Users / Personas
- **Owner (Sergei)** — single power user. Maintains the portfolio, reads the projection and
  dashboard, runs what-if scenarios. Wants correctness first, then speed.
- **Household** — the projection covers a household's combined finances. Not multi-tenant
  SaaS; sharing with other users is a future add-on (Portfolio already has `user_id`).

## Features
| Feature | State | Notes |
|---|---|---|
| 30-year net-worth & cash-flow projection | Shipped | `compute_projection`, monthly steps, cached on change |
| Assets / loans / revenue streams / cash flows CRUD | Shipped | FastAPI routes + SQLAlchemy repositories |
| Dated historical measurements (anchoring) | Shipped | `HistoricalMeasurement`, shifts applied in projection |
| Multi-portfolio scoping + export/import | Shipped | Active portfolio via `X-Portfolio-Id` header |
| Scenarios (what-if actions layered on base) | Shipped | `Scenario` / `ScenarioResult`, scenario cache |
| Projection caching on portfolio_version bump | Shipped | `ProjectionCache`, SHA256 cache key |
| Fast cold recompute (<0.4s) | Next | Vectorize per-date aggregation (M1 item 1) |
| No chart blank on refetch | Next | `placeholderData: keepPreviousData` (M1 item 2) |
| Dashboard tile agrees with projection | Next | Include standalone cash flows; current-year rent (M1 items 3–5) |

(States: Shipped · Next · Future)

## Non-Functional Requirements
- **Performance:** cold projection recompute < 0.4s (currently ~1.44s of a ~1.9s cold
  request); warm (cached) reads are already sub-100ms. Editing must feel instant.
- **Correctness:** projection math is golden-master; the speed refactor (M1 item 1) must be
  byte-identical. Dashboard/summary numbers must agree with the projection.
- **Reliability:** single-user local mode when `CLERK_SECRET_KEY` is empty; Clerk in prod.
- **Deploy:** manual (`vercel --prod` for frontend; Neon for prod DB).

## Success Criteria
- After an edit, the projection updates in < 0.4s cold recompute and the chart never blanks.
- Dashboard summary tile matches the projection's near-term net cash flow for portfolio 1.
- Stepped-rent cash flow equals the contracted flat amount within each lease year.
- `pytest fplan_v2/tests -q` model suite green; projection golden test passes.

## Constraints
- Stack locked: Python 3.12 FastAPI + core projection engine + SQLAlchemy/Postgres, React 18
  + Vite + TypeScript + shadcn/ui frontend.
- Preserve golden-master projection semantics — item 1 is speed-only, zero output change.
- Manual Vercel/Neon deploy; no CI-gated pipeline.
- `test_projections_integration.py` needs a seeded DB and fails in dev — treat as
  environmental, not a regression. `test_models_basic.py` is the reliable unit suite.

## Non-Goals (M1)
- No change to projection math/results from item 1 (speed only). Items 3–5 change results
  intentionally and carry their own tests.
- Not rewriting the projection engine or its golden-master semantics.
- Not the Neon prod push / Vercel deploy (tracked separately, done manually).
- No new user-facing features; no multi-tenant / SaaS work.

## Open Questions
- `yearly_fee` inconsistency, prime-holds-flat, and stale rate CSVs (see project memory
  `engine-followups`) — out of M1 scope, revisit after the perf/correctness pass.
- Pension annuitization modeling decision (see project memory `config-loading`).
