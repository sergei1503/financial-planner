# Multi-Portfolio Feature

Status: **implemented, reviewed, and verified locally** (2026-07-14). Not yet committed, not yet on Neon/Vercel.

A user now owns **one or more portfolios**. Every asset, loan, revenue stream, cash flow,
historical measurement, and scenario belongs to a portfolio. This enables multiple what-if
portfolios and provides the transport to move data between environments (local → Neon).

---

## 1. What was built

**Schema (prior commits `119f45b`, `6ada36a`, migrations `003`/`004`):**
- `portfolios` table; `portfolio_id` FK on the 6 owned entities; backfill of one default portfolio per user.
- `external_id` is unique **per portfolio** (was per user) — so a portfolio can be copied/imported without collisions.

**Backend API (`fplan_v2/api/`):**
- `get_current_portfolio` dependency (`auth.py`) — resolves the active portfolio from the
  `X-Portfolio-Id` header, validates ownership (404 if not yours), falls back to the user's default.
- `routes/portfolios.py` (new) — `GET/POST /api/portfolios`, `PUT /{id}` (rename),
  `POST /{id}/set-default`, `DELETE /{id}` (guards the last portfolio, promotes a new default),
  `GET /{id}/export` (full-fidelity JSON), `POST /import` (JSON → new portfolio).
- **Per-route scoping** — assets, loans, revenue_streams, cash_flows, historical_measurements,
  scenarios, projections now filter by the active portfolio. Filtering is **additive**
  (`portfolio_id` on top of the existing `user_id` filter), so a single-portfolio user is
  unaffected. Projection & scenario **cache keys** include `portfolio_id`.

**Frontend (`fplan_v2/frontend/src/`):**
- `api/client.ts` injects `X-Portfolio-Id` (mirrors the existing auth token provider).
- `contexts/portfolio-context.tsx` — active portfolio (persisted in `localStorage`), self-heals
  if the stored id was deleted, and on switch invalidates **all** queries (`refetchType: 'all'`).
- `components/portfolio-switcher.tsx` — header dropdown: switch / new / rename / set-default /
  delete / export (download) / import (upload). Bilingual (en/he), RTL.

---

## 2. Design decisions

| Decision | Rationale |
|---|---|
| Active portfolio via **`X-Portfolio-Id` header** (not query param) | One interceptor scopes every request uniformly; minimal per-hook churn; mirrors the auth-token pattern. |
| **Additive** scoping (`portfolio_id` alongside `user_id`) | Zero behavior change for existing single-portfolio data; isolation kicks in only with a 2nd portfolio. |
| Fallback to **default portfolio** when header absent | Backwards-compatible; the app works even before the provider resolves. |
| Switch → `invalidateQueries({ refetchType: 'all' })` | Queries carry no portfolio in their key; refetching **inactive** queries too avoids stale charts (see review finding F1). |
| No engine changes | The engine consumes pre-filtered asset/loan lists, so scoping the repo calls is sufficient. |

---

## 3. Review (2026-07-14) — findings & resolution

Two independent reviewers (backend + frontend) graded the diff. **Two blockers were found and fixed**:

- **B1 (blocker, fixed)** — Standalone revenue streams (salary) and standalone cash flows were
  loaded by `user_id` only inside `compute_projection`, leaking across portfolios in every
  projection. Fixed by threading `portfolio_id` through `compute_projection` →
  `_project_standalone_revenue_streams` / `_project_standalone_cash_flows` and
  `RevenueStreamRepository.get_standalone` / `CashFlowRepository.get_by_user`.
  *Verified:* portfolio A's projection excludes portfolio B's standalone salary and vice-versa.
- **F1 (blocker, fixed)** — After switching portfolios on the Dashboard, projection charts on
  other pages showed the **previous** portfolio's data, because the projection query opts out of
  refetch-on-mount and `invalidateQueries()` only refetches *active* queries. Fixed by
  `refetchType: 'all'` on switch/self-heal. *Verified:* switch to an empty portfolio → in-app nav
  to Projections now shows "no data" instead of stale charts.

Also fixed: **B2** scenario cache served stale results after editing a scenario's actions (cache
key now includes the scenario's `updated_at`); **F3** create/rename dialogs missing
`DialogDescription` (a11y); **F4** dead import-error fallback.

### Known follow-ups (documented, not blocking)
- **B3** — A scenario action that changes a revenue stream *immediately* (no date) is a no-op:
  `compute_projection` reloads standalone streams from the DB rather than taking the
  scenario-modified copies. Pre-existing; needs `compute_projection` to accept revenue streams.
