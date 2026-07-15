# Architecture: Financial Planner (fplan_v2)

- **Status:** active · **Updated:** 2026-07-14

## System Overview
A two-tier app: a Python 3.12 **FastAPI** backend serving a REST API over a **Postgres**
database (SQLAlchemy ORM), and a **React 18 + Vite + TypeScript** SPA (shadcn/ui, Tailwind,
TanStack Query, Recharts). The heart is the **core projection engine** (`fplan_v2/core`):
pure business models for assets/loans/revenue streams plus `compute_projection`, which walks
~360 monthly steps to produce a 30-year net-worth and cash-flow projection. Results are
cached in `ProjectionCache` keyed by a portfolio version that bumps on every mutation, so
warm reads are cheap and only edits trigger a recompute.

```
React SPA (Vite :3034) ──/api,/health──▶ FastAPI (:8034)
  TanStack Query          proxy            ├─ api/routes/*      (CRUD + projections)
  Recharts                                 ├─ db/repositories/* (SQLAlchemy, version bump)
  X-Portfolio-Id header ───────────────▶   ├─ core/engine       (compute_projection)
                                           └─ core/models       (Asset/Loan/RevenueStream)
                                                  │
                                           Postgres (local dev / Neon prod)
                                           ProjectionCache keyed by portfolio_version
```

## Tech Stack
| Layer | Choice | Why |
|---|---|---|
| Language/Runtime | Python 3.12 (backend), TypeScript (frontend) | Numeric modeling in Python; typed SPA |
| Backend framework | FastAPI + Uvicorn | Async REST, OpenAPI, dependency injection |
| Projection engine | `fplan_v2/core` (pandas / numpy-financial) | Pure, testable financial models |
| Data | Postgres via SQLAlchemy ORM | JSONB config, FK integrity, connection pooling |
| Frontend | React 18 + Vite + shadcn/ui + Tailwind | Fast dev, component library, utility CSS |
| Data fetching | TanStack Query | Cache, staleTime, invalidation on edit |
| Charts | Recharts | Net-worth / cash-flow / amortization charts |
| Auth | Clerk (prod) / single-user local mode | `CLERK_SECRET_KEY` empty ⇒ user id 1 |
| Infra/Deploy | Vercel (frontend) + Neon (prod Postgres), manual | `vercel --prod`; no CI gate |

## Key Decisions (ADR index)
> One line per decision, linking to its full ADR in `docs/decisions/`. The ADR holds
> context, alternatives, and consequences. Supersede ADRs rather than rewriting history.
- [ADR-0001](decisions/adr-0001-stack-and-structure.md) — FastAPI + core engine + SQLAlchemy/Postgres + React/Vite; projections cached on a portfolio_version bump (2026-07-14, accepted)
- [ADR-0002](decisions/adr-0002-projection-performance-strategy.md) — Optimize projection speed by vectorizing per-date aggregation, not by changing the cache/invalidation model (2026-07-14, accepted)

## File / Module Structure
- `fplan_v2/api/main.py` — FastAPI app, CORS, routers, health checks.
- `fplan_v2/api/routes/projections.py` — `compute_projection` (hot path), cache read/store,
  `_build_cash_flow_breakdown`, `_apply_cash_conversions`, per-date series builders.
- `fplan_v2/api/routes/{assets,loans,revenue_streams,cash_flows,historical_measurements,scenarios,portfolios,demo}.py` — CRUD + feature endpoints.
- `fplan_v2/api/schemas.py` — Pydantic request/response models (`ProjectionResponse` etc.).
- `fplan_v2/api/auth.py` — Clerk verification / single-user fallback.
- `fplan_v2/core/models/{asset,loan,revenue_stream}.py` — pure business models (growth, amortization).
- `fplan_v2/core/engine/{scenario_engine,index_tracker}.py` — scenario layering, prime/CPI index lookup.
- `fplan_v2/db/models.py` — SQLAlchemy ORM (all tables).
- `fplan_v2/db/repositories/base.py` — `BaseRepository` (version bump on write), `get_portfolio_summary_optimized`.
- `fplan_v2/db/repositories/*_repository.py` — per-entity data access.
- `fplan_v2/db/connection.py` — engine, session, pooling.
- `fplan_v2/frontend/src/hooks/use-projections.ts` — `useProjectionQuery` (staleTime 5min, invalidates `['projection']` on edit).
- `fplan_v2/frontend/src/features/projections/*` — charts (net-worth, cash-flow, amortization) + scenario builder.
- `fplan_v2/frontend/src/features/dashboard/dashboard-page.tsx` — summary tiles.
- `fplan_v2/frontend/src/api/*` — typed API clients (send `X-Portfolio-Id`).
- `fplan_v2/tests/` — pytest suites (see standards for the reliable vs environmental split).

## Data Model
Owned tree, all portfolio-scoped:
- **User** `1—N` **Portfolio**; `portfolio_version` on both bumps on any write to invalidate cache.
- **Portfolio** `1—N` **Asset / Loan / RevenueStream / CashFlow / HistoricalMeasurement / Scenario**.
- **Asset** types: `real_estate | stock | pension | cash`; optional loans as collateral.
- **Loan** types: `fixed | prime_pegged | cpi_pegged | variable`; optional `collateral_asset_id`.
- **RevenueStream** types: `rent | dividend | pension | salary`; `amount`, `growth_rate`,
  `period`, optional `asset_id` — the stepped-rent correctness work lives here.
- **CashFlow** `deposit | withdrawal` over a date range; `from_own_capital` flag distinguishes
  transfers from external in/out — the summary-tile correctness work depends on this.
- **HistoricalMeasurement** — dated `actual_value` per `(entity_type, entity_id)`; anchors the
  projection via measurement shifts.
- **ProjectionCache** — `cache_key = SHA256(portfolio_id:portfolio_version:start:end:as_of)`,
  unique per `(user_id, cache_key)`; **ScenarioCache** mirrors this per scenario.
- **IndexData** (`prime`, `cpi`) — rate series consumed by `IndexTracker` for pegged loans.
- **Key invariant:** every mutation bumps `portfolio_version`, so a stale cache key can never
  be read; the projection output for a given key is deterministic (golden-master).

## External Dependencies
- **Neon** — serverless Postgres (prod); local Postgres for dev (`fplan_v2` DB).
- **Clerk** — auth in prod; bypassed when `CLERK_SECRET_KEY` is empty.
- **Vercel** — frontend hosting + serverless API (manual deploy).
- **Python:** FastAPI, Uvicorn, SQLAlchemy, pandas, numpy / numpy-financial, pydantic.
- **JS:** React 18, Vite, TanStack Query, Recharts, shadcn/ui (Radix), Tailwind.

## Constraints & Trade-offs
- **Optimizes for:** correctness and interactive feel on a single household's data. Cache-on-
  change keeps warm reads instant without a background job.
- **Gives up:** multi-tenant scale, real-time collaboration, and CI-gated deploys — all
  deliberately out of scope. The engine is single-threaded Python; the M1 lever is
  vectorizing the per-date aggregation (ADR-0002), not sharding or async compute.
- **Golden-master risk:** any engine change risks silently altering projections; mitigated by
  a snapshot golden test around `ProjectionResponse` for portfolio 1.
