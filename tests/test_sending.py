import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from outreach_mvp.api import create_app
from outreach_mvp.send_log import SendLog
from outreach_mvp.storage import JsonCampaignStore

from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)
SEND_ENV = {
    **NO_LLM_KEYS,
    "APP_BASE_URL": "https://test.example",
    "UNSUBSCRIBE_SECRET": "test-secret",
    "DAILY_SEND_CAP": "2",
}


class FakeGmailSendClient:
    def __init__(self):
        self.sent = []

    def send_message(self, raw_message):
        self.sent.append(raw_message)
        return {"id": f"gmail-msg-{len(self.sent)}"}


class FakeOutlookSendClient:
    def __init__(self):
        self.sent = []

    def send_mail(self, payload):
        self.sent.append(payload)
        return {}


def payload(delivery_mode="auto_send", postal="12 Industrial Way, Muscat", lead_count=3):
    leads = [
        {
            "first_name": f"L{i}",
            "last_name": "M",
            "email": f"lead{i}@example.om",
            "title": "Procurement Manager",
            "company_name": f"Co{i}",
            "country": "Oman",
            "industry": "Industrial",
            "website": "",
            "context": "pumps",
        }
        for i in range(lead_count)
    ]
    details = {"postal_address": postal} if postal else {}
    return {
        "company": {"name": "Acme", "website": "", "description": "Industrial pumps manufacturer.", "details": details},
        "campaign": {
            "name": "send-test",
            "target_country": "Oman",
            "target_region": "",
            "max_drafts": 10,
            "sender_name": "P",
            "sender_email": "p@example.com",
            "template": "Hi {{first_name}}, {{lead_context}} {{value_prop}} {{sender_name}}",
            "target_titles": ["Procurement Manager"],
            "target_industries": ["Industrial"],
            "delivery_mode": delivery_mode,
        },
        "leads": leads,
        "llm_provider": "deterministic",
    }


class SendEndpointTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(os.environ, SEND_ENV)
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.gmail = FakeGmailSendClient()
        self.client = TestClient(
            create_app(storage_dir=Path(self.tmpdir.name), gmail_send_client=self.gmail)
        )

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def _create(self, body=None):
        created = self.client.post("/campaigns/draft", json=body or payload()).json()
        return created["campaign_id"], created

    def _approve(self, cid, draft_id):
        response = self.client.patch(f"/campaigns/{cid}/drafts/{draft_id}/approve", json={"approved_by": "t"})
        assert response.status_code == 200, response.text

    def _send(self, cid, draft_id, provider="gmail"):
        return self.client.post(f"/campaigns/{cid}/drafts/{draft_id}/send", json={"provider": provider})

    def test_unapproved_draft_cannot_send(self):
        cid, _ = self._create()
        response = self._send(cid, "draft-1")
        self.assertEqual(response.status_code, 409)
        self.assertIn("approved", response.json()["detail"])
        self.assertEqual(self.gmail.sent, [])

    def test_draft_mode_campaign_cannot_send(self):
        cid, _ = self._create(payload(delivery_mode="draft"))
        self._approve(cid, "draft-1")
        response = self._send(cid, "draft-1")
        self.assertEqual(response.status_code, 409)
        self.assertIn("delivery_mode", response.json()["detail"])

    def test_missing_postal_address_blocks_send(self):
        cid, _ = self._create(payload(postal=""))
        self._approve(cid, "draft-1")
        response = self._send(cid, "draft-1")
        self.assertEqual(response.status_code, 409)
        self.assertIn("postal", response.json()["detail"])

    def test_successful_send_records_everything(self):
        cid, _ = self._create()
        self._approve(cid, "draft-1")
        response = self._send(cid, "draft-1")
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["status"], "sent")
        self.assertTrue(body["sent_at"])
        self.assertEqual(len(self.gmail.sent), 1)

        log = SendLog(Path(self.tmpdir.name) / "send_log.json")
        self.assertTrue(log.was_sent(cid, "draft-1"))
        stored = JsonCampaignStore(Path(self.tmpdir.name)).load_campaign(cid)
        self.assertTrue(stored.drafts[0].sent_at)

    def test_double_send_rejected(self):
        cid, _ = self._create()
        self._approve(cid, "draft-1")
        self.assertEqual(self._send(cid, "draft-1").status_code, 201)
        response = self._send(cid, "draft-1")
        self.assertEqual(response.status_code, 409)
        self.assertIn("already sent", response.json()["detail"])

    def test_daily_cap_blocks_third_send(self):
        cid, _ = self._create()
        for draft_id in ["draft-1", "draft-2", "draft-3"]:
            self._approve(cid, draft_id)
        self.assertEqual(self._send(cid, "draft-1").status_code, 201)
        self.assertEqual(self._send(cid, "draft-2").status_code, 201)
        response = self._send(cid, "draft-3")
        self.assertEqual(response.status_code, 409)
        self.assertIn("daily send cap", response.json()["detail"])
        self.assertEqual(len(self.gmail.sent), 2)

    def test_suppressed_recipient_blocks_send(self):
        cid, _ = self._create()
        self._approve(cid, "draft-1")
        from outreach_mvp.suppression import SuppressionStore

        SuppressionStore(Path(self.tmpdir.name) / "suppression.json").add("lead0@example.om", "test")
        response = self._send(cid, "draft-1")
        self.assertEqual(response.status_code, 409)
        self.assertIn("suppression", response.json()["detail"])

    def test_unconfigured_provider_returns_503(self):
        cid, _ = self._create()
        self._approve(cid, "draft-1")
        response = self._send(cid, "draft-1", provider="outlook")
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
