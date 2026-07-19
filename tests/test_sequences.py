import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from outreach_mvp.api import create_app
from outreach_mvp.compliance import ComplianceAgent
from outreach_mvp.email_agent import EmailPersonalizationAgent
from outreach_mvp.models import CampaignInput, CompanyInput, LeadInput
from outreach_mvp.orchestrator import DraftFirstOrchestrator
from outreach_mvp.sequences import advance_campaign
from outreach_mvp.storage import JsonCampaignStore
from outreach_mvp.suppression import SuppressionStore

from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)

STAGES = [{"offset_days": 3, "template": "Hi {{first_name}}, just floating my earlier note about {{value_prop}}. {{sender_name}}"}]


def build_campaign(tmpdir, stages=None):
    company = CompanyInput("Acme", "", "Industrial pumps manufacturer", {})
    campaign = CampaignInput(
        "seq-test", "Oman", "", 5, "P", "p@example.com",
        "Hi {{first_name}}, {{value_prop}}", ["Procurement Manager"], ["Industrial"],
        stages=stages if stages is not None else list(STAGES),
    )
    lead = LeadInput("Said", "M", "said@example.om", "Procurement Manager", "Muscat Ind", "Oman", "Industrial", "", "pumps")
    result = DraftFirstOrchestrator().create_draft_campaign(company, campaign, [lead])
    store = JsonCampaignStore(Path(tmpdir))
    path = store.save(result)
    return store, path.stem


def make_agent():
    return EmailPersonalizationAgent(ComplianceAgent(), None)


class SequenceAdvanceTests(unittest.TestCase):
    def test_unsent_draft_produces_no_followup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store, cid = build_campaign(tmpdir)
            outcome = advance_campaign(store, cid, make_agent())
            self.assertEqual(outcome["created_count"], 0)
            self.assertEqual(outcome["skipped"][0]["reason"], "not_sent")

    def test_due_sent_draft_gets_pending_followup(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store, cid = build_campaign(tmpdir)
            store.mark_draft_sent(cid, "draft-1", "2026-07-01T10:00:00+00:00")
            now = datetime(2026, 7, 10, tzinfo=timezone.utc)
            outcome = advance_campaign(store, cid, make_agent(), now=now)

            self.assertEqual(outcome["created_count"], 1)
            reloaded = store.load_campaign(cid)
            self.assertEqual(len(reloaded.drafts), 2)
            followup = reloaded.drafts[1]
            self.assertEqual(followup.followup_of, "draft-1")
            self.assertEqual(followup.stage, 1)
            self.assertFalse(followup.approved)
            self.assertEqual(followup.review_status, "pending")
            self.assertIn("floating my earlier note", followup.body)

    def test_not_due_yet_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store, cid = build_campaign(tmpdir)
            store.mark_draft_sent(cid, "draft-1", "2026-07-09T10:00:00+00:00")
            now = datetime(2026, 7, 10, tzinfo=timezone.utc)
            outcome = advance_campaign(store, cid, make_agent(), now=now)
            self.assertEqual(outcome["created_count"], 0)
            self.assertEqual(outcome["skipped"][0]["reason"], "not_due")

    def test_replied_draft_never_advances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store, cid = build_campaign(tmpdir)
            store.mark_draft_sent(cid, "draft-1", "2026-07-01T10:00:00+00:00")
            store.mark_draft_replied(cid, "draft-1", "interested")
            outcome = advance_campaign(store, cid, make_agent(), now=datetime(2026, 7, 20, tzinfo=timezone.utc))
            self.assertEqual(outcome["created_count"], 0)
            self.assertEqual(outcome["skipped"][0]["reason"], "replied")

    def test_suppressed_lead_never_advances(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store, cid = build_campaign(tmpdir)
            store.mark_draft_sent(cid, "draft-1", "2026-07-01T10:00:00+00:00")
            suppression = SuppressionStore(Path(tmpdir) / "suppression.json")
            suppression.add("said@example.om", "test")
            outcome = advance_campaign(store, cid, make_agent(), suppression=suppression, now=datetime(2026, 7, 20, tzinfo=timezone.utc))
            self.assertEqual(outcome["created_count"], 0)
            self.assertEqual(outcome["skipped"][0]["reason"], "suppressed")

    def test_advance_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store, cid = build_campaign(tmpdir)
            store.mark_draft_sent(cid, "draft-1", "2026-07-01T10:00:00+00:00")
            now = datetime(2026, 7, 20, tzinfo=timezone.utc)
            first = advance_campaign(store, cid, make_agent(), now=now)
            second = advance_campaign(store, cid, make_agent(), now=now)
            self.assertEqual(first["created_count"], 1)
            self.assertEqual(second["created_count"], 0)
            reasons = {item["reason"] for item in second["skipped"]}
            self.assertIn("followup_exists", reasons)
            self.assertEqual(len(store.load_campaign(cid).drafts), 2)

    def test_no_stages_means_no_followups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store, cid = build_campaign(tmpdir, stages=[])
            store.mark_draft_sent(cid, "draft-1", "2026-07-01T10:00:00+00:00")
            outcome = advance_campaign(store, cid, make_agent(), now=datetime(2026, 7, 20, tzinfo=timezone.utc))
            self.assertEqual(outcome["created_count"], 0)


class AdvanceEndpointTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(os.environ, NO_LLM_KEYS)
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def test_advance_endpoint_creates_followup(self):
        payload = {
            "company": {"name": "Acme", "website": "", "description": "Industrial pumps manufacturer.", "details": {}},
            "campaign": {
                "name": "seq-api", "target_country": "Oman", "target_region": "", "max_drafts": 5,
                "sender_name": "P", "sender_email": "p@example.com",
                "template": "Hi {{first_name}}, {{value_prop}}",
                "target_titles": ["Procurement Manager"], "target_industries": ["Industrial"],
                "stages": [{"offset_days": 3, "template": "Hi {{first_name}}, following up. {{sender_name}}"}],
            },
            "leads": [{
                "first_name": "Said", "last_name": "M", "email": "said@example.om",
                "title": "Procurement Manager", "company_name": "X", "country": "Oman",
                "industry": "Industrial", "website": "", "context": "pumps",
            }],
            "llm_provider": "deterministic",
        }
        cid = self.client.post("/campaigns/draft", json=payload).json()["campaign_id"]
        JsonCampaignStore(Path(self.tmpdir.name)).mark_draft_sent(cid, "draft-1", "2026-07-01T10:00:00+00:00")

        response = self.client.post(f"/campaigns/{cid}/advance", json={"now": "2026-07-10T00:00:00+00:00"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["created_count"], 1)
        drafts = self.client.get(f"/campaigns/{cid}/drafts").json()["drafts"]
        self.assertEqual(len(drafts), 2)
        self.assertEqual(drafts[1]["followup_of"], "draft-1")

    def test_advance_unknown_campaign_404(self):
        self.assertEqual(self.client.post("/campaigns/nope/advance", json={}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
