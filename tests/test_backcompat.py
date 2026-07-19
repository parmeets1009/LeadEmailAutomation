import json
import tempfile
import unittest
from pathlib import Path

from outreach_mvp.storage import JsonCampaignStore

# Exact shape written by the pre-change serializer: no score_threshold, no source,
# no generated_by / llm_error / render_warnings. Safety invariant 4: these files
# (including approvals) must keep loading forever.
OLD_FORMAT_CAMPAIGN = {
    "campaign": {
        "name": "Legacy Campaign",
        "target_country": "United Arab Emirates",
        "target_region": "UAE",
        "max_drafts": 10,
        "sender_name": "Maya",
        "sender_email": "maya@acme.example",
        "template": "Hi {{first_name}}",
        "target_titles": ["Procurement Manager"],
        "target_industries": ["Industrial"],
    },
    "business_profile": {
        "company_name": "Acme",
        "website": "",
        "summary": "Legacy summary",
        "product_categories": ["Widgets"],
        "buyer_personas": ["Procurement Manager"],
        "target_industries": ["Industrial"],
        "value_propositions": ["value"],
        "suggested_apollo_filters": {"person_titles": ["Procurement Manager"]},
    },
    "drafts": [
        {
            "lead": {
                "first_name": "Ahmed",
                "last_name": "Khan",
                "email": "ahmed@example.ae",
                "title": "Procurement Manager",
                "company_name": "Gulf",
                "country": "United Arab Emirates",
                "industry": "Industrial",
                "website": "",
                "context": "supplies",
            },
            "subject": "Legacy subject",
            "body": "Legacy body. If this is not relevant, reply 'not relevant'.",
            "personalization_reason": "legacy",
            "lead_score": {"score": 95, "reasons": ["country_match"]},
            "compliance": {"status": "passed", "reasons": []},
            "approval_required": True,
            "draft_id": "draft-1",
            "review_status": "approved",
            "approved": True,
            "approved_by": "parmeet",
            "review_notes": "approved before the upgrade",
            "edited_by": "",
        }
    ],
    "skipped": {},
    "status": "drafts_ready_for_review",
    "llm_provider": "deterministic",
    "llm_model": "deterministic-v1",
    "prompt_version": "draft-first-v1",
}


class BackwardCompatibilityTests(unittest.TestCase):
    def test_old_format_campaign_loads_with_defaults_and_keeps_approval(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "legacy-campaign.json"
            path.write_text(json.dumps(OLD_FORMAT_CAMPAIGN), encoding="utf-8")
            store = JsonCampaignStore(Path(tmpdir))
            result = store.load_campaign("legacy-campaign")

        draft = result.drafts[0]
        self.assertTrue(draft.approved)
        self.assertEqual(draft.approved_by, "parmeet")
        self.assertEqual(draft.generated_by, "fallback")
        self.assertEqual(draft.llm_error, "")
        self.assertEqual(draft.render_warnings, [])
        self.assertEqual(draft.lead.source, "")
        self.assertEqual(result.campaign.score_threshold, 50)
        self.assertEqual(result.business_profile.generated_by, "fallback")

    def test_corrupt_file_does_not_brick_campaign_listing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            good = Path(tmpdir) / "legacy-campaign.json"
            good.write_text(json.dumps(OLD_FORMAT_CAMPAIGN), encoding="utf-8")
            (Path(tmpdir) / "corrupt.json").write_text("this is not json{", encoding="utf-8")
            store = JsonCampaignStore(Path(tmpdir))
            with self.assertLogs("outreach_mvp.storage", level="WARNING"):
                campaigns = store.list_campaigns()

        self.assertEqual(len(campaigns), 1)
        self.assertEqual(campaigns[0]["campaign_id"], "legacy-campaign")


if __name__ == "__main__":
    unittest.main()
