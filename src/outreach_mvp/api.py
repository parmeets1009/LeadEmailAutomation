from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .apollo import ApolloLeadProvider, ApolloProviderNotConfigured, ApolloSearchClient
from .dashboard import FRONTEND_DIR, dashboard_html
from .enrichment import ScraplingEnrichmentProvider
from .llm import DEFAULT_MODELS, LLMRouter
from .mailbox import ApprovalRequiredError, GmailApiDraftStore, GmailDraftClient, LocalMailboxDraftStore, OutlookApiDraftStore, OutlookDraftClient, UnsupportedMailboxProviderError
from .models import CampaignInput, CompanyInput, LeadInput, to_plain_data
from .oauth_clients import GmailOAuthDraftClient, OutlookOAuthDraftClient, create_mailbox_clients_from_env
from .oauth_setup import OAuthConfigurationError, OAuthSetupService, OAuthStateError, create_oauth_setup_service_from_env
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
    delivery: str = "local"


class ApolloLeadSearchRequest(BaseModel):
    titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    company_domains: list[str] = Field(default_factory=list)
    company_names: list[str] = Field(default_factory=list)
    keywords: str = ""
    max_leads: int = 25


def create_app(
    storage_dir: Path | str = Path("campaign_runs"),
    gmail_draft_client: GmailDraftClient | None = None,
    outlook_draft_client: OutlookDraftClient | None = None,
    apollo_client: ApolloSearchClient | None = None,
    load_oauth_clients_from_env: bool = True,
    oauth_service: OAuthSetupService | None = None,
) -> FastAPI:
    app = FastAPI(title="Lead Email Automation API", version="0.1.0")
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
    storage_path = Path(storage_dir)
    store = JsonCampaignStore(storage_path)
    mailbox_store = LocalMailboxDraftStore(storage_path / "mailbox_drafts")
    oauth_service = oauth_service or create_oauth_setup_service_from_env(storage_path)
    if load_oauth_clients_from_env and (gmail_draft_client is None or outlook_draft_client is None):
        oauth_clients = create_mailbox_clients_from_env()
        gmail_draft_client = gmail_draft_client or oauth_clients.gmail
        outlook_draft_client = outlook_draft_client or oauth_clients.outlook
    gmail_api_store = GmailApiDraftStore(gmail_draft_client) if gmail_draft_client else None
    outlook_api_store = OutlookApiDraftStore(outlook_draft_client) if outlook_draft_client else None
    apollo_provider = ApolloLeadProvider(client=apollo_client) if apollo_client else ApolloLeadProvider.from_env()

    def get_gmail_api_store() -> GmailApiDraftStore | None:
        nonlocal gmail_api_store
        if gmail_api_store is None and oauth_service.token_path("gmail").exists():
            gmail_api_store = GmailApiDraftStore(GmailOAuthDraftClient.from_authorized_user_file(oauth_service.token_path("gmail")))
        return gmail_api_store

    def get_outlook_api_store() -> OutlookApiDraftStore | None:
        nonlocal outlook_api_store
        if outlook_api_store is None and oauth_service.token_path("outlook").exists():
            outlook_api_store = OutlookApiDraftStore(OutlookOAuthDraftClient.from_token_file(oauth_service.token_path("outlook")))
        return outlook_api_store

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

    @app.get("/mailboxes/status")
    def mailbox_status() -> dict[str, Any]:
        return oauth_service.status()

    @app.get("/oauth/providers")
    def oauth_providers() -> dict[str, Any]:
        return oauth_service.status()

    @app.get("/oauth/{provider}/start")
    def oauth_start(provider: str) -> dict[str, str]:
        try:
            return oauth_service.start(provider)
        except OAuthConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/oauth/{provider}/callback")
    def oauth_callback(provider: str, code: str, state: str) -> dict[str, Any]:
        try:
            return oauth_service.callback(provider, code=code, state=state)
        except OAuthConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except OAuthStateError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/companies/profile")
    def profile_company(company: CompanyRequest) -> dict[str, Any]:
        profile = DraftFirstOrchestrator().profile_company(company.to_domain())
        return to_plain_data(profile)

    @app.post("/leads/apollo/search")
    def search_apollo_leads(request: ApolloLeadSearchRequest) -> dict[str, Any]:
        if apollo_provider is None:
            raise HTTPException(status_code=503, detail="Apollo lead provider not configured; use CSV fallback or set APOLLO_API_KEY")
        try:
            leads = apollo_provider.search_leads(
                titles=request.titles,
                locations=request.locations,
                industries=request.industries,
                company_domains=request.company_domains,
                company_names=request.company_names,
                keywords=request.keywords,
                max_leads=request.max_leads,
            )
        except ApolloProviderNotConfigured as exc:
            raise HTTPException(status_code=503, detail=f"{exc}; use CSV fallback") from exc
        return {"source": "apollo", "count": len(leads), "leads": to_plain_data(leads), "fallback_available": "csv"}

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

    @app.get("/campaigns")
    def list_campaigns() -> dict[str, Any]:
        campaigns = store.list_campaigns()
        return {"count": len(campaigns), "campaigns": campaigns}

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
            delivery = request.delivery.strip().lower()
            provider = request.provider.strip().lower()
            if delivery == "gmail_api":
                if provider != "gmail":
                    raise UnsupportedMailboxProviderError("gmail_api delivery only supports provider 'gmail'")
                active_gmail_store = get_gmail_api_store()
                if active_gmail_store is None:
                    raise HTTPException(status_code=503, detail="gmail draft client not configured")
                mailbox_result = active_gmail_store.create_draft(result.campaign, draft)
            elif delivery == "outlook_graph":
                if provider != "outlook":
                    raise UnsupportedMailboxProviderError("outlook_graph delivery only supports provider 'outlook'")
                active_outlook_store = get_outlook_api_store()
                if active_outlook_store is None:
                    raise HTTPException(status_code=503, detail="outlook draft client not configured")
                mailbox_result = active_outlook_store.create_draft(result.campaign, draft)
            elif delivery == "local":
                mailbox_result = mailbox_store.create_draft(request.provider, result.campaign, draft)
            else:
                raise UnsupportedMailboxProviderError(f"unsupported mailbox delivery '{request.delivery}'")
        except ApprovalRequiredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except UnsupportedMailboxProviderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return to_plain_data(mailbox_result)

    return app


app = create_app()
