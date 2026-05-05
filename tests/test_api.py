import tempfile
import unittest
from pathlib import Path

from starlette.testclient import TestClient

from outreach_mvp.api import create_app


class ApiWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_health_endpoint_reports_ok(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_company_profile_endpoint_returns_structured_profile(self):
        response = self.client.post(
            "/companies/profile",
            json={
                "name": "Acme Rubber Works",
                "website": "https://acme.example",
                "description": "Rubber products manufacturer making gaskets and seals for industrial distributors.",
                "details": {"certifications": "ISO 9001"},
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["company_name"], "Acme Rubber Works")
        self.assertIn("Procurement Manager", body["buyer_personas"])
        self.assertIn("Custom rubber products", body["product_categories"])

    def test_create_and_get_draft_campaign(self):
        payload = {
            "company": {
                "name": "Acme Rubber Works",
                "website": "https://acme.example",
                "description": "Rubber products manufacturer for OEMs, industrial distributors, and construction suppliers.",
                "details": {"certifications": "ISO 9001"},
            },
            "campaign": {
                "name": "UAE distributor outreach",
                "target_country": "United Arab Emirates",
                "target_region": "UAE",
                "max_drafts": 2,
                "sender_name": "Maya",
                "sender_email": "maya@acme.example",
                "template": "Hi {{first_name}}, I noticed {{company_name}} works in {{lead_context}}. We manufacture {{value_prop}}. Best, {{sender_name}}",
                "target_titles": ["Procurement Manager", "Sourcing Manager"],
                "target_industries": ["Industrial", "Construction"],
            },
            "leads": [
                {
                    "first_name": "Ahmed",
                    "last_name": "Khan",
                    "email": "ahmed@example.ae",
                    "title": "Procurement Manager",
                    "company_name": "Gulf Industrial Supplies",
                    "country": "United Arab Emirates",
                    "industry": "Industrial",
                    "website": "https://gulf.example",
                    "context": "industrial maintenance supplies in Dubai",
                },
                {
                    "first_name": "Bob",
                    "last_name": "Smith",
                    "email": "bob@example.com",
                    "title": "Marketing Manager",
                    "company_name": "US Retail Co",
                    "country": "United States",
                    "industry": "Retail",
                    "website": "https://retail.example",
                    "context": "consumer retail",
                },
            ],
        }

        create_response = self.client.post("/campaigns/draft", json=payload)

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["campaign_id"], "uae-distributor-outreach")
        self.assertEqual(created["status"], "drafts_ready_for_review")
        self.assertEqual(len(created["drafts"]), 1)
        self.assertEqual(created["drafts"][0]["lead"]["email"], "ahmed@example.ae")
        self.assertEqual(created["skipped"]["bob@example.com"], "low_score")

        get_response = self.client.get("/campaigns/uae-distributor-outreach")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["campaign"]["name"], "UAE distributor outreach")

    def test_get_unknown_campaign_returns_404(self):
        response = self.client.get("/campaigns/not-found")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "campaign not found")


if __name__ == "__main__":
    unittest.main()
