# Lead Email Automation — Roadmap & Improvement Checklist

A living plan for evolving the app from a draft-first MVP into a production-grade B2B outreach product. Each item is a concrete checklist line — check it off as we ship.

> Status legend: `[ ]` not started · `[~]` in progress · `[x]` done · `[-]` deferred / won't do

Last updated: 2026-01

---

## 0. Current state (what's already done)

- [x] FastAPI core with draft-first orchestrator (profile + lead + email + compliance agents)
- [x] CLI for CSV → draft campaign generation
- [x] JSON-file campaign persistence (`/app/campaign_runs/`)
- [x] LLMRouter with deterministic / codex / gemini providers + safe fallback
- [x] Apollo lead provider with CSV fallback
- [x] Scrapling enrichment provider with static-fetch fallback
- [x] Gmail + Outlook OAuth setup endpoints
- [x] Local + Gmail + Outlook mailbox draft adapters (all gated on `draft.approved`)
- [x] FastAPI bridge mounting outreach_mvp under `/api` on port 8001
- [x] Multi-page React webapp (Vite + Router + Tailwind) on port 3000
- [x] 7 pages: Dashboard, Company Profile, Campaign Builder, Leads, Campaigns, Review Queue, Mailboxes
- [x] localStorage-backed app state with memoized context
- [x] 33 unit tests + 12 backend integration tests, all green
- [x] Critical fix: ReviewQueue infinite render loop (memoized context callbacks)
- [x] Vite HMR disabled to stop preview-ingress reload loop

---

## TIER 1 — Make it usable for one real user (1–2 days each)

### T1.1 Authentication & per-user isolation

- [ ] Decide auth model (Emergent Google Auth recommended; JWT custom auth as fallback)
- [ ] Call `integration_playbook_expert_v2` with chosen auth integration
- [ ] Add `User` model (id, email, name, created_at)
- [ ] Add login / logout pages and protect every page with route guard
- [ ] Add `user_id` field to every `CampaignResult` and persistence record
- [ ] Filter `GET /api/campaigns`, `/campaigns/{id}`, draft endpoints by `user_id`
- [ ] Pass real authenticated user identity to `approved_by` (replacing the hardcoded `"dashboard"`)
- [ ] Update `test_credentials.md` with seed account
- [ ] Regression: full draft → approve → mailbox flow under authenticated user

### T1.2 Universal Emergent LLM key + real Gemini integration

- [ ] Call `integration_playbook_expert_v2` for "Gemini text via Universal Emergent key"
- [ ] Replace `urllib.request` blocking calls in `outreach_mvp/llm.py` with `emergentintegrations` async client
- [ ] Make `LLMRouter._safe_complete` truly async; await it from FastAPI handlers
- [ ] Pin valid model names in `DEFAULT_MODELS` (no more guessed `gpt-5.5`)
- [ ] Surface LLM errors in logs with structured payload (currently swallowed by bare `except`)
- [ ] Add unit test that the deterministic fallback still triggers when the key is unset
- [ ] Add UI affordance: "Provider: Gemini · Model: gemini-3-flash" badge on Campaign Builder

### T1.3 Migrate persistence to MongoDB

- [ ] Add `pymongo` / `motor` to backend requirements
- [ ] Define collections: `campaigns`, `drafts`, `audit_log`, `suppression_list`, `oauth_tokens`
- [ ] Build `MongoCampaignStore` implementing the same interface as `JsonCampaignStore`
- [ ] Migration script: import existing `/app/campaign_runs/*.json` into Mongo
- [ ] Replace `JsonCampaignStore` injection in `outreach_mvp/api.py`
- [ ] Indexes: `(user_id, created_at desc)` on campaigns; `(campaign_id, draft_id)` on drafts
- [ ] Strip `_id` in every API response (Pydantic response models)
- [ ] Regression: list/get/approve/edit roundtrips against Mongo

### T1.4 Audit log

- [ ] Define `AuditEvent { id, user_id, campaign_id, draft_id, action, before, after, ts }`
- [ ] Wrap `approve_draft`, `edit_draft`, `create_mailbox_draft` in audit middleware
- [ ] Endpoint `GET /api/campaigns/{id}/audit` returning chronological events
- [ ] UI: "Activity" tab on Review Queue showing the audit timeline per draft
- [ ] Compliance polish: include `approved_by`, IP, user-agent in each event
- [ ] Export audit log as CSV for compliance teams

---

## TIER 2 — Make it valuable for a team (2–5 days each)

### T2.1 Subject-line variants + AI rewrite

- [ ] Add `variants: list[EmailDraft]` field on `CampaignResult` (or denormalized children)
- [ ] Endpoint `POST /api/campaigns/{id}/drafts/{draft_id}/rewrite` with `{ tone, length, style }`
- [ ] LLM prompt template per tone (warmer / shorter / more direct / executive)
- [ ] UI: "Rewrite" button on each draft card with tone selector
- [ ] Persist last 3 versions of subject + body so users can revert
- [ ] A/B test selector at campaign level (which variant is "primary")

