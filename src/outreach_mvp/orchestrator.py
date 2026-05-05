from __future__ import annotations

from .compliance import ComplianceAgent
from .email_agent import EmailPersonalizationAgent
from .lead_agent import LeadQualificationAgent
from .models import CampaignInput, CampaignResult, CompanyInput, LeadInput
from .profile_agent import BusinessProfileAgent
from .llm import LLMRouter


class DraftFirstOrchestrator:
    def __init__(self, suppression_list: set[str] | None = None, llm_router: LLMRouter | None = None, llm_provider: str = "deterministic", llm_model: str | None = None) -> None:
        self.llm_router = llm_router or LLMRouter(provider=llm_provider, model=llm_model)
        self.compliance = ComplianceAgent(suppression_list)
        self.profile_agent = BusinessProfileAgent(self.llm_router)
        self.lead_agent = LeadQualificationAgent()
        self.email_agent = EmailPersonalizationAgent(self.compliance, self.llm_router)

    def profile_company(self, company: CompanyInput):
        return self.profile_agent.profile(company)

    def create_draft_campaign(self, company: CompanyInput, campaign: CampaignInput, leads: list[LeadInput]) -> CampaignResult:
        profile = self.profile_company(company)
        skipped: dict[str, str] = {}
        scored = []
        for lead in leads:
            precheck = self.compliance.precheck_lead(lead)
            if precheck:
                skipped[lead.email] = precheck
                continue
            score = self.lead_agent.score(lead, campaign)
            if score.score < 50:
                skipped[lead.email] = "low_score"
                continue
            scored.append((lead, score))

        scored.sort(key=lambda item: item[1].score, reverse=True)
        max_drafts = min(campaign.max_drafts, 50)
        drafts = []
        for lead, score in scored[:max_drafts]:
            draft = self.email_agent.draft(profile, campaign, lead, score)
            if draft.compliance.status == "passed":
                drafts.append(draft)
            else:
                skipped[lead.email] = ",".join(draft.compliance.reasons)

        return CampaignResult(
            campaign=campaign,
            business_profile=profile,
            drafts=drafts,
            skipped=skipped,
            llm_provider=self.llm_router.provider,
            llm_model=self.llm_router.model,
            prompt_version=self.llm_router.prompt_version,
        )
