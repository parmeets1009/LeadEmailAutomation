from __future__ import annotations

from .models import CampaignInput, LeadInput, LeadScore


class LeadQualificationAgent:
    def score(self, lead: LeadInput, campaign: CampaignInput) -> LeadScore:
        score = 0
        reasons: list[str] = []
        lead_country = self._norm(lead.country)
        target_country = self._norm(campaign.target_country)
        target_region = self._norm(campaign.target_region)
        if target_country and (target_country in lead_country or lead_country in target_country):
            score += 30
            reasons.append("country_match")
        elif target_region and target_region in lead_country:
            score += 30
            reasons.append("region_match")

        title = self._norm(lead.title)
        for target_title in campaign.target_titles:
            if self._norm(target_title) in title or title in self._norm(target_title):
                score += 30
                reasons.append("title_match")
                break

        industry = self._norm(lead.industry + " " + lead.context)
        for target_industry in campaign.target_industries:
            if self._norm(target_industry) in industry:
                score += 25
                reasons.append("industry_match")
                break

        if lead.website:
            score += 5
            reasons.append("has_website")
        if lead.context:
            score += 10
            reasons.append("has_context")
        if not lead.email:
            score = 0
            reasons.append("missing_email")
        return LeadScore(score=min(score, 100), reasons=reasons)

    def _norm(self, value: str) -> str:
        normalized = value.strip().lower()
        if normalized == "uae":
            return "united arab emirates"
        return normalized