### T2.2 Follow-up sequences

- [ ] Extend `CampaignInput` with `stages: list[Stage]` where each stage = (offset_days, template, llm_provider)
- [ ] Orchestrator generates draft per stage per lead
- [ ] Approval gate per stage (Stage 2 cannot send if Stage 1 not approved AND no reply)
- [ ] UI: "Sequence" view showing stages as a vertical timeline
- [ ] Suppression rule: stop sequence on reply (depends on T2.3)

### T2.3 Reply sync

- [ ] Gmail `users.history.list` watcher (push notifications via Pub/Sub)
- [ ] Microsoft Graph subscription for `Messages` collection
- [ ] On inbound message matching a sent draft → mark draft.replied = true
- [ ] Auto-suppress lead from active sequences
- [ ] UI: "Replied" badge in Review Queue + Campaigns table

### T2.4 GDPR / CAN-SPAM compliant unsubscribe

- [ ] Generate a per-lead signed token: `/u/{token}`
- [ ] Public unsubscribe endpoint that adds the lead to global + user suppression list
- [ ] Replace "reply 'not relevant'" footer with a real link + physical address line
- [ ] List-Unsubscribe and List-Unsubscribe-Post headers on Gmail/Graph drafts (RFC 8058)
- [ ] DPA / lawful-basis flag per campaign for EU leads
- [ ] Compliance test cases for footer requirements

### T2.5 Review queue power features

- [ ] Search by lead name/company/email
- [ ] Filters: status (pending/edited/approved), score range, country, industry
- [ ] Sort by score desc / created_at / company
- [ ] Bulk select with shift-click
- [ ] Bulk approve with confirmation modal showing total count
- [ ] Bulk skip with reason capture (compliance / not a fit / wrong region)
- [ ] Pagination at 50/page

---

## TIER 3 — Turn it into a product (1–3 weeks each)

### T3.1 Deliverability dashboard

- [ ] SPF / DKIM / DMARC checker for sender domain (DNS lookups)
- [ ] Warmup integration (e.g., MailReach, Lemwarm) — at minimum a manual setup guide
- [ ] Domain reputation widget (Google Postmaster Tools API)
- [ ] Per-day send-rate guardrails enforced at orchestrator level

### T3.2 Analytics

- [ ] Open tracking pixel (with explicit user consent banner — GDPR honest mode)
- [ ] Click tracking with branded short links + redirect endpoint
- [ ] Reply rate, click rate, open rate per campaign / sequence stage / variant
- [ ] Funnel chart: drafts → approved → mailbox → opened → clicked → replied
- [ ] Weekly digest email to campaign owner

### T3.3 CRM integrations

- [ ] HubSpot: push approved lead as Contact, sync replies as Engagement notes
- [ ] Salesforce: Lead + Activity sync
- [ ] Pipedrive: Person + Activity sync
- [ ] Slack notification on every approval / reply
- [ ] Webhook delivery system (signed, retried, with replay UI)

### T3.4 Multi-tenant + billing

- [ ] Workspace model (Workspace ↔ Users ↔ Campaigns)
- [ ] Roles: owner / editor / approver / viewer
- [ ] Stripe metered billing (drafts generated, drafts approved, mailbox drafts created)
- [ ] Usage dashboard with current cycle counters
- [ ] Plan limits enforced at orchestrator level

---

## QUICK WINS (each ≤ a few hours)

- [ ] Reset-state button (clears localStorage + currentCampaignId)
- [ ] Copy-to-clipboard on draft subject + body
- [ ] Share preview link `/review/<id>?share=ro` (read-only)
- [ ] Single-draft dry-run preview without persisting
- [ ] Template variable autocomplete (`{{first_name}}`, `{{company_name}}`, etc.)
- [ ] Per-draft "Regenerate" button (re-runs LLM for that one draft)
- [ ] Bulk approve all passing drafts
- [ ] Empty-state CTA on Dashboard for first campaign
- [ ] ESLint + Prettier on frontend
- [ ] TypeScript migration on frontend (incremental, file-by-file)
- [ ] Structured logging on backend (`structlog` or `loguru`)
- [ ] `GET /api/healthz` deep health (Mongo + LLM key + OAuth) for monitoring
- [ ] Persist real `approved_by` from auth context (depends on T1.1)
- [ ] Loading skeletons on Dashboard / Review Queue (vs. plain "Loading…" text)
- [ ] Keyboard shortcuts in Review Queue (`a` approve · `e` focus body · `j/k` next/prev)

---

