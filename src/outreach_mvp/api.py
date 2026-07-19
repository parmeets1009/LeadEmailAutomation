from __future__ import annotations

import html
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .apollo import ApolloLeadProvider, ApolloProviderNotConfigured, ApolloRateLimited, ApolloSearchClient
from .compliance import ComplianceAgent
from .contacted import ContactedStore
from .dashboard import FRONTEND_DIR, dashboard_html
from .deliverability import check_domain, is_valid_domain
from .email_agent import EmailPersonalizationAgent
from .enrichment import ScraplingEnrichmentProvider
from .llm import AVAILABLE_PROVIDERS, DEFAULT_MODELS, LLMRouter
from .mailbox import (
    ApprovalRequiredError,
    GmailApiDraftStore,
    GmailApiSendStore,
    GmailDraftClient,
    GmailSendClient,
    LocalMailboxDraftStore,
    OutlookApiDraftStore,
    OutlookApiSendStore,
    OutlookDraftClient,
    OutlookSendClient,
    UnsupportedMailboxProviderError,
)
from .models import CampaignInput, CompanyInput, LeadInput, to_plain_data
from .oauth_clients import GmailOAuthDraftClient, OutlookOAuthDraftClient, create_mailbox_clients_from_env
from .oauth_setup import OAuthConfigurationError, OAuthSetupService, OAuthStateError, create_oauth_setup_service_from_env
from .orchestrator import DraftFirstOrchestrator
from .replies import ReplyClient, ReplySyncService
from .send_log import DEFAULT_DAILY_SEND_CAP, SendLog
from .sequences import advance_campaign
from .storage import JsonCampaignStore
from .suppression import SuppressionStore
from .unsubscribe import DEV_SECRET, verify_token


class CompanyRequest(BaseModel):
    name: str
    website: str = ""
    description: str
    details: dict[str, str] = Field(default_factory=dict)

    def to_domain(self) -> CompanyInput:
        return CompanyInput(name=self.name, website=self.website, description=self.description, details=self.details)


class StageRequest(BaseModel):
    offset_days: int = Field(ge=1, le=60)
    template: str = Field(min_length=1)


class CampaignRequest(BaseModel):
    name: str
    target_country: str
    target_region: str
    max_drafts: int = Field(default=10, ge=1, le=50, description="Drafts per run; the MVP hard cap is 50.")
    sender_name: str
    sender_email: str
    template: str
    target_titles: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    score_threshold: int = Field(default=50, ge=0, le=100)
    delivery_mode: str = Field(default="draft", pattern="^(draft|auto_send)$")
    stages: list[StageRequest] = Field(default_factory=list, max_length=3)

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
            score_threshold=self.score_threshold,
            delivery_mode=self.delivery_mode,
            stages=[{"offset_days": stage.offset_days, "template": stage.template} for stage in self.stages],
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
    llm_provider: str | None = None
    llm_model: str | None = None
    enrich_websites: bool = False
    llm_scoring: bool = True
    allow_recontact: bool = False


class SendDraftRequest(BaseModel):
    provider: str


class SyncRepliesRequest(BaseModel):
    newer_than_days: int = Field(default=7, ge=1, le=30)


class AdvanceRequest(BaseModel):
    now: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


class IcpRequest(BaseModel):
    company: CompanyRequest
    exclusions: list[str] = Field(default_factory=list)


class ApolloSearchFromProfileRequest(BaseModel):
    suggested_apollo_filters: dict[str, Any] = Field(default_factory=dict)
    max_leads: int = Field(default=25, ge=1, le=100)


