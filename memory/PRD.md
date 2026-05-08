# Lead Email Automation — PRD

## Original problem statement
"pls run this app" -> "can you change the UI and make it a multipage UI? sections segregated on different pages? make it a proper webapp" -> "all good".

## Architecture (Emergent preview)
- Backend: `/app/backend/server.py` — FastAPI bridge mounting `outreach_mvp.api` under `/api` on port 8001.
- Backend logic: `/app/src/outreach_mvp/` (existing draft-first email outreach engine).
- Frontend: Vite + React 18 + React Router + Tailwind on port 3000 at `/app/frontend/`.
- Routing: `/api/*` -> backend, everything else -> frontend (Emergent ingress rule).
- State: localStorage-backed React Context (`/app/frontend/src/state/AppState.jsx`).

## Pages implemented
1. **Dashboard** (`/`) — workspace overview, metrics (drafts/approved/saved campaigns), quick links, mailbox status, recent campaigns.
2. **Company Profile** (`/company`) — form + "Preview profile" calling `POST /api/companies/profile`.
3. **Campaign Builder** (`/campaign`) — targeting, sender, LLM provider/model, enrichment toggle, template editor.
4. **Leads** (`/leads`) — CSV paste / Apollo search tabs, "Generate drafts" -> `POST /api/campaigns/draft` -> redirect to review.
5. **Campaigns** (`/campaigns`) — table of saved campaigns with open action.
6. **Review Queue** (`/review/:id`) — per-draft edit subject/body, approve, save edits, create local/Gmail/Outlook mailbox draft. Stats for drafts/approved/skipped.
7. **Mailboxes** (`/mailboxes`) — Gmail / Outlook OAuth status and connect actions, with graceful "needs OAuth" badges when env vars missing.

## Design
- Source of truth: `/app/design_guidelines.json` (Outfit + IBM Plex Sans, ink-900 base, cobalt accents, grid-borders technical look). Persistent sidebar nav + safety pill (`Human approval required`) in top bar.

## Implemented (Jan 2026)
- Backend bridge under `/api` (port 8001).
- Multi-page React app on port 3000 (Vite).
- Persistent app state via localStorage.
- Backend: 12/12 pytest cases pass (`/app/backend/tests/test_outreach_api.py`).
- Frontend: 100% retest pass — Dashboard, Company Profile, Campaign Builder, Leads (Generate -> Review redirect), Campaigns table, Review Queue (approve + edit + mailbox actions), Mailboxes (graceful no-OAuth state), state persistence across navigation.
- **Bug fixed**: ReviewQueue infinite render loop — memoized `update`/`updateSection`/`reset` in AppState with useCallback + useMemo; removed redundant `update({currentCampaignId})` inside `ReviewQueue.load()`.

## Backlog
- P1: Provide OAuth env vars to enable live Gmail (`GOOGLE_OAUTH_*`) / Outlook (`MICROSOFT_OAUTH_*`) draft creation.
- P1: Provide `APOLLO_API_KEY` to enable Apollo lead search (CSV fallback works today).
- P2 (upstream): `POST /api/campaigns/draft` returns drafts with empty `draft_id`; consumers must re-fetch via `GET`. Frontend already does this; fix is in `outreach_mvp` if non-browser clients are added.
- P2: Wire Universal Emergent LLM key into the Gemini provider for richer drafts.
- P3: In-place draft state updates instead of full campaign re-fetch on approve/edit.

## Enhancement
A "Send to clipboard / share preview link" action on each approved draft would let the user collaborate with a manager (paste preview URL into Slack/email) before live mailbox draft creation — high impact, low effort, very on-brand for a "human approval required" tool.