## PLAYBOOK EXECUTION LOG (see docs/JUNIOR-IMPLEMENTATION-PLAYBOOK.md)

- [x] 2026-07-19 — Adversarial review round 2 (5 reviewers over the Phase 2-4 diff; some verifiers lost to a session limit, so unverified findings were re-verified by hand) — all confirmed findings fixed: **critical** JSON-store corrupt-file wipe (stores now fail LOUD on corruption, atomic tmp+os.replace writes, per-path in-process locks — see `_jsonfile.py`); TOCTOU on the send cap/double-send (send endpoint fully serialized under a lock); DEV_SECRET fallback (app now REFUSES to start without `UNSUBSCRIBE_SECRET` when `APP_BASE_URL` is set); unsubscribe-page XSS (escaped) + root-relative form action (now relative — works under `/api` prefix); suppressed recipients blocked at mailbox-draft creation; replied leads blocked from sending; OOO replies no longer kill sequences; own-footer quoting no longer auto-suppresses positive repliers ("not relevant" is a short-reply-only trigger); Apollo `data:null`/non-numeric retry-after crashes; SPA deep links now serve index.html through the bridge; compose `--env-file` + quoted-hash guidance corrected; hostinger deploy doc rewritten for the 8001 bridge; `PATCH .../mark-sent` added so sequences work in draft mode; tests made hermetic against developer env vars. Suite 126 → 144 green.

- [x] 2026-07-19 — Phase 2 complete: Apollo pagination + 429-retry + locked-email counting + in-search dedupe (`ApolloSearchResult`), `POST /leads/apollo/search-from-profile`, both Apollo endpoints drop already-contacted leads; enrichment fetches `/about`, caches per domain, and (LLM on) distills a specific `outreach_hook` via Claude; cross-campaign `ContactedStore` (marked at mailbox-draft/send time, `allow_recontact` override); ICP builder (`POST/GET /icp`).
- [x] 2026-07-19 — Phase 3 complete: permanent `SuppressionStore` + signed one-click unsubscribe (`/u/{token}`, HMAC, public, never 500s) feeding every drafting run; compliance footer now carries sender identity + postal address + unsubscribe link; live send (`.../send`) for `delivery_mode:"auto_send"` campaigns behind seven server-enforced preconditions incl. `DAILY_SEND_CAP` read from the send log; reply sync (`/mailboxes/{p}/sync-replies`) with Claude classification + keyword fallback, instant suppression on unsubscribe intent; follow-up sequences (`campaign.stages`, `POST .../advance`, per-stage approval, stops on reply/suppression/existing follow-up); `GET /deliverability/{domain}` SPF/DKIM/DMARC checker + `docs/deliverability-checklist.md`. Gmail/Outlook OAuth scopes extended (send + read).
- [x] 2026-07-19 — Phase 4 groundwork: bridge (`backend/server.py`) now serves the built React app at `/` with the API under `/api`; `deploy/lead-email-compose.yml` rewritten — runs the bridge, Traefik Basic Auth on everything EXCEPT the public `/api/u/` unsubscribe routes, env via `.env`, `APP_BASE_URL` includes `/api`; GitHub Actions CI added; Emergent `.gitconfig` removed; `.gitignore` cleaned (runtime store files excluded); `dev.sh` helpers. Suite 86 → 126 tests green; bridge + unsubscribe + live-DNS deliverability smoke-verified over HTTP.

- [x] 2026-07-19 — Phase 0 complete: all 6 confirmed bugs fixed test-first (country/title/industry matching, max_drafts 1..50 validation, Apollo provenance separation via `LeadInput.source`, batch dedupe, campaign-name collision suffixing, template render warnings + "Hi there" fallback). E2E backend tests repointed to localhost with clean skip.
- [x] 2026-07-19 — Adversarial review round (5 reviewers + 2 verifiers per finding, 34 confirmed findings) fixed: malformed LLM fit_score can no longer crash a run; `score_threshold=0` honored; requested-but-unconfigured providers surface `provider_not_configured:*` in `llm_error` instead of silently templating; long-form country names match again (token-subset ≥2 rule, dots stripped); LLM scoring failures visible (`llm_score_failed` reason / `low_score(llm_scoring_failed)` skip); scoring band extends to threshold (monotonic); suppression entries stripped; whitespace-only API keys ignored; blank LLM output recorded as `llm_returned_blank_fields`; corrupt campaign file no longer bricks `/campaigns`; CLI provider errors exit cleanly; `ReplyClassificationOutput` uses `Literal` enums; React dist rebuilt with provenance UI. Suite 66 → 86 tests green.
- **Playbook erratum (2026-07-19):** §4.3 originally specified `suggested_apollo_filters: dict[str, list[str]]` for the profile schema — structured outputs transform open dicts to `additionalProperties:false` objects with no properties, so Claude could only ever return `{}` (silent blanking). Corrected in the playbook: use an explicit nested model. Implemented as `ApolloFilters` in `claude_client.py` with a schema regression test.
- **Decision (2026-07-19):** new-format campaign JSONs are NOT readable by the pre-change code (rollback requires relocating `campaign_runs/`). Accepted consciously — app is pre-deployment; forward compatibility (old files → new code) is tested in `tests/test_backcompat.py`.
- [x] 2026-07-19 — Phase 1 core complete: `claude` provider via official `anthropic` SDK (`claude-opus-4-8`, structured outputs through `messages.parse`), prompts in `prompts.py`, per-draft provenance (`generated_by`, `llm_error`, `render_warnings`) surfaced in API + ReviewQueue badges, hybrid rule+LLM scoring (40–69 band, `llm_scoring` flag), ThreadPoolExecutor parallelism for enrichment + drafting, guessed model IDs (`gpt-5.5`, `gemini-3.1-pro-preview`) removed — codex/gemini now require an explicit model. Unit suite 33 → 66 tests, all green; live-key acceptance checks (playbook §4) still pending an `ANTHROPIC_API_KEY`.

