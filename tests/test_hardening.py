"""Regression tests for the round-2 adversarial review findings."""
import os
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from outreach_mvp._jsonfile import StoreCorruptError
from outreach_mvp.api import create_app
from outreach_mvp.apollo import ApolloLeadProvider, ApolloRateLimited, ApolloRestClient
from outreach_mvp.mailbox import ApprovalRequiredError, GmailApiSendStore, OutlookApiSendStore
from outreach_mvp.models import CampaignInput, EmailDraft, LeadInput, LeadScore, ComplianceResult
from outreach_mvp.replies import heuristic_classification
from outreach_mvp.send_log import SendLog
from outreach_mvp.storage import JsonCampaignStore
from outreach_mvp.suppression import SuppressionStore

from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)


class StoreIntegrityTests(unittest.TestCase):
    def test_corrupt_suppression_file_raises_instead_of_wiping(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "suppression.json"
            store = SuppressionStore(path)
            store.add("victim1@x.om", "unsubscribe")
            path.write_text('{"victim1@x.om": {"reason', encoding="utf-8")  # torn write
            with self.assertRaises(StoreCorruptError):
                store.add("new@x.om", "test")
            with self.assertRaises(StoreCorruptError):
                store.contains("victim1@x.om")
            # The corrupt file is untouched — nothing was overwritten.
            self.assertIn("victim1", path.read_text(encoding="utf-8"))

    def test_missing_and_empty_files_are_empty_stores(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "suppression.json"
            self.assertFalse(SuppressionStore(path).contains("a@b.co"))
            path.write_text("", encoding="utf-8")
            self.assertFalse(SuppressionStore(path).contains("a@b.co"))

    def test_concurrent_adds_lose_nothing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SuppressionStore(Path(tmpdir) / "suppression.json")
            threads = [threading.Thread(target=store.add, args=(f"lead{i}@x.om", "t")) for i in range(30)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len(store.all_emails()), 30)


class SendLogBoundaryTests(unittest.TestCase):
    def test_cap_counts_only_today_for_the_mailbox(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log = SendLog(Path(tmpdir) / "send_log.json")
            log.append(email="a@x.om", campaign_id="c", draft_id="d1", mailbox="gmail", ts="2026-07-18T23:59:00+00:00")
            log.append(email="b@x.om", campaign_id="c", draft_id="d2", mailbox="gmail", ts="2026-07-19T00:01:00+00:00")
            log.append(email="c@x.om", campaign_id="c", draft_id="d3", mailbox="outlook", ts="2026-07-19T10:00:00+00:00")
            now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
            self.assertEqual(log.sends_today("gmail", now=now), 1)
            self.assertEqual(log.sends_today("outlook", now=now), 1)


def make_draft(approved=True):
    lead = LeadInput("S", "M", "s@x.om", "PM", "X", "Oman", "Industrial", "")
    return EmailDraft(
        lead=lead, subject="s", body="b", personalization_reason="r",
        lead_score=LeadScore(90, []), compliance=ComplianceResult("passed", []),
        draft_id="draft-1", review_status="approved" if approved else "pending", approved=approved,
    )


class SendStoreGateTests(unittest.TestCase):
    def test_gmail_send_store_refuses_unapproved(self):
        campaign = CampaignInput("t", "Oman", "", 5, "P", "p@x.om", "Hi")
        with self.assertRaises(ApprovalRequiredError):
            GmailApiSendStore(client=None).send(campaign, make_draft(approved=False))

    def test_outlook_send_store_refuses_unapproved(self):
        campaign = CampaignInput("t", "Oman", "", 5, "P", "p@x.om", "Hi")
        with self.assertRaises(ApprovalRequiredError):
            OutlookApiSendStore(client=None).send(campaign, make_draft(approved=False))

    def test_outlook_send_store_sends_approved(self):
        sent = []

        class FakeOutlook:
            def send_mail(self, payload):
                sent.append(payload)
                return {}

        campaign = CampaignInput("t", "Oman", "", 5, "P", "p@x.om", "Hi")
        result = OutlookApiSendStore(FakeOutlook()).send(campaign, make_draft())
        self.assertEqual(result.status, "sent")
        self.assertEqual(sent[0]["message"]["toRecipients"][0]["emailAddress"]["address"], "s@x.om")
        self.assertTrue(sent[0]["saveToSentItems"])


class SecretEnforcementTests(unittest.TestCase):
    def test_public_base_url_without_secret_refuses_to_start(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env = {**NO_LLM_KEYS, "APP_BASE_URL": "https://lead.example/api", "UNSUBSCRIBE_SECRET": ""}
            with mock.patch.dict(os.environ, env):
                with self.assertRaisesRegex(RuntimeError, "UNSUBSCRIBE_SECRET"):
                    create_app(storage_dir=Path(tmpdir))

    def test_unsubscribe_page_escapes_hostile_email(self):
        from outreach_mvp.unsubscribe import make_token

        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(os.environ, {**NO_LLM_KEYS, "UNSUBSCRIBE_SECRET": "s3cret"}):
                client = TestClient(create_app(storage_dir=Path(tmpdir)))
                token = make_token("<script>alert(1)</script>@x.om", "s3cret")
                page = client.get(f"/u/{token}")
        self.assertEqual(page.status_code, 200)
        self.assertNotIn("<script>alert(1)</script>", page.text)
        self.assertIn("&lt;script&gt;", page.text)


class ReplyHeuristicHardeningTests(unittest.TestCase):
    def test_quoted_own_footer_does_not_suppress_positive_reply(self):
        snippet = (
            "Yes, very interested — send the catalogue. "
            "If this is not relevant, reply 'not relevant' and I will not contact you again. "
            "Unsubscribe with one click: https://lead.example/api/u/abc.def"
        )
        result = heuristic_classification(snippet)
        self.assertNotEqual(result["category"], "unsubscribe")

    def test_short_not_relevant_reply_still_suppresses(self):
        self.assertEqual(heuristic_classification("not relevant, thanks")["category"], "unsubscribe")

    def test_long_positive_reply_containing_not_relevant_is_not_suppressed(self):
        text = (
            "Thanks for reaching out. Your competitor pitch last week was not relevant to us, "
            "but yours actually is — we are retendering our pump supply next quarter and would "
            "like to see certifications, lead times, and reference customers in the Gulf region."
        )
        self.assertNotEqual(heuristic_classification(text)["category"], "unsubscribe")


class MailboxSuppressionAndRepliedGuardTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(
            os.environ,
            {**NO_LLM_KEYS, "APP_BASE_URL": "https://t.example", "UNSUBSCRIBE_SECRET": "s3cret", "DAILY_SEND_CAP": "20"},
        )
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()

        class FakeGmailSend:
            def send_message(self, raw):
                return {"id": "m1"}

        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name), gmail_send_client=FakeGmailSend()))
        payload = {
            "company": {"name": "Acme", "website": "", "description": "Industrial pumps manufacturer.", "details": {"postal_address": "12 Way, Muscat"}},
            "campaign": {
                "name": "guard-test", "target_country": "Oman", "target_region": "", "max_drafts": 5,
                "sender_name": "P", "sender_email": "p@example.com", "template": "Hi {{first_name}}, {{value_prop}}",
                "target_titles": ["Procurement Manager"], "target_industries": ["Industrial"],
                "delivery_mode": "auto_send",
            },
            "leads": [{
                "first_name": "Said", "last_name": "M", "email": "said@example.om", "title": "Procurement Manager",
                "company_name": "X", "country": "Oman", "industry": "Industrial", "website": "", "context": "pumps",
            }],
            "llm_provider": "deterministic",
        }
        self.cid = self.client.post("/campaigns/draft", json=payload).json()["campaign_id"]
        self.client.patch(f"/campaigns/{self.cid}/drafts/draft-1/approve", json={"approved_by": "t"})

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def test_suppressed_recipient_blocked_from_mailbox_draft(self):
        SuppressionStore(Path(self.tmpdir.name) / "suppression.json").add("said@example.om", "test")
        response = self.client.post(f"/campaigns/{self.cid}/drafts/draft-1/mailbox-drafts", json={"provider": "gmail"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("suppression", response.json()["detail"])

    def test_replied_lead_cannot_be_sent(self):
        JsonCampaignStore(Path(self.tmpdir.name)).mark_draft_replied(self.cid, "draft-1", "interested")
        response = self.client.post(f"/campaigns/{self.cid}/drafts/draft-1/send", json={"provider": "gmail"})
        self.assertEqual(response.status_code, 409)
        self.assertIn("replied", response.json()["detail"])

    def test_mark_sent_enables_sequences_in_draft_mode(self):
        response = self.client.patch(f"/campaigns/{self.cid}/drafts/draft-1/mark-sent")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["sent_at"])
        second = self.client.patch(f"/campaigns/{self.cid}/drafts/draft-1/mark-sent")
        self.assertEqual(second.status_code, 409)


class ApolloHardeningTests(unittest.TestCase):
    def test_multi_page_pagination_dedupes_and_counts(self):
        class PagedClient:
            def search_people(self, *, filters, page, per_page):
                if page == 1:
                    return {
                        "people": [
                            {"first_name": "A", "email": "a@x.om", "title": "PM"},
                            {"first_name": "L", "email": "email_not_unlocked@domain.com", "title": "PM"},
                        ],
                        "pagination": {"total_pages": 2},
                    }
                return {
                    "people": [
                        {"first_name": "A", "email": "a@x.om", "title": "PM"},  # duplicate across pages
                        {"first_name": "B", "email": "b@x.om", "title": "PM"},
                    ],
                    "pagination": {"total_pages": 2},
                }

        result = ApolloLeadProvider(client=PagedClient()).search_leads(titles=["PM"], max_leads=2)
        self.assertEqual([lead.email for lead in result.leads], ["a@x.om", "b@x.om"])
        self.assertEqual(result.locked_email_count, 1)
        self.assertEqual(result.pages_fetched, 2)

    def test_null_data_envelope_does_not_crash(self):
        class NullClient:
            def search_people(self, *, filters, page, per_page):
                return {"data": None}

        result = ApolloLeadProvider(client=NullClient()).search_leads(titles=["PM"], max_leads=5)
        self.assertEqual(result.leads, [])

    def test_429_retries_once_then_raises(self):
        sleeps = []

        class Resp:
            def __init__(self, status, headers=None, body=None):
                self.status_code = status
                self.headers = headers or {}
                self._body = body or {}

            def json(self):
                return self._body

            def raise_for_status(self):
                pass

        responses = [Resp(429, {"retry-after": "notanumber"}), Resp(200, body={"people": []})]
        with mock.patch("outreach_mvp.apollo.httpx.post", side_effect=lambda *a, **k: responses.pop(0)):
            client = ApolloRestClient(api_key="k", sleep=sleeps.append)
            data = client.search_people(filters={}, page=1, per_page=10)
        self.assertEqual(data, {"people": []})
        self.assertEqual(sleeps, [60])  # non-numeric retry-after falls back to 60s

        responses = [Resp(429), Resp(429)]
        with mock.patch("outreach_mvp.apollo.httpx.post", side_effect=lambda *a, **k: responses.pop(0)):
            client = ApolloRestClient(api_key="k", sleep=lambda s: None)
            with self.assertRaises(ApolloRateLimited):
                client.search_people(filters={}, page=1, per_page=10)


if __name__ == "__main__":
    unittest.main()
