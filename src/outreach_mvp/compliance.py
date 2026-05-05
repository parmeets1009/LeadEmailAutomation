from __future__ import annotations

from .models import CampaignInput, ComplianceResult, LeadInput


class ComplianceAgent:
    def __init__(self, suppression_list: set[str] | None = None) -> None:
        self.suppression_list = {email.lower() for email in (suppression_list or set())}

    def precheck_lead(self, lead: LeadInput) -> str | None:
        if not lead.email:
            return "missing_email"
        if lead.email.lower() in self.suppression_list:
            return "suppressed"
        return None

    def check_draft(self, lead: LeadInput, campaign: CampaignInput, body: str) -> ComplianceResult:
        reasons: list[str] = []
        if not lead.email:
            reasons.append("missing_email")
        if lead.email.lower() in self.suppression_list:
            reasons.append("suppressed")
        if "unsubscribe" not in body.lower() and "not relevant" not in body.lower():
            reasons.append("missing_opt_out_language")
        if campaign.max_drafts > 50:
            reasons.append("daily_cap_above_mvp_limit")
        if not campaign.sender_email:
            reasons.append("missing_sender")
        return ComplianceResult(status="failed" if reasons else "passed", reasons=reasons)

    def add_opt_out_footer(self, body: str) -> str:
        if "unsubscribe" in body.lower() or "not relevant" in body.lower():
            return body
        return body.rstrip() + "\n\nIf this is not relevant, reply 'not relevant' and I will not contact you again."
