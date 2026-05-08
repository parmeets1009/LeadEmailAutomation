# Deep Analysis — Lead Email Automation (Jan 2026)

> Living document. Last updated after switching to multi-page Vite/React UI.

## 1. App identity
Draft-first B2B email outreach. Core invariant: the system never sends email — every draft requires explicit human approval before any local or live (Gmail/Outlook) mailbox draft is created.

## 2. Architecture
- Backend: FastAPI bridge `/app/backend/server.py` mounting `outreach_mvp` API under `/api` on port 8001.
- Domain: pure-Python `outreach_mvp/` — orchestrator + agents (profile, lead, email, compliance) + adapters (apollo, enrichment, mailbox local/Gmail/Outlook, llm).
- Frontend: Vite + React 18 + React Router + Tailwind, 7 pages, sidebar nav, dark technical aesthetic.
- State: localStorage-backed React Context (memoized).
- Persistence: JSON files in `/app/campaign_runs/`.
- Tests: 33 unit tests + 12 backend integration tests (testing subagent), all green.

## 3. Pros
- Safety-first invariants enforced at every adapter boundary (`ApprovalRequiredError`).
- Clean domain/framework separation; CLI works without HTTP.
- Adapter pattern with `Protocol` types makes everything injectable + testable.
- Frozen dataclasses + symmetric serializer.
- Multi-page UI maps 1:1 to funnel stages.
- Graceful fallbacks: no Apollo → CSV path; no LLM key → deterministic; no OAuth → local artifacts.

## 4. Cons / risks
- Single-tenant JSON file storage on ephemeral disk.
- No authentication; public preview URL has full power.
- Lead scoring & profile extraction are keyword-based and brittle.
- LLM client uses blocking `urllib.request` from FastAPI handlers; bare except hides errors; model defaults may not exist.
- Compliance footer is not GDPR/CAN-SPAM compliant on its own.
- POST /campaigns/draft returns drafts with empty draft_id (frontend re-fetches as workaround).
- Vite HMR disabled in preview ingress (manual refresh during dev).
- Zero observability (no logs, metrics, or audit trail of who approved what).

## 5. Gaps (missing functionality)
- Reply / bounce / unsubscribe sync.
- Scheduling.
- Multi-user / teams / roles.
- A/B testing, follow-up sequences, template library, AI rewrite.
- Deliverability tooling (SPF/DKIM, warmup).
- Deeper enrichment (LinkedIn, funding, tech-stack).
- Analytics (open/click/reply funnel).
- Real audit log.
- Export, search/filter in review queue.
- Webhooks / CRM integrations.

## 6. Roadmap
**Tier 1 (1–2 days each):** Auth + per-user isolation; real LLM via Universal Emergent key; audit log; Mongo persistence.
**Tier 2 (2–5 days each):** Subject variants + AI rewrite; follow-up sequences; reply sync; one-click unsubscribe; review queue search/filter/bulk approve.
**Tier 3 (1–3 weeks each):** Deliverability dashboard; analytics; CRM integrations; multi-tenant + Stripe billing.

## 7. Quick wins (hours)
- Reset state button.
- Copy-to-clipboard on subject/body.
- Share-preview link.
- Single-draft dry-run.
- Template variable autocomplete.
- Per-draft Regenerate button.
- Bulk approve.
- Empty-state first-campaign wizard.
- Lint + Prettier + TS on frontend.
- Persist real `approved_by` user (depends on auth).

## 8. Recommended next step
Tier-1 four-pack: Universal LLM key wiring → Auth → Mongo migration → Audit log. Each is self-contained and unlocks downstream features.
