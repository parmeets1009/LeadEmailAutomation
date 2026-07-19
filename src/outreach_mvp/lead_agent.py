from __future__ import annotations

import re

from .models import CampaignInput, LeadInput, LeadScore

# Common shorthand for countries leads type into CRMs. Keys are matched AFTER
# dots are stripped and whitespace collapsed, so "U.A.E" and "u.s." hit "uae"/"us".
COUNTRY_ALIASES = {
    "uae": "united arab emirates",
    "usa": "united states",
    "us": "united states",
    "united states of america": "united states",
    "uk": "united kingdom",
    "ksa": "saudi arabia",
    "prc": "china",
    "the netherlands": "netherlands",
    "holland": "netherlands",
}

DEFAULT_WEIGHTS = {
    "country_match": 30,
    "region_match": 30,
    "title_match": 30,
    "industry_match": 25,
    "has_website": 5,
    "has_context": 10,
}


class LeadQualificationAgent:
    def __init__(self, weights: dict[str, int] | None = None) -> None:
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    def score(self, lead: LeadInput, campaign: CampaignInput) -> LeadScore:
        score = 0
        reasons: list[str] = []
        lead_country = self._norm_country(lead.country)
        target_country = self._norm_country(campaign.target_country)
        target_region = self._norm_country(campaign.target_region)
        # Equality after alias normalization, plus multi-token subset for long
        # forms ("United States of America" vs "United States"). Substring
        # matching produced false positives like "oman" inside "romania"; the
        # >=2-token rule keeps single-token traps (Guinea/Papua New Guinea,
        # Sudan/South Sudan) from coming back.
        if target_country and self._country_matches(lead_country, target_country):
            score += self.weights["country_match"]
            reasons.append("country_match")
        elif target_region and self._tokens(target_region) and self._tokens(target_region) <= self._tokens(lead_country):
            score += self.weights["region_match"]
            reasons.append("region_match")

        # A target title matches only when ALL its tokens appear in the lead title:
        # "Procurement Manager" matches "Senior Procurement Manager" but a bare
        # "Manager" lead no longer matches specific targets.
        lead_title_tokens = self._tokens(lead.title)
        for target_title in campaign.target_titles:
            target_tokens = self._tokens(target_title)
            if target_tokens and target_tokens <= lead_title_tokens:
                score += self.weights["title_match"]
                reasons.append("title_match")
                break

        # Industry matches on the industry field only; context already earns its
        # own points and polluted this check with incidental keyword mentions.
        industry_tokens = self._tokens(lead.industry)
        for target_industry in campaign.target_industries:
            target_tokens = self._tokens(target_industry)
            if target_tokens and target_tokens <= industry_tokens:
                score += self.weights["industry_match"]
                reasons.append("industry_match")
                break

        if lead.website:
            score += self.weights["has_website"]
            reasons.append("has_website")
        if lead.context:
            score += self.weights["has_context"]
            reasons.append("has_context")
        if not lead.email:
            score = 0
            reasons.append("missing_email")
        return LeadScore(score=min(score, 100), reasons=reasons)

    def _norm_country(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", value.replace(".", "").strip().lower())
        return COUNTRY_ALIASES.get(normalized, normalized)

    def _country_matches(self, lead_country: str, target_country: str) -> bool:
        if lead_country == target_country:
            return True
        lead_tokens = self._tokens(lead_country)
        target_tokens = self._tokens(target_country)
        small, big = (lead_tokens, target_tokens) if len(lead_tokens) <= len(target_tokens) else (target_tokens, lead_tokens)
        return len(small) >= 2 and small <= big

    def _tokens(self, value: str) -> set[str]:
        return set(re.findall(r"[a-z0-9]+", value.lower()))
