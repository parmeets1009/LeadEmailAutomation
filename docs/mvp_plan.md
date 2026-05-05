# Draft-First Email Outreach MVP Plan

Goal: Build a safe draft-first MVP that turns a company description, target region, lead list, and email template into reviewed personalized email drafts. It does not auto-send emails.

Architecture:
- Core Python package with deterministic orchestration and agent-like services.
- CSV/manual lead import first, with adapter interfaces for Apollo and Scrapling.
- JSON file storage for local MVP persistence.
- CLI demo for generating campaign drafts.
- Tests cover business profile generation, lead scoring, draft generation, compliance checks, and campaign orchestration.

MVP scope:
1. Create an AI-style business profile from plain company details using deterministic local logic as a safe placeholder.
2. Normalize manually supplied leads.
3. Score leads for country/region/title/company fit.
4. Generate personalized drafts from a user template and available lead/company context.
5. Enforce draft-first safety: daily cap, unsubscribe phrase, approval_required=true, and no sending.
6. Persist campaign results as JSON.

Future integrations:
- ApolloLeadProvider: calls Apollo MCP/API when a paid key has endpoint access.
- ScraplingEnrichmentProvider: fetches public company pages for personalization facts.
- Gmail/OutlookSender: creates drafts/sends only after explicit approval.
- LLMRouter: strong model for profiles/final emails; cheap model for scoring/classification.

Initial files:
- src/outreach_mvp/models.py
- src/outreach_mvp/profile_agent.py
- src/outreach_mvp/lead_agent.py
- src/outreach_mvp/email_agent.py
- src/outreach_mvp/compliance.py
- src/outreach_mvp/orchestrator.py
- src/outreach_mvp/storage.py
- src/outreach_mvp/cli.py
- tests/test_draft_workflow.py
