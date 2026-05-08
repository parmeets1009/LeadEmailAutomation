# Lead Email Automation MVP — PRD

## Original problem statement
"pls run this app" — user requested running the existing draft-first email outreach FastAPI app in the Emergent preview environment.

## Architecture (as deployed in Emergent preview)
- Source app: `outreach_mvp` (FastAPI + static HTML/JS dashboard) at `/app/src/outreach_mvp/`.
- Routing constraint: `/api/*` -> backend port 8001, all other paths -> frontend port 3000.
- Bridge: `/app/backend/server.py` mounts `outreach_mvp.api` under `/api` on port 8001.
- Frontend: `/app/frontend/` Node + Express server on port 3000 serves the dashboard from `public/`, injecting `window.__ENV__.REACT_APP_BACKEND_URL` so `app.js` calls `${BACKEND_URL}/api/...`.
- Supervisor manages backend (`uvicorn server:app`) and frontend (`yarn start` -> `node server.js`).

## Implemented (Jan 2026)
- Installed editable `email-outreach-mvp` package into `/root/.venv` so the supervisor backend can import it.
- Created `/app/backend/server.py`, `/app/backend/.env`, `/app/backend/requirements.txt`.
- Created `/app/frontend/` with `package.json`, `server.js`, `.env`, and dashboard assets in `public/` (modified `app.js` to use `API_BASE = ${REACT_APP_BACKEND_URL}/api`).
- Verified via public preview URL:
  - `GET /api/health` -> 200 `{status: ok}`.
  - `GET /api/llm/providers` -> 200 with deterministic/codex/gemini.
  - `POST /api/campaigns/draft` -> 201, persists to `/app/campaign_runs/`.
  - `GET /api/campaigns` -> shows saved campaigns.
  - Dashboard loads at `/` and renders Campaign Workspace, Builder, History, Mailbox Connections, Review Queue.
- All 33 existing unit tests pass (`PYTHONPATH=src python -m unittest discover -s tests`).

## Backlog / Next action items
- P1: Optional Apollo + Gmail/Outlook OAuth env wiring (requires `APOLLO_API_KEY`, Google/Microsoft OAuth client IDs/secrets — user must supply).
- P1: LLM provider live calls (currently deterministic; switching to codex/gemini needs `LLM_API_KEY` / Gemini key).
- P2: Replace ad-hoc Express frontend with React/Vite if richer UI is desired.
- P2: Add campaign export (CSV) and lead enrichment toggle for static fetch fallback.

## Enhancement idea
Want to plug Gemini for richer personalization? Connect the Universal Emergent LLM key and switch the LLM Provider dropdown from "Deterministic fallback" to "Gemini" — drafts immediately get warmer, lead-context-aware copy without code changes.
