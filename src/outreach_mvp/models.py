from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


@dataclass(frozen=True)
class CompanyInput:
    name: str
    website: str
    description: str
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BusinessProfile:
    company_name: str
    website: str
    summary: str
    product_categories: list[str]
    buyer_personas: list[str]
    target_industries: list[str]
    value_propositions: list[str]
    suggested_apollo_filters: dict[str, list[str] | str]


@dataclass(frozen=True)
class CampaignInput:
    name: str
    target_country: str
    target_region: str
    max_drafts: int
    sender_name: str
    sender_email: str
    template: str
    target_titles: list[str] = field(default_factory=list)
    target_industries: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LeadInput:
    first_name: str
    last_name: str
    email: str
    title: str
    company_name: str
    country: str
    industry: str
    website: str
    context: str = ""


@dataclass(frozen=True)
class LeadScore:
    score: int
    reasons: list[str]


@dataclass(frozen=True)
class ComplianceResult:
    status: str
    reasons: list[str]


@dataclass(frozen=True)
class EmailDraft:
    lead: LeadInput
    subject: str
    body: str
    personalization_reason: str
    lead_score: LeadScore
    compliance: ComplianceResult
    approval_required: bool = True


@dataclass(frozen=True)
class CampaignResult:
    campaign: CampaignInput
    business_profile: BusinessProfile
    drafts: list[EmailDraft]
    skipped: dict[str, str]
    status: str = "drafts_ready_for_review"


def to_plain_data(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_plain_data(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    if isinstance(value, dict):
        return {str(key): to_plain_data(item) for key, item in value.items()}
    return value


def from_campaign_result(data: dict[str, Any]) -> CampaignResult:
    profile_data = data["business_profile"]
    drafts = []
    for draft_data in data.get("drafts", []):
        lead = LeadInput(**draft_data["lead"])
        score = LeadScore(**draft_data["lead_score"])
        compliance = ComplianceResult(**draft_data["compliance"])
        drafts.append(
            EmailDraft(
                lead=lead,
                subject=draft_data["subject"],
                body=draft_data["body"],
                personalization_reason=draft_data["personalization_reason"],
                lead_score=score,
                compliance=compliance,
                approval_required=draft_data.get("approval_required", True),
            )
        )
    return CampaignResult(
        campaign=CampaignInput(**data["campaign"]),
        business_profile=BusinessProfile(**profile_data),
        drafts=drafts,
        skipped=data.get("skipped", {}),
        status=data.get("status", "drafts_ready_for_review"),
    )
