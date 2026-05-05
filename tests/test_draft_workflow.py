import tempfile
import unittest
from pathlib import Path

from outreach_mvp.models import CompanyInput, CampaignInput, LeadInput
from outreach_mvp.orchestrator import DraftFirstOrchestrator
from outreach_mvp.storage import JsonCampaignStore


class DraftFirstWorkflowTests(unittest.TestCase):
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
