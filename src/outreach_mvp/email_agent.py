from __future__ import annotations

import re

from .models import BusinessProfile, CampaignInput, EmailDraft, LeadInput, LeadScore
from .compliance import ComplianceAgent


class EmailPersonalizationAgent:
    def __init__(self, compliance: ComplianceAgent | None = None) -> None:
        self.compliance = compliance or ComplianceAgent()

    def draft(self, profile: BusinessProfile, campaign: CampaignInput, lead: LeadInput, score: LeadScore) -> EmailDraft:
        value_prop = profile.value_propositions[0] if profile.value_propositions else "reliable supply and responsive service"
        lead_context = lead.context or f"the {lead.industry or 'your'} sector"
        variables = {
            "first_name": lead.first_name,
            "last_name": lead.last_name,
            "company_name": lead.company_name,
            "lead_context": lead_context,
            "value_prop": value_prop,
            "sender_name": campaign.sender_name,
            "sender_email": campaign.sender_email,
            "target_region": campaign.target_region,
        }
        body = self._render(campaign.template, variables)
        body = self.compliance.add_opt_out_footer(body)
        subject = f"Potential supply fit for {lead.company_name}"
        reason = f"Personalized using title '{lead.title}', company '{lead.company_name}', and context '{lead_context}'."
        compliance = self.compliance.check_draft(lead, campaign, body)
        return EmailDraft(
            lead=lead,
            subject=subject,
            body=body,
            personalization_reason=reason,
            lead_score=score,
            compliance=compliance,
            approval_required=True,
        )

    def _render(self, template: str, variables: dict[str, str]) -> str:
        def replace(match: re.Match[str]) -> str:
            key = match.group(1).strip()
            return variables.get(key, "")

        return re.sub(r"{{\s*([^}]+)\s*}}", replace, template)
