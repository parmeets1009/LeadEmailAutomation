import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from outreach_mvp.api import create_app
from outreach_mvp.compliance import ComplianceAgent
from outreach_mvp.contacted import ContactedStore
from outreach_mvp.email_agent import EmailPersonalizationAgent
from outreach_mvp.models import BusinessProfile, CampaignInput, LeadInput, LeadScore
from outreach_mvp.orchestrator import DraftFirstOrchestrator
from outreach_mvp.suppression import SuppressionStore
from outreach_mvp.unsubscribe import make_token, unsubscribe_url, verify_token

from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)


def sample_payload(**campaign_overrides):
    campaign = {
        "name": "contact-test",
        "target_country": "Oman",
        "target_region": "",
        "max_drafts": 5,
        "sender_name": "P",
        "sender_email": "p@example.com",
        "template": "Hi {{first_name}}, {{lead_context}} {{value_prop}} {{sender_name}}",
        "target_titles": ["Procurement Manager"],
        "target_industries": ["Industrial"],
    }
    campaign.update(campaign_overrides)
    return {
        "company": {"name": "Acme", "website": "", "description": "Industrial pumps manufacturer.", "details": {}},
        "campaign": campaign,
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


class ContactedStoreTests(unittest.TestCase):
    def test_store_roundtrip_and_normalization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ContactedStore(Path(tmpdir) / "contacted.json")
            self.assertFalse(store.was_contacted("a@b.co"))
            store.add(" A@B.co ", "camp-1", "draft-1")
            self.assertTrue(store.was_contacted("a@b.co"))
            self.assertEqual(store.lookup("a@b.co")["campaign_id"], "camp-1")
            self.assertEqual(store.count(), 1)

    def test_orchestrator_skips_already_contacted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            contacted = ContactedStore(Path(tmpdir) / "contacted.json")
            contacted.add("said@example.om", "old-camp", "draft-1")
            payload = sample_payload()
            from outreach_mvp.models import CompanyInput

            company = CompanyInput("Acme", "", "Industrial pumps manufacturer", {})
            campaign = CampaignInput(**{k: v for k, v in payload["campaign"].items()})
            lead = LeadInput(**payload["leads"][0])

            result = DraftFirstOrchestrator(contacted_store=contacted).create_draft_campaign(company, campaign, [lead])
            self.assertEqual(result.drafts, [])
            self.assertEqual(result.skipped["said@example.om"], "already_contacted")

            rerun = DraftFirstOrchestrator(contacted_store=contacted, allow_recontact=True).create_draft_campaign(company, campaign, [lead])
            self.assertEqual(len(rerun.drafts), 1)


class ApiContactedFlowTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(os.environ, NO_LLM_KEYS)
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def test_mailbox_draft_marks_contacted_and_next_campaign_skips(self):
        created = self.client.post("/campaigns/draft", json=sample_payload()).json()
        cid = created["campaign_id"]
        self.client.patch(f"/campaigns/{cid}/drafts/draft-1/approve", json={"approved_by": "t"})
        mailbox = self.client.post(f"/campaigns/{cid}/drafts/draft-1/mailbox-drafts", json={"provider": "gmail"})
        self.assertEqual(mailbox.status_code, 201)

        second = self.client.post("/campaigns/draft", json=sample_payload(name="contact-test-2")).json()
        self.assertEqual(second["drafts"], [])
        self.assertEqual(second["skipped"]["said@example.om"], "already_contacted")

        third_payload = sample_payload(name="contact-test-3")
        third_payload["allow_recontact"] = True
        third = self.client.post("/campaigns/draft", json=third_payload).json()
        self.assertEqual(len(third["drafts"]), 1)


class UnsubscribeTokenTests(unittest.TestCase):
    def test_token_roundtrip(self):
        token = make_token("Person@Example.com", "secret")
        self.assertEqual(verify_token(token, "secret"), "person@example.com")

    def test_tampered_and_garbage_tokens_rejected(self):
        token = make_token("person@example.com", "secret")
        self.assertIsNone(verify_token(token, "other-secret"))
        self.assertIsNone(verify_token(token[:-1] + ("0" if token[-1] != "0" else "1"), "secret"))
        self.assertIsNone(verify_token("garbage", "secret"))
        self.assertIsNone(verify_token("", "secret"))


class UnsubscribeEndpointTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(os.environ, {**NO_LLM_KEYS, "UNSUBSCRIBE_SECRET": "test-secret"})
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def test_unsubscribe_flow_suppresses_email_permanently(self):
        token = make_token("said@example.om", "test-secret")
        confirm = self.client.get(f"/u/{token}")
        self.assertEqual(confirm.status_code, 200)
        self.assertIn("said@example.om", confirm.text)

        apply_response = self.client.post(f"/u/{token}")
        self.assertEqual(apply_response.status_code, 200)
        self.assertIn("unsubscribed", apply_response.text.lower())

        store = SuppressionStore(Path(self.tmpdir.name) / "suppression.json")
        self.assertTrue(store.contains("said@example.om"))

        # The suppressed address must never be drafted again.
        result = self.client.post("/campaigns/draft", json=sample_payload(name="post-unsub")).json()
        self.assertEqual(result["drafts"], [])
        self.assertEqual(result["skipped"]["said@example.om"], "suppressed")

    def test_invalid_token_never_500s(self):
        self.assertEqual(self.client.get("/u/not-a-token").status_code, 200)
        self.assertIn("not valid", self.client.get("/u/not-a-token").text)
        self.assertEqual(self.client.post("/u/not-a-token").status_code, 200)


class FooterTests(unittest.TestCase):
    def test_footer_contains_link_and_identity_when_configured(self):
        agent = EmailPersonalizationAgent(
            ComplianceAgent(),
            None,
            unsubscribe_base_url="https://app.example",
            unsubscribe_secret="test-secret",
        )
        profile = BusinessProfile(
            company_name="Acme", website="", summary="s", product_categories=[], buyer_personas=[],
            target_industries=[], value_propositions=["pumps"], suggested_apollo_filters={},
            postal_address="12 Industrial Way, Muscat",
        )
        campaign = CampaignInput("t", "Oman", "", 5, "P", "p@example.com", "Hi {{first_name}}", ["x"], ["y"])
        lead = LeadInput("Said", "M", "said@example.om", "PM", "X", "Oman", "Industrial", "")
        draft = agent.draft(profile, campaign, lead, LeadScore(90, []))
        expected_url = unsubscribe_url("https://app.example", "said@example.om", "test-secret")
        self.assertIn(expected_url, draft.body)
        self.assertIn("12 Industrial Way, Muscat", draft.body)
        self.assertEqual(draft.compliance.status, "passed")


if __name__ == "__main__":
    unittest.main()
