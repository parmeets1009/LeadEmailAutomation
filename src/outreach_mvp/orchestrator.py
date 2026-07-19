from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from .compliance import ComplianceAgent
from .email_agent import EmailPersonalizationAgent
from .lead_agent import LeadQualificationAgent
from .models import CampaignInput, CampaignResult, CompanyInput, EmailDraft, LeadInput, LeadScore
from .profile_agent import BusinessProfileAgent
from .llm import LLMRouter
from .enrichment import ScraplingEnrichmentProvider

logger = logging.getLogger("outreach_mvp.orchestrator")

# Rules and LLM disagree most in the middle band; only those leads are worth an LLM
# call. The upper bound is raised to the campaign threshold when the threshold is
# higher, so a stronger-by-rules lead is never skipped while a weaker one gets an
# LLM rescue (monotonicity).
LLM_SCORING_BAND = (40, 70)


class DraftFirstOrchestrator:
    def __init__(
        self,
        suppression_list: set[str] | None = None,
        llm_router: LLMRouter | None = None,
        llm_provider: str = "deterministic",
        llm_model: str | None = None,
        enrichment_provider: ScraplingEnrichmentProvider | None = None,
        llm_scoring: bool = True,
        max_workers: int = 4,
        contacted_store=None,
        allow_recontact: bool = False,
        unsubscribe_base_url: str = "",
        unsubscribe_secret: str = "",
    ) -> None:
        self.llm_router = llm_router or LLMRouter(provider=llm_provider, model=llm_model)
        self.enrichment_provider = enrichment_provider
        self.compliance = ComplianceAgent(suppression_list)
        self.profile_agent = BusinessProfileAgent(self.llm_router)
        self.lead_agent = LeadQualificationAgent()
        self.email_agent = EmailPersonalizationAgent(
            self.compliance,
            self.llm_router,
            unsubscribe_base_url=unsubscribe_base_url,
            unsubscribe_secret=unsubscribe_secret,
        )
        self.llm_scoring = llm_scoring
        self.max_workers = max(1, max_workers)
        self.contacted_store = contacted_store
        self.allow_recontact = allow_recontact

    def profile_company(self, company: CompanyInput):
        return self.profile_agent.profile(company)

    def create_draft_campaign(self, company: CompanyInput, campaign: CampaignInput, leads: list[LeadInput]) -> CampaignResult:
        profile = self.profile_company(company)
        skipped: dict[str, str] = {}

        # Dedupe by email within the batch — first occurrence wins.
        seen_emails: set[str] = set()
        unique_leads: list[LeadInput] = []
        for lead in leads:
            key = lead.email.strip().lower()
            if key and key in seen_emails:
                skipped[lead.email] = "duplicate_in_batch"
                continue
            if key:
                seen_emails.add(key)
            unique_leads.append(lead)

        original_contexts = [lead.context for lead in unique_leads]
        if self.enrichment_provider and unique_leads:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                unique_leads = list(executor.map(self.enrichment_provider.enrich, unique_leads))

        threshold = getattr(campaign, "score_threshold", 50)
        band_low, band_high = LLM_SCORING_BAND[0], max(LLM_SCORING_BAND[1], threshold)
        scored: list[tuple[LeadInput, LeadScore]] = []
        for lead, original_context in zip(unique_leads, original_contexts):
            precheck = self.compliance.precheck_lead(lead)
            if precheck:
                skipped[lead.email] = precheck
                continue
            if self.contacted_store is not None and not self.allow_recontact and self.contacted_store.was_contacted(lead.email):
                skipped[lead.email] = "already_contacted"
                continue
            score = self.lead_agent.score(lead, campaign)
            if lead.context and not original_context:
                score.reasons.append("website_enriched_context")
            if self.llm_scoring and self.llm_router.enabled and band_low <= score.score < band_high:
                fit, fit_error = self.llm_router.score_lead(profile, campaign, lead)
                if fit_error:
                    score.reasons.append("llm_score_failed")
                elif fit:
                    # The fit dict is unvalidated for non-Claude providers — treat
                    # every field defensively; a malformed response must never
                    # abort the campaign run.
                    raw = fit.get("disqualifiers")
                    if isinstance(raw, str) and raw.strip():
                        raw = [raw]
                    disqualifiers = [str(item).strip() for item in raw if str(item).strip()] if isinstance(raw, list) else []
                    if disqualifiers:
                        skipped[lead.email] = ("llm_disqualified:" + ",".join(disqualifiers))[:160]
                        continue
                    try:
                        fit_score = max(0, min(int(fit.get("fit_score", score.score)), 100))
                    except (TypeError, ValueError):
                        logger.warning("LLM returned non-numeric fit_score %r for %s; keeping rule score", fit.get("fit_score"), lead.email)
                        score.reasons.append("llm_score_invalid")
                    else:
                        score = LeadScore(score=fit_score, reasons=score.reasons + ["llm_scored"])
            if score.score < threshold:
                llm_trouble = "llm_score_failed" in score.reasons or "llm_score_invalid" in score.reasons
                skipped[lead.email] = "low_score(llm_scoring_failed)" if llm_trouble else "low_score"
                continue
            scored.append((lead, score))

        scored.sort(key=lambda item: item[1].score, reverse=True)
        max_drafts = min(campaign.max_drafts, 50)
        selected = scored[:max_drafts]

        candidate_drafts: list[EmailDraft] = []
        if selected:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                candidate_drafts = list(
                    executor.map(lambda pair: self.email_agent.draft(profile, campaign, pair[0], pair[1]), selected)
                )

        drafts: list[EmailDraft] = []
        for draft in candidate_drafts:
            if draft.compliance.status == "passed":
                drafts.append(draft)
            else:
                skipped[draft.lead.email] = ",".join(draft.compliance.reasons)

        return CampaignResult(
            campaign=campaign,
            business_profile=profile,
            drafts=drafts,
            skipped=skipped,
            llm_provider=self.llm_router.provider,
            llm_model=self.llm_router.model,
            prompt_version=self.llm_router.prompt_version,
        )
