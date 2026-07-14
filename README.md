# Financial Planner

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A full-stack financial planning tool for projecting assets, loans, and net worth over time. Built for the Israeli market with Hebrew RTL support, but works for any portfolio.

**[Live Demo](https://financial-planner-sandy.vercel.app)** — try it without signing up.

## Features

- **Multi-asset portfolio** — real estate, stocks, pension, cash
- **Loan modeling** — fixed, prime-pegged, CPI-pegged, variable rate mortgages
- **Revenue streams** — rent, salary, dividends, pension payouts with growth projections
- **Cash flow breakdown** — per-source attribution (income vs. expense)
- **Historical measurements** — overlay actual values on projected trends
- **Projection engine** — net worth, asset breakdown, loan amortization over time
- **Demo mode** — visitors see a realistic sample portfolio without signing in
- **Bilingual** — Hebrew (RTL) and English

## Stack

| Layer | Technology |
|-------|------------|
| Frontend | React, TypeScript, Vite, shadcn/ui, Recharts, TanStack Query |
| Backend | FastAPI, SQLAlchemy, Pandas |
| Database | PostgreSQL (any provider — Neon, Supabase, local) |
| Auth | Clerk (optional — works without it in single-user mode) |
| Deployment | Vercel (static frontend + Python serverless API) |

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (local, Docker, or a free [Neon](https://neon.tech) database)

### 1. Clone and install

```bash
git clone https://github.com/sergei1503/financial-planner.git
cd financial-planner

# Backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd fplan_v2/frontend
npm install
cd ../..
```

### 2. Configure environment

```bash
# Backend
cp .env.example .env
# Edit .env — set DATABASE_URL or NEON_DATABASE_URL to your PostgreSQL connection string

# Frontend
cp fplan_v2/frontend/.env.example fplan_v2/frontend/.env
# Edit if needed (defaults work for local dev without auth)
```

**Minimal `.env` for local dev (no auth):**
```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fplan
```

That's it. No Clerk keys needed — the app runs in single-user mode automatically.

### 3. Initialize database and seed data

```bash
# Create tables
python -c "from fplan_v2.db.connection import init_db; init_db()"

# Seed sample data (optional)
python -m fplan_v2.scripts.seed_dev_data
```

### 4. Run

```bash
# Backend (terminal 1) — port must match the frontend's VITE_API_URL
uvicorn fplan_v2.api.main:app --reload --port 8034

# Frontend (terminal 2) — Vite is pinned to port 3034 (see vite.config.ts)
cd fplan_v2/frontend && npm run dev
```

Open http://localhost:3034 — you're in.

> **Ports:** the dev setup is wired to **backend `:8034`** and **frontend `:3034`** — the frontend's
> `VITE_API_URL` defaults to `http://localhost:8034`, and `vite.config.ts` pins the dev server to `3034`.
> If you change one, change the other.
>
> **Single-user mode:** with no Clerk keys, every request maps to **`user_id = 1`**. Seed or import
> your portfolio onto user 1 to see it locally.

### Using Docker for PostgreSQL

If you don't have PostgreSQL installed locally:

```bash
docker run -d --name fplan-db \
  -e POSTGRES_DB=fplan \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16

# Then set in .env:
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fplan
```

## Environment Variables

### Backend (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` or `NEON_DATABASE_URL` | Yes | PostgreSQL connection string |
| `CLERK_SECRET_KEY` | No | Clerk backend secret. Omit for single-user mode. |
| `CLERK_ISSUER` | No | Clerk issuer URL |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

### Frontend (`fplan_v2/frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | No | API base URL (default: `http://localhost:8034` for dev, same origin in prod) |
| `VITE_CLERK_PUBLISHABLE_KEY` | No | Clerk publishable key. Omit to skip auth entirely. |

## Architecture

```
financial-planner/
├── fplan_v2/
│   ├── api/                # FastAPI routes, auth, schemas
│   ├── core/               # Business logic (asset/loan/revenue models)
│   ├── db/                 # SQLAlchemy ORM models, repositories, connection
│   ├── scripts/            # Database seeding and migration scripts
│   ├── tests/              # API and model tests
│   └── frontend/           # React + Vite application
│       └── src/
│           ├── api/        # API client (axios)
│           ├── components/ # UI components (shadcn/ui based)
│           ├── features/   # Page-level features (dashboard, assets, loans...)
│           ├── hooks/      # TanStack Query hooks
│           └── i18n/       # Hebrew + English translations
├── api/                    # Vercel serverless entry point
├── data/                   # Public economic data (prime rates, CPI)
├── vercel.json             # Vercel deployment config
└── requirements.txt        # Python dependencies
```

## Deployment (Vercel)

The app deploys to Vercel with the frontend as static files and the backend as Python serverless functions.

1. Connect your GitHub repo to Vercel
2. Set environment variables in the Vercel dashboard (`NEON_DATABASE_URL`, `CLERK_SECRET_KEY`, etc.)
3. Push to `main` — auto-deploys

## Auth Modes

| Mode | Config | Behavior |
|------|--------|----------|
| **No auth** | No Clerk env vars | Single user, no sign-in required |
| **Clerk + demo** | Clerk configured | Signed-out visitors see demo portfolio; sign in for your own |
| **Clerk only** | Clerk configured, no demo user seeded | Standard auth flow |

To enable demo mode with Clerk, seed the demo user:
```bash
python -m fplan_v2.scripts.seed_demo_data
```

## History & migrating from v1

This is **v2** — a React + FastAPI rewrite of an earlier **Streamlit** prototype (repo `fplan`).
v1 stored portfolios as JSON/YAML config files; v2 is database-backed (one row per asset/loan,
plus a `historical_measurements` table for logged actual values).

A migration script imports a v1 config (its `asset_list` / `loan_list` / per-asset `history`) into
the v2 database for a given user:

```bash
python -m fplan_v2.migrations.migrate_from_v1 --config path/to/v1_config.json --user-id 1
```

Notes:
- The importer needs the v1 parser from the old `fplan` repo (`backend/`) on `PYTHONPATH`.
- Reset the target user's portfolio first if it already has data, to avoid duplicate rows.
- `--dry-run` has a known summary-printer bug; the real (non-dry) run is correct and de-duplicates.

## License

[MIT](LICENSE)
