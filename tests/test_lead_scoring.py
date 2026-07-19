import unittest

from outreach_mvp.lead_agent import LeadQualificationAgent
from outreach_mvp.models import CampaignInput, LeadInput


def make_campaign(**overrides):
    defaults = dict(
        name="probe",
        target_country="Oman",
        target_region="",
        max_drafts=10,
        sender_name="P",
        sender_email="p@example.com",
        template="Hi {{first_name}}",
        target_titles=["Procurement Manager"],
        target_industries=["Industrial"],
    )
    defaults.update(overrides)
    return CampaignInput(**defaults)


def make_lead(**overrides):
    defaults = dict(
        first_name="Test",
        last_name="Lead",
        email="lead@example.com",
        title="Procurement Manager",
        company_name="TestCo",
        country="Oman",
        industry="Industrial",
        website="",
        context="",
    )
    defaults.update(overrides)
    return LeadInput(**defaults)


class LeadScoringTests(unittest.TestCase):
    def setUp(self):
        self.agent = LeadQualificationAgent()

    def test_romania_does_not_match_oman(self):
        score = self.agent.score(make_lead(country="Romania"), make_campaign(target_country="Oman"))
        self.assertNotIn("country_match", score.reasons)

    def test_country_alias_uae_and_usa(self):
        uae = self.agent.score(make_lead(country="UAE"), make_campaign(target_country="United Arab Emirates"))
        self.assertIn("country_match", uae.reasons)
        usa = self.agent.score(make_lead(country="USA"), make_campaign(target_country="United States"))
        self.assertIn("country_match", usa.reasons)

    def test_long_form_country_names_still_match(self):
        cases = [
            ("United States of America", "United States"),
            ("U.A.E", "UAE"),
            ("The Netherlands", "Netherlands"),
            ("United Arab Emirates", "Emirates of the United Arab"),  # token-set, order-free
        ]
        for lead_country, target in cases:
            score = self.agent.score(make_lead(country=lead_country), make_campaign(target_country=target))
            self.assertIn("country_match", score.reasons, f"{lead_country} vs {target}")

    def test_single_token_country_subsets_do_not_match(self):
        for lead_country, target in [("South Sudan", "Sudan"), ("Papua New Guinea", "Guinea")]:
            score = self.agent.score(make_lead(country=lead_country), make_campaign(target_country=target))
            self.assertNotIn("country_match", score.reasons, f"{lead_country} vs {target}")

    def test_region_match_uses_tokens_not_substrings(self):
        campaign = make_campaign(target_country="", target_region="UAE")
        match = self.agent.score(make_lead(country="United Arab Emirates"), campaign)
        self.assertIn("region_match", match.reasons)
        no_match = self.agent.score(make_lead(country="Romania"), make_campaign(target_country="", target_region="Oman"))
        self.assertNotIn("region_match", no_match.reasons)

    def test_generic_manager_title_does_not_match(self):
        score = self.agent.score(make_lead(title="Manager"), make_campaign())
        self.assertNotIn("title_match", score.reasons)

    def test_senior_procurement_manager_matches(self):
        score = self.agent.score(make_lead(title="Senior Procurement Manager"), make_campaign())
        self.assertIn("title_match", score.reasons)

    def test_industry_not_matched_from_context(self):
        lead = make_lead(industry="Retail", context="we mention construction in passing")
        score = self.agent.score(lead, make_campaign(target_industries=["Construction"]))
        self.assertNotIn("industry_match", score.reasons)

    def test_industry_token_subset_matches(self):
        lead = make_lead(industry="Industrial Manufacturing")
        score = self.agent.score(lead, make_campaign(target_industries=["Manufacturing"]))
        self.assertIn("industry_match", score.reasons)

    def test_missing_email_zeroes_score(self):
        score = self.agent.score(make_lead(email=""), make_campaign())
        self.assertEqual(score.score, 0)
        self.assertIn("missing_email", score.reasons)


if __name__ == "__main__":
    unittest.main()
