# Email Outreach Draft-First MVP

This is a safe draft-first MVP core for an AI-assisted outbound email app.

It generates personalized email drafts from:
- a company profile description
- campaign settings
- a CSV/manual lead list
- a user-provided email template

It does not send email. Every draft has `approval_required: true`.

## What is implemented

- Business profile agent: converts company details into a structured business profile and Apollo-style filter suggestions.
- Lead qualification agent: scores leads by region/country, title, industry, website, and context.
- Email personalization agent: fills a template and adds opt-out language.
- Compliance agent: blocks missing emails, suppressed contacts, missing opt-out text, and MVP cap violations.
- Orchestrator: creates a draft campaign and skips unsafe/low-score leads.
- JSON persistence.
- CLI for CSV-to-draft campaign generation.
- FastAPI backend for health checks, LLM provider discovery, company profiling, campaign draft generation, campaign retrieval, draft review/approval, local draft artifact creation, Gmail/Outlook OAuth setup, mailbox status, and live draft creation.
- Browser frontend served at `/` with separate static assets under `/assets/` for company/campaign entry, LLM provider selection, optional website enrichment, CSV/Apollo lead sourcing, campaign history/reopen, campaign health metrics, draft generation, editing, approval, and mailbox draft creation.
- ApolloLeadProvider and `/leads/apollo/search` endpoint normalize Apollo people search results into the app's draft-ready lead shape, with CSV fallback when Apollo is not configured.
- LLMRouter abstraction for deterministic fallback, Codex/OpenAI-compatible, and Gemini/OpenAI-compatible draft/profile generation with safe deterministic fallback when credentials are missing or calls fail.
- ScraplingEnrichmentProvider for optional public lead-website context extraction, using Scrapling when installed and a safe static HTTP fallback otherwise.
- GmailApiDraftStore builds Gmail RFC 2822/base64url draft payloads and calls an injected OAuth-backed client only after approval; it still never sends email.
- OutlookApiDraftStore builds Microsoft Graph message payloads and calls an OAuth-backed Graph client only after approval; it still never sends email.
- OAuth setup endpoints and dashboard mailbox connection panel support Gmail and Outlook connect/status flows.

## What comes next

- Add reply/bounce/unsubscribe sync and lead response graph analytics.

## Test

```bash
cd /opt/data/email-outreach-mvp
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## API server

Run locally:

```bash
cd /opt/data/email-outreach-mvp
PYTHONPATH=src uvicorn outreach_mvp.api:app --reload
```

Open the dashboard:

```text
http://127.0.0.1:8000/
```

The dashboard currently supports:

- entering company profile details;
- entering campaign targeting and sender details;
- campaign history and reopening saved campaigns;
- pasting lead CSV data;
- generating draft emails;
- editing generated subject/body text;
- approving drafts;
- connecting Gmail/Outlook mailboxes;
- creating local Gmail/Outlook-shaped mailbox draft artifacts for approved drafts.

Live Gmail/Outlook draft creation is available after OAuth tokens are connected. The app creates drafts only; it does not send email.

Available endpoints:

- `GET /health` returns `{ "status": "ok" }`.
- `GET /llm/providers` lists switchable LLM providers and default models.
- `GET /mailboxes/status` reports Gmail/Outlook OAuth configuration and connection status.
- `GET /oauth/providers` returns the same mailbox OAuth provider status payload.
- `GET /oauth/gmail/start` and `GET /oauth/outlook/start` create provider authorization URLs.
- `GET /oauth/gmail/callback` and `GET /oauth/outlook/callback` exchange OAuth codes and persist token JSON under `campaign_runs/oauth_tokens/`.
- `POST /companies/profile` creates a structured business profile from company details.
- `POST /leads/apollo/search` searches Apollo when configured and returns normalized lead objects compatible with `/campaigns/draft`; when Apollo is not configured, use the CSV fallback.
- `POST /campaigns/draft` creates draft-first campaign output from company, campaign, and leads payloads. It persists the result to `campaign_runs/{campaign_id}.json`.
- `GET /campaigns` lists saved campaign summaries for reopen/history UI.
- `GET /campaigns/{campaign_id}` loads a saved campaign result.
- `GET /campaigns/{campaign_id}/drafts` lists reviewable drafts with stable draft IDs and review status.
- `PATCH /campaigns/{campaign_id}/drafts/{draft_id}/approve` marks a draft as approved and stores reviewer notes.
- `PATCH /campaigns/{campaign_id}/drafts/{draft_id}/edit` updates draft subject/body and resets approval status to edited/pending re-approval.
- `POST /campaigns/{campaign_id}/drafts/{draft_id}/mailbox-drafts` creates a safe local Gmail/Outlook-shaped draft artifact only after draft approval. With an injected Gmail client, `{ "provider": "gmail", "delivery": "gmail_api" }` creates a real Gmail draft instead of a local artifact. With an injected Outlook client, `{ "provider": "outlook", "delivery": "outlook_graph" }` creates a real Microsoft Graph draft.

Minimal API example:

```bash
curl -s http://127.0.0.1:8000/health
```

Draft campaign requests use this shape:

```json
{
  "company": {
    "name": "Acme Rubber Works",
    "website": "https://acme.example",
    "description": "Rubber products manufacturer for OEMs and industrial distributors.",
    "details": {"certifications": "ISO 9001"}
  },
  "campaign": {
    "name": "UAE distributor outreach",
    "target_country": "United Arab Emirates",
    "target_region": "UAE",
    "max_drafts": 10,
    "sender_name": "Maya",
    "sender_email": "maya@acme.example",
    "template": "Hi {{first_name}}, I noticed {{company_name}} works in {{lead_context}}. We manufacture {{value_prop}}. Best, {{sender_name}}",
    "target_titles": ["Procurement Manager", "Sourcing Manager"],
    "target_industries": ["Industrial", "Construction"]
  },
  "leads": [
    {
      "first_name": "Ahmed",
      "last_name": "Khan",
      "email": "ahmed@example.ae",
      "title": "Procurement Manager",
      "company_name": "Gulf Industrial Supplies",
      "country": "United Arab Emirates",
      "industry": "Industrial",
      "website": "https://gulf.example",
      "context": "industrial maintenance supplies in Dubai"
    }
  ],
  "llm_provider": "gemini",
  "llm_model": "gemini-3.1-pro-preview",
  "enrich_websites": true
}
```

Review workflow examples:

```bash
# List drafts for review
curl -s http://127.0.0.1:8000/campaigns/uae-distributor-outreach/drafts

