# Draft-First Email Outreach MVP Plan

Goal: Build a safe draft-first MVP that turns a company description, target region, lead list, and email template into reviewed personalized email drafts. It does not auto-send emails.

Architecture:
- Core Python package with deterministic orchestration and agent-like services.
- CSV/manual lead import first, with adapter interfaces for Apollo and Scrapling.
- JSON file storage for local MVP persistence.
- CLI demo for generating campaign drafts.
- FastAPI backend exposing health, LLM provider discovery, profile, draft campaign, saved campaign retrieval, draft listing, draft approval, draft editing, approved local mailbox draft artifact endpoints, and OAuth-backed Gmail/Microsoft Graph draft creation paths.
- Built-in browser frontend at `/` with static assets under `/assets/` for company/campaign input, LLM provider selection, mailbox OAuth connection status/setup, optional Scrapling/static website enrichment, lead CSV paste, campaign health metrics, draft generation, draft editing, draft approval, and safe local/live mailbox draft creation.
- Tests cover business profile generation, LLM routing, Scrapling/static enrichment, lead scoring, draft generation, compliance checks, campaign orchestration, API behavior, frontend shell and static assets, OAuth setup/status endpoints, approval-gated local mailbox artifacts, and OAuth-backed Gmail/Outlook draft-client wiring.

MVP scope:
1. Create an AI-style business profile from plain company details using deterministic local logic as a safe fallback or LLMRouter-backed Codex/Gemini generation.
2. Normalize manually supplied leads.
3. Score leads for country/region/title/company fit.
4. Generate personalized drafts from a user template and available lead/company context.
5. Optionally enrich leads with public website title/meta/H1 context before scoring and drafting.
6. Enforce draft-first safety: daily cap, unsubscribe phrase, approval_required=true, and no sending.
7. Persist campaign results as JSON.
8. Support backend review workflow with stable draft IDs, pending/edited/approved states, reviewer notes, and edit persistence.
9. Create safe provider-shaped Gmail/Outlook local draft artifacts only after explicit draft approval; do not send email.
10. Build Gmail and Outlook API draft adapters that encode approved drafts for Gmail raw messages or Microsoft Graph JSON and call OAuth-backed clients without sending.
11. Provide a minimal browser dashboard for manually connecting mailboxes, generating, editing, approving, and mailbox-drafting before any live email-sending feature exists.
12. Preserve model metadata (`llm_provider`, `llm_model`, `prompt_version`) on campaign results for future analytics and auditability.

Development sequence:
1. LLMRouter for deterministic fallback, Codex, and Gemini profile/draft generation. Done.
2. ScraplingEnrichmentProvider for public company pages and personalization facts. Done.
3. Gmail/Outlook draft artifact adapter: creates local provider-shaped drafts only after explicit approval. Done.
4. Gmail API draft adapter: builds Gmail raw draft payloads and calls an injected OAuth-backed client only after approval. Done.
5. Outlook/Microsoft Graph draft adapter: builds Graph message JSON and calls an OAuth-backed client only after approval. Done.
6. First-class OAuth setup/status endpoints and dashboard mailbox connection panel for Gmail and Outlook. Done.
7. Frontend shell refactored into package static assets with campaign health metrics, review queue interactions, robust CSV parsing, and live/local mailbox draft delivery selection. Started.
8. ApolloLeadProvider: calls Apollo MCP/API when a paid key has endpoint access, with CSV fallback.

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
- src/outreach_mvp/api.py
- src/outreach_mvp/dashboard.py
- tests/test_draft_workflow.py
- tests/test_api.py
