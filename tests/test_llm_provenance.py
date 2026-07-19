import os
import unittest
from unittest import mock

from outreach_mvp.llm import LLMRouter, StaticLLMClient
from outreach_mvp.models import CampaignInput, CompanyInput, LeadInput
from outreach_mvp.orchestrator import DraftFirstOrchestrator

from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)


class RaisingClient:
    def complete_json(self, *, provider, model, task, payload):
        raise RuntimeError("boom")


def make_inputs():
    company = CompanyInput("Acme", "", "Industrial pumps manufacturer", {})
    campaign = CampaignInput(
        "provenance", "Oman", "", 5, "P", "p@example.com",
        "Hi {{first_name}}, {{lead_context}} {{value_prop}} {{sender_name}}",
        ["Procurement Manager"], ["Industrial"],
    )
    lead = LeadInput("Said", "M", "said@example.om", "Procurement Manager", "Muscat Ind", "Oman", "Industrial", "", "pumps")
    return company, campaign, lead


class ProvenanceTests(unittest.TestCase):
    def test_deterministic_drafts_are_marked_fallback(self):
        company, campaign, lead = make_inputs()
        result = DraftFirstOrchestrator().create_draft_campaign(company, campaign, [lead])
        draft = result.drafts[0]
        self.assertEqual(draft.generated_by, "fallback")
        self.assertEqual(draft.llm_error, "")
        self.assertEqual(result.business_profile.generated_by, "fallback")

    def test_claude_provider_uses_injected_client_and_marks_llm(self):
        client = StaticLLMClient(
            profile_response={
                "summary": "Claude summary",
                "product_categories": ["Pumps"],
                "buyer_personas": ["Procurement Manager"],
                "target_industries": ["Industrial"],
                "value_propositions": ["reliable pumps"],
                "suggested_apollo_filters": {"person_titles": ["Procurement Manager"]},
            },
            draft_response={
                "subject": "Pumps for Muscat Ind",
                "body": "Claude-written body for Said.",
                "personalization_reason": "Used the pumps context.",
            },
        )
        router = LLMRouter(provider="claude", client=client)
        company, campaign, lead = make_inputs()
        result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, campaign, [lead])

        self.assertEqual(result.llm_provider, "claude")
        self.assertEqual(result.llm_model, "claude-opus-4-8")
        self.assertEqual(result.business_profile.generated_by, "llm")
        draft = result.drafts[0]
        self.assertEqual(draft.generated_by, "llm")
        self.assertEqual(draft.subject, "Pumps for Muscat Ind")
        self.assertIn("not relevant", draft.body.lower())  # footer still appended

    def test_router_reports_fallback_reason_when_llm_fails(self):
        router = LLMRouter(provider="claude", client=RaisingClient())
        company, campaign, lead = make_inputs()
        with self.assertLogs("outreach_mvp.llm", level="WARNING"):
            result = DraftFirstOrchestrator(llm_router=router, llm_scoring=False).create_draft_campaign(company, campaign, [lead])
        draft = result.drafts[0]
        self.assertEqual(draft.generated_by, "fallback")
        self.assertIn("RuntimeError", draft.llm_error)

    def test_claude_without_key_is_disabled_and_falls_back_visibly(self):
        with mock.patch.dict(os.environ, NO_LLM_KEYS):
            router = LLMRouter(provider="claude")
            self.assertFalse(router.enabled)
            company, campaign, lead = make_inputs()
            result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, campaign, [lead])
        draft = result.drafts[0]
        self.assertEqual(draft.generated_by, "fallback")
        # A requested-but-unconfigured provider must never look like an
        # intentional deterministic run.
        self.assertTrue(draft.llm_error.startswith("provider_not_configured:claude"), draft.llm_error)

    def test_blank_llm_subject_or_body_is_recorded_as_error(self):
        client = StaticLLMClient(draft_response={"subject": "S", "body": "", "personalization_reason": "r"})
        router = LLMRouter(provider="claude", client=client)
        company, campaign, lead = make_inputs()
        result = DraftFirstOrchestrator(llm_router=router, llm_scoring=False).create_draft_campaign(company, campaign, [lead])
        draft = result.drafts[0]
        self.assertEqual(draft.generated_by, "fallback")
        self.assertEqual(draft.llm_error, "llm_returned_blank_fields")

    def test_codex_and_gemini_require_explicit_model_when_key_present(self):
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "GOOGLE_API_KEY": "", "GEMINI_API_KEY": "g-test"}):
            with self.assertRaisesRegex(ValueError, "explicit llm_model"):
                LLMRouter(provider="codex")
            with self.assertRaisesRegex(ValueError, "explicit llm_model"):
                LLMRouter(provider="gemini")
            # With an explicit model they construct fine.
            self.assertEqual(LLMRouter(provider="codex", model="my-model").model, "my-model")


