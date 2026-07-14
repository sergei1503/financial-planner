# Financial Planner (fplan_v2)

## Profile
- **Stack:** vercel-standard
- **Git User:** sergei1503@gmail.com
- **PM:** Linear

## Quick Context
Personal financial planning tool with Python backend and Next.js frontend.

## Dev Server Ports

| Service  | Port | Start Command |
|----------|------|---------------|
| Frontend | 3034 | `cd fplan_v2/frontend && npm run dev` |
| Backend  | 8034 | `uvicorn fplan_v2.api.main:app --reload --port 8034` |

Always use these ports when starting services locally. The frontend proxies `/api` and `/health` to the backend.

## Relevant Agents & Skills

| Agent/Skill | Use For |
|---|---|
| `frontend-developer` | Component development |
| `/deploy` | Production deployment |
| `diagnostic-workflow` | Debug auth/env/layer issues |
| `bug-fix-workflow` | Structured bug fixing |