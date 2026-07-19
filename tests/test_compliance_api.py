import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from outreach_mvp.api import create_app
from outreach_mvp.suppression import SuppressionStore

from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)


def sample_payload(name="compliance-test"):
    return {
        "company": {"name": "Acme", "website": "", "description": "Industrial pumps manufacturer.", "details": {}},
        "campaign": {
            "name": name, "target_country": "Oman", "target_region": "", "max_drafts": 5,
            "sender_name": "P", "sender_email": "p@example.com",
            "template": "Hi {{first_name}}, {{value_prop}}",
            "target_titles": ["Procurement Manager"], "target_industries": ["Industrial"],
        },
        "leads": [{
            "first_name": "Said", "last_name": "M", "email": "said@example.om",
            "title": "Procurement Manager", "company_name": "X", "country": "Oman",
            "industry": "Industrial", "website": "", "context": "pumps",
        }],
        "llm_provider": "deterministic",
    }


class ComplianceApiTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(os.environ, NO_LLM_KEYS)
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def test_overview_empty(self):
        body = self.client.get("/compliance/overview").json()
        self.assertEqual(body["suppression_count"], 0)
        self.assertEqual(body["contacted_count"], 0)
        self.assertEqual(body["suppression"], [])

    def test_manual_suppress_shows_in_overview_and_blocks_drafting(self):
        response = self.client.post("/compliance/suppress", json={"email": "  Said@Example.om ", "reason": "phoned in"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["email"], "said@example.om")

        overview = self.client.get("/compliance/overview").json()
        self.assertEqual(overview["suppression_count"], 1)
        self.assertEqual(overview["suppression"][0]["email"], "said@example.om")
        self.assertEqual(overview["suppression"][0]["reason"], "phoned in")

        # The suppressed address must not be drafted.
        result = self.client.post("/campaigns/draft", json=sample_payload()).json()
        self.assertEqual(result["drafts"], [])
        self.assertEqual(result["skipped"]["said@example.om"], "suppressed")

        store = SuppressionStore(Path(self.tmpdir.name) / "suppression.json")
        self.assertTrue(store.contains("said@example.om"))

    def test_suppress_rejects_non_email(self):
        self.assertEqual(self.client.post("/compliance/suppress", json={"email": "notanemail"}).status_code, 422)

    def test_campaign_list_includes_sent_and_replied_counts(self):
        self.client.post("/campaigns/draft", json=sample_payload("counts-test"))
        campaigns = self.client.get("/campaigns").json()["campaigns"]
        self.assertTrue(campaigns)
        row = campaigns[0]
        self.assertIn("sent_count", row)
        self.assertIn("replied_count", row)
        self.assertIn("delivery_mode", row)
        self.assertEqual(row["sent_count"], 0)
        self.assertEqual(row["replied_count"], 0)


if __name__ == "__main__":
    unittest.main()
