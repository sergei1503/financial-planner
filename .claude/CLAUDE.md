# Financial Planner (fplan_v2)

## Dev Server Ports

| Service  | Port | Start Command |
|----------|------|---------------|
| Frontend | 3034 | `cd fplan_v2/frontend && npm run dev` |
| Backend  | 8034 | `uvicorn fplan_v2.api.main:app --reload --port 8034` |

Always use these ports when starting services locally. The frontend proxies `/api` and `/health` to the backend.
