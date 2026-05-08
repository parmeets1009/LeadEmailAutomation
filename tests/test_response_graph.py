import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from outreach_mvp.models import (
    BusinessProfile,
    CampaignInput,
    CampaignResult,
    ComplianceResult,
    EmailDraft,
    LeadInput,
    LeadScore,
)
from outreach_mvp.response_graph import LeadResponseGraphBuilder, ResponseEvent, ResponseEventStore


class ResponseGraphTests(unittest.TestCase):
    def test_response_event_store_appends_loads_and_filters_jsonl_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ResponseEventStore(Path(tmpdir) / "response_events.jsonl")
            reply = ResponseEvent(
                event_id="evt-reply-1",
                campaign_id="uae-distributor-outreach",
                draft_id="draft-1",
                email="ahmed@example.ae",
                event_type="reply",
                classification="interested",
                notes="Asked for catalogue",
                occurred_at="2026-05-08T10:00:00Z",
            )
            bounce = ResponseEvent(
                event_id="evt-bounce-1",
                campaign_id="other-campaign",
                draft_id="draft-9",
                email="bounce@example.com",
                event_type="bounce",
                classification="hard_bounce",
            )

            store.append(reply)
            store.append(bounce)
            reloaded = ResponseEventStore(Path(tmpdir) / "response_events.jsonl")

            self.assertEqual([event.event_id for event in reloaded.list_events()], ["evt-reply-1", "evt-bounce-1"])
            self.assertEqual([event.email for event in reloaded.list_events(campaign_id="uae-distributor-outreach")], ["ahmed@example.ae"])
            self.assertEqual([event.event_type for event in reloaded.events_for_draft("uae-distributor-outreach", "draft-1")], ["reply"])

    def test_response_graph_builds_nodes_edges_and_segment_metrics(self):
        result = self._campaign_result()
        events = [
            ResponseEvent("evt-reply-1", "uae-distributor-outreach", "draft-1", "ahmed@example.ae", "reply", "interested"),
            ResponseEvent("evt-bounce-1", "uae-distributor-outreach", "draft-2", "sara@example.ae", "bounce", "hard_bounce"),
        ]

        graph = LeadResponseGraphBuilder().build("uae-distributor-outreach", result, events)

        node_kinds = {node["kind"] for node in graph["nodes"]}
        edge_kinds = {edge["kind"] for edge in graph["edges"]}
        self.assertIn("Campaign", node_kinds)
        self.assertIn("Lead", node_kinds)
        self.assertIn("EmailDraft", node_kinds)
        self.assertIn("ResponseEvent", node_kinds)
        self.assertIn("GENERATED", edge_kinds)
        self.assertIn("DRAFTED_FOR", edge_kinds)
        self.assertIn("HAS_OUTCOME", edge_kinds)
        self.assertEqual(graph["metrics"]["total_drafts"], 2)
        self.assertEqual(graph["metrics"]["replies"], 1)
        self.assertEqual(graph["metrics"]["bounces"], 1)
        self.assertEqual(graph["metrics"]["reply_rate"], 0.5)
        self.assertEqual(graph["metrics"]["bounce_rate"], 0.5)
        self.assertEqual(graph["metrics"]["by_industry"]["Industrial"]["replies"], 1)
        self.assertEqual(graph["metrics"]["by_title"]["Procurement Manager"]["reply_rate"], 1.0)
        self.assertEqual(graph["metrics"]["skipped_reasons"], {"low_score": 1})

    def test_response_graph_calculates_unsubscribe_and_conversion_rates(self):
        result = self._campaign_result()
        events = [
            ResponseEvent("evt-unsub-1", "uae-distributor-outreach", "draft-1", "ahmed@example.ae", "unsubscribe", "unsubscribe"),
            ResponseEvent("evt-conv-1", "uae-distributor-outreach", "draft-2", "sara@example.ae", "conversion", "catalogue_requested"),
        ]

        metrics = LeadResponseGraphBuilder().build("uae-distributor-outreach", result, events)["metrics"]

        self.assertEqual(metrics["unsubscribes"], 1)
        self.assertEqual(metrics["conversions"], 1)
        self.assertEqual(metrics["unsubscribe_rate"], 0.5)
        self.assertEqual(metrics["conversion_rate"], 0.5)

    def test_response_graph_rates_are_unique_by_draft_and_ignore_stale_events(self):
        result = self._campaign_result()
        events = [
            ResponseEvent("evt-reply-1", "uae-distributor-outreach", "draft-1", "ahmed@example.ae", "reply", "interested"),
            ResponseEvent("evt-reply-2", "uae-distributor-outreach", "draft-1", "ahmed@example.ae", "reply", "follow_up_reply"),
            ResponseEvent("evt-stale", "uae-distributor-outreach", "missing-draft", "old@example.ae", "reply", "stale"),
        ]

        metrics = LeadResponseGraphBuilder().build("uae-distributor-outreach", result, events)["metrics"]

        self.assertEqual(metrics["replies"], 1)
        self.assertEqual(metrics["reply_events"], 2)
        self.assertEqual(metrics["ignored_events"], 1)
        self.assertEqual(metrics["reply_rate"], 0.5)
        self.assertEqual(metrics["by_title"]["Procurement Manager"]["replies"], 1)
        self.assertEqual(metrics["by_title"]["Procurement Manager"]["reply_events"], 2)
        self.assertEqual(metrics["by_title"]["Procurement Manager"]["reply_rate"], 1.0)

    def test_response_graph_supports_all_valid_event_type_metrics(self):
        result = self._campaign_result()
        events = [
            ResponseEvent("evt-no-1", "uae-distributor-outreach", "draft-1", "ahmed@example.ae", "not_interested", "not_now"),
            ResponseEvent("evt-ooo-1", "uae-distributor-outreach", "draft-2", "sara@example.ae", "out_of_office", "auto_reply"),
        ]

        metrics = LeadResponseGraphBuilder().build("uae-distributor-outreach", result, events)["metrics"]

        self.assertEqual(metrics["not_interested"], 1)
        self.assertEqual(metrics["not_interested_events"], 1)
        self.assertEqual(metrics["out_of_office"], 1)
        self.assertEqual(metrics["out_of_office_events"], 1)
        self.assertEqual(metrics["by_title"]["Procurement Manager"]["not_interested"], 1)
        self.assertEqual(metrics["by_title"]["Sourcing Manager"]["out_of_office"], 1)

    def _campaign_result(self):
        campaign = CampaignInput(
            "UAE distributor outreach",
            "United Arab Emirates",
            "UAE",
            2,
            "Maya",
            "maya@acme.example",
            "Hi {{first_name}}",
            ["Procurement Manager", "Sourcing Manager"],
            ["Industrial", "Construction"],
        )
        profile = BusinessProfile(
            "Acme Rubber Works",
            "https://acme.example",
            "Rubber products manufacturer",
            ["Rubber products"],
            ["Procurement Manager"],
            ["Industrial"],
            ["Custom rubber products"],
            {"person_titles": ["Procurement Manager"]},
        )
        passed = ComplianceResult("passed", [])
        draft_1 = EmailDraft(
            LeadInput("Ahmed", "Khan", "ahmed@example.ae", "Procurement Manager", "Gulf Industrial Supplies", "United Arab Emirates", "Industrial", "https://gulf.example", "industrial supplies"),
            "Potential supply fit for Gulf Industrial Supplies",
            "Body with not relevant opt-out",
            "title and country fit",
            LeadScore(90, ["country_match", "title_match"]),
            passed,
            draft_id="draft-1",
            approved=True,
            review_status="approved",
        )
        draft_2 = replace(
            draft_1,
            lead=LeadInput("Sara", "Noor", "sara@example.ae", "Sourcing Manager", "BuildRight UAE", "United Arab Emirates", "Construction", "https://buildright.example", "construction procurement"),
            subject="Potential supply fit for BuildRight UAE",
            draft_id="draft-2",
            lead_score=LeadScore(80, ["country_match", "industry_match"]),
            approved=False,
            review_status="pending",
        )
        return CampaignResult(campaign, profile, [draft_1, draft_2], {"bob@example.com": "low_score"})


if __name__ == "__main__":
    unittest.main()