- **B4** — Create endpoints (`cash_flows`, `historical_measurements`) don't validate that the
  referenced `target_asset_id` / `entity_id` is in the active portfolio (the UI already scopes the
  pickers, so only reachable via direct API). Add a same-portfolio check for hardening.
- **B5** — `get_current_portfolio`'s defensive default-create can race for a brand-new Clerk user's
  first two concurrent requests. Prefer creating the default at user-creation time.
- **B6** — `portfolio_id` is nullable; add a NOT-NULL migration once backfill is confirmed everywhere.
- **F2** — If the `localStorage` active id was deleted in another session, the first data requests
  404 (brief error flash) before self-heal recovers. Optional: clear the header proactively.
- A portfolio with income/cash-flows but **no assets and no loans** returns an empty projection
  (pre-existing short-circuit in `run_projection`).

---

## 4. Verification done (local, single-user, `localhost:5432/fplan_v2`)
- CRUD + single-default invariant + last-portfolio delete guard (400) + default promotion.
- Export → import round-trip (identical portfolio).
- Cross-portfolio isolation: asset added to B → B=1 / default=7; cross-portfolio fetch → 403; bad id → 404.
- Standalone-stream leak fix (see B1).
- Projection `/run` scoped; empty portfolio → empty result, no error.
- Full UI flow via agent-browser: create → auto-switch → scoped refetch → switch back → delete → auto-heal.
- `tsc --noEmit` clean; all backend modules import clean.

---

## 5. Production deployment runbook (Neon + Vercel, including portfolio)

**Context:** production runs on Vercel, backed by **Neon**. Sergei's own data currently lives on the
self-hosted Postgres (`46.224.85.106`, only reachable from his network); his parents' data is on Neon.
The portfolio migrations were applied **only to the local `fplan_v2` DB** so far.

### Step 1 — Apply portfolio migrations to Neon
Both are idempotent (`IF NOT EXISTS` / `IF EXISTS` guards).
```bash
# Against the Neon connection string (NOT the self-hosted box):
psql "$NEON_PROD_DATABASE_URL" -f fplan_v2/migrations/003_add_portfolios.sql
psql "$NEON_PROD_DATABASE_URL" -f fplan_v2/migrations/004_portfolio_scoped_unique.sql
```
`003` creates the table + `portfolio_id` columns and **backfills one default portfolio per existing
user**, assigning all their rows to it. `004` swaps `external_id` uniqueness from per-user to
per-portfolio. Verify: `SELECT count(*) FROM portfolios;` ≥ number of users, and every entity row has a
non-null `portfolio_id`.

### Step 2 — Move Sergei's data into Neon (the point of export/import)
From Sergei's network (so the self-hosted DB is reachable):
```bash
# Export his portfolio from the self-hosted DB
NEON_DATABASE_URL='<self-hosted url>' \
  python -m fplan_v2.scripts.portfolio_io export --portfolio-id <id> --out sergei.json

# Import into Neon as a portfolio under his (Clerk-mapped) user id
NEON_DATABASE_URL='<neon prod url>' \
  python -m fplan_v2.scripts.portfolio_io import --in sergei.json --user-id <neon_user_id> --name "My Portfolio"
```
Or, once deployed, do this from the UI: **Export** on the source, **Import** on the target — no CLI needed.

### Step 3 — Deploy to Vercel
- The backend already has the new `portfolios` router registered in `api/main.py`; no route config needed.
- Confirm CORS: `CORS_ORIGINS` must include the production frontend origin (already handled via env).
- Env vars unchanged (`NEON_DATABASE_URL`, `CLERK_*`, `VITE_*`). No new env vars for this feature.
- On Vercel the DB tables are **pre-created** (lifespan skips `init_db` when `VERCEL` is set), so the
  migrations in Step 1 are the source of truth — run them before the first request.
- Deploy via the usual `/deploy` flow.

### Step 4 — Smoke test production
- `GET /api/portfolios` returns the user's portfolio(s), default first.
- Create a 2nd portfolio, add an asset, confirm the dashboard/projection scope to it, delete it.
- Confirm existing users see all their data under their default portfolio (backfill worked).

### Pre-deploy checklist
- [ ] `003` + `004` run on Neon prod; every entity row has `portfolio_id`.
- [ ] Single-default-per-user holds for every user (`SELECT user_id, count(*) FROM portfolios WHERE is_default GROUP BY user_id;` all = 1).
- [ ] Frontend build passes (`tsc -b && vite build`).
- [ ] Sergei's data imported into Neon and verified (net worth matches the self-hosted source).
- [ ] Post-deploy smoke test (Step 4) green.
