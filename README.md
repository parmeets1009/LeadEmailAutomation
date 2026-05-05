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

## What comes next

- Replace deterministic profile/email logic with LLMRouter calls.
- Add ApolloLeadProvider using the configured Apollo MCP connector once the API key has endpoint access.
- Add ScraplingEnrichmentProvider to fetch public company website context.
- Add Gmail/Outlook draft creation after OAuth setup.
- Add web dashboard and manual approval UI.

## Test

```bash
cd /opt/data/email-outreach-mvp
PYTHONPATH=src python3 -m unittest tests.test_draft_workflow -v
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