class HybridScoringTests(unittest.TestCase):
    def test_llm_disqualifier_skips_borderline_lead(self):
        client = StaticLLMClient(lead_fit_response={"fit_score": 20, "fit_reasons": [], "disqualifiers": ["competitor"]})
        router = LLMRouter(provider="claude", client=client)
        company, campaign, lead = make_inputs()
        # Borderline lead: no country match -> 30+25+10 = 65, inside the 40-69 LLM band.
        borderline = LeadInput("B", "L", "b@example.qa", "Procurement Manager", "QatarCo", "Qatar", "Industrial", "", "pumps")
        result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, campaign, [borderline])

        self.assertEqual(result.drafts, [])
        self.assertTrue(result.skipped["b@example.qa"].startswith("llm_disqualified:competitor"))

    def test_llm_fit_score_can_promote_borderline_lead(self):
        client = StaticLLMClient(
            lead_fit_response={"fit_score": 88, "fit_reasons": ["ideal buyer"], "disqualifiers": []},
            draft_response={"subject": "S", "body": "B", "personalization_reason": "r"},
        )
        router = LLMRouter(provider="claude", client=client)
        company, campaign, _ = make_inputs()
        strict_campaign = CampaignInput(
            "provenance", "Oman", "", 5, "P", "p@example.com",
            "Hi {{first_name}}, {{value_prop}}", ["Procurement Manager"], ["Industrial"],
            score_threshold=70,
        )
        borderline = LeadInput("B", "L", "b@example.qa", "Procurement Manager", "QatarCo", "Qatar", "Industrial", "", "pumps")
        result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, strict_campaign, [borderline])

        self.assertEqual(len(result.drafts), 1)
        self.assertEqual(result.drafts[0].lead_score.score, 88)
        self.assertIn("llm_scored", result.drafts[0].lead_score.reasons)

    def test_llm_scoring_disabled_skips_llm_entirely(self):
        client = StaticLLMClient(lead_fit_response={"fit_score": 0, "fit_reasons": [], "disqualifiers": ["should not be consulted"]})
        router = LLMRouter(provider="claude", client=client)
        company, campaign, _ = make_inputs()
        borderline = LeadInput("B", "L", "b@example.qa", "Procurement Manager", "QatarCo", "Qatar", "Industrial", "", "pumps")
        result = DraftFirstOrchestrator(llm_router=router, llm_scoring=False).create_draft_campaign(company, campaign, [borderline])
        # 65 >= default threshold 50, drafted without consulting the fit client.
        self.assertEqual(len(result.drafts), 1)

    def test_malformed_fit_score_never_crashes_the_run(self):
        company, campaign, _ = make_inputs()
        borderline = LeadInput("B", "L", "b@example.qa", "Procurement Manager", "QatarCo", "Qatar", "Industrial", "", "pumps")
        for bad_value in ("85/100", None, "high", 55.9):
            client = StaticLLMClient(
                lead_fit_response={"fit_score": bad_value, "fit_reasons": [], "disqualifiers": []},
                draft_response={"subject": "S", "body": "B", "personalization_reason": "r"},
            )
            router = LLMRouter(provider="claude", client=client)
            result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, campaign, [borderline])
            self.assertEqual(len(result.drafts), 1, f"crashed or skipped for fit_score={bad_value!r}")
            if bad_value == 55.9:
                # floats are coercible — accepted and clamped.
                self.assertEqual(result.drafts[0].lead_score.score, 55)
            else:
                # Non-coercible: rule score kept, invalidity recorded.
                self.assertEqual(result.drafts[0].lead_score.score, 65)
                self.assertIn("llm_score_invalid", result.drafts[0].lead_score.reasons)

    def test_string_disqualifier_is_not_iterated_per_character(self):
        client = StaticLLMClient(lead_fit_response={"fit_score": 55, "fit_reasons": [], "disqualifiers": "competitor"})
        router = LLMRouter(provider="claude", client=client)
        company, campaign, _ = make_inputs()
        borderline = LeadInput("B", "L", "b@example.qa", "Procurement Manager", "QatarCo", "Qatar", "Industrial", "", "pumps")
        result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, campaign, [borderline])
        self.assertEqual(result.skipped["b@example.qa"], "llm_disqualified:competitor")

    def test_band_boundaries_control_llm_consultation(self):
        # Weights: title 30, industry 25, context 10, website 5; country never matches.
        disqualify = StaticLLMClient(
            lead_fit_response={"fit_score": 10, "fit_reasons": [], "disqualifiers": ["disqualified"]},
            draft_response={"subject": "S", "body": "B", "personalization_reason": "r"},
        )
        router = LLMRouter(provider="claude", client=disqualify)
        company, campaign, _ = make_inputs()
        lead35 = LeadInput("A", "L", "a35@example.qa", "Intern", "QatarCo", "Qatar", "Industrial", "", "pumps")
        lead40 = LeadInput("B", "L", "b40@example.qa", "Intern", "QatarCo", "Qatar", "Industrial", "https://q.example", "pumps")
        lead70 = LeadInput("C", "L", "c70@example.qa", "Procurement Manager", "QatarCo", "Qatar", "Industrial", "https://q.example", "pumps")
        result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, campaign, [lead35, lead40, lead70])

        # 35 < band: never consulted, plain low_score skip.
        self.assertEqual(result.skipped["a35@example.qa"], "low_score")
        # 40 = band floor: consulted and disqualified.
        self.assertEqual(result.skipped["b40@example.qa"], "llm_disqualified:disqualified")
        # 70 = band ceiling (default threshold 50): NOT consulted, drafted on rules.
        self.assertEqual([d.lead.email for d in result.drafts], ["c70@example.qa"])

    def test_band_extends_to_threshold_for_monotonicity(self):
        promote = StaticLLMClient(
            lead_fit_response={"fit_score": 88, "fit_reasons": ["ideal"], "disqualifiers": []},
            draft_response={"subject": "S", "body": "B", "personalization_reason": "r"},
        )
        router = LLMRouter(provider="claude", client=promote)
        company, _, _ = make_inputs()
        strict = CampaignInput(
            "monotonic", "Oman", "", 5, "P", "p@example.com", "Hi {{first_name}}, {{value_prop}}",
            ["Procurement Manager"], ["Industrial"], score_threshold=80,
        )
        lead70 = LeadInput("C", "L", "c70@example.qa", "Procurement Manager", "QatarCo", "Qatar", "Industrial", "https://q.example", "pumps")
        result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, strict, [lead70])
        # Rule score 70 < threshold 80, but the band now extends to the threshold:
        # the LLM is consulted and promotes the lead instead of it being skipped.
        self.assertEqual(len(result.drafts), 1)
        self.assertEqual(result.drafts[0].lead_score.score, 88)

    def test_fit_failure_is_visible_in_reasons_and_skip_marker(self):
        class FitFailingClient:
            def complete_json(self, *, provider, model, task, payload):
                if task == "lead_fit":
                    raise RuntimeError("fit endpoint down")
                if task == "email_draft":
                    return {"subject": "S", "body": "B", "personalization_reason": "r"}
                return {}

        company, campaign, _ = make_inputs()
        borderline = LeadInput("B", "L", "b@example.qa", "Procurement Manager", "QatarCo", "Qatar", "Industrial", "", "pumps")

        # Above threshold: drafted, with the failed consultation on the record.
        router = LLMRouter(provider="claude", client=FitFailingClient())
        with self.assertLogs("outreach_mvp.llm", level="WARNING"):
            result = DraftFirstOrchestrator(llm_router=router).create_draft_campaign(company, campaign, [borderline])
        self.assertEqual(len(result.drafts), 1)
        self.assertIn("llm_score_failed", result.drafts[0].lead_score.reasons)

        # Below threshold: the skip reason says the LLM rescue never happened.
        strict = CampaignInput(
            "strict", "Oman", "", 5, "P", "p@example.com", "Hi {{first_name}}, {{value_prop}}",
            ["Procurement Manager"], ["Industrial"], score_threshold=70,
        )
        router2 = LLMRouter(provider="claude", client=FitFailingClient())
        with self.assertLogs("outreach_mvp.llm", level="WARNING"):
            result2 = DraftFirstOrchestrator(llm_router=router2).create_draft_campaign(company, strict, [borderline])
        self.assertEqual(result2.skipped["b@example.qa"], "low_score(llm_scoring_failed)")


if __name__ == "__main__":
    unittest.main()
