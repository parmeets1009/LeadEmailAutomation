import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from outreach_mvp.api import create_app
from outreach_mvp.compliance import ComplianceAgent
from outreach_mvp.models import CampaignInput, CompanyInput, LeadInput
from outreach_mvp.orchestrator import DraftFirstOrchestrator

from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)


def sample_payload(max_drafts=5):
    return {
        "company": {"name": "Acme", "website": "", "description": "Industrial pumps manufacturer.", "details": {}},
        "campaign": {
            "name": "guardrail-test",
            "target_country": "Oman",
            "target_region": "",
            "max_drafts": max_drafts,
            "sender_name": "P",
            "sender_email": "p@example.com",
            "template": "Hi {{first_name}}, {{lead_context}} {{value_prop}} {{sender_name}}",
            "target_titles": ["Procurement Manager"],
            "target_industries": ["Industrial"],
        },
        "leads": [
            {
                "first_name": "Said",
                "last_name": "M",
                "email": "said@example.om",
                "title": "Procurement Manager",
                "company_name": "Muscat Ind",
                "country": "Oman",
                "industry": "Industrial",
                "website": "",
                "context": "pumps",
            }
        ],
        "llm_provider": "deterministic",
    }


class MaxDraftsValidationTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(os.environ, NO_LLM_KEYS)
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def test_max_drafts_over_50_returns_422(self):
        response = self.client.post("/campaigns/draft", json=sample_payload(max_drafts=60))
        self.assertEqual(response.status_code, 422)
        self.assertIn("max_drafts", str(response.json()))

    def test_max_drafts_zero_returns_422(self):
        response = self.client.post("/campaigns/draft", json=sample_payload(max_drafts=0))
        self.assertEqual(response.status_code, 422)

    def test_max_drafts_50_is_accepted_and_produces_drafts(self):
        response = self.client.post("/campaigns/draft", json=sample_payload(max_drafts=50))
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()["drafts"]), 1)


class EmailFormatTests(unittest.TestCase):
    def test_invalid_email_format_precheck(self):
        agent = ComplianceAgent()
        bad = LeadInput("A", "B", "notanemail", "T", "C", "Oman", "Industrial", "")
        self.assertEqual(agent.precheck_lead(bad), "invalid_email_format")
        good = LeadInput("A", "B", "a@b.co", "T", "C", "Oman", "Industrial", "")
        self.assertIsNone(agent.precheck_lead(good))

    def test_invalid_email_lead_is_skipped_by_orchestrator(self):
        company = CompanyInput("Acme", "", "Industrial pumps manufacturer", {})
        campaign = CampaignInput("t", "Oman", "", 5, "P", "p@example.com", "Hi {{first_name}}", ["Procurement Manager"], ["Industrial"])
        lead = LeadInput("Bad", "Email", "not-an-email", "Procurement Manager", "X", "Oman", "Industrial", "", "pumps")
        result = DraftFirstOrchestrator().create_draft_campaign(company, campaign, [lead])
        self.assertEqual(result.drafts, [])
        self.assertEqual(result.skipped["not-an-email"], "invalid_email_format")


class ComplianceHardeningTests(unittest.TestCase):
    def test_check_draft_flags_invalid_email_format(self):
        agent = ComplianceAgent()
        campaign = CampaignInput("t", "Oman", "", 5, "P", "p@example.com", "Hi", ["Procurement Manager"], ["Industrial"])
        bad = LeadInput("A", "B", "notanemail", "T", "C", "Oman", "Industrial", "")
        result = agent.check_draft(bad, campaign, "body with unsubscribe link")
        self.assertEqual(result.status, "failed")
        self.assertIn("invalid_email_format", result.reasons)

    def test_suppression_entries_are_stripped(self):
        agent = ComplianceAgent(suppression_list={"  opt@example.om  "})
        lead = LeadInput("O", "P", "opt@example.om", "T", "C", "Oman", "Industrial", "")
        self.assertEqual(agent.precheck_lead(lead), "suppressed")

    def test_orchestrator_caps_max_drafts_over_50_without_zero_drafts_trap(self):
        # The CLI path has no pydantic validation, so the orchestrator itself must
        # cap at 50 and never reintroduce the old compliance zero-drafts trap.
        company = CompanyInput("Acme", "", "Industrial pumps manufacturer", {})
        campaign = CampaignInput("big", "Oman", "", 60, "P", "p@example.com", "Hi {{first_name}}, {{value_prop}}", ["Procurement Manager"], ["Industrial"])
        leads = [
            LeadInput("L", str(i), f"lead{i}@example.om", "Procurement Manager", f"Co{i}", "Oman", "Industrial", "", "pumps")
            for i in range(55)
        ]
        result = DraftFirstOrchestrator().create_draft_campaign(company, campaign, leads)
        self.assertEqual(len(result.drafts), 50)
        self.assertTrue(all(d.compliance.status == "passed" for d in result.drafts))

    def test_score_threshold_zero_is_respected(self):
        company = CompanyInput("Acme", "", "Industrial pumps manufacturer", {})
        campaign = CampaignInput(
            "zero", "Oman", "", 5, "P", "p@example.com", "Hi {{first_name}}, {{value_prop}}",
            ["Procurement Manager"], ["Industrial"], score_threshold=0,
        )
        weak = LeadInput("W", "L", "weak@example.de", "Intern", "X", "Germany", "Retail", "", "misc")
        result = DraftFirstOrchestrator(llm_scoring=False).create_draft_campaign(company, campaign, [weak])
        self.assertEqual(len(result.drafts), 1)


class FooterInvariantTests(unittest.TestCase):
    def test_footer_always_present_in_passed_drafts(self):
        company = CompanyInput("Acme", "", "Industrial pumps manufacturer", {})
        campaign = CampaignInput("t", "Oman", "", 5, "P", "p@example.com", "Hi {{first_name}}, short note.", ["Procurement Manager"], ["Industrial"])
        lead = LeadInput("Said", "M", "said@example.om", "Procurement Manager", "X", "Oman", "Industrial", "", "pumps")
        result = DraftFirstOrchestrator().create_draft_campaign(company, campaign, [lead])
        self.assertEqual(len(result.drafts), 1)
        body = result.drafts[0].body.lower()
        self.assertTrue("not relevant" in body or "unsubscribe" in body)
        self.assertEqual(result.drafts[0].compliance.status, "passed")


if __name__ == "__main__":
    unittest.main()
