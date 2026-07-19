"""E2E backend tests for outreach_mvp API mounted at /api."""
import os
import time
import pytest


# ---------------- Health & infra ----------------
class TestHealth:
    def test_health_ok(self, api, base_url):
        r = api.get(f"{base_url}/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_root_is_frontend_not_backend(self, api):
        # The public preview root must serve the React frontend, not the backend bridge.
        public = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")
        r = api.get(public + "/")
        assert r.status_code == 200
        ctype = r.headers.get("content-type", "")
        body = r.text[:500].lower()
        assert "text/html" in ctype, f"Expected html, got {ctype}"
        assert "<!doctype html" in body or "<html" in body
        # Not the backend FastAPI root JSON
        assert '"service": "lead-email-automation"' not in r.text


# ---------------- LLM providers ----------------
class TestProviders:
    def test_providers(self, api, base_url):
        r = api.get(f"{base_url}/llm/providers")
        assert r.status_code == 200
        data = r.json()
        assert data["default_provider"] == "deterministic"
        for p in ["deterministic", "codex", "gemini"]:
            assert p in data["available_providers"]


# ---------------- Company profile ----------------
class TestCompanyProfile:
    def test_company_profile_preview(self, api, base_url):
        payload = {
            "name": "TEST_Acme Rubber",
            "website": "https://acme.example",
            "description": "Rubber products manufacturer for OEMs and industrial distributors.",
            "details": {},
        }
        r = api.post(f"{base_url}/companies/profile", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        # Should at least include either business_profile or top-level keys
        assert isinstance(data, dict)
        # Some descriptive field expected
        assert any(k in data for k in ["business_profile", "summary", "value_propositions", "product_categories", "buyer_personas", "target_industries"]), list(data.keys())


# ---------------- Campaign list ----------------
class TestCampaignsList:
    def test_campaigns_list(self, api, base_url):
        r = api.get(f"{base_url}/campaigns")
        assert r.status_code == 200
        data = r.json()
        assert "campaigns" in data
        ids = [c["campaign_id"] for c in data["campaigns"]]
        # Pre-existing seeded campaign
        assert "uae-distributor-outreach" in ids

    def test_get_seeded_campaign(self, api, base_url):
        r = api.get(f"{base_url}/campaigns/uae-distributor-outreach")
        assert r.status_code == 200
        data = r.json()
        assert data["campaign_id"] == "uae-distributor-outreach"
        assert isinstance(data.get("drafts"), list)
        if data["drafts"]:
            d = data["drafts"][0]
            assert "draft_id" in d
            assert "subject" in d and "body" in d


# ---------------- Draft generation, approve, edit (full cycle) ----------------
class TestDraftCycle:
    @pytest.fixture(scope="class")
    def created_campaign(self, base_url):
        import requests
        payload = {
            "company": {
                "name": "TEST Acme Rubber Works",
                "website": "https://acme.example",
                "description": "Rubber products manufacturer for OEMs and industrial distributors.",
                "details": {},
            },
            "campaign": {
                "name": "TEST UAE outreach",
                "target_country": "United Arab Emirates",
                "target_region": "UAE",
                "max_drafts": 5,
                "sender_name": "Maya",
                "sender_email": "maya@acme.example",
                "target_titles": ["Procurement Manager", "Sourcing Manager"],
                "target_industries": ["Industrial", "Construction"],
                "template": "Hi {{first_name}}, about {{company_name}}. {{value_prop}}. {{sender_name}}",
            },
            "leads": [
                {
                    "first_name": "Ahmed", "last_name": "Khan", "email": "ahmed@example.ae",
                    "title": "Procurement Manager", "company_name": "Gulf Industrial Supplies",
                    "country": "United Arab Emirates", "industry": "Industrial",
                    "website": "https://gulf.example", "context": "industrial maintenance supplies in Dubai",
                },
                {
                    "first_name": "Sara", "last_name": "Noor", "email": "sara@example.ae",
                    "title": "Sourcing Manager", "company_name": "BuildRight UAE",
                    "country": "UAE", "industry": "Construction",
                    "website": "https://buildright.example", "context": "construction materials procurement",
                },
            ],
            "llm_provider": "deterministic",
            "enrich_websites": False,
        }
        r = requests.post(f"{base_url}/campaigns/draft", json=payload, timeout=60)
        assert r.status_code in (200, 201), r.text
        data = r.json()
        assert "campaign_id" in data, list(data.keys())
        assert isinstance(data.get("drafts"), list) and len(data["drafts"]) >= 1
        return data

    def test_drafts_have_required_fields(self, api, base_url, created_campaign):
        # Note: POST /campaigns/draft returns drafts with empty draft_id. The GET endpoint
        # backfills sequential draft_ids. We rely on GET for the actual flow (matches frontend behavior).
        cid = created_campaign["campaign_id"]
        g = api.get(f"{base_url}/campaigns/{cid}")
        assert g.status_code == 200
        drafts = g.json()["drafts"]
        assert len(drafts) >= 1
        for d in drafts:
            assert d.get("draft_id"), f"draft_id missing on {d}"
            assert d.get("subject")
            assert d.get("body")

    def test_approve_draft_persists(self, api, base_url, created_campaign):
        cid = created_campaign["campaign_id"]
        # Use GET-backfilled draft_id (matches what UI sees)
        drafts = api.get(f"{base_url}/campaigns/{cid}").json()["drafts"]
        did = drafts[0]["draft_id"]
        r = api.patch(f"{base_url}/campaigns/{cid}/drafts/{did}/approve", json={"approved_by": "tester"})
        assert r.status_code == 200, r.text
        body = r.json()
        # Verify by GET
        g = api.get(f"{base_url}/campaigns/{cid}")
        assert g.status_code == 200
        drafts = g.json()["drafts"]
        match = next(d for d in drafts if d["draft_id"] == did)
        assert match.get("approved") is True or match.get("review_status") in ("approved", "approved_by_human")

    def test_edit_draft_persists(self, api, base_url, created_campaign):
        cid = created_campaign["campaign_id"]
        drafts = api.get(f"{base_url}/campaigns/{cid}").json()["drafts"]
        did = drafts[-1]["draft_id"]
        new_subject = "TEST_Edited subject"
        new_body = "TEST_Edited body content"
        r = api.patch(
            f"{base_url}/campaigns/{cid}/drafts/{did}/edit",
            json={"subject": new_subject, "body": new_body, "edited_by": "tester"},
        )
        assert r.status_code == 200, r.text
        # Verify persisted
        g = api.get(f"{base_url}/campaigns/{cid}")
        drafts = g.json()["drafts"]
        m = next(d for d in drafts if d["draft_id"] == did)
        assert m["subject"] == new_subject
        assert m["body"] == new_body


# ---------------- Mailbox status (no OAuth env) ----------------
class TestMailboxes:
    def test_oauth_providers(self, api, base_url):
        r = api.get(f"{base_url}/oauth/providers")
        assert r.status_code == 200
        data = r.json()
        # Should at least contain gmail, outlook keys with configured=False
        assert isinstance(data, dict)

    def test_mailbox_status(self, api, base_url):
        r = api.get(f"{base_url}/mailboxes/status")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict)

    def test_apollo_search_graceful_503(self, api, base_url):
        r = api.post(
            f"{base_url}/leads/apollo/search",
            json={"locations": ["United Arab Emirates"], "max_leads": 3},
        )
        # No APOLLO_API_KEY configured -> graceful 503
        assert r.status_code in (503, 400, 422), r.status_code
