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

Future intelligence layer: Lead Response Graph
- Add a graphify-like module inside the app for mapping lead generation, lead attributes, campaigns, email variants, enrichment facts, sent emails, replies, bounces, unsubscribes, and conversions.
- This should be a product feature, not just a development tool: it analyzes which business types respond, which countries/industries/titles engage, which value propositions work, and which email contents underperform.
- Store graph nodes for CompanyProfile, Campaign, Lead, Organization, Industry, Country, BuyerPersona, EmailDraft, EmailVariant, SendEvent, ReplyEvent, BounceEvent, UnsubscribeEvent, EnrichmentFact, and Outcome.
- Store graph edges such as TARGETS, GENERATED, SENT_TO, WORKS_AT, LOCATED_IN, IN_INDUSTRY, USED_VALUE_PROP, PERSONALIZED_WITH, REPLIED_TO, BOUNCED, UNSUBSCRIBED, CONVERTED, and SIMILAR_TO.
- Produce analytics such as response rate by industry/title/country, best-performing subject lines, best-performing personalization facts, bounce-prone segments, unsubscribe-prone segments, and lead-score calibration.
- Feed graph insights back into the app to improve future lead scoring, email template recommendations, personalization prompts, campaign targeting, and send scheduling.
- Start simple with NetworkX/JSON graph exports, then move to Postgres graph tables or Neo4j if query complexity grows.

Additional product improvements to consider:
- A/B and multi-armed bandit testing for subject lines, CTAs, value propositions, and email length.
- Deliverability health module: SPF/DKIM/DMARC checks, bounce-rate thresholds, warm-up limits, sending-window recommendations, and spam-word scoring.
- Reply intelligence: classify replies as interested, pricing request, catalogue request, not interested, wrong person, out of office, bounce, unsubscribe, or follow-up later.
- Auto-generated reply drafts for positive responses, but still require user approval.
- Follow-up sequence builder with strict stop conditions on reply, bounce, or unsubscribe.
- ICP recommender that learns from positive replies and suggests better industries, titles, company sizes, and regions.
- Template library for manufacturers, exporters, distributors, SaaS, agencies, and local service businesses.
- Regional localization: adapt tone, wording, currency, business etiquette, and compliance footer by country/region.
- CRM/export integrations for HubSpot, Pipedrive, Salesforce, Zoho, Airtable, Google Sheets, and CSV.
- Product catalogue/attachment manager with safer link-based sharing and per-campaign landing pages.
- Human approval queues with lead score, personalization reason, source facts, compliance status, and suggested edits.
- Suppression and consent ledger with source, reason contacted, opt-out history, and audit trail.
- Campaign simulator that estimates expected drafts, send volume, cost, risk, and likely response before launch.
- Prompt/version tracking so each generated email is traceable to model, prompt, template, and source facts.

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
