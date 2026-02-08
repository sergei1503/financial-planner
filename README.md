# Financial Planner

A full-stack financial planning tool for projecting assets, loans, and net worth over time.

## Stack

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL (Neon)
- **Frontend**: React + TypeScript + Vite + shadcn/ui + Recharts
- **Auth**: Clerk (email sign-in) with single-user fallback
- **Deployment**: Vercel (frontend static + Python serverless API)

## Features

- Multi-asset portfolio tracking (real estate, stocks, pension, cash)
- Loan modeling (fixed, prime-pegged, CPI-pegged, variable)
- Revenue stream projections (rent, salary, dividends, pension payouts)
- Historical measurement overlays on projections
- Cash flow breakdown with per-source attribution
- Projection caching with automatic invalidation on data changes
- Hebrew RTL interface

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (or a Neon database)

### Backend

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your database URL

# Run the API server
uvicorn fplan_v2.api.main:app --reload --port 8000
```

### Frontend

```bash
cd fplan_v2/frontend

# Install dependencies
npm install

# Set environment variables
cp .env.example .env
# Edit .env with your Clerk publishable key

# Run dev server
npm run dev
```

### Environment Variables

#### Backend (set in `.env` or Vercel dashboard)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEON_DATABASE_URL` | Yes | PostgreSQL connection string |
| `CLERK_SECRET_KEY` | No | Clerk backend secret (omit for single-user mode) |
| `CLERK_ISSUER` | No | Clerk issuer URL |
| `CORS_ORIGINS` | No | Comma-separated allowed origins |

#### Frontend (set in `fplan_v2/frontend/.env` or Vercel dashboard)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_URL` | No | API base URL (defaults to same origin in production) |
| `VITE_CLERK_PUBLISHABLE_KEY` | Yes | Clerk frontend publishable key |

## Architecture

```
financial-planner/
├── fplan_v2/               # Python package
│   ├── api/                # FastAPI routes, auth, schemas
│   ├── core/               # Business logic (asset/loan/revenue models, projections)
│   ├── db/                 # SQLAlchemy models, repositories, connection management
│   ├── scripts/            # Database seeding and migration scripts
│   └── frontend/           # React + Vite application
├── data/                   # Public economic data (prime rates, CPI)
├── api/                    # Vercel serverless entry point
├── vercel.json             # Vercel deployment configuration
└── requirements.txt        # Python dependencies
```

## Deployment

The app deploys to Vercel with:
- Frontend built as static files
- Backend running as Python serverless functions via Mangum
- Database on Neon PostgreSQL

Push to `main` to trigger automatic deployment.
