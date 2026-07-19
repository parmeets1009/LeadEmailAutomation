import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from outreach_mvp.api import create_app
from outreach_mvp.contacted import ContactedStore
from outreach_mvp.llm import LLMRouter, StaticLLMClient
from outreach_mvp.models import CampaignInput, CompanyInput, LeadInput
from outreach_mvp.orchestrator import DraftFirstOrchestrator
from outreach_mvp.replies import ReplySyncService, extract_email, heuristic_classification
from outreach_mvp.storage import JsonCampaignStore
from outreach_mvp.suppression import SuppressionStore

from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)


class FakeReplyClient:
    def __init__(self, messages):
        self.messages = messages

    def list_recent_messages(self, newer_than_days=7):
        return self.messages


def build_campaign(tmpdir):
    company = CompanyInput("Acme", "", "Industrial pumps manufacturer", {})
    campaign = CampaignInput("reply-test", "Oman", "", 5, "P", "p@example.com", "Hi {{first_name}}, {{value_prop}}", ["Procurement Manager"], ["Industrial"])
    lead = LeadInput("Said", "M", "said@example.om", "Procurement Manager", "Muscat Ind", "Oman", "Industrial", "", "pumps")
    result = DraftFirstOrchestrator().create_draft_campaign(company, campaign, [lead])
    store = JsonCampaignStore(Path(tmpdir))
    path = store.save(result)
    return store, path.stem


class HeuristicTests(unittest.TestCase):
    def test_extract_email(self):
        self.assertEqual(extract_email("Said M <Said@Example.om>"), "said@example.om")
        self.assertEqual(extract_email("said@example.om"), "said@example.om")

    def test_keyword_classification(self):
        self.assertEqual(heuristic_classification("please UNSUBSCRIBE me")["suggested_action"], "remove_and_suppress")
        self.assertEqual(heuristic_classification("I am out of office until Monday")["category"], "out_of_office")
        self.assertEqual(heuristic_classification("not interested, thanks")["suggested_action"], "stop_sequence")
        self.assertEqual(heuristic_classification("tell me more about pricing")["category"], "other")


class ReplySyncTests(unittest.TestCase):
    def test_unsubscribe_reply_suppresses_and_marks_replied(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store, cid = build_campaign(tmpdir)
            contacted = ContactedStore(Path(tmpdir) / "contacted.json")
            contacted.add("said@example.om", cid, "draft-1")
            suppression = SuppressionStore(Path(tmpdir) / "suppression.json")
            service = ReplySyncService(store, contacted, suppression, llm_router=None)

            client = FakeReplyClient([
                {"from_email": "Said M <said@example.om>", "subject": "RE: pumps", "snippet": "please remove me from your list"},
                {"from_email": "stranger@nowhere.com", "subject": "spam", "snippet": "buy now"},
            ])
            summary = service.sync(client)

            self.assertEqual(summary["matched_count"], 1)
            self.assertEqual(summary["ignored_count"], 1)
            self.assertTrue(suppression.contains("said@example.om"))
            reloaded = store.load_campaign(cid)
            self.assertTrue(reloaded.drafts[0].replied)
            self.assertIn("unsubscribe", reloaded.drafts[0].reply_summary)

    def test_llm_classification_used_when_enabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store, cid = build_campaign(tmpdir)
            contacted = ContactedStore(Path(tmpdir) / "contacted.json")
            contacted.add("said@example.om", cid, "draft-1")
            suppression = SuppressionStore(Path(tmpdir) / "suppression.json")
            router = LLMRouter(provider="claude", client=StaticLLMClient(
                reply_response={"category": "interested", "summary": "Wants a catalogue.", "suggested_action": "reply_personally"}
            ))
            service = ReplySyncService(store, contacted, suppression, llm_router=router)
            client = FakeReplyClient([{"from_email": "said@example.om", "subject": "RE:", "snippet": "sounds good, send details"}])
            summary = service.sync(client)

            self.assertEqual(summary["matched"][0]["category"], "interested")
            self.assertFalse(suppression.contains("said@example.om"))
            self.assertTrue(store.load_campaign(cid).drafts[0].replied)


class ReplyEndpointTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(os.environ, NO_LLM_KEYS)
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def test_sync_endpoint_with_injected_client(self):
        client_fake = FakeReplyClient([])
        client = TestClient(create_app(storage_dir=Path(self.tmpdir.name), gmail_reply_client=client_fake))
        response = client.post("/mailboxes/gmail/sync-replies", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["matched_count"], 0)

    def test_sync_endpoint_503_when_not_connected(self):
        client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))
        response = client.post("/mailboxes/gmail/sync-replies", json={})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
