from __future__ import annotations

import re

from .models import CampaignInput, ComplianceResult, LeadInput

# Deliberately loose: rejects obvious garbage, not a full RFC 5322 validator.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ComplianceAgent:
    def __init__(self, suppression_list: set[str] | None = None) -> None:
        # Strip AND lower: pasted suppression lists routinely carry padding, and a
        # padded entry that fails to match would let a suppressed address through.
        self.suppression_list = {email.strip().lower() for email in (suppression_list or set()) if email.strip()}

    def precheck_lead(self, lead: LeadInput) -> str | None:
        if not lead.email:
            return "missing_email"
        if not EMAIL_RE.match(lead.email):
            return "invalid_email_format"
        if lead.email.lower() in self.suppression_list:
            return "suppressed"
        return None

    def check_draft(self, lead: LeadInput, campaign: CampaignInput, body: str) -> ComplianceResult:
        reasons: list[str] = []
        if not lead.email:
            reasons.append("missing_email")
        elif not EMAIL_RE.match(lead.email):
            reasons.append("invalid_email_format")
        if lead.email.lower() in self.suppression_list:
            reasons.append("suppressed")
        if "unsubscribe" not in body.lower() and "not relevant" not in body.lower():
            reasons.append("missing_opt_out_language")
        if not campaign.sender_email:
            reasons.append("missing_sender")
        return ComplianceResult(status="failed" if reasons else "passed", reasons=reasons)

    def add_opt_out_footer(self, body: str, unsubscribe_url: str = "", sender_identity: str = "") -> str:
        if "unsubscribe" in body.lower() or "not relevant" in body.lower():
            return body
        lines = [body.rstrip(), ""]
        if sender_identity:
            lines.append(sender_identity)
        lines.append("If this is not relevant, reply 'not relevant' and I will not contact you again.")
        if unsubscribe_url:
            lines.append(f"Unsubscribe with one click: {unsubscribe_url}")
        return "\n".join(lines)