# Approve a draft
curl -s -X PATCH http://127.0.0.1:8000/campaigns/uae-distributor-outreach/drafts/draft-1/approve \
  -H 'Content-Type: application/json' \
  -d '{"approved_by":"parmeet","notes":"Looks good"}'

# Create a Gmail-shaped local mailbox draft artifact after approval
curl -s -X POST http://127.0.0.1:8000/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts \
  -H 'Content-Type: application/json' \
  -d '{"provider":"gmail"}'

# Create an Outlook-shaped local mailbox draft artifact after approval
curl -s -X POST http://127.0.0.1:8000/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts \
  -H 'Content-Type: application/json' \
  -d '{"provider":"outlook"}'

# If the app is started with an injected OAuth-backed Gmail client, create a real Gmail draft
curl -s -X POST http://127.0.0.1:8000/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts \
  -H 'Content-Type: application/json' \
  -d '{"provider":"gmail","delivery":"gmail_api"}'

# If the app is started with an injected OAuth-backed Outlook client, create a real Outlook draft
curl -s -X POST http://127.0.0.1:8000/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts \
  -H 'Content-Type: application/json' \
  -d '{"provider":"outlook","delivery":"outlook_graph"}'
```

## OAuth-backed mailbox draft configuration

The dashboard includes a Mailbox Connections panel that calls:

```bash
curl -s http://127.0.0.1:8000/mailboxes/status
curl -s http://127.0.0.1:8000/oauth/gmail/start
curl -s http://127.0.0.1:8000/oauth/outlook/start
```

Configure OAuth apps with environment variables before starting the API:

- `APP_BASE_URL`: public base URL used to build default callback URLs, e.g. `https://app.example.com`.
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `GOOGLE_OAUTH_REDIRECT_URI`: defaults to `${APP_BASE_URL}/oauth/gmail/callback`.
- `MICROSOFT_OAUTH_CLIENT_ID`
- `MICROSOFT_OAUTH_CLIENT_SECRET`
- `MICROSOFT_OAUTH_REDIRECT_URI`: defaults to `${APP_BASE_URL}/oauth/outlook/callback`.

OAuth callback exchanges persist tokens under:

```text
campaign_runs/oauth_tokens/gmail_token.json
campaign_runs/oauth_tokens/outlook_token.json
```

The default API app also supports externally supplied token paths:

- `GMAIL_TOKEN_PATH` or `GOOGLE_TOKEN_PATH`: Google authorized-user token JSON with `https://www.googleapis.com/auth/gmail.compose` scope.
- `GOOGLE_CLIENT_SECRET_PATH`: optional Google OAuth client secret path, retained for setup tooling/documentation.
- `OUTLOOK_TOKEN_PATH`: JSON file containing a Microsoft Graph `access_token` with `Mail.ReadWrite` permission.
- `OUTLOOK_ACCESS_TOKEN`: direct Microsoft Graph access token fallback for development.

When no OAuth variables are present, local draft artifact creation still works and live delivery modes return `503` instead of sending or guessing credentials.

Required OAuth permissions:

- Gmail: `https://www.googleapis.com/auth/gmail.compose`
- Microsoft Graph delegated permission: `Mail.ReadWrite`

Live draft modes create drafts only. They do not call Gmail send or Microsoft Graph send.

## Lead CSV columns

```csv
first_name,last_name,email,title,company_name,country,industry,website,context
Ahmed,Khan,ahmed@example.ae,Procurement Manager,Gulf Industrial Supplies,United Arab Emirates,Industrial,https://gulf.example,industrial maintenance supplies in Dubai
```

## CLI example

```bash
PYTHONPATH=src python3 -m outreach_mvp.cli \
  --company-name "Acme Rubber Works" \
  --company-description "Rubber products manufacturer for OEMs and industrial distributors" \
  --campaign-name "UAE distributor outreach" \
  --target-country "United Arab Emirates" \
  --target-region "UAE" \
  --sender-name "Maya" \
  --sender-email "maya@acme.example" \
  --template "Hi {{first_name}}, I noticed {{company_name}} works in {{lead_context}}. We manufacture {{value_prop}}. Would it make sense to send a short catalogue? Best, {{sender_name}}" \
  --leads-csv sample_leads.csv \
  --max-drafts 10 \
  --llm-provider gemini \
  --llm-model gemini-3.1-pro-preview \
  --enrich-websites
```
