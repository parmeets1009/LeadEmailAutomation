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
- FastAPI backend for health checks, company profiling, campaign draft generation, campaign retrieval, and draft review/approval.
- Minimal built-in dashboard at `/` for company/campaign entry, CSV lead paste, draft generation, editing, and approval.

## What comes next

- Replace deterministic profile/email logic with LLMRouter calls.
- Add ApolloLeadProvider using the configured Apollo MCP connector once the API key has endpoint access.
- Add ScraplingEnrichmentProvider to fetch public company website context.
- Add Gmail/Outlook draft creation after OAuth setup.
- Add web dashboard and manual approval UI.

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
- pasting lead CSV data;
- generating draft emails;
- editing generated subject/body text;
- approving drafts.

Available endpoints:

- `GET /health` returns `{ "status": "ok" }`.
- `POST /companies/profile` creates a structured business profile from company details.
- `POST /campaigns/draft` creates draft-first campaign output from company, campaign, and leads payloads. It persists the result to `campaign_runs/{campaign_id}.json`.
- `GET /campaigns/{campaign_id}` loads a saved campaign result.
- `GET /campaigns/{campaign_id}/drafts` lists reviewable drafts with stable draft IDs and review status.
- `PATCH /campaigns/{campaign_id}/drafts/{draft_id}/approve` marks a draft as approved and stores reviewer notes.
- `PATCH /campaigns/{campaign_id}/drafts/{draft_id}/edit` updates draft subject/body and resets approval status to edited/pending re-approval.

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
  ]
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

# Edit a draft; edited drafts are no longer approved until reviewed again
curl -s -X PATCH http://127.0.0.1:8000/campaigns/uae-distributor-outreach/drafts/draft-1/edit \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Updated subject","body":"Updated body with not relevant opt-out","edited_by":"parmeet"}'
```

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
  --max-drafts 10
```
