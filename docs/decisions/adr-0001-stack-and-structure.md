# ADR 0001: Foundational stack & structure

- **Status:** accepted
- **Date:** 2026-07-14
- **Deciders:** Owner (Sergei) — recorded during sdlc-kit onboarding
- **Related:** PRD `docs/prd.md`, Architecture `docs/architecture.md`

## Context
fplan_v2 is a personal/household financial planner that must (a) hold a whole household's
assets, loans, income and expenses, (b) model Israeli instruments (prime/CPI-pegged loans,
stepped rent, pension), (c) project 30 years of net worth and cash flow, and (d) feel
interactive when the owner edits inputs. It is a single power user, not multi-tenant SaaS.
This ADR records the stack and structure that already exist, so future changes have a
baseline to reason against. The recompute is non-trivial (~360 monthly steps over many
entities), so caching strategy is part of the foundation, not an afterthought.

## Decision
We will keep the existing three-part structure:
1. **A Python 3.12 FastAPI backend** (`fplan_v2/api`) serving a REST API, with a **pure core
   projection engine** (`fplan_v2/core/models` + `fplan_v2/core/engine`) that owns all
   financial math (pandas / numpy-financial), kept independent of the web and DB layers.
2. **SQLAlchemy over Postgres** (`fplan_v2/db`) with a repository layer; local Postgres for
   dev, Neon for prod. All domain entities are portfolio-scoped.
3. **A React 18 + Vite + TypeScript SPA** (`fplan_v2/frontend`) using shadcn/ui + Tailwind,
   TanStack Query for data, Recharts for visualization; the active portfolio travels in an
   `X-Portfolio-Id` header.

**Projections are cached on change:** every mutation bumps `user.portfolio_version` (in
`BaseRepository`), and `ProjectionCache` is keyed by
`SHA256(portfolio_id:portfolio_version:start:end:as_of)`. Warm reads hit the cache; only an
edit invalidates it. Auth is Clerk in prod and a single-user local mode (user id 1) when
`CLERK_SECRET_KEY` is empty. Deploys are manual (`vercel --prod` + Neon).

## Alternatives considered
- **Single-process app (compute in the frontend or a monolith)** — rejected: the financial
  math is easier to test and reuse as a pure Python core, and Postgres gives durable,
  queryable history and JSONB config.
- **Recompute on every read (no cache)** — rejected: the cold recompute is ~1.4s; without a
  cache, every dashboard load and refetch would pay it. Version-bump caching makes warm
  reads instant and confines the cost to actual edits.
- **Time-based cache expiry** — rejected: correctness would drift between the tile and the
  chart; a deterministic version key guarantees a stale result can never be served.

## Consequences
- **Positive:** clean separation lets the engine be unit-tested without a DB
  (`test_models_basic.py`); warm reads are sub-100ms; the model is deterministic and
  golden-masterable; the stack is familiar and cheap to run single-user.
- **Negative / trade-offs:** single-threaded Python engine caps raw compute speed (addressed
  in ADR-0002); manual deploys mean no automated gate; multi-tenant/collaboration would need
  real work (portfolio is `user_id`-scoped but sharing is unbuilt).
- **Follow-ups:** ADR-0002 records the performance strategy. Engine follow-ups (yearly_fee
  inconsistency, prime-holds-flat, stale rate CSVs) tracked in project memory, out of M1.