## TECHNICAL DEBT / KNOWN ISSUES

- [ ] **Backend**: `POST /api/campaigns/draft` returns drafts with empty `draft_id`; clients must re-fetch via GET. Fix at the orchestrator/serializer level so the POST response is self-sufficient.
- [x] **Backend**: ~~`outreach_mvp/llm.py` uses blocking `urllib.request` inside async FastAPI handlers~~ — handlers are sync `def` (threadpool), Claude uses the official SDK; urllib remains only for optional codex/gemini.
- [x] **Backend**: ~~bare `except Exception: return {}` hides every LLM failure~~ — failures now log a WARNING and surface per-draft as `llm_error` with `generated_by: "fallback"`.
- [x] **Backend**: ~~hardcoded daily-cap `> 50` in compliance~~ — removed; `max_drafts` is validated 1..50 at the API with a clear 422 (the silent zero-drafts trap is gone).
- [ ] **Frontend**: Vite HMR disabled because the WebSocket can't tunnel the Emergent ingress; consider production-build serve in dev too, or set up an HMR proxy.
- [ ] **Frontend**: `DraftCard.useEffect([draft.subject, draft.body])` could clobber unsaved edits on a parent re-render; tracked but not currently triggered.
- [ ] **Frontend**: status-bar text in Review Queue can show stale message after a follow-up action (cosmetic).
- [ ] **Tests**: no end-to-end browser tests checked into the repo (testing subagent runs ad-hoc Playwright).
- [ ] **Tests**: no CI workflow file (`.github/workflows/ci.yml`).
- [ ] **DevEx**: no `Makefile` / `justfile` with `make test`, `make lint`, `make dev`.

---

## INTEGRATION PLAYBOOK CHECKLIST (call before implementing)

Authentication is always an integration. Do NOT write auth code without calling `integration_playbook_expert_v2` first.

- [ ] Auth (Emergent Google Auth or JWT custom) — required before T1.1
- [ ] Gemini text via Universal Emergent LLM key — required before T1.2
- [ ] OpenAI Whisper-1 (only if voice features land later)
- [ ] Stripe (only when billing — T3.4)
- [ ] HubSpot / Salesforce / Pipedrive (T3.3)
- [ ] Slack webhooks (T3.3)
- [ ] Google Pub/Sub for Gmail watchers (T2.3)
- [ ] Microsoft Graph subscriptions (T2.3)

---

## DECISION LOG

| Date | Decision | Reason |
|---|---|---|
| 2026-01 | Multi-page React UI on Vite (not Next.js) | Lighter, faster startup, no SSR needed for B2B internal tool. |
| 2026-01 | localStorage state (not Redux/Zustand) | One context is plenty for current scope; avoid premature abstraction. |
| 2026-01 | Disabled Vite HMR | Preview ingress can't tunnel WS; HMR was triggering full-reload loop. |
| 2026-01 | Kept JSON-file persistence for now | Preserve domain code shape; migrate to Mongo in T1.3 with adapter swap. |
| 2026-01 | Wrapped outreach_mvp under `/api` on backend, served React on port 3000 | Match Emergent ingress routing (`/api/*` → 8001, else → 3000). |

---

## HOW TO CONTRIBUTE TO THIS ROADMAP

1. Pick an unchecked item from the highest-priority tier with budget for it.
2. If it touches an integration, call `integration_playbook_expert_v2` first.
3. Implement, then verify with the testing subagent.
4. Move the box to `[x]` and add a one-liner to the Decision Log if a tradeoff was made.
5. Keep this file the single source of truth — `/app/memory/ANALYSIS.md` is the deeper "why", `ROADMAP.md` is the actionable "what".
