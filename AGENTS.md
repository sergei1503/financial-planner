# AGENTS.md — Financial Planner (fplan_v2)

Guidance for any AI coding agent working in this repo. Keep it short and current; every
line must change how an agent behaves. Deeper detail lives in `docs/` — link, don't restate.

## Overview
A personal/household financial planner: it projects 30-year net worth and cash flow from a
household's assets, loans, revenue streams and cash flows, anchored by dated historical
measurements, fast enough to explore what-ifs. Backend is Python 3.12 + FastAPI with a pure
core projection engine (`fplan_v2/core`, pandas / numpy-financial) over SQLAlchemy/Postgres.
Frontend is React 18 + Vite + TypeScript + shadcn/ui + Tailwind, TanStack Query, Recharts.
Single power user, not multi-tenant SaaS. See `docs/prd.md` and `docs/architecture.md`.

## Setup
- Auth: set `CLERK_SECRET_KEY=` (empty) for single-user local mode (user id 1); Clerk in prod.
- Local DB: `postgresql://sergeibenkovitch@localhost:5432/fplan_v2`; run backend with
  `NEON_DATABASE_URL=<local> USE_POOLER=false`.
- Frontend deps: `cd fplan_v2/frontend && npm install`.

## Commands
- Backend (port 8034): `CLERK_SECRET_KEY= NEON_DATABASE_URL=postgresql://sergeibenkovitch@localhost:5432/fplan_v2 USE_POOLER=false uvicorn fplan_v2.api.main:app --reload --port 8034`
- Frontend (port 3034, proxies `/api` + `/health`): `cd fplan_v2/frontend && npm run dev`
- Test (full): `CLERK_SECRET_KEY= pytest fplan_v2/tests -q`
- Test (single): `CLERK_SECRET_KEY= pytest fplan_v2/tests/test_models_basic.py -q`
- Frontend build / lint: `cd fplan_v2/frontend && npm run build` / `npm run lint`

## Code style
- Python `snake_case`; private helpers `_prefixed`; ORM classes singular, tables plural.
- Use the exact CHECK-constrained enum strings for asset/loan/stream/flow types (see
  `docs/standards.md`).
- Frontend: `kebab-case.tsx`, hooks `use-*.ts`, feature code under `src/features/<area>/`.

## Testing
- Add or update tests for every change, even when not asked.
- `test_models_basic.py` is the reliable no-DB unit suite; `test_projections_integration.py`
  needs a seeded DB and fails in dev — **treat those failures as environmental, not
  regressions.** Never weaken/skip/delete a test to make it pass.
- Behavior-preserving engine changes (e.g. vectorizing `compute_projection`) MUST be guarded
  by a golden snapshot of `ProjectionResponse` for portfolio 1 (see `docs/standards.md`).

## Boundaries
- Never: commit secrets, force-push, or change DB schema / dependencies without asking.
- Never mutate rows outside `BaseRepository` — writes there bump `portfolio_version` and
  invalidate the projection cache; bypassing it serves stale projections.
- Ask first: destructive migrations, dependency additions, large refactors, and any change
  to golden-master projection math.
- Deploys are manual (`vercel --prod` + Neon). Don't automate or trigger a deploy.

## Git
- Commit as `Sergei Benkovitch <sergei1503@gmail.com>` (never `hello@nomemoo.com`).
- Conventional commits (`feat(portfolio): …`). Run the model test suite before committing.

## Structure
- `fplan_v2/api/` — FastAPI app + routes (`projections.py` holds the hot `compute_projection`).
- `fplan_v2/core/` — pure projection engine (models + engine). `fplan_v2/db/` — ORM +
  repositories. `fplan_v2/frontend/src/` — SPA (features / components / hooks / api).
- Planning docs: `docs/prd.md`, `docs/architecture.md`, `docs/plan.md`, `docs/progress.md`,
  `docs/standards.md`, `docs/decisions/`. Start each task from `docs/progress.md`.
