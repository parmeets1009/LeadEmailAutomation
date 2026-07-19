# LeadEmailAutomation — Implementation Playbook

**Purpose:** Complete, step-by-step instructions to evolve this repo from a draft-first MVP into a working, automated, AI-driven lead-generation app that actually gets you leads.
**Audience:** The implementing developer ("you"). Written so you can execute without asking the author what they meant. If a step requires interpretation, report it as a doc bug.
**Author:** Claude (senior review pass, 2026-07-19), based on a full code analysis with every claimed bug reproduced by running the code.
**Repo state this was written against:** `master` @ `a9fc4b1` (cloned from https://github.com/parmeets1009/LeadEmailAutomation.git).
**Validated on:** Windows 11, Python 3.13.3. Production target: Linux VPS (Hostinger, Docker + Traefik).

---

## ⚡ HANDOVER STATUS (updated 2026-07-19, end of build session)

**Phases 0–4 of this playbook are IMPLEMENTED.** 144 unit tests green; two adversarial
review rounds (77 agents each) ran and every confirmed finding was fixed — the
`PLAYBOOK EXECUTION LOG` in `ROADMAP.md` records exactly what was done, every
decision, and two playbook errata. The React UI carries a LIGHT professional design system in the REAL Novatide
brand identity: official logo from `frontend/public/novatide-logo.png` (sourced
from the Novatide skill's brand assets — NEVER redraw or replace it), deep teal
`#0F4C5C` accent, warm paper surfaces, Fraunces display serif, and a
Canva-generated abstract tide texture (`frontend/public/tide-art.png`) as
dashboard décor. Design tokens live in `frontend/src/index.css` +
`frontend/tailwind.config.js`. TWO deliberate token tricks (rename only in a
dedicated sweep): the color key `cobalt` holds the TEAL values, and the `zinc`
scale is INVERTED (low numbers = dark text on light surfaces) so every page
restyled centrally. After any frontend edit: `npm run build` and commit the
regenerated `frontend/dist/` files.

**What remains (in priority order) — pick up here:**

1. **Live-key acceptance runs** — nothing external has been exercised with real
   credentials. Set `ANTHROPIC_API_KEY` and run the Phase 1 §4 checklist (AI
   drafts for a non-rubber company); then Apollo (`APOLLO_API_KEY`, §5 checklist),
   then Google/Microsoft OAuth app registration + mailbox connect + one real
   draft→approve→mailbox-draft cycle, then reply-sync against a real inbox.
2. **Deploy — DONE (2026-07-19).** Live at **https://outreach.novatide.app** on
   the shared Hostinger VPS `200.97.163.52` (same box as the SRPPL IMS and the
   Zerodha app) — NOT via the Traefik compose file: nginx vhost + certbot +
   systemd `lead-email.service` (uvicorn bridge on 127.0.0.1:8101,
   app in `/opt/lead-email`, secrets in `/opt/lead-email/.env`, Basic Auth
   creds in `/root/lead-email-credentials.txt`, public `/api/u/` unauthenticated,
   nightly campaign_runs backup cron). Update flow: `git push` → SSH
   `cd /opt/lead-email && git pull && systemctl restart lead-email`.
   `docs/hostinger-traefik-deploy.md` (Traefik variant) remains for a future
   dedicated host.
3. **UI for the Phase 3 features** — sending, sequences (advance/mark-sent),
   reply sync, ICP, and deliverability exist as API endpoints only (all listed in
   README.md). Build ReviewQueue send/mark-sent buttons, a Sequences view, and a
   deliverability widget on Mailboxes. Follow the existing component classes; do
   not reintroduce generic AI styling.
4. **First real campaign** — ≤20 leads, draft mode, per `docs/deliverability-checklist.md`.
5. **Later:** Mongo migration trigger (§7.3), `feat/ui-ux-pro-redesign` branch
   review (predates this work — cherry-pick ideas only, do NOT merge blind over
   the new provenance UI), POST `/campaigns/draft` empty-`draft_id` debt item.

Known conscious decisions: JSON stores are single-process (in-process locks only —
matches the single-container deploy); rollback to pre-2026-07-19 code cannot read
new campaign files; per-mailbox (not global) daily send cap.

---

## 0. Read this first — ground rules

These are non-negotiable. Every phase below assumes them.

### 0.1 Safety invariants (never break these)

1. **The app never sends email without an explicit human approval step for the campaign.** Today it never sends at all (drafts only). Phase 3 introduces optional sending — but sending is ALWAYS gated on `draft.approved == True`, and the per-day cap is enforced in code, not in the UI. If a change makes it possible for an unapproved draft to reach a mailbox, that change is wrong regardless of what else it fixes.
2. **Suppression is sacred.** An email address on the suppression list must never receive a draft, a send, or a follow-up. Suppression checks live in `ComplianceAgent` — do not bypass it "just for testing".
3. **Never commit secrets.** API keys, OAuth client secrets, and tokens go in environment variables or `campaign_runs/oauth_tokens/` (gitignored). If you find a secret in the repo, rotate it and remove it from history.
4. **Every outbound email must contain a working opt-out and truthful sender identity.** This is a legal requirement (CAN-SPAM; and stricter rules for EU recipients), not a preference. See §6.5.

### 0.2 Working process (repeat for every task in this document)

1. **Read before writing.** Open every file the task names. Read the whole file, not the snippet.
2. **Write the failing test first.** Every bug fix below names the test to write. Run it, watch it fail, then fix the code, then watch it pass.
3. **Run the full suite after every change:**
   ```bash
   # from repo root (Linux/macOS/Git Bash)
   PYTHONPATH=src python -m unittest discover -s tests -v
   ```
   Expected: `OK` and a count that only ever goes UP. (33 tests pass at the time of writing.)
4. **Verify end-to-end, not just unit tests.** Start the server and exercise the real flow:
   ```bash
   PYTHONPATH=src uvicorn outreach_mvp.api:app --port 8000
   curl -s http://127.0.0.1:8000/health          # expect {"status":"ok"}
   ```
   then run the smoke flow in §0.4.
5. **Small commits, plain messages.** One logical change per commit: `fix: word-boundary country matching in lead scoring`. Never `Auto-generated changes`.
6. **Update `ROADMAP.md`** — tick the box, add a Decision Log line if you made a tradeoff.
7. **When you finish a phase, run the phase's acceptance checklist** (at the end of each phase section) before starting the next.

### 0.3 Things a previous build got wrong — don't repeat them

- **Never guess model names.** The current code contains `gpt-5.5` and `gemini-3.1-pro-preview` as guesses ([src/outreach_mvp/llm.py](../src/outreach_mvp/llm.py) `DEFAULT_MODELS`). Guessed model IDs fail silently here because errors are swallowed. Model IDs in this doc (`claude-opus-4-8`, `claude-haiku-4-5`) are exact — use them verbatim, never append date suffixes.
- **Never swallow exceptions.** `except Exception: return {}` (llm.py `_safe_complete`) is why nobody can tell whether a draft was AI-written or template-filled. Log the error, surface it in the API response, and record which path produced the output.
- **Never put machine bookkeeping in human-facing fields.** The `"Apollo lead: …"` provenance string ends up verbatim inside email bodies (§3, bug 4). Provenance goes in its own field.
- **Tests that hit hardcoded URLs rot.** `backend/tests/conftest.py` targets a dead Emergent preview URL. Tests must run against localhost or an env-var-provided URL, and skip cleanly when the target is absent.

### 0.4 The smoke flow (memorize it — you'll run it dozens of times)

```bash
# 1. create a draft campaign (deterministic provider, no keys needed)
curl -s -X POST http://127.0.0.1:8000/campaigns/draft \
  -H 'Content-Type: application/json' -d @docs/samples/draft_payload.json
# expect: HTTP 201, JSON with "status":"drafts_ready_for_review" and non-empty "drafts"

# 2. approve draft 1
curl -s -X PATCH http://127.0.0.1:8000/campaigns/<campaign_id>/drafts/draft-1/approve \
  -H 'Content-Type: application/json' -d '{"approved_by":"<your-name>","notes":"smoke"}'
# expect: "approved": true

# 3. create a local mailbox draft artifact
curl -s -X POST http://127.0.0.1:8000/campaigns/<campaign_id>/drafts/draft-1/mailbox-drafts \
  -H 'Content-Type: application/json' -d '{"provider":"gmail"}'
# expect: HTTP 201, "status":"draft_created"
```

(Create `docs/samples/draft_payload.json` from the example in [README.md](../README.md) if it does not exist yet — first task of Phase 0.)

---

## 1. The system today (what you inherit)

### 1.1 Map

```
                           ┌────────────────────────────────────────────┐
                           │  src/outreach_mvp  (the real app)          │
 CSV paste / Apollo ──────▶│  orchestrator.py                           │
                           │   ├─ profile_agent.py  (company → profile) │
                           │   ├─ lead_agent.py     (lead → score)      │
                           │   ├─ email_agent.py    (lead → draft)      │
                           │   ├─ compliance.py     (gate + footer)     │
                           │   ├─ enrichment.py     (website → context) │
                           │   └─ llm.py            (LLMRouter)         │
                           │  storage.py  → campaign_runs/*.json        │
                           │  api.py      → FastAPI, serves old JS UI   │
                           │  mailbox.py / oauth_*.py → Gmail/Outlook   │
                           └────────────────────────────────────────────┘
 backend/server.py  = thin bridge mounting the above under /api (port 8001)
 frontend/          = newer React 7-page dashboard (talks to /api)
 deploy/            = docker-compose for Hostinger+Traefik (serves OLD UI only)
```

Two UIs exist. The deploy config only ships the old embedded one. Deciding the UI is §7.2.

### 1.2 What verifiably works (all confirmed by execution, 2026-07-19)

- 33 unit tests green on Python 3.13.
- Full flow: draft → approve → local mailbox artifact → campaign listing.
- OAuth setup endpoints, Apollo client, enrichment fallback (unit-tested; not exercised against live Google/Microsoft/Apollo).

### 1.3 What is verifiably broken (each reproduced by running the code)

| # | Bug | Where | Reproduced result |
|---|-----|-------|-------------------|
| 1 | Country substring match — wrong countries pass | `lead_agent.py` `_norm`/score | Romania lead scored `country_match` for target Oman ("oman" ⊂ "r**oman**ia") |
| 2 | Bidirectional title substring — generic titles pass | `lead_agent.py` | Title "Manager" got full `title_match` vs "Procurement Manager" |
| 3 | `max_drafts > 50` silently yields ZERO drafts | `compliance.py` `check_draft` + `orchestrator.py` | `max_drafts=60` → 0 drafts, every lead skipped `daily_cap_above_mvp_limit` |
| 4 | Apollo provenance string leaks into email body | `apollo.py` `_person_to_lead` + `email_agent.py` | Body contained "…works in **Apollo lead: Procurement Manager · …**" |
| 5 | No dedupe — duplicate lead = duplicate drafts | `orchestrator.py` | Same lead twice in CSV → two drafts to same address |
| 6 | Same campaign name silently overwrites prior run + approvals | `storage.py` `_slug`/`save` | Approve → regenerate same name → `approved` reset to `False` |

Plus structural issues: silent LLM fallback with misleading `llm_provider` label, rubber-company-specific keyword fallbacks in `profile_agent.py`, template variables silently rendering to `""`, the dead opt-out compliance check (footer added before the check runs), no email format validation, sequential blocking enrichment/LLM calls.

### 1.4 Deployment state

Nothing is live. The Emergent preview 404s; `lead.hermes-agent-2bhv.srv1390211.hstgr.cloud` resolves and Traefik answers but no route/container exists. `deploy/lead-email-compose.yml` + `docs/hostinger-traefik-deploy.md` are ready but were never executed, and they contain **no authentication** — do not deploy before §7.1.

---

## 2. The target (what "actually gets you leads" means)

A lead-generation app earns its name when it moves people through this funnel with minimal manual work:

```
 ICP definition → Source leads → Enrich → Score → Draft (AI) → Human approve
      │                                                            │
      └──────────────── learning loop ◀── Replies ◀── Follow-ups ◀─┘
                                                                (deliver)
```

**The success metric is qualified replies per week** (someone answering "yes, tell me more"), not drafts generated. Every phase below exists to move that number.

Target architecture (end of Phase 3):

```
            ┌─ ICP Builder (Claude interview → saved ICP + Apollo filters)
            │
 Scheduler ─┼─ Sourcing (Apollo search / CSV) ──▶ dedupe vs contacted-store
 (daily)    │                                          │
            ├─ Enrichment (website scrape → Claude 1-line hook)  [parallel]
            │                                          │
            ├─ Scoring (rules pre-filter + Claude judgment on borderline)
            │                                          │
            ├─ Drafting (Claude, per-lead subject+body, provenance-labelled)
            │                                          │
            └─ Review queue (human approves / edits / bulk approve)
                                                       │
               Delivery: Gmail/Outlook DRAFTS (default) or capped auto-send
                                                       │
               Reply sync (poll mailbox) → Claude classifies → stop/continue
                                                       │
               Unsubscribe endpoint + suppression store (global, permanent)
```

Phases: **0** fix foundation → **1** Claude becomes the brain → **2** sourcing & enrichment that scale → **3** delivery, follow-ups, replies, compliance → **4** productionize (auth, DB, deploy, CI). Do them in order; each phase leaves the app shippable.

---

## 3. PHASE 0 — Fix the foundation (≈ 1 day)

Every fix: write the named failing test in `tests/`, fix, run full suite. Keep each fix its own commit.

### 3.1 Bug 1+2 — real matching in `LeadQualificationAgent` ([src/outreach_mvp/lead_agent.py](../src/outreach_mvp/lead_agent.py))

**Do:**
1. Add a module-level alias table and normalize through it:
   ```python
   COUNTRY_ALIASES = {
       "uae": "united arab emirates", "usa": "united states", "us": "united states",
       "u.s.": "united states", "uk": "united kingdom", "u.k.": "united kingdom",
       "ksa": "saudi arabia", "roc": "taiwan", "prc": "china",
   }
   ```
2. Replace substring country matching with **whole-string equality after normalization** (`lead_country == target_country`). Region match: compare against a token set (`target_region in lead_country.split()`), not substring.
3. Replace bidirectional title substring with **token-subset matching**: a target title matches when *all* of its tokens appear in the lead title's token set. `"procurement manager"` matches lead `"senior procurement manager"`, but bare `"manager"` no longer matches `"procurement manager"` targets (the target's `procurement` token is missing from... careful: direction matters — tokens of TARGET ⊆ tokens of LEAD title. `manager` lead lacks `procurement` → no match. Correct.)
4. Industry: match against `lead.industry` tokens only — stop concatenating `context` into the industry haystack (context already earns its own +10).
5. Make weights and threshold parameters: `LeadQualificationAgent(weights=None, threshold=50)` with today's numbers as defaults; orchestrator passes them through from a new optional `CampaignInput.score_threshold` field (default 50).

**Tests (`tests/test_lead_scoring.py`):**
- `test_romania_does_not_match_oman` — score has no `country_match`.
- `test_country_alias_uae_and_usa` — "UAE" lead matches "United Arab Emirates" target; "USA" matches "United States".
- `test_generic_manager_title_does_not_match` — bare "Manager" gets no `title_match`.
- `test_senior_procurement_manager_matches` — token-superset title still matches.
- `test_industry_not_matched_from_context` — context mentioning "construction" alone doesn't produce `industry_match`.

### 3.2 Bug 3 — reject bad `max_drafts` at the front door

**Do:**
1. In [api.py](../src/outreach_mvp/api.py) `CampaignRequest`, validate: `max_drafts` must be `1..50` → Pydantic `Field(ge=1, le=50)`. FastAPI then returns a clear 422 automatically.
2. In [compliance.py](../src/outreach_mvp/compliance.py), delete the `daily_cap_above_mvp_limit` per-draft reason (it can no longer trigger, and it was the zero-drafts trap). Keep the orchestrator's `min(campaign.max_drafts, 50)` as belt-and-braces.
3. While in `compliance.py`: add email **format** validation to `precheck_lead` — reject `invalid_email_format` when the address doesn't match a simple RFC-ish regex (`^[^@\s]+@[^@\s]+\.[^@\s]+$`). Do not over-engineer with full RFC 5322.
4. Also fix the dead check: `check_draft` runs *after* `add_opt_out_footer`, so `missing_opt_out_language` can never fire. Make `EmailPersonalizationAgent.draft` call `check_draft` on the **final** body but keep the reason meaningful by asserting the footer's presence (it now genuinely verifies the invariant instead of being decorative). One assertion-style check is enough.

**Tests:** `test_max_drafts_over_50_returns_422` (FastAPI TestClient), `test_invalid_email_format_precheck`, `test_footer_always_present_in_passed_drafts`.

### 3.3 Bug 4 — separate Apollo provenance from human text ([src/outreach_mvp/apollo.py](../src/outreach_mvp/apollo.py))

**Do:**
1. Add `source: str = ""` to `LeadInput` in [models.py](../src/outreach_mvp/models.py) (and to serializers — follow how existing fields flow through `to_plain_data`/`from_campaign_result`).
2. In `_person_to_lead`, set `source="apollo"` and build `context` WITHOUT the "Apollo lead" prefix — join the parts only: `"Procurement Manager · Gulf Traders · Industrial · Oman"`. Better: leave `context=""` so website enrichment can run, and put the parts in context only when there is no website.
3. Grep the repo for `"Apollo lead"` — no other producer should exist.

**Tests:** `test_apollo_lead_context_has_no_provenance_prefix`, `test_apollo_lead_source_field_set`, and an orchestrator-level `test_apollo_sourced_email_body_contains_no_bookkeeping` that generates a draft from a fake Apollo person and asserts `"Apollo"` not in the body.

### 3.4 Bug 5 — dedupe leads ([src/outreach_mvp/orchestrator.py](../src/outreach_mvp/orchestrator.py))

**Do:** before the scoring loop, dedupe by lowercased email, keeping the first occurrence; record dropped ones as `skipped[email] = "duplicate_in_batch"`. Because `skipped` is keyed by email, a duplicate would overwrite the first record — that is acceptable for now, but switch `skipped` to `list[dict]` with `{email, reason}` entries if you touch its shape (update the React ReviewQueue + old UI consumers if you do; otherwise leave shape alone).

**Test:** `test_duplicate_leads_produce_single_draft`.

### 3.5 Bug 6 — stop silent campaign overwrite ([src/outreach_mvp/storage.py](../src/outreach_mvp/storage.py))

**Do:** in `save`, if `<slug>.json` already exists, suffix with a counter: `<slug>-2.json`, `<slug>-3.json`, … (loop until free). Return the path as today; the API already echoes `campaign_id` from the stem, so the client learns the real id. Do NOT use timestamps (`Date.now`-style ids leak into URLs and are ugly to type).

**Tests:** `test_same_name_creates_new_campaign_id`, `test_existing_campaign_approvals_survive_regenerate` (approve in campaign A, regenerate same name, reload A, assert still approved).

### 3.6 Template rendering honesty ([src/outreach_mvp/email_agent.py](../src/outreach_mvp/email_agent.py))

**Do:**
1. `_render` collects unknown variable names instead of silently blanking them; return `(text, unknown_vars)`.
2. Draft gains `render_warnings: list[str]` (add to `EmailDraft` model + serializer) — e.g. `["unknown_variable:first_nam"]`. The React ReviewQueue shows a warning badge later; for now the field existing is enough.
3. Greeting fallback: when `first_name` is empty, substitute `"there"` **only** in greeting position — simplest robust rule: if `first_name` is empty, set the variable to `"there"`.

**Tests:** `test_unknown_template_variable_produces_warning`, `test_missing_first_name_renders_hi_there`.

### 3.7 Repoint the rotten E2E tests ([backend/tests/conftest.py](../backend/tests/conftest.py))

**Do:** default `BASE_URL` to `http://127.0.0.1:8001`; at session start, try `GET {BASE_URL}/api/health` with a 2 s timeout and `pytest.skip("backend not running at BASE_URL")` on failure. Delete the hardcoded Emergent URL everywhere (`grep -rn emergentagent`).

**Verify:** `python -m pytest backend/tests -q` → all **skipped** with no server, all **passing** with `PYTHONPATH=src uvicorn server:app --port 8001 --app-dir backend` running.

### Phase 0 acceptance checklist

- [ ] Full unit suite green; count ≥ 45 (33 old + ~12 new).
- [ ] Smoke flow (§0.4) passes.
- [ ] `max_drafts=60` request returns 422 with a message a non-developer understands.
- [ ] A campaign regenerated under the same name gets a new id; the old one keeps its approvals.
- [ ] `grep -rn "Apollo lead" src/` returns nothing.

---

## 4. PHASE 1 — Make Claude the brain (≈ 1–2 days)

Today, with no keys configured, every "AI" output is keyword rules tuned to a rubber company. This phase replaces the brain and makes provenance honest.

### 4.1 Add the Anthropic SDK properly

**Do not** route Claude through the existing OpenAI-compatible `urllib` client. Use the official SDK.

1. Add to `pyproject.toml` dependencies: `"anthropic>=0.116.0"`. Reinstall (`pip install -e .`).
2. New file `src/outreach_mvp/claude_client.py`:

```python
from __future__ import annotations

import logging
from typing import Any

import anthropic
from pydantic import BaseModel

logger = logging.getLogger("outreach_mvp.llm")

# Exact model IDs — never edit these to "close enough" names.
CLAUDE_MODEL_DEFAULT = "claude-opus-4-8"   # drafting, profiling, reply reading
CLAUDE_MODEL_FAST = "claude-haiku-4-5"     # optional cost lever for bulk scoring


class ClaudeStructuredClient:
    """Structured-output Claude calls. Raises on failure — callers decide fallback."""

    def __init__(self, model: str = CLAUDE_MODEL_DEFAULT) -> None:
        self.model = model
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    def parse(self, *, system: str, user_payload: dict[str, Any], schema: type[BaseModel], max_tokens: int = 2048) -> BaseModel:
        import json
        response = self._client.messages.parse(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}],
            output_format=schema,
        )
        if response.parsed_output is None:
            raise RuntimeError(f"Claude returned unparseable output (stop_reason={response.stop_reason})")
        return response.parsed_output
```

Notes for you:
- `messages.parse` + a Pydantic class gives validated objects — no hand-rolled JSON parsing, no `response_format` guessing.
- Let `anthropic.APIStatusError` / `RateLimitError` propagate — the router (next section) catches them ONCE, logs, and falls back visibly.
- The SDK retries 429/5xx twice on its own; do not wrap in your own retry loop.

### 4.2 Rework `LLMRouter` ([src/outreach_mvp/llm.py](../src/outreach_mvp/llm.py))

1. Add provider `"claude"` to `SUPPORTED_PROVIDERS`; `DEFAULT_MODELS["claude"] = "claude-opus-4-8"`. Make `"claude"` the default provider in `api.py`'s `DraftCampaignRequest` and `/llm/providers` **when `ANTHROPIC_API_KEY` is set**, else `"deterministic"`.
2. Delete the guessed IDs `gpt-5.5` / `gemini-3.1-pro-preview`. If you keep the codex/gemini providers at all, leave their model empty and require the caller to pass one explicitly; otherwise remove those providers entirely (recommended — YAGNI: dead options are maintenance).
3. Kill the silent failure. `_safe_complete` becomes:

```python
def _safe_complete(self, task, payload):
    if self._client is None:
        return {}, "no_client"
    try:
        return self._client.complete_json(...), None
    except Exception as exc:                      # noqa: BLE001 — boundary log
        logger.warning("LLM %s call failed for task=%s: %s", self.provider, task, exc)
        return {}, f"{type(exc).__name__}: {exc}"
```

4. **Per-draft provenance.** Add to `EmailDraft`: `generated_by: str` (`"llm"` or `"fallback"`) and `llm_error: str = ""`. `EmailPersonalizationAgent.draft` sets them. Same on `BusinessProfile`: `generated_by`. The campaign result keeps `llm_provider` (what was *requested*); drafts now say what actually *happened*.
5. Surface it: `/campaigns/{id}/drafts` already serializes drafts, so the fields flow automatically once they're on the model. Add a badge in the React ReviewQueue (`frontend/src/pages/ReviewQueue.jsx`): render `draft.generated_by === "fallback"` as a amber "template" chip with `llm_error` in the tooltip.

**Tests:** `test_router_reports_fallback_reason` (inject a client that raises; assert draft `generated_by == "fallback"` and `llm_error` non-empty), `test_claude_provider_uses_injected_client` (inject a fake `ClaudeStructuredClient`; assert draft text comes from it, `generated_by == "llm"`). Never call the live API in tests.

### 4.3 The prompts (use these verbatim as v1, then iterate)

Keep prompts in a new `src/outreach_mvp/prompts.py` as module constants so tests can import them and diffs are reviewable.

**Company profile** (system prompt; user payload = the JSON already built in `llm.py`):

```
You are a B2B go-to-market analyst. From the company details provided, produce
a business profile for cold-outreach targeting.
Rules:
- Ground every claim in the provided details. Do not invent certifications,
  markets, or products. If a field cannot be supported, use an empty list.
- buyer_personas: job titles of the people who would BUY this offering, most
  likely decision-maker first.
- value_propositions: max 3, each ≤ 12 words, concrete (no "high quality
  solutions" filler).
- suggested_apollo_filters: person_titles (from personas),
  organization_locations (from stated markets), q_organization_keyword_tags
  (from target industries).
```

Pydantic schema: mirror `BusinessProfile` fields (`summary`, `product_categories`, `buyer_personas`, `target_industries`, `value_propositions`), with `suggested_apollo_filters` as an **explicit nested model** (`person_titles`, `organization_locations`, `q_organization_keyword_tags` — each `list[str]`). NEVER type it `dict[str, list[str]]`: structured-output schemas force `additionalProperties: false`, which turns an open dict into an object with no properties, and the model can then only ever return `{}` — silently blanking the field. (Erratum found by adversarial review, 2026-07-19.)

**Email draft** (system prompt; user payload = profile + campaign + lead + enriched context):

```
You write short, effective B2B cold emails. Write ONE email for the lead
provided, from the sender provided.
Hard rules:
- 60–120 words body. No fluff openers ("I hope this finds you well").
- Subject: ≤ 7 words, specific to the lead's company or context, not clickbait,
  no ALL CAPS, no "quick question".
- Reference ONE concrete, verifiable detail from the lead's context or website
  summary. If none exists, open with the industry problem your value prop
  solves — do not fabricate familiarity ("loved your recent post").
- One clear, low-friction call to action (a question they can answer in one
  line — not "book a 30-minute call").
- Do NOT add an unsubscribe/opt-out footer; the system appends it.
- Do not claim the email was sent, and never invent facts about the lead.
- personalization_reason: one sentence naming exactly which lead detail you used.
```

Schema: `{subject: str, body: str, personalization_reason: str}`.

**Lead scoring assist** (only for borderline leads — see §4.4):

```
You are qualifying leads for the campaign described. Given the campaign
targeting and one lead, return:
- fit_score: integer 0-100 (100 = ideal buyer).
- fit_reasons: max 3 short strings.
- disqualifiers: list of hard reasons this lead should be skipped
  (wrong geography, competitor, student/academic, obviously personal email),
  empty if none.
Be strict: a generic title with no company signal is a 40, not a 70.
```

**Reply classification** (Phase 3, listed here so all prompts live together):

```
Classify the reply below from a cold-email recipient. Return:
- category: one of interested | not_interested | unsubscribe | out_of_office
  | wrong_person | bounce | other
- summary: one sentence.
- suggested_action: one of reply_personally | stop_sequence | remove_and_suppress
  | retry_later | forward_to_human
Unsubscribe intent in ANY wording (including "stop", "not relevant", legal
threats) → category unsubscribe, action remove_and_suppress.
```

### 4.4 Wire the brain into the pipeline

1. **Profile:** `BusinessProfileAgent.profile` already prefers the LLM. With Claude registered it now works; keep keyword fallback but mark `generated_by="fallback"`. Delete nothing yet — the rubber keywords stay as a last-resort fallback until Phase 2 proves stability, then delete `_product_categories`-style rubber specifics and fall back to generic wording only.
2. **Drafting:** `EmailPersonalizationAgent` already prefers the LLM — keep, plus provenance fields.
3. **Scoring hybrid** (new): rules run first (fast, free). Leads scoring **40–69** go to Claude for `fit_score` (rules and LLM disagree most in the middle); final score = LLM's if present. Leads with any `disqualifiers` are skipped with that reason. This caps LLM cost at the ambiguous slice. Implement in orchestrator behind `llm_scoring: bool = True` on the request.
4. **Concurrency:** LLM drafting per lead is independent — run with `concurrent.futures.ThreadPoolExecutor(max_workers=4)` inside the orchestrator (the SDK client is thread-safe; FastAPI sync endpoints already run in a threadpool so no event-loop concern). Same executor pattern for enrichment fetches. Cap 4 to stay polite on rate limits.

### 4.5 Cost model (so you can answer "what does this cost?")

Per lead with Opus 4.8 (input $5/MTok, output $25/MTok): profile is once per campaign (~1.5k in / 400 out ≈ $0.018). Per draft ~1.2k in / 300 out ≈ **$0.014**. A 50-lead campaign with scoring assists ≈ **$1–2 total**. Log `response.usage.input_tokens/output_tokens` at INFO per call so real numbers replace this estimate. If volume grows 10×, move scoring+classification to `claude-haiku-4-5` ($1/$5 per MTok) — the owner's call, not yours.

### Phase 1 acceptance checklist

- [ ] With `ANTHROPIC_API_KEY` set: generate a campaign for a NON-rubber business (use Novatide: IT consulting) — profile personas/industries are plausibly IT-consulting, not "Gaskets".
- [ ] Drafts show `generated_by:"llm"`, distinct subjects per lead, one verifiable personalization detail each.
- [ ] Unset the key: same request still succeeds, drafts say `generated_by:"fallback"`, `/campaigns/draft` response contains no silent lie about the provider.
- [ ] Break the key (set to `sk-ant-invalid`): request succeeds on fallback and `llm_error` names an auth error; the server log shows one WARNING per failed call.
- [ ] Full suite green; no test calls the live API.

---

## 5. PHASE 2 — Sourcing & enrichment that actually get leads (≈ 2–3 days)

### 5.1 Finish Apollo ([src/outreach_mvp/apollo.py](../src/outreach_mvp/apollo.py))

The client exists but has never met the real API. Do this with a real (free-tier) Apollo account and `APOLLO_API_KEY` set.

1. **Pagination:** `search_leads` fetches page 1 only. Loop pages until `max_leads` collected or `data["pagination"]["total_pages"]` exhausted; be defensive — log and stop on missing keys.
2. **Rate limiting:** on `httpx.HTTPStatusError` 429, sleep `int(response.headers.get("retry-after", "60"))` and retry once; on second 429 raise a clear error the API maps to HTTP 503 with detail "Apollo rate limited — try later".
3. **Locked emails:** free-tier Apollo returns `"email_not_unlocked@domain.com"` placeholders. Filter them (`if lead.email.endswith("@domain.com") or "not_unlocked" in lead.email: skip`) and count them in the response (`"locked_email_count": n`) so the user understands why 25 requested ≠ 25 usable.
4. **ICP → filters bridge:** `/companies/profile` already produces `suggested_apollo_filters`. Add endpoint `POST /leads/apollo/search-from-profile` that takes `{profile, max_leads}` and maps `person_titles→titles`, `organization_locations→locations`, `q_organization_keyword_tags→industries`. The React Leads page gets a "Search with suggested filters" button.
5. **Contacted-store check:** see §5.3 — sourcing must drop already-contacted emails before they reach drafting.

**Tests:** fake `ApolloSearchClient` returning 2 pages → assert pagination; locked-email filtering; 429-retry behavior with a stub.

### 5.2 Enrichment worth reading ([src/outreach_mvp/enrichment.py](../src/outreach_mvp/enrichment.py))

Title+meta+h1 is a start, but the drafts live or die on this context.

1. **Fetch more:** after the homepage, also try `/about` (`urljoin(website, "/about")`) — best-effort, same 10 s timeout, ignore failures.
2. **Claude summarize:** when the LLM is enabled, pass the scraped text (truncate to ~4k chars) through Claude with schema `{company_summary: str, outreach_hook: str}`:
   ```
   From this website text, extract:
   - company_summary: one factual sentence on what the company does.
   - outreach_hook: ONE specific, non-generic detail a salesperson could
     reference in a cold email (a named product line, market, certification,
     recent milestone). If nothing specific exists, return "".
   Do not invent details.
   ```
   Store `outreach_hook` into `lead.context` (it feeds `{{lead_context}}` and the drafting prompt); keep raw title/meta as fallback.
3. **Parallel + cached:** enrich with the Phase-1 `ThreadPoolExecutor`; add an in-process dict cache keyed by domain so 10 leads from one company cost one fetch. (Persistent cache comes free with Mongo in Phase 4 — don't build one now.)
4. **Robots + politeness:** fetch only the two public marketing pages above, keep the existing honest User-Agent, and never bypass auth walls or bot checks. If a site blocks, move on — plenty of leads.

**Tests:** injectable fetcher (already the pattern) + fake Claude → assert hook lands in context; cache hit count; about-page fallback.

### 5.3 The contacted-store (dedupe across campaigns)

New file `src/outreach_mvp/contacted.py`: `ContactedStore` with `add(email, campaign_id, ts)` / `was_contacted(email) -> bool`, JSON-file-backed at `campaign_runs/contacted.json` (same durability story as everything else until Mongo). Hook it:
- Orchestrator: skip with reason `already_contacted` (override flag `allow_recontact: bool = False` on the request for deliberate re-runs).
- Mark as contacted at **mailbox-draft creation** (the moment a message is placed in a real mailbox), not at draft generation.

**Tests:** contacted lead skipped; `allow_recontact=True` bypasses; marking happens on mailbox-draft, not on generate.

### 5.4 ICP builder (small but high-leverage)

A one-page flow (extend Company Profile page): the user answers 4 free-text questions — what do you sell, who buys it, where, who must NOT be contacted (competitors/domains). `POST /icp` runs Claude once with the profile prompt + an `exclusions` field, saves `campaign_runs/icp.json`, and Campaign Builder pre-fills targeting + suppression from it. Endpoint + storage + prefill ≈ half a day; skip fancy UI.

### Phase 2 acceptance checklist

- [ ] Live Apollo search (with key) returns usable leads, honest `locked_email_count`, paginates past 25.
- [ ] Drafts for leads WITH websites reference a real, checkable site detail (spot-check 5 by opening the site).
- [ ] Generating the same campaign twice produces zero drafts the second time — all `already_contacted` — unless `allow_recontact` set. (Contacted marking via mailbox-draft step.)
- [ ] 25-lead campaign with enrichment completes in < 60 s (parallelism working).

---

## 6. PHASE 3 — Delivery, follow-ups, replies, compliance (≈ 3–5 days)

This is where it becomes an outreach machine rather than a draft generator. Order matters: compliance store first, then delivery, then replies, then sequences.

### 6.1 Real unsubscribe + suppression store (build FIRST)

1. `SuppressionStore` (`campaign_runs/suppression.json`): `add(email, reason, ts)` / `contains(email)`. `ComplianceAgent` reads it in addition to the per-request list.
2. Signed unsubscribe tokens: `itsdangerous`-free stdlib approach — `hmac.new(SECRET_KEY, email, sha256)` hex, token = `base64url(email)+"."+sig`. `UNSUBSCRIBE_SECRET` env var, required in production.
3. Public endpoints (NO auth — they must work for recipients): `GET /u/{token}` → confirmation page with a POST button; `POST /u/{token}` → verify sig, add to suppression, plain "You're unsubscribed" page. Never 500 on bad tokens; show "invalid link".
4. Footer upgrade in `compliance.py`:
   ```
   {sender_name} · {company_name} · {postal_address}
   If you'd rather not hear from me, one click and you're out: {unsubscribe_url}
   ```
   `postal_address` comes from a new `CompanyInput.details["postal_address"]`; refuse to enable auto-send mode (§6.3) when it's empty. Keep the old "reply 'not relevant'" line too — replies are good signals.
5. Reply "not relevant"/unsubscribe classification (§6.4) also feeds this store.

**Tests:** token round-trip, tampered token rejected, suppressed lead skipped at precheck, footer contains url+address.

### 6.2 Deliverability groundwork (document + verify, mostly not code)

Write `docs/deliverability-checklist.md` for the owner and implement one endpoint:
- **Domain:** send from a warmed real mailbox on your own domain (parmeet@…), never a fresh throwaway domain with day-one volume.
- **DNS:** SPF (`v=spf1 include:_spf.google.com ~all` for Gmail / `include:spf.protection.outlook.com` for M365), DKIM enabled in the provider admin console, DMARC start at `v=DMARC1; p=none; rua=mailto:you@domain` then tighten.
- **Endpoint `GET /deliverability/{domain}`:** `dns.resolver` (add `dnspython` dep) lookups for SPF TXT, DMARC TXT at `_dmarc.`, common DKIM selectors (`google._domainkey`, `selector1._domainkey`); return found/missing per record. UI shows red/green on the Mailboxes page.
- **Volume rules (enforced in §6.3):** start ≤ 20/day/mailbox, +10/week, hard cap 50/day. Plain-text-looking emails (we already do), no tracking pixels in v1, no link shorteners.

### 6.3 Sending — two modes, drafts stay the default

Mode A (today, default): approved drafts land in the user's Gmail/Outlook **Drafts** folder; the human presses Send. Zero new risk.

Mode B (new, opt-in per campaign `delivery_mode: "draft" | "auto_send"`):
1. Gmail: `users.messages.send` — needs scope `https://www.googleapis.com/auth/gmail.send` added in [oauth_setup.py](../src/outreach_mvp/oauth_setup.py) scopes; users must reconnect mailboxes once. Outlook: Graph `/me/sendMail` — scope `Mail.Send`.
2. New `SendLog` (`campaign_runs/send_log.json`): every send appends `{email, campaign_id, draft_id, ts, mailbox}`. The **per-day cap check reads this log** (`sends_today(mailbox) < DAILY_SEND_CAP` env, default 20) and refuses beyond it with a clear API error. Cap lives server-side; the UI merely displays it.
3. Auto-send preconditions (server-enforced): draft approved ✚ campaign `delivery_mode=auto_send` ✚ postal address present ✚ unsubscribe URL in body ✚ recipient not suppressed/contacted ✚ under daily cap. Any failure → 409 with the reason. Send timing: add ±3 min jitter between sends (background thread), never a burst loop.
4. UI: campaign builder gets a delivery-mode radio, defaulting to drafts, with an explicit warning sentence on auto-send.

**Tests:** cap refusal at N+1, precondition matrix (parameterized), send log append; Gmail/Graph clients tested with injected fakes exactly like the existing draft clients.

### 6.4 Reply sync + classification

Polling beats push infrastructure at this scale (Pub/Sub / Graph webhooks are ROADMAP T2.3 — skip for now).
1. `POST /mailboxes/{provider}/sync-replies` (plus a scheduler hook, §6.6): Gmail `users.messages.list` with `q="in:inbox newer_than:7d"`, match `From` addresses against contacted-store; Outlook Graph `/me/messages?$filter=receivedDateTime ge …`.
2. Each matched reply → Claude reply-classification prompt (§4.3). Act on `suggested_action`: `remove_and_suppress` → SuppressionStore + stop sequence; `stop_sequence` → mark lead replied (new `replied: bool` on the draft/lead record) so follow-ups halt; others → surface in UI only.
3. ReviewQueue/Campaigns UI: "Replied" badge + classification summary.

**Tests:** fake mailbox client returning canned replies; classification via injected fake LLM; suppression/stop side-effects asserted.

### 6.5 Compliance reality check (read once, then it's built in)

B2B cold email is lawful in most places **when** you tell the truth about who you are, include a working opt-out and a physical address, honor opt-outs promptly (we do it instantly), and keep volumes sane. EU/UK recipients are stricter (PECR/GDPR "legitimate interest") — the pragmatic v1 rule: keep EU sending in Mode A (human sends each one) and log a `legal_basis:"legitimate_interest_b2b"` field per campaign. Never buy scraped personal-address lists; Apollo business contacts + your own CSVs only. Everything in 6.1–6.3 exists to make the compliant path the only path the code allows.

### 6.6 Follow-up sequences (last, it leans on everything above)

1. `CampaignInput.stages: list[Stage]` where `Stage = {offset_days: int, template: str}`; stage 0 is the existing email.
2. Generation: drafts for stage 0 only. A daily scheduler tick (§7.4 cron or `POST /campaigns/{id}/advance`) finds approved+sent stage-N drafts older than `offset_days` where lead not replied/suppressed → generates stage-N+1 drafts into the review queue (approval per stage — no auto-approve).
3. Claude prompt addition for follow-ups: "This is follow-up #N to an unanswered email (included below). Reference it in one clause, add ONE new angle, ≤ 80 words, no guilt-tripping."
4. Stop conditions (any): reply, suppression, 3 stages, campaign paused.

**Tests:** stage advance eligibility matrix; reply halts sequence; per-stage approval required.

### Phase 3 acceptance checklist

- [ ] Unsubscribe link from a real received draft works end-to-end and the address never gets drafted again.
- [ ] `GET /deliverability/<your-domain>` shows SPF+DKIM+DMARC green for the sending domain.
- [ ] Mode B refuses to send the 21st email of the day and beyond (prove with an integration test AND once manually with the log).
- [ ] A real reply to a test campaign is fetched, classified, and stops that lead's sequence.
- [ ] A 2-stage sequence advances only after `offset_days`, only without a reply, and lands the follow-up in the review queue unapproved.

---

## 7. PHASE 4 — Productionize (≈ 1 week, interleave with Phase 2/3 as needed)

### 7.1 Auth (before ANY public deployment)

Two layers, cheapest-first:
1. **Now:** Traefik Basic Auth in [deploy/lead-email-compose.yml](../deploy/lead-email-compose.yml):
   ```yaml
   - traefik.http.middlewares.lead-auth.basicauth.users=admin:$$apr1$$xxxxxxxx$$yyyyyyyyyyyyyyy
   - traefik.http.routers.lead-email.middlewares=lead-auth
   ```
   Generate with `htpasswd -nb admin '<strong password>'` and **double every `$` to `$$`** for compose. Exception: the public unsubscribe route must bypass auth — give `/u/` its own router without the middleware:
   ```yaml
   - traefik.http.routers.lead-unsub.rule=Host(`lead.…`) && PathPrefix(`/u/`)
   - traefik.http.routers.lead-unsub.entrypoints=websecure
   - traefik.http.routers.lead-unsub.tls.certresolver=letsencrypt
   ```
2. **Later (multi-user):** ROADMAP T1.1 JWT auth. Not a blocker for owner-only use.

### 7.2 Pick the UI (recommendation: ship the React app)

The compose file serves the OLD embedded JS dashboard. The React app is better and where the redesign branch (`feat/ui-ux-pro-redesign`) points. Do:
1. Serve built React from FastAPI: `npm run build` in `frontend/`, mount in `backend/server.py`: `app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="ui")` AFTER the `/api` mount. Set `REACT_APP_BACKEND_URL=""` at build so the app calls same-origin `/api`.
2. Compose runs `backend.server:app` (port 8001) instead of `outreach_mvp.api:app`; update the Traefik service port label; add a build step for the frontend (either commit `dist/` as today, or a two-stage Dockerfile — committing dist is acceptable at this scale).
3. Review `feat/ui-ux-pro-redesign` (+1006/−3447): if the redesign supersedes pages you'd otherwise fix, merge it FIRST, then apply UI tasks from Phases 1–3 on top. Decide by diffing, don't merge blind.
4. Retire the embedded `src/outreach_mvp/frontend/` once React is confirmed serving (delete + remove the `/` route and `/assets` mount in `api.py`; keep `/health`).

### 7.3 MongoDB migration (ROADMAP T1.3 — follow it as written)

Trigger: when JSON files exceed ~50 campaigns or Phase 3 send/reply logs make file contention real. The store interfaces (`JsonCampaignStore`, `ContactedStore`, `SuppressionStore`, `SendLog`) are the seam — build `Mongo*` twins with identical methods, swap by env var `STORAGE=mongo|json`, migrate with a one-shot script importing every `campaign_runs/*.json`. Indexes: `(campaign_id)`, `(email)` on contacted/suppression, `(mailbox, sent_at)` on send log.

### 7.4 Deployment runbook (supersedes assumptions in docs/hostinger-traefik-deploy.md)

Pre-flight discovered facts (2026-07-19): Traefik answers on the VPS but even the root hermes host 404s — verify what is actually running before assuming the guide's environment.
1. `ssh` to the VPS. `docker ps` — confirm a traefik container; `docker network ls | grep traefik` — note the real network name; `docker inspect <traefik> | grep certresolver` — note the real resolver name. Fix both names in the compose file if they differ.
2. `git clone` the repo to `/opt/lead-email` (or rsync). Create `/opt/lead-email/.env` with the production env vars (§9) — compose reads it via `env_file: ../.env` (add that line).
3. `mkdir -p campaign_runs && docker compose -f deploy/lead-email-compose.yml up -d`.
4. Verify inside-out: `docker compose logs -f` shows uvicorn on 8000/8001 → `docker exec` curl localhost health → `curl -I https://lead.…/health` expect 200 and a real LE certificate (`curl -vI 2>&1 | grep issuer` shows Let's Encrypt, not TRAEFIK DEFAULT CERT).
5. Browser: login prompt (Basic Auth working) → dashboard loads → run the §0.4 smoke flow against the public URL.
6. Set the OAuth redirect URIs in Google/Microsoft consoles to the public URLs and connect mailboxes.
7. **Backups:** nightly `tar czf` of `campaign_runs/` to a second location (cron on the VPS). This folder IS the database until 7.3.

### 7.5 CI + hygiene

1. `.github/workflows/ci.yml`: on push/PR — setup Python 3.13, `pip install -e . && pip install pytest httpx`, run unit suite, run `pytest backend/tests` (they self-skip without a server — that's fine, they gate deploys elsewhere).
2. Remove `.gitconfig` (Emergent bot identity) from the repo root; add `campaign_runs/*.json` runtime data patterns to `.gitignore` (keep the two committed samples or move them to `docs/samples/`).
3. `make`-style helper (`justfile` or plain `dev.sh`): `test`, `serve`, `smoke` targets so nobody re-derives the commands.

### OAuth app registration (one-time console clicking, ~1 h)

- **Google Cloud Console** → new project → OAuth consent screen: External, Testing mode, add the owner as test user (Testing mode avoids the verification process; fine for personal use) → scopes `gmail.compose` (+ `gmail.send` + `gmail.readonly` for Phase 3) → Credentials → OAuth client (Web) → redirect URI `https://lead.…/oauth/gmail/callback` → put id/secret in env.
- **Microsoft Entra admin center** → App registrations → new → redirect URI `https://lead.…/oauth/outlook/callback` → API permissions: Microsoft Graph delegated `Mail.ReadWrite` (+ `Mail.Send`, `Mail.Read` for Phase 3) → certificates & secrets → client secret → env.

---

## 8. Skills you need (and where each is used)

| Skill | Depth needed | Used in | If you're weak here |
|---|---|---|---|
| Python 3.11+ (dataclasses, typing, threads) | solid | everywhere | Read `models.py` + `orchestrator.py` until they're obvious |
| FastAPI + Pydantic v2 | solid | api.py, new endpoints | fastapi.tiangolo.com tutorial, sections 1–8 |
| pytest/unittest + dependency injection | solid | every task | Copy the injected-fake pattern in `tests/test_oauth_clients.py` |
| Claude API (Messages, `parse`, structured output) | working | Phase 1, 2, 3 | platform.claude.com/docs; §4 of this doc is the contract |
| OAuth 2.0 auth-code flow (concept) | working | mailbox connect | Read `oauth_setup.py` top-to-bottom; it's a clean reference |
| Gmail API / Microsoft Graph mail | working | Phase 3 | `users.messages` + `/me/sendMail`,`/me/messages` docs only |
| DNS + email auth (SPF/DKIM/DMARC) | conceptual | §6.2 | One evening: read your own domain's records with `dig TXT` |
| Docker Compose + Traefik labels | working | Phase 4 | The existing compose file + traefik.io routing docs |
| React (read/modify, not architect) | basic | UI badges, pages | Pages in `frontend/src/pages/` are small and self-similar |
| Cold-outreach craft (what makes replies) | conceptual | prompts, review | The prompt rules in §4.3 encode it; keep emails short, specific, honest |

Explicitly NOT needed: Kubernetes, message queues, microservices, LangChain-style frameworks. Resist adding them.

---

## 9. Environment variable reference (production `.env`)

| Var | Phase | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | 1 | The brain. Without it: honest deterministic fallback. |
| `APOLLO_API_KEY` | 2 | Lead sourcing; absent → CSV-only. |
| `APP_BASE_URL` | 0 | `https://lead.hermes-agent-2bhv.srv1390211.hstgr.cloud` |
| `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET` | deploy | From §7 OAuth registration |
| `MICROSOFT_OAUTH_CLIENT_ID` / `MICROSOFT_OAUTH_CLIENT_SECRET` | deploy |〃 |
| `GOOGLE_OAUTH_REDIRECT_URI` / `MICROSOFT_OAUTH_REDIRECT_URI` | deploy | Default derives from APP_BASE_URL |
| `UNSUBSCRIBE_SECRET` | 3 | Long random string; rotating it invalidates old links (acceptable) |
| `DAILY_SEND_CAP` | 3 | Default 20; raise slowly per §6.2 |
| `STORAGE` | 4 | `json` (default) or `mongo` |
| `MONGO_URL` | 4 | Only when STORAGE=mongo |

---

## 10. Order of battle & definition of done

| Order | Work | Effort | Done when |
|---|---|---|---|
| 1 | Phase 0 foundation fixes | 1 day | §3 checklist all ticked |
| 2 | Phase 1 Claude brain | 1–2 days | §4 checklist; a non-rubber company gets sane AI output |
| 3 | Deploy privately (7.1, 7.2 step 1–2, 7.4) | 1 day | Public URL, Basic Auth, LE cert, smoke flow passes remotely |
| 4 | Phase 2 sourcing/enrichment | 2–3 days | §5 checklist; Apollo → drafts pipeline runs end-to-end |
| 5 | Phase 3 compliance→delivery→replies→sequences | 3–5 days | §6 checklist; first real campaign sent to ≤20 real leads |
| 6 | Phase 4 remainder (CI, Mongo when needed) | ongoing | CI green badge; backups running |

**The app "actually gets you leads" when:** one command/click sources 25 fresh ICP-matched leads, enriches and scores them, drafts personalized emails you approve in under 10 minutes, delivers them within caps, catches the replies, and never emails anyone who opted out — and the weekly funnel (sourced → drafted → approved → sent → replied) is visible on the dashboard. Build toward that sentence; when in doubt, pick the option that moves a real reply closer.

---

*Questions, ambiguities, or steps that didn't work as written: record them in `ROADMAP.md` under a "Playbook errata" heading rather than silently working around them.*
