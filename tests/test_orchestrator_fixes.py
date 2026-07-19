import unittest

from outreach_mvp.apollo import ApolloLeadProvider
from outreach_mvp.models import CampaignInput, CompanyInput, LeadInput
from outreach_mvp.orchestrator import DraftFirstOrchestrator


def make_company():
    return CompanyInput("Acme", "", "Industrial pumps manufacturer", {})


def make_campaign(**overrides):
    defaults = dict(
        name="orchestrator-fixes",
        target_country="Oman",
        target_region="",
        max_drafts=10,
        sender_name="P",
        sender_email="p@example.com",
        template="Hi {{first_name}}, I noticed {{company_name}} works in {{lead_context}}. {{value_prop}}. Best, {{sender_name}}",
        target_titles=["Procurement Manager"],
        target_industries=["Industrial"],
    )
    defaults.update(overrides)
    return CampaignInput(**defaults)


def make_lead(**overrides):
    defaults = dict(
        first_name="Said",
        last_name="M",
        email="said@example.om",
        title="Procurement Manager",
        company_name="Muscat Ind",
        country="Oman",
        industry="Industrial",
        website="",
        context="pumps",
    )
    defaults.update(overrides)
    return LeadInput(**defaults)


class DedupeTests(unittest.TestCase):
    def test_duplicate_leads_produce_single_draft(self):
        lead = make_lead()
        result = DraftFirstOrchestrator().create_draft_campaign(make_company(), make_campaign(), [lead, lead])
        self.assertEqual(len(result.drafts), 1)
        self.assertEqual(result.skipped[lead.email], "duplicate_in_batch")

    def test_duplicate_detection_is_case_insensitive(self):
        first = make_lead(email="Said@Example.om")
        second = make_lead(email="said@example.om")
        result = DraftFirstOrchestrator().create_draft_campaign(make_company(), make_campaign(), [first, second])
        self.assertEqual(len(result.drafts), 1)


class ApolloBodyCleanlinessTests(unittest.TestCase):
    def test_apollo_sourced_email_body_contains_no_bookkeeping(self):
        person = {
            "first_name": "Fatima",
            "last_name": "Ali",
            "email": "fatima@gulf.example",
            "title": "Procurement Manager",
            "organization": {"name": "Gulf Traders", "industry": "Industrial"},
            "country": "Oman",
        }
        lead = ApolloLeadProvider()._person_to_lead(person)
        result = DraftFirstOrchestrator().create_draft_campaign(make_company(), make_campaign(), [lead])

        self.assertEqual(len(result.drafts), 1)
        self.assertNotIn("Apollo", result.drafts[0].body)
        self.assertNotIn("Apollo", result.drafts[0].subject)


class TemplateRenderingTests(unittest.TestCase):
    def test_missing_first_name_renders_hi_there(self):
        lead = make_lead(first_name="")
        result = DraftFirstOrchestrator().create_draft_campaign(make_company(), make_campaign(), [lead])
        self.assertEqual(len(result.drafts), 1)
        self.assertIn("Hi there,", result.drafts[0].body)

    def test_unknown_template_variable_produces_warning(self):
        campaign = make_campaign(template="Hi {{first_nam}}, {{value_prop}}. Best, {{sender_name}}")
        result = DraftFirstOrchestrator().create_draft_campaign(make_company(), campaign, [make_lead()])
        self.assertEqual(len(result.drafts), 1)
        self.assertIn("unknown_variable:first_nam", result.drafts[0].render_warnings)

    def test_known_variables_produce_no_warnings(self):
        result = DraftFirstOrchestrator().create_draft_campaign(make_company(), make_campaign(), [make_lead()])
        self.assertEqual(result.drafts[0].render_warnings, [])


class ScoreThresholdTests(unittest.TestCase):
    def test_campaign_score_threshold_is_honored(self):
        # This lead scores 65 (title 30 + industry 25 + context 10) with no country match.
        lead = make_lead(country="Qatar")
        default_result = DraftFirstOrchestrator().create_draft_campaign(make_company(), make_campaign(), [lead])
        self.assertEqual(len(default_result.drafts), 1)

        strict = make_campaign(score_threshold=70)
        strict_result = DraftFirstOrchestrator().create_draft_campaign(make_company(), strict, [lead])
        self.assertEqual(strict_result.drafts, [])
        self.assertEqual(strict_result.skipped[lead.email], "low_score")


if __name__ == "__main__":
    unittest.main()
