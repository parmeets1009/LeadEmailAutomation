from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

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