class SuppressRequest(BaseModel):
    email: str
    reason: str = "manual"


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
    default_llm_provider: str | None = None,
    gmail_send_client: GmailSendClient | None = None,
    outlook_send_client: OutlookSendClient | None = None,
    gmail_reply_client: ReplyClient | None = None,
    outlook_reply_client: ReplyClient | None = None,
) -> FastAPI:
    default_llm_provider = default_llm_provider or ("claude" if (os.getenv("ANTHROPIC_API_KEY") or "").strip() else "deterministic")
    app_base_url = (os.getenv("APP_BASE_URL") or "").strip()
    unsubscribe_secret = (os.getenv("UNSUBSCRIBE_SECRET") or "").strip()
    if not unsubscribe_secret:
        if app_base_url:
            # A public deployment with the well-known dev secret would let anyone
            # forge unsubscribe tokens and mass-suppress arbitrary addresses.
            raise RuntimeError("UNSUBSCRIBE_SECRET must be set when APP_BASE_URL is configured — refusing to start with the public dev secret")
        unsubscribe_secret = DEV_SECRET
    send_lock = threading.Lock()
    app = FastAPI(title="Lead Email Automation API", version="0.1.0")
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR), name="assets")
    storage_path = Path(storage_dir)
    store = JsonCampaignStore(storage_path)
    mailbox_store = LocalMailboxDraftStore(storage_path / "mailbox_drafts")
    contacted_store = ContactedStore(storage_path / "contacted.json")
    suppression_store = SuppressionStore(storage_path / "suppression.json")
    send_log = SendLog(storage_path / "send_log.json")
    oauth_service = oauth_service or create_oauth_setup_service_from_env(storage_path)
    if load_oauth_clients_from_env and (gmail_draft_client is None or outlook_draft_client is None):
        oauth_clients = create_mailbox_clients_from_env()
        gmail_draft_client = gmail_draft_client or oauth_clients.gmail
        outlook_draft_client = outlook_draft_client or oauth_clients.outlook
    # The env-loaded OAuth clients also implement send/list — reuse them unless
    # dedicated clients were injected.
    if gmail_send_client is None and gmail_draft_client is not None and hasattr(gmail_draft_client, "send_message"):
        gmail_send_client = gmail_draft_client
    if outlook_send_client is None and outlook_draft_client is not None and hasattr(outlook_draft_client, "send_mail"):
        outlook_send_client = outlook_draft_client
    if gmail_reply_client is None and gmail_draft_client is not None and hasattr(gmail_draft_client, "list_recent_messages"):
        gmail_reply_client = gmail_draft_client
    if outlook_reply_client is None and outlook_draft_client is not None and hasattr(outlook_draft_client, "list_recent_messages"):
        outlook_reply_client = outlook_draft_client
    gmail_api_store = GmailApiDraftStore(gmail_draft_client) if gmail_draft_client else None
    outlook_api_store = OutlookApiDraftStore(outlook_draft_client) if outlook_draft_client else None
    gmail_send_store = GmailApiSendStore(gmail_send_client) if gmail_send_client else None
    outlook_send_store = OutlookApiSendStore(outlook_send_client) if outlook_send_client else None
    apollo_provider = ApolloLeadProvider(client=apollo_client) if apollo_client else ApolloLeadProvider.from_env()

    def _gmail_client_from_token():
        return GmailOAuthDraftClient.from_authorized_user_file(oauth_service.token_path("gmail"))

    def _outlook_client_from_token():
        return OutlookOAuthDraftClient.from_token_file(oauth_service.token_path("outlook"))

    def get_gmail_api_store() -> GmailApiDraftStore | None:
        nonlocal gmail_api_store
        if gmail_api_store is None and oauth_service.token_path("gmail").exists():
            gmail_api_store = GmailApiDraftStore(_gmail_client_from_token())
        return gmail_api_store

    def get_outlook_api_store() -> OutlookApiDraftStore | None:
        nonlocal outlook_api_store
        if outlook_api_store is None and oauth_service.token_path("outlook").exists():
            outlook_api_store = OutlookApiDraftStore(_outlook_client_from_token())
        return outlook_api_store

    def get_send_store(provider: str):
        nonlocal gmail_send_store, outlook_send_store
        if provider == "gmail":
            if gmail_send_store is None and oauth_service.token_path("gmail").exists():
                gmail_send_store = GmailApiSendStore(_gmail_client_from_token())
            return gmail_send_store
        if outlook_send_store is None and oauth_service.token_path("outlook").exists():
            outlook_send_store = OutlookApiSendStore(_outlook_client_from_token())
        return outlook_send_store

    def get_reply_client(provider: str) -> ReplyClient | None:
        nonlocal gmail_reply_client, outlook_reply_client
        if provider == "gmail":
            if gmail_reply_client is None and oauth_service.token_path("gmail").exists():
                gmail_reply_client = _gmail_client_from_token()
            return gmail_reply_client
        if outlook_reply_client is None and oauth_service.token_path("outlook").exists():
            outlook_reply_client = _outlook_client_from_token()
        return outlook_reply_client

    def build_router(provider: str | None, model: str | None) -> LLMRouter:
        try:
            return LLMRouter(provider=provider or default_llm_provider, model=model)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — provider client construction must not 500 opaquely
            raise HTTPException(status_code=503, detail=f"LLM provider initialization failed: {exc}") from exc

    @app.get("/", response_class=HTMLResponse)
    def dashboard() -> str:
        return dashboard_html()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/llm/providers")
    def llm_providers() -> dict[str, Any]:
        return {
            "default_provider": default_llm_provider,
            "available_providers": list(AVAILABLE_PROVIDERS),
            "default_models": dict(DEFAULT_MODELS),
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

    def _run_apollo_search(**search_kwargs: Any) -> dict[str, Any]:
        if apollo_provider is None:
            raise HTTPException(status_code=503, detail="Apollo lead provider not configured; use CSV fallback or set APOLLO_API_KEY")
        try:
            result = apollo_provider.search_leads(**search_kwargs)
        except ApolloProviderNotConfigured as exc:
            raise HTTPException(status_code=503, detail=f"{exc}; use CSV fallback") from exc
        except ApolloRateLimited as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        fresh = [lead for lead in result.leads if not contacted_store.was_contacted(lead.email)]
        return {
            "source": "apollo",
            "count": len(fresh),
            "leads": to_plain_data(fresh),
            "locked_email_count": result.locked_email_count,
            "already_contacted_count": len(result.leads) - len(fresh),
            "pages_fetched": result.pages_fetched,
            "fallback_available": "csv",
        }

    @app.post("/leads/apollo/search")
    def search_apollo_leads(request: ApolloLeadSearchRequest) -> dict[str, Any]:
        return _run_apollo_search(
            titles=request.titles,
            locations=request.locations,
            industries=request.industries,
            company_domains=request.company_domains,
            company_names=request.company_names,
            keywords=request.keywords,
            max_leads=request.max_leads,
        )

    @app.post("/leads/apollo/search-from-profile")
    def search_apollo_from_profile(request: ApolloSearchFromProfileRequest) -> dict[str, Any]:
        filters = request.suggested_apollo_filters or {}

        def _as_list(value: Any) -> list[str]:
            if isinstance(value, list):
                return [str(item) for item in value if str(item).strip()]
            return [str(value)] if str(value or "").strip() else []

        return _run_apollo_search(
            titles=_as_list(filters.get("person_titles")),
            locations=_as_list(filters.get("organization_locations")),
            industries=_as_list(filters.get("q_organization_keyword_tags")),
            max_leads=request.max_leads,
        )

    @app.post("/campaigns/draft", status_code=201)
    def create_draft_campaign(request: DraftCampaignRequest) -> dict[str, Any]:
        llm_router = build_router(request.llm_provider, request.llm_model)
        enrichment_provider = ScraplingEnrichmentProvider(llm_router=llm_router) if request.enrich_websites else None
        orchestrator = DraftFirstOrchestrator(
            suppression_list=set(request.suppression_list) | suppression_store.all_emails(),
            llm_router=llm_router,
            enrichment_provider=enrichment_provider,
            llm_scoring=request.llm_scoring,
            contacted_store=contacted_store,
            allow_recontact=request.allow_recontact,
            unsubscribe_base_url=app_base_url,
            unsubscribe_secret=unsubscribe_secret if app_base_url else "",
        )
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
        if suppression_store.contains(draft.lead.email):
            raise HTTPException(status_code=409, detail="recipient is on the suppression list")
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
        # A message is now in a mailbox (artifact or live draft) — record the
        # contact so future sourcing/campaigns skip this address.
        contacted_store.add(draft.lead.email, campaign_id, draft_id)
        return to_plain_data(mailbox_result)

    @app.patch("/campaigns/{campaign_id}/drafts/{draft_id}/mark-sent")
    def mark_sent(campaign_id: str, draft_id: str) -> dict[str, Any]:
        """Record that the human pressed Send in their own mail client (draft
        mode). Enables follow-up sequences without the auto-send path."""
        try:
            result = store.load_campaign(campaign_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="campaign not found") from exc
        draft = next((item for item in result.drafts if item.draft_id == draft_id), None)
        if draft is None:
            raise HTTPException(status_code=404, detail="draft not found")
        if not draft.approved:
            raise HTTPException(status_code=409, detail="only approved drafts can be marked sent")
        if draft.sent_at:
            raise HTTPException(status_code=409, detail="draft already marked sent")
        sent_at = datetime.now(timezone.utc).isoformat()
        updated = store.mark_draft_sent(campaign_id, draft_id, sent_at)
        contacted_store.add(draft.lead.email, campaign_id, draft_id, ts=sent_at)
        return to_plain_data(updated)

    @app.post("/campaigns/{campaign_id}/drafts/{draft_id}/send", status_code=201)
    def send_draft(campaign_id: str, draft_id: str, request: SendDraftRequest) -> dict[str, Any]:
        provider = request.provider.strip().lower()
        if provider not in {"gmail", "outlook"}:
            raise HTTPException(status_code=400, detail=f"unsupported provider '{request.provider}'")
        try:
            result = store.load_campaign(campaign_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="campaign not found") from exc
        draft = next((item for item in result.drafts if item.draft_id == draft_id), None)
        if draft is None:
            raise HTTPException(status_code=404, detail="draft not found")
        # The whole check-then-send-then-record section is serialized: without the
        # lock, parallel requests could double-send a draft or blow past the cap.
        with send_lock:
            # Preconditions — every one is server-enforced; the UI merely mirrors them.
            if not draft.approved or draft.review_status != "approved":
                raise HTTPException(status_code=409, detail="draft must be approved before sending")
            if getattr(result.campaign, "delivery_mode", "draft") != "auto_send":
                raise HTTPException(status_code=409, detail="campaign delivery_mode is 'draft' — recreate the campaign with delivery_mode='auto_send' to send from the app")
            if suppression_store.contains(draft.lead.email):
                raise HTTPException(status_code=409, detail="recipient is on the suppression list")
            lead_email = draft.lead.email.strip().lower()
            if any(d.replied for d in result.drafts if d.lead.email.strip().lower() == lead_email):
                raise HTTPException(status_code=409, detail="lead already replied — sending stopped")
            if send_log.was_sent(campaign_id, draft_id):
                raise HTTPException(status_code=409, detail="draft already sent")
            if not result.business_profile.postal_address:
                raise HTTPException(status_code=409, detail="postal address required for auto-send — set company.details.postal_address")
            if "unsubscribe" not in draft.body.lower():
                raise HTTPException(status_code=409, detail="unsubscribe link required in body for auto-send — set APP_BASE_URL and UNSUBSCRIBE_SECRET before generating drafts")
            cap = int((os.getenv("DAILY_SEND_CAP") or "").strip() or DEFAULT_DAILY_SEND_CAP)
            if send_log.sends_today(provider) >= cap:
                raise HTTPException(status_code=409, detail=f"daily send cap ({cap}) reached for {provider}")
            sender = get_send_store(provider)
            if sender is None:
                raise HTTPException(status_code=503, detail=f"{provider} send client not configured")
            try:
                send_result = sender.send(result.campaign, draft)
            except ApprovalRequiredError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            sent_at = datetime.now(timezone.utc).isoformat()
            send_log.append(email=draft.lead.email, campaign_id=campaign_id, draft_id=draft_id, mailbox=provider, ts=sent_at)
            contacted_store.add(draft.lead.email, campaign_id, draft_id, ts=sent_at)
            store.mark_draft_sent(campaign_id, draft_id, sent_at)
        data = to_plain_data(send_result)
        data["sent_at"] = sent_at
        return data

    @app.post("/campaigns/{campaign_id}/advance")
    def advance_sequences(campaign_id: str, request: AdvanceRequest) -> dict[str, Any]:
        llm_router = build_router(request.llm_provider, request.llm_model)
        email_agent = EmailPersonalizationAgent(
            ComplianceAgent(suppression_store.all_emails()),
            llm_router,
            unsubscribe_base_url=app_base_url,
            unsubscribe_secret=unsubscribe_secret if app_base_url else "",
        )
        now = None
        if request.now:
            try:
                now = datetime.fromisoformat(request.now)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="'now' must be an ISO 8601 timestamp") from exc
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
        try:
            return advance_campaign(store, campaign_id, email_agent, suppression_store, now)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="campaign not found") from exc

    @app.post("/mailboxes/{provider}/sync-replies")
    def sync_replies(provider: str, request: SyncRepliesRequest) -> dict[str, Any]:
        provider = provider.strip().lower()
        if provider not in {"gmail", "outlook"}:
            raise HTTPException(status_code=400, detail=f"unsupported provider '{provider}'")
        client = get_reply_client(provider)
        if client is None:
            raise HTTPException(status_code=503, detail=f"{provider} mailbox not connected")
        llm_router = build_router(None, None)
        service = ReplySyncService(store, contacted_store, suppression_store, llm_router)
        return service.sync(client, request.newer_than_days)

    @app.post("/icp", status_code=201)
    def save_icp(request: IcpRequest) -> dict[str, Any]:
        llm_router = build_router(None, None)
        profile = DraftFirstOrchestrator(llm_router=llm_router).profile_company(request.company.to_domain())
        data = {
            "profile": to_plain_data(profile),
            "exclusions": [item.strip().lower() for item in request.exclusions if item.strip()],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        (storage_path / "icp.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return data

    @app.get("/icp")
    def get_icp() -> dict[str, Any]:
        icp_path = storage_path / "icp.json"
        if not icp_path.exists():
            raise HTTPException(status_code=404, detail="no ICP saved yet — POST /icp first")
        return json.loads(icp_path.read_text(encoding="utf-8"))

    @app.get("/deliverability/{domain}")
    def deliverability(domain: str) -> dict[str, Any]:
        if not is_valid_domain(domain):
            raise HTTPException(status_code=400, detail="invalid domain")
        try:
            return check_domain(domain)
        except Exception as exc:  # noqa: BLE001 — DNS layer errors are environmental
            raise HTTPException(status_code=503, detail=f"DNS check failed: {exc}") from exc

    # ---- Compliance: make the suppression + contacted stores visible/actionable ----

    @app.get("/compliance/overview")
    def compliance_overview() -> dict[str, Any]:
        raw = suppression_store._load()  # {email: {reason, ts}}
        entries = sorted(
            ({"email": email, **meta} for email, meta in raw.items()),
            key=lambda item: str(item.get("ts", "")),
            reverse=True,
        )
        return {
            "suppression_count": len(entries),
            "suppression": entries,
            "contacted_count": contacted_store.count(),
        }

    @app.post("/compliance/suppress", status_code=201)
    def suppress_email(request: SuppressRequest) -> dict[str, Any]:
        email = request.email.strip().lower()
        if "@" not in email:
            raise HTTPException(status_code=422, detail="a valid email address is required")
        suppression_store.add(email, request.reason or "manual")
        return {"email": email, "suppressed": True}

    # ---- Public unsubscribe endpoints: NO auth, must stay reachable by recipients ----

    @app.get("/u/{token}", response_class=HTMLResponse)
    def unsubscribe_confirm(token: str) -> str:
        email = verify_token(token, unsubscribe_secret)
        if email is None:
            return "<html><body><h3>This unsubscribe link is not valid.</h3></body></html>"
        # html.escape: the email came from a signed token, but tokens sign raw
        # strings — never reflect unescaped input. Empty form action posts back
        # to the CURRENT URL, so the flow works under any path prefix (/api/u/…).
        return (
            "<html><body><h3>Unsubscribe</h3>"
            f"<p>Stop all future emails to <strong>{html.escape(email)}</strong>?</p>"
            "<form method='post' action=''><button type='submit'>Unsubscribe me</button></form>"
            "</body></html>"
        )

    @app.post("/u/{token}", response_class=HTMLResponse)
    def unsubscribe_apply(token: str) -> str:
        email = verify_token(token, unsubscribe_secret)
        if email is None:
            return "<html><body><h3>This unsubscribe link is not valid.</h3></body></html>"
        suppression_store.add(email, "unsubscribe_link")
        return "<html><body><h3>You're unsubscribed.</h3><p>You will not hear from us again.</p></body></html>"

    return app


app = create_app()
