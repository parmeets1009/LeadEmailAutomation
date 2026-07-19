import base64
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from outreach_mvp.api import create_app

# Blank every external-service env var so tests are hermetic regardless of the
# developer's shell (empty string is falsy — no real client is ever built).
from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)


class FakeGmailDraftClient:
    def __init__(self):
        self.raw_messages = []

    def create_draft(self, raw_message: str) -> dict[str, str]:
        self.raw_messages.append(raw_message)
        return {"id": "gmail-draft-123", "message_id": "gmail-message-456"}


class FakeOutlookDraftClient:
    def __init__(self):
        self.messages = []

    def create_draft(self, message: dict) -> dict[str, str]:
        self.messages.append(message)
        return {"id": "outlook-draft-789"}


class FakeApolloClient:
    def __init__(self):
        self.calls = []

    def search_people(self, *, filters, page, per_page):
        self.calls.append({"filters": filters, "page": page, "per_page": per_page})
        return {
            "people": [
                {
                    "first_name": "Ahmed",
                    "last_name": "Khan",
                    "email": "ahmed@example.ae",
                    "title": "Procurement Manager",
                    "organization": {"name": "Gulf Industrial Supplies", "industry": "Industrial", "website_url": "https://gulf.example"},
                    "country": "United Arab Emirates",
                }
            ]
        }


class ApiWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(os.environ, NO_LLM_KEYS)
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def test_health_endpoint_reports_ok(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_llm_providers_endpoint_lists_switchable_providers(self):
        response = self.client.get("/llm/providers")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["default_provider"], "deterministic")
        self.assertIn("claude", body["available_providers"])
        self.assertIn("codex", body["available_providers"])
        self.assertIn("gemini", body["available_providers"])
        self.assertEqual(body["default_models"]["claude"], "claude-opus-4-8")

    def test_llm_default_provider_is_claude_when_key_is_configured(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))
            body = client.get("/llm/providers").json()
        self.assertEqual(body["default_provider"], "claude")

    def test_dashboard_endpoint_serves_review_ui(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        html = response.text
        self.assertIn("Lead Email Automation", html)
        self.assertIn("Company Profile", html)
        self.assertIn("Campaign Builder", html)
        self.assertIn("LLM provider", html)
        self.assertIn("claude-opus-4-8", html)
        self.assertIn("Enrich lead websites", html)
        self.assertIn("Lead CSV", html)
        self.assertIn("Draft Review", html)
        self.assertIn("Mailbox Connections", html)
        self.assertIn("Connect Gmail", html)
        self.assertIn("Connect Outlook", html)
        self.assertIn("Campaign History", html)
        self.assertIn("/mailboxes/status", html)
        self.assertIn("/oauth/gmail/start", html)
        self.assertIn("/oauth/outlook/start", html)
        self.assertIn("/campaigns", html)
        self.assertIn("/campaigns/draft", html)
        self.assertIn("mailbox-drafts", html)
        self.assertIn("/drafts/draft-1/approve", html)
        self.assertIn("/drafts/draft-1/edit", html)
        self.assertIn('/assets/app.css', html)
        self.assertIn('/assets/app.js', html)
        self.assertIn('Campaign Health', html)
        self.assertIn('Review Queue', html)

    def test_frontend_assets_are_served_for_dashboard(self):
        css_response = self.client.get("/assets/app.css")
        js_response = self.client.get("/assets/app.js")

        self.assertEqual(css_response.status_code, 200)
        self.assertIn("text/css", css_response.headers["content-type"])
        self.assertIn("--accent", css_response.text)
        self.assertIn("dashboard-shell", css_response.text)

        self.assertEqual(js_response.status_code, 200)
        self.assertIn("javascript", js_response.headers["content-type"])
        self.assertIn("function csvToLeads", js_response.text)
        self.assertIn("function renderDrafts", js_response.text)
        self.assertIn("function loadCampaignHistory", js_response.text)
        self.assertIn("function openCampaign", js_response.text)
        self.assertIn("Review Queue", js_response.text)
        self.assertIn("Apollo", js_response.text)

    def test_apollo_lead_search_returns_normalized_leads_from_injected_client(self):
        apollo_client = FakeApolloClient()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name), apollo_client=apollo_client))

        response = self.client.post(
            "/leads/apollo/search",
            json={
                "titles": ["Procurement Manager"],
                "locations": ["United Arab Emirates"],
                "industries": ["Industrial"],
                "max_leads": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source"], "apollo")
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["leads"][0]["email"], "ahmed@example.ae")
        self.assertEqual(body["leads"][0]["company_name"], "Gulf Industrial Supplies")
        self.assertEqual(apollo_client.calls[0]["filters"]["titles"], ["Procurement Manager"])
        self.assertEqual(apollo_client.calls[0]["per_page"], 3)

    def test_apollo_lead_search_returns_503_when_provider_not_configured(self):
        response = self.client.post(
            "/leads/apollo/search",
            json={"titles": ["Procurement Manager"], "max_leads": 3},
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("CSV fallback", response.json()["detail"])

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
            "llm_provider": "gemini",
            "llm_model": "gemini-3.1-pro-preview",
        }

        create_response = self.client.post("/campaigns/draft", json=payload)

        self.assertEqual(create_response.status_code, 201)
        created = create_response.json()
        self.assertEqual(created["campaign_id"], "uae-distributor-outreach")
        self.assertEqual(created["llm_provider"], "gemini")
        self.assertEqual(created["llm_model"], "gemini-3.1-pro-preview")
        self.assertEqual(created["status"], "drafts_ready_for_review")
        self.assertEqual(len(created["drafts"]), 1)
        self.assertEqual(created["drafts"][0]["lead"]["email"], "ahmed@example.ae")
        self.assertEqual(created["skipped"]["bob@example.com"], "low_score")

        get_response = self.client.get("/campaigns/uae-distributor-outreach")
        self.assertEqual(get_response.status_code, 200)
        self.assertEqual(get_response.json()["campaign"]["name"], "UAE distributor outreach")

    def test_campaign_list_endpoint_returns_saved_campaign_summaries(self):
        self._create_sample_campaign()
        second_payload = self._sample_campaign_payload(
            campaign_name="Saudi distributor outreach",
            target_country="Saudi Arabia",
            target_region="KSA",
            lead_overrides={"email": "riyadh@example.sa", "company_name": "Riyadh Supplies", "country": "Saudi Arabia", "context": "industrial sourcing in Riyadh"},
        )
        self.client.post("/campaigns/draft", json=second_payload)

        response = self.client.get("/campaigns")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["campaigns"][0]["campaign_id"], "saudi-distributor-outreach")
        self.assertEqual(body["campaigns"][1]["campaign_id"], "uae-distributor-outreach")
        self.assertEqual(body["campaigns"][0]["status"], "drafts_ready_for_review")
        self.assertEqual(body["campaigns"][0]["draft_count"], 1)
        self.assertEqual(body["campaigns"][0]["approved_count"], 0)

    def test_campaign_list_endpoint_returns_empty_state_when_no_campaigns_exist(self):
        response = self.client.get("/campaigns")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"count": 0, "campaigns": []})

    def test_draft_review_workflow_lists_approves_and_edits_drafts(self):
        self._create_sample_campaign()

        list_response = self.client.get("/campaigns/uae-distributor-outreach/drafts")
        self.assertEqual(list_response.status_code, 200)
        drafts = list_response.json()["drafts"]
        self.assertEqual(len(drafts), 1)
        self.assertEqual(drafts[0]["draft_id"], "draft-1")
        self.assertEqual(drafts[0]["review_status"], "pending")
        self.assertFalse(drafts[0]["approved"])

        approve_response = self.client.patch(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/approve",
            json={"approved_by": "parmeet", "notes": "Looks good"},
        )
        self.assertEqual(approve_response.status_code, 200)
        approved = approve_response.json()
        self.assertEqual(approved["draft_id"], "draft-1")
        self.assertEqual(approved["review_status"], "approved")
        self.assertTrue(approved["approved"])
        self.assertEqual(approved["approved_by"], "parmeet")
        self.assertEqual(approved["review_notes"], "Looks good")

        edit_response = self.client.patch(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/edit",
            json={"subject": "Updated subject", "body": "Updated body with not relevant opt-out", "edited_by": "parmeet"},
        )
        self.assertEqual(edit_response.status_code, 200)
        edited = edit_response.json()
        self.assertEqual(edited["subject"], "Updated subject")
        self.assertEqual(edited["body"], "Updated body with not relevant opt-out")
        self.assertEqual(edited["review_status"], "edited")
        self.assertFalse(edited["approved"])
        self.assertEqual(edited["edited_by"], "parmeet")

        get_response = self.client.get("/campaigns/uae-distributor-outreach")
        persisted_draft = get_response.json()["drafts"][0]
        self.assertEqual(persisted_draft["subject"], "Updated subject")
        self.assertEqual(persisted_draft["review_status"], "edited")

    def test_gmail_and_outlook_draft_creation_requires_approval(self):
        self._create_sample_campaign()

        blocked = self.client.post(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts",
            json={"provider": "gmail"},
        )
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["detail"], "draft must be approved before mailbox draft creation")

        self.client.patch(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/approve",
            json={"approved_by": "parmeet"},
        )

        gmail = self.client.post(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts",
            json={"provider": "gmail"},
        )
        self.assertEqual(gmail.status_code, 201)
        gmail_body = gmail.json()
        self.assertEqual(gmail_body["provider"], "gmail")
        self.assertEqual(gmail_body["status"], "draft_created")
        self.assertIn("maya@acme.example", gmail_body["from_email"])

        outlook = self.client.post(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts",
            json={"provider": "outlook"},
        )
        self.assertEqual(outlook.status_code, 201)
        self.assertEqual(outlook.json()["provider"], "outlook")

    def test_live_gmail_draft_creation_uses_injected_client_after_approval(self):
        gmail_client = FakeGmailDraftClient()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name), gmail_draft_client=gmail_client))
        self._create_sample_campaign()

        missing_client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))
        not_configured = missing_client.post(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts",
            json={"provider": "gmail", "delivery": "gmail_api"},
        )
        self.assertEqual(not_configured.status_code, 503)
        self.assertEqual(not_configured.json()["detail"], "gmail draft client not configured")

        blocked = self.client.post(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts",
            json={"provider": "gmail", "delivery": "gmail_api"},
        )
        self.assertEqual(blocked.status_code, 409)

        self.client.patch(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/approve",
            json={"approved_by": "parmeet"},
        )
        response = self.client.post(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts",
            json={"provider": "gmail", "delivery": "gmail_api"},
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["provider"], "gmail")
        self.assertEqual(body["status"], "draft_created")
        self.assertEqual(body["mailbox_draft_id"], "gmail-draft-123")
        self.assertEqual(body["storage_path"], "gmail_api")
        self.assertEqual(len(gmail_client.raw_messages), 1)
        decoded = base64.urlsafe_b64decode(gmail_client.raw_messages[0] + "===").decode("utf-8")
        self.assertIn("To: ahmed@example.ae", decoded)
        self.assertIn("From: Maya <maya@acme.example>", decoded)
        self.assertIn("Subject: Potential supply fit for Gulf Industrial Supplies", decoded)
        self.assertIn("industrial maintenance supplies in Dubai", decoded)

    def test_live_outlook_draft_creation_uses_injected_client_after_approval(self):
        outlook_client = FakeOutlookDraftClient()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name), outlook_draft_client=outlook_client))
        self._create_sample_campaign()

        missing_client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))
        not_configured = missing_client.post(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts",
            json={"provider": "outlook", "delivery": "outlook_graph"},
        )
        self.assertEqual(not_configured.status_code, 503)
        self.assertEqual(not_configured.json()["detail"], "outlook draft client not configured")

        blocked = self.client.post(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts",
            json={"provider": "outlook", "delivery": "outlook_graph"},
        )
        self.assertEqual(blocked.status_code, 409)

        self.client.patch(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/approve",
            json={"approved_by": "parmeet"},
        )
        response = self.client.post(
            "/campaigns/uae-distributor-outreach/drafts/draft-1/mailbox-drafts",
            json={"provider": "outlook", "delivery": "outlook_graph"},
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["provider"], "outlook")
        self.assertEqual(body["status"], "draft_created")
        self.assertEqual(body["mailbox_draft_id"], "outlook-draft-789")
        self.assertEqual(body["storage_path"], "outlook_graph")
        self.assertEqual(len(outlook_client.messages), 1)
        message = outlook_client.messages[0]
        self.assertEqual(message["subject"], "Potential supply fit for Gulf Industrial Supplies")
        self.assertEqual(message["toRecipients"][0]["emailAddress"]["address"], "ahmed@example.ae")
        self.assertEqual(message["body"]["contentType"], "Text")
        self.assertIn("industrial maintenance supplies in Dubai", message["body"]["content"])

    def test_unknown_draft_review_endpoint_returns_404(self):
        self._create_sample_campaign()

        response = self.client.patch(
            "/campaigns/uae-distributor-outreach/drafts/missing/approve",
            json={"approved_by": "parmeet"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "draft not found")

    def test_get_unknown_campaign_returns_404(self):
        response = self.client.get("/campaigns/not-found")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "campaign not found")

    def _create_sample_campaign(self):
        return self.client.post("/campaigns/draft", json=self._sample_campaign_payload())

    def _sample_campaign_payload(
        self,
        campaign_name: str = "UAE distributor outreach",
        target_country: str = "United Arab Emirates",
        target_region: str = "UAE",
        lead_overrides: dict | None = None,
    ):
        lead = {
            "first_name": "Ahmed",
            "last_name": "Khan",
            "email": "ahmed@example.ae",
            "title": "Procurement Manager",
            "company_name": "Gulf Industrial Supplies",
            "country": "United Arab Emirates",
            "industry": "Industrial",
            "website": "https://gulf.example",
            "context": "industrial maintenance supplies in Dubai",
        }
        if lead_overrides:
            lead.update(lead_overrides)
        return {
            "company": {
                "name": "Acme Rubber Works",
                "website": "https://acme.example",
                "description": "Rubber products manufacturer for OEMs, industrial distributors, and construction suppliers.",
                "details": {"certifications": "ISO 9001"},
            },
            "campaign": {
                "name": campaign_name,
                "target_country": target_country,
                "target_region": target_region,
                "max_drafts": 2,
                "sender_name": "Maya",
                "sender_email": "maya@acme.example",
                "template": "Hi {{first_name}}, I noticed {{company_name}} works in {{lead_context}}. We manufacture {{value_prop}}. Best, {{sender_name}}",
                "target_titles": ["Procurement Manager", "Sourcing Manager"],
                "target_industries": ["Industrial", "Construction"],
            },
            "leads": [lead],
        }


if __name__ == "__main__":
    unittest.main()
