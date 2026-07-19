import tempfile
import unittest
from pathlib import Path

from outreach_mvp.models import CampaignInput, CompanyInput, LeadInput
from outreach_mvp.orchestrator import DraftFirstOrchestrator
from outreach_mvp.storage import JsonCampaignStore


def build_result():
    company = CompanyInput("Acme", "", "Industrial pumps manufacturer", {})
    campaign = CampaignInput("Repeat Name", "Oman", "", 5, "P", "p@example.com", "Hi {{first_name}}", ["Procurement Manager"], ["Industrial"])
    lead = LeadInput("Said", "M", "said@example.om", "Procurement Manager", "X", "Oman", "Industrial", "", "pumps")
    return DraftFirstOrchestrator().create_draft_campaign(company, campaign, [lead])


class StorageCollisionTests(unittest.TestCase):
    def test_same_name_creates_new_campaign_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonCampaignStore(Path(tmpdir))
            first = store.save(build_result())
            second = store.save(build_result())
            third = store.save(build_result())

        self.assertEqual(first.stem, "repeat-name")
        self.assertEqual(second.stem, "repeat-name-2")
        self.assertEqual(third.stem, "repeat-name-3")

    def test_existing_campaign_approvals_survive_regenerate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = JsonCampaignStore(Path(tmpdir))
            first = store.save(build_result())
            approved = store.approve_draft(first.stem, "draft-1", approved_by="parmeet")
            self.assertTrue(approved.approved)

            # Regenerating under the same campaign name must not touch the old run.
            store.save(build_result())
            reloaded = store.load_campaign(first.stem)

        self.assertTrue(reloaded.drafts[0].approved)
        self.assertEqual(reloaded.drafts[0].approved_by, "parmeet")


if __name__ == "__main__":
    unittest.main()
