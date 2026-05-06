from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Literal, Protocol

from .models import CampaignInput, EmailDraft, to_plain_data

MailboxProvider = Literal["gmail", "outlook"]
SUPPORTED_MAILBOX_PROVIDERS = {"gmail", "outlook"}


@dataclass(frozen=True)
class MailboxDraftResult:
    provider: str
    status: str
    draft_id: str
    mailbox_draft_id: str
    to_email: str
    from_email: str
    subject: str
    storage_path: str


class GmailDraftClient(Protocol):
    def create_draft(self, raw_message: str) -> dict[str, Any]:
        """Create a Gmail draft from a base64url RFC 2822 message."""


class OutlookDraftClient(Protocol):
    def create_draft(self, message: dict[str, Any]) -> dict[str, Any]:
        """Create an Outlook/Microsoft Graph draft message."""


class MailboxDraftError(Exception):
    pass


class ApprovalRequiredError(MailboxDraftError):
    pass


class UnsupportedMailboxProviderError(MailboxDraftError):
    pass


class LocalMailboxDraftStore:
    """Safe draft-first mailbox adapter.

    This creates provider-shaped local draft artifacts only after approval. The
    live Gmail/Outlook OAuth senders can later replace this storage boundary
    without changing approval rules or API contracts.
    """

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def create_draft(self, provider: str, campaign: CampaignInput, draft: EmailDraft) -> MailboxDraftResult:
        normalized = provider.strip().lower()
        if normalized not in SUPPORTED_MAILBOX_PROVIDERS:
            raise UnsupportedMailboxProviderError(f"unsupported mailbox provider '{provider}'")
        if not draft.approved or draft.review_status != "approved":
            raise ApprovalRequiredError("draft must be approved before mailbox draft creation")
        mailbox_draft_id = f"{normalized}-{self._slug(campaign.name)}-{draft.draft_id}"
        path = self.directory / f"{mailbox_draft_id}.json"
        payload = {
            "provider": normalized,
            "status": "draft_created",
            "mailbox_draft_id": mailbox_draft_id,
            "campaign": to_plain_data(campaign),
            "draft": to_plain_data(draft),
            "to_email": draft.lead.email,
            "from_email": campaign.sender_email,
            "subject": draft.subject,
            "body": draft.body,
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return MailboxDraftResult(
            provider=normalized,
            status="draft_created",
            draft_id=draft.draft_id,
            mailbox_draft_id=mailbox_draft_id,
            to_email=draft.lead.email,
            from_email=campaign.sender_email,
            subject=draft.subject,
            storage_path=str(path),
        )

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "campaign"


class GmailApiDraftStore:
    """Live Gmail draft adapter boundary.

    The injected client owns OAuth/token concerns. This adapter only enforces
    the same approval gate as local artifacts and builds the Gmail raw RFC 2822
    draft payload. It never sends email.
    """

    def __init__(self, client: GmailDraftClient) -> None:
        self.client = client

    def create_draft(self, campaign: CampaignInput, draft: EmailDraft) -> MailboxDraftResult:
        if not draft.approved or draft.review_status != "approved":
            raise ApprovalRequiredError("draft must be approved before mailbox draft creation")
        raw_message = build_gmail_raw_message(campaign, draft)
        response = self.client.create_draft(raw_message)
        mailbox_draft_id = str(response.get("id") or response.get("draft_id") or "")
        if not mailbox_draft_id:
            mailbox_draft_id = "gmail-draft-created"
        return MailboxDraftResult(
            provider="gmail",
            status="draft_created",
            draft_id=draft.draft_id,
            mailbox_draft_id=mailbox_draft_id,
            to_email=draft.lead.email,
            from_email=campaign.sender_email,
            subject=draft.subject,
            storage_path="gmail_api",
        )


class OutlookApiDraftStore:
    """Live Outlook/Microsoft Graph draft adapter boundary.

    The injected client owns OAuth/token concerns. This adapter enforces the
    approval gate and builds a Graph message JSON payload. It never sends email.
    """

    def __init__(self, client: OutlookDraftClient) -> None:
        self.client = client

    def create_draft(self, campaign: CampaignInput, draft: EmailDraft) -> MailboxDraftResult:
        if not draft.approved or draft.review_status != "approved":
            raise ApprovalRequiredError("draft must be approved before mailbox draft creation")
        message = build_outlook_message(campaign, draft)
        response = self.client.create_draft(message)
        mailbox_draft_id = str(response.get("id") or response.get("draft_id") or "")
        if not mailbox_draft_id:
            mailbox_draft_id = "outlook-draft-created"
        return MailboxDraftResult(
            provider="outlook",
            status="draft_created",
            draft_id=draft.draft_id,
            mailbox_draft_id=mailbox_draft_id,
            to_email=draft.lead.email,
            from_email=campaign.sender_email,
            subject=draft.subject,
            storage_path="outlook_graph",
        )


def build_outlook_message(campaign: CampaignInput, draft: EmailDraft) -> dict[str, Any]:
    email_address: dict[str, str] = {"address": draft.lead.email}
    lead_name = " ".join(part for part in [draft.lead.first_name, draft.lead.last_name] if part).strip()
    if lead_name:
        email_address["name"] = lead_name
    return {
        "subject": draft.subject,
        "body": {"contentType": "Text", "content": draft.body},
        "toRecipients": [{"emailAddress": email_address}],
    }


def build_gmail_raw_message(campaign: CampaignInput, draft: EmailDraft) -> str:
    message = EmailMessage()
    message["To"] = draft.lead.email
    message["From"] = _format_sender(campaign.sender_name, campaign.sender_email)
    message["Subject"] = draft.subject
    message.set_content(draft.body, cte="8bit")
    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii").rstrip("=")


def _format_sender(sender_name: str, sender_email: str) -> str:
    name = sender_name.strip()
    if not name:
        return sender_email
    safe_name = name.replace('"', "'")
    return f'"{safe_name}" <{sender_email}>' if "," in safe_name else f"{safe_name} <{sender_email}>"
