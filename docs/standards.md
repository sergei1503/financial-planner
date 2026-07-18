# Standards: Financial Planner (fplan_v2)

- **Status:** active · **Updated:** 2026-07-14

Concrete, project-specific conventions and the exact commands to build, run, and test.
Keep this current; delete anything an agent can infer from the code.

## Stack (exact)
- **Backend:** Python 3.12, FastAPI + Uvicorn, SQLAlchemy ORM, pandas, numpy /
  numpy-financial, pydantic. Package root `fplan_v2/` (importable as `fplan_v2.*`).
- **Frontend:** React 18 + Vite + TypeScript, shadcn/ui (Radix) + Tailwind, TanStack Query,
  Recharts. Root `fplan_v2/frontend/`.
- **Data:** Postgres (local dev + Neon prod) via SQLAlchemy.
- **Auth:** Clerk in prod; single-user local mode (user id 1) when `CLERK_SECRET_KEY` is empty.
- **Deploy:** Vercel (frontend) + Neon (prod DB), MANUAL (`vercel --prod`). No CI gate.

## Run (local dev)
- **Backend** (port 8034, single-user local mode):
  ```
  CLERK_SECRET_KEY= NEON_DATABASE_URL=postgresql://sergeibenkovitch@localhost:5432/fplan_v2 \
    USE_POOLER=false uvicorn fplan_v2.api.main:app --reload --port 8034
  ```
- **Frontend** (port 3034, proxies `/api` and `/health` to :8034):
  ```
  cd fplan_v2/frontend && npm run dev
  ```
- Local dev DB: `postgresql://sergeibenkovitch@localhost:5432/fplan_v2`.

## Test
- **Command:** `CLERK_SECRET_KEY= pytest fplan_v2/tests -q`
- **Single file:** `CLERK_SECRET_KEY= pytest fplan_v2/tests/test_models_basic.py -q`
- **CAVEAT (important):** `test_models_basic.py` is the reliable unit suite (15 tests, no DB).
  `test_projections_integration.py` needs a seeded test DB and currently FAILS in dev
  environments — treat those failures as **environmental, not regressions**. Do not "fix"
  them by weakening tests; a green model suite is the M1 gate.
- **Frontend:** no unit-test runner wired up; verify UI changes manually via the dev server.

## Deploy & production migrations
Production is **Vercel** (frontend + FastAPI serverless at `api/index.py`) backed by **Neon**
(`NEON_DATABASE_URL`). Deploys are **manual** — `git push` does not deploy on its own.

- **Golden rule — schema-first.** Apply any new `fplan_v2/migrations/*.sql` to the Neon prod DB
  **before** deploying code that reads the new columns, or the deployed app 500s on the missing
  schema. Order: **migrate Neon → `vercel --prod --yes` → verify `/health`.**
- Writes to prod still go through `BaseRepository` (bumps `portfolio_version`, invalidates the
  projection cache — a code-only fix isn't reflected for a user until their version bumps).
- **Exact connection commands, the Neon project id, and the prod user/portfolio map live in the
  gitignored `fplan_v2/docs/DATABASE_ACCESS.local.md`** (kept off this public repo — no secrets
  here). Neon is reached via `neonctl`; note the `.env` `NEON_DATABASE_URL` points at a firewalled
  box, not prod, so use `neonctl` for real production.

## Golden-master rule
The projection is golden-master. Any change to `compute_projection` or `fplan_v2/core` that
is meant to be behavior-preserving (e.g. the M1 vectorization) MUST be guarded by a snapshot
test of the full `ProjectionResponse` for portfolio 1, asserting equality before/after.
Changes that intentionally alter results (M1 items 3–5) must ship their own asserting test.

## Naming conventions
- **Python:** `snake_case` functions/vars, `PascalCase` classes; private helpers prefixed
  `_` (e.g. `_build_cash_flow_breakdown`, `_apply_cash_conversions`). SQLAlchemy tables are
  plural (`assets`, `loans`); ORM classes singular (`Asset`, `Loan`).
- **Entity types are CHECK-constrained** (see `fplan_v2/db/models.py`): asset_type
  ∈ {real_estate, stock, pension, cash}; loan_type ∈ {fixed, prime_pegged, cpi_pegged,
  variable}; stream_type ∈ {rent, dividend, pension, salary}; flow_type ∈ {deposit,
  withdrawal}. Use these exact strings.
- **Frontend:** files `kebab-case.tsx`; hooks `use-*.ts`; feature code under
  `src/features/<area>/`, shared UI under `src/components/`, API clients under `src/api/`.

## API & error conventions
- Routes live in `fplan_v2/api/routes/*` and mount under `/api/<area>`; Pydantic
  request/response models in `fplan_v2/api/schemas.py`.
- The active portfolio is passed by the frontend via the `X-Portfolio-Id` header; keep
  endpoints portfolio-scoped.
- A global exception handler in `main.py` returns `500 {error, detail, type}` for uncaught
  errors — don't swallow exceptions locally to hide them; let real errors surface.
- Every write goes through `BaseRepository`, which bumps `portfolio_version` to invalidate
  the projection cache. Do not mutate rows outside the repository layer, or the cache goes stale.

## Testing conventions
- Add or update a test for every change, even when not asked.
- Prefer no-DB unit tests in `test_models_basic.py` style for engine/model logic.
- Run the relevant test before handing off; run the full model suite before a commit.
- Never weaken, skip, or delete a test to make it pass.

## Git
- Commit as `Sergei Benkovitch <sergei1503@gmail.com>` (never `hello@nomemoo.com` — breaks
  Vercel Hobby deploys).
- Conventional-commit style, matching history (`feat(portfolio): …`, `chore(vercel): …`).
- Run the model test suite before committing.
