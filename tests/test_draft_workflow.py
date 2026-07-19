import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from outreach_mvp.models import CompanyInput, CampaignInput, LeadInput
from outreach_mvp.orchestrator import DraftFirstOrchestrator
from outreach_mvp.llm import LLMRouter, StaticLLMClient
from outreach_mvp.enrichment import ScraplingEnrichmentProvider, StaticPageFetcher
from outreach_mvp.storage import JsonCampaignStore


class DraftFirstWorkflowTests(unittest.TestCase):
    def test_llm_router_switches_between_providers(self):
        no_keys = {"ANTHROPIC_API_KEY": "", "OPENAI_API_KEY": "", "GOOGLE_API_KEY": "", "GEMINI_API_KEY": ""}
        with mock.patch.dict(os.environ, no_keys):
            self.assertEqual(LLMRouter(provider="claude").provider, "claude")
            self.assertEqual(LLMRouter(provider="codex").provider, "codex")
            self.assertEqual(LLMRouter(provider="gemini").provider, "gemini")
            self.assertEqual(LLMRouter(provider="deterministic").provider, "deterministic")

        with self.assertRaisesRegex(ValueError, "Unsupported LLM provider"):
            LLMRouter(provider="unknown")

    def test_llm_router_uses_injected_client_for_profile_and_email(self):
        client = StaticLLMClient(
            profile_response={
                "summary": "LLM summary for Acme",
                "product_categories": ["LLM gaskets"],
                "buyer_personas": ["LLM Buyer"],
                "target_industries": ["LLM Industrial"],
                "value_propositions": ["LLM value prop"],
                "suggested_apollo_filters": {"person_titles": ["LLM Buyer"]},
            },
            draft_response={
                "subject": "LLM subject",
                "body": "LLM body for Ahmed",
                "personalization_reason": "LLM reason",
            },
        )
        router = LLMRouter(provider="gemini", model="gemini-3.1-pro-preview", client=client)
        company = CompanyInput("Acme", "", "Rubber manufacturer", {})
        campaign = CampaignInput("Test", "UAE", "UAE", 1, "Maya", "maya@example.com", "Hello {{first_name}}", ["Procurement Manager"], ["Industrial"])
        lead = LeadInput("Ahmed", "Khan", "ahmed@example.ae", "Procurement Manager", "Gulf", "UAE", "Industrial", "", "industrial supplies")

        result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, campaign, [lead])

        self.assertEqual(result.business_profile.summary, "LLM summary for Acme")
        self.assertEqual(result.drafts[0].subject, "LLM subject")
        self.assertIn("not relevant", result.drafts[0].body.lower())
        self.assertTrue(result.drafts[0].approval_required)
        self.assertEqual(result.llm_provider, "gemini")
        self.assertEqual(result.llm_model, "gemini-3.1-pro-preview")

    def test_scrapling_enrichment_extracts_public_website_context(self):
        fetcher = StaticPageFetcher({
            "https://gulf.example": """
            <html><head><title>Gulf Industrial Supplies</title>
            <meta name="description" content="Industrial maintenance and construction supply distributor in Dubai." />
            </head><body><h1>Industrial maintenance supplies</h1></body></html>
            """
        })
        provider = ScraplingEnrichmentProvider(fetcher=fetcher)
        lead = LeadInput("Ahmed", "Khan", "ahmed@example.ae", "Procurement Manager", "Gulf", "UAE", "Industrial", "https://gulf.example", "")

        enriched = provider.enrich(lead)

        self.assertIn("Gulf Industrial Supplies", enriched.context)
        self.assertIn("Industrial maintenance", enriched.context)

    def test_orchestrator_uses_enrichment_before_scoring_and_drafting(self):
        fetcher = StaticPageFetcher({
            "https://gulf.example": "<title>Gulf Industrial Supplies</title><meta name='description' content='Industrial maintenance distributor in Dubai.'>"
        })
        provider = ScraplingEnrichmentProvider(fetcher=fetcher)
        company = CompanyInput("Acme", "", "Rubber products manufacturer", {})
        campaign = CampaignInput("Enrich", "UAE", "UAE", 1, "Maya", "maya@example.com", "Hi {{first_name}}, I saw {{lead_context}}. {{value_prop}}", ["Procurement Manager"], ["Industrial"])
        lead = LeadInput("Ahmed", "Khan", "ahmed@example.ae", "Procurement Manager", "Gulf", "UAE", "Industrial", "https://gulf.example", "")

        result = DraftFirstOrchestrator(enrichment_provider=provider).create_draft_campaign(company, campaign, [lead])

        self.assertEqual(len(result.drafts), 1)
        self.assertIn("Industrial maintenance distributor", result.drafts[0].body)
        self.assertIn("website_enriched_context", result.drafts[0].lead_score.reasons)

    def test_business_profile_extracts_icp_and_value_props_for_manufacturer(self):
        company = CompanyInput(
            name="Acme Rubber Works",
            website="https://acme-rubber.example",
            description="We are a rubber products manufacturer making custom gaskets, seals, mats and molded parts for industrial buyers.",
            details={"certifications": "ISO 9001", "export_markets": "UAE, Saudi Arabia"},
        )

        result = DraftFirstOrchestrator().profile_company(company)

        self.assertEqual(result.company_name, "Acme Rubber Works")
        self.assertIn("rubber", result.summary.lower())
        self.assertIn("Procurement Manager", result.buyer_personas)
        self.assertIn("Industrial", result.target_industries)
        self.assertIn("custom rubber products", " ".join(result.value_propositions).lower())
        self.assertIn("person_titles", result.suggested_apollo_filters)

    def test_campaign_generates_only_top_scored_region_matched_drafts(self):
        company = CompanyInput(
            name="Acme Rubber Works",
            website="https://acme-rubber.example",
            description="Rubber products manufacturer for OEMs, industrial distributors, and construction suppliers.",
            details={"certifications": "ISO 9001"},
        )
        campaign = CampaignInput(
            name="UAE distributor outreach",
            target_country="United Arab Emirates",
            target_region="UAE",
            max_drafts=2,
            sender_name="Maya",
            sender_email="maya@acme-rubber.example",
            template="Hi {{first_name}},\n\nI noticed {{company_name}} works in {{lead_context}}. We manufacture {{value_prop}}.\n\nWould it make sense to send a short catalogue?\n\nBest,\n{{sender_name}}",
            target_titles=["Procurement Manager", "Sourcing Manager"],
            target_industries=["Industrial", "Construction"],
        )
        leads = [
            LeadInput(first_name="Ahmed", last_name="Khan", email="ahmed@example.ae", title="Procurement Manager", company_name="Gulf Industrial Supplies", country="United Arab Emirates", industry="Industrial", website="https://gulf.example", context="industrial maintenance supplies in Dubai"),
            LeadInput(first_name="Sara", last_name="Noor", email="sara@example.ae", title="Sourcing Manager", company_name="BuildRight UAE", country="UAE", industry="Construction", website="https://buildright.example", context="construction materials procurement"),
            LeadInput(first_name="Bob", last_name="Smith", email="bob@example.com", title="Marketing Manager", company_name="US Retail Co", country="United States", industry="Retail", website="https://retail.example", context="consumer retail"),
        ]

        result = DraftFirstOrchestrator().create_draft_campaign(company, campaign, leads)

        self.assertEqual(len(result.drafts), 2)
        self.assertEqual([draft.lead.email for draft in result.drafts], ["ahmed@example.ae", "sara@example.ae"])
        self.assertTrue(all(draft.approval_required for draft in result.drafts))
        self.assertTrue(all("unsubscribe" in draft.body.lower() or "not relevant" in draft.body.lower() for draft in result.drafts))
        self.assertTrue(all(draft.compliance.status == "passed" for draft in result.drafts))
        self.assertGreaterEqual(result.drafts[0].lead_score.score, result.drafts[1].lead_score.score)

    def test_compliance_blocks_missing_email_and_unsubscribed_leads(self):
        company = CompanyInput(name="Acme", website="", description="Rubber products manufacturer", details={})
        campaign = CampaignInput(
            name="Test",
            target_country="UAE",
            target_region="UAE",
            max_drafts=10,
            sender_name="Maya",
            sender_email="maya@acme.example",
            template="Hello {{first_name}}, {{value_prop}}",
            target_titles=["Procurement Manager"],
            target_industries=["Industrial"],
        )
        leads = [
            LeadInput(first_name="No", last_name="Email", email="", title="Procurement Manager", company_name="No Email LLC", country="UAE", industry="Industrial", website="", context=""),
            LeadInput(first_name="Opt", last_name="Out", email="optout@example.ae", title="Procurement Manager", company_name="Opt Out LLC", country="UAE", industry="Industrial", website="", context=""),
            LeadInput(first_name="Good", last_name="Lead", email="good@example.ae", title="Procurement Manager", company_name="Good LLC", country="UAE", industry="Industrial", website="", context=""),
        ]

        result = DraftFirstOrchestrator(suppression_list={"optout@example.ae"}).create_draft_campaign(company, campaign, leads)

        self.assertEqual(len(result.drafts), 1)
        self.assertEqual(result.drafts[0].lead.email, "good@example.ae")
        self.assertEqual(result.skipped[""], "missing_email")
        self.assertEqual(result.skipped["optout@example.ae"], "suppressed")

    def test_campaign_result_can_be_persisted_as_json(self):
        company = CompanyInput(name="Acme", website="", description="Rubber products manufacturer", details={})
        campaign = CampaignInput(
            name="Persist",
            target_country="UAE",
            target_region="UAE",
            max_drafts=1,
            sender_name="Maya",
            sender_email="maya@acme.example",
            template="Hello {{first_name}}, {{value_prop}}",
            target_titles=["Procurement Manager"],
            target_industries=["Industrial"],
        )
        leads = [LeadInput(first_name="Good", last_name="Lead", email="good@example.ae", title="Procurement Manager", company_name="Good LLC", country="UAE", industry="Industrial", website="", context="industrial supplies")]
        result = DraftFirstOrchestrator().create_draft_campaign(company, campaign, leads)

        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonCampaignStore(Path(tmpdir))
            saved_path = store.save(result)
            loaded = store.load(saved_path.name)

        self.assertEqual(loaded.campaign.name, "Persist")
        self.assertEqual(loaded.drafts[0].lead.email, "good@example.ae")
        self.assertEqual(loaded.status, "drafts_ready_for_review")


if __name__ == "__main__":
    unittest.main()
