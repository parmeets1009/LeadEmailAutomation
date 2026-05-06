from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .dashboard import dashboard_html
from .enrichment import ScraplingEnrichmentProvider
from .llm import DEFAULT_MODELS, LLMRouter
from .mailbox import ApprovalRequiredError, LocalMailboxDraftStore, UnsupportedMailboxProviderError
from .models import CampaignInput, CompanyInput, LeadInput, to_plain_data
from .orchestrator import DraftFirstOrchestrator
from .storage import JsonCampaignStore


class CompanyRequest(BaseModel):
    name: str
    website: str = ""
    description: str
    details: dict[str, str] = Field(default_factory=dict)

    def to_domain(self) -> CompanyInput:
        return CompanyInput(name=self.name, website=self.website, description=self.description, details=self.details)


class CampaignRequest(BaseModel):
    name: str
    target_country: str
    target_region: str
    max_drafts: int = 10
    sender_name: str
    sender_email: str
    template: str
    target_titles: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)

    def to_domain(self) -> CampaignInput:
        return CampaignInput(
            name=self.name,
            target_country=self.target_country,
            target_region=self.target_region,
            max_drafts=self.max_drafts,
            sender_name=self.sender_name,
            sender_email=self.sender_email,
            template=self.template,
            target_titles=self.target_titles,
            target_industries=self.target_industries,
        )


class LeadRequest(BaseModel):
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    title: str = ""
    company_name: str = ""
    country: str = ""
    industry: str = ""
    website: str = ""
    context: str = ""

    def to_domain(self) -> LeadInput:
        return LeadInput(
            first_name=self.first_name,
            last_name=self.last_name,
            email=self.email,
            title=self.title,
            company_name=self.company_name,
            country=self.country,
            industry=self.industry,
            website=self.website,
            context=self.context,
        )


class DraftCampaignRequest(BaseModel):
    company: CompanyRequest
    campaign: CampaignRequest
    leads: list[LeadRequest]
    suppression_list: list[str] = Field(default_factory=list)
    llm_provider: str = "deterministic"
    llm_model: str | None = None
    enrich_websites: bool = False


class ApproveDraftRequest(BaseModel):
    approved_by: str = ""
    notes: str = ""


class EditDraftRequest(BaseModel):
    subject: str | None = None
    body: str | None = None
    edited_by: str = ""


class MailboxDraftRequest(BaseModel):
    provider: str


def create_app(storage_dir: Path | str = Path("campaign_runs")) -> FastAPI:
    app = FastAPI(title="Lead Email Automation API", version="0.1.0")
    store = JsonCampaignStore(Path(storage_dir))
    mailbox_store = LocalMailboxDraftStore(Path(storage_dir) / "mailbox_drafts")

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return dashboard_html()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/llm/providers")
    def llm_providers() -> dict[str, Any]:
        return {
            "default_provider": "deterministic",
            "available_providers": ["deterministic", "codex", "gemini"],
            "default_models": {
                "deterministic": DEFAULT_MODELS["deterministic"],
                "codex": DEFAULT_MODELS["codex"],
                "gemini": DEFAULT_MODELS["gemini"],
            },
        }

    @app.post("/companies/profile")
    def profile_company(company: CompanyRequest) -> dict[str, Any]:
        profile = DraftFirstOrchestrator().profile_company(company.to_domain())
        return to_plain_data(profile)

    @app.post("/campaigns/draft", status_code=201)
    def create_draft_campaign(request: DraftCampaignRequest) -> dict[str, Any]:
        try:
            llm_router = LLMRouter(provider=request.llm_provider, model=request.llm_model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        enrichment_provider = ScraplingEnrichmentProvider() if request.enrich_websites else None
        orchestrator = DraftFirstOrchestrator(suppression_list=set(request.suppression_list), llm_router=llm_router, enrichment_provider=enrichment_provider)
        result = orchestrator.create_draft_campaign(
            company=request.company.to_domain(),
            campaign=request.campaign.to_domain(),
            leads=[lead.to_domain() for lead in request.leads],
        )
        saved_path = store.save(result)
        data = to_plain_data(result)
        data["campaign_id"] = saved_path.stem
        return data

    @app.get("/campaigns/{campaign_id}")
    def get_campaign(campaign_id: str) -> dict[str, Any]:
        try:
            result = store.load_campaign(campaign_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="campaign not found") from exc
        data = to_plain_data(result)
        data["campaign_id"] = campaign_id
        return data

    @app.get("/campaigns/{campaign_id}/drafts")
    def list_drafts(campaign_id: str) -> dict[str, Any]:
        try:
            result = store.load_campaign(campaign_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="campaign not found") from exc
        return {"campaign_id": campaign_id, "drafts": to_plain_data(result.drafts)}

    @app.patch("/campaigns/{campaign_id}/drafts/{draft_id}/approve")
    def approve_draft(campaign_id: str, draft_id: str, request: ApproveDraftRequest) -> dict[str, Any]:
        try:
            draft = store.approve_draft(campaign_id, draft_id, approved_by=request.approved_by, notes=request.notes)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="campaign not found") from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="draft not found") from exc
        return to_plain_data(draft)

    @app.patch("/campaigns/{campaign_id}/drafts/{draft_id}/edit")
    def edit_draft(campaign_id: str, draft_id: str, request: EditDraftRequest) -> dict[str, Any]:
        try:
            draft = store.edit_draft(campaign_id, draft_id, subject=request.subject, body=request.body, edited_by=request.edited_by)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="campaign not found") from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="draft not found") from exc
        return to_plain_data(draft)

    @app.post("/campaigns/{campaign_id}/drafts/{draft_id}/mailbox-drafts", status_code=201)
    def create_mailbox_draft(campaign_id: str, draft_id: str, request: MailboxDraftRequest) -> dict[str, Any]:
        try:
            result = store.load_campaign(campaign_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="campaign not found") from exc
        draft = next((item for item in result.drafts if item.draft_id == draft_id), None)
        if draft is None:
            raise HTTPException(status_code=404, detail="draft not found")
        try:
            mailbox_result = mailbox_store.create_draft(request.provider, result.campaign, draft)
        except ApprovalRequiredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except UnsupportedMailboxProviderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return to_plain_data(mailbox_result)

    return app


app = create_app()
