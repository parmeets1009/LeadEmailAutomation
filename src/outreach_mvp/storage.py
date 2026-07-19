from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from dataclasses import replace

from ._jsonfile import atomic_write_json
from .models import CampaignResult, EmailDraft, from_campaign_result, to_plain_data

logger = logging.getLogger("outreach_mvp.storage")


class JsonCampaignStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, result: CampaignResult) -> Path:
        slug = self._slug(result.campaign.name)
        # A campaign name reused for a new run must never overwrite the previous
        # run (that silently wiped approvals) — suffix until the id is free.
        path = self.directory / f"{slug}.json"
        counter = 2
        while path.exists():
            path = self.directory / f"{slug}-{counter}.json"
            counter += 1
        atomic_write_json(path, to_plain_data(self._with_draft_ids(result)))
        return path

    def load(self, filename: str) -> CampaignResult:
        path = self.directory / filename
        return self._with_draft_ids(from_campaign_result(json.loads(path.read_text(encoding="utf-8"))))

    def save_campaign(self, campaign_id: str, result: CampaignResult) -> Path:
        path = self.directory / f"{campaign_id}.json"
        atomic_write_json(path, to_plain_data(self._with_draft_ids(result)))
        return path

    def load_campaign(self, campaign_id: str) -> CampaignResult:
        return self.load(f"{campaign_id}.json")

    def list_campaigns(self) -> list[dict[str, str | int]]:
        campaigns = []
        for path in sorted(self.directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                result = self.load(path.name)
            except Exception:  # noqa: BLE001 — one corrupt file must not brick the whole listing
                logger.warning("Skipping unreadable campaign file %s", path.name)
                continue
            campaigns.append(
                {
                    "campaign_id": path.stem,
                    "name": result.campaign.name,
                    "status": result.status,
                    "draft_count": len(result.drafts),
                    "approved_count": sum(1 for draft in result.drafts if draft.approved),
                }
            )
        return campaigns

    def approve_draft(self, campaign_id: str, draft_id: str, approved_by: str, notes: str = "") -> EmailDraft:
        result = self.load_campaign(campaign_id)
        updated_drafts = []
        updated_draft = None
        for draft in result.drafts:
            if draft.draft_id == draft_id:
                updated_draft = replace(
                    draft,
                    review_status="approved",
                    approved=True,
                    approved_by=approved_by,
                    review_notes=notes,
                )
                updated_drafts.append(updated_draft)
            else:
                updated_drafts.append(draft)
        if updated_draft is None:
            raise KeyError(draft_id)
        self.save_campaign(campaign_id, replace(result, drafts=updated_drafts))
        return updated_draft

    def edit_draft(self, campaign_id: str, draft_id: str, subject: str | None = None, body: str | None = None, edited_by: str = "") -> EmailDraft:
        result = self.load_campaign(campaign_id)
        updated_drafts = []
        updated_draft = None
        for draft in result.drafts:
            if draft.draft_id == draft_id:
                updated_draft = replace(
                    draft,
                    subject=subject if subject is not None else draft.subject,
                    body=body if body is not None else draft.body,
                    review_status="edited",
                    approved=False,
                    approved_by="",
                    edited_by=edited_by,
                )
                updated_drafts.append(updated_draft)
            else:
                updated_drafts.append(draft)
        if updated_draft is None:
            raise KeyError(draft_id)
        self.save_campaign(campaign_id, replace(result, drafts=updated_drafts))
        return updated_draft

    def mark_draft_sent(self, campaign_id: str, draft_id: str, sent_at: str) -> EmailDraft:
        return self._update_draft(campaign_id, draft_id, lambda draft: replace(draft, sent_at=sent_at))

    def mark_draft_replied(self, campaign_id: str, draft_id: str, reply_summary: str) -> EmailDraft:
        return self._update_draft(campaign_id, draft_id, lambda draft: replace(draft, replied=True, reply_summary=reply_summary))

    def append_drafts(self, campaign_id: str, new_drafts: list[EmailDraft]) -> CampaignResult:
        result = self.load_campaign(campaign_id)
        combined = replace(result, drafts=list(result.drafts) + list(new_drafts))
        self.save_campaign(campaign_id, combined)
        return self.load_campaign(campaign_id)

    def _update_draft(self, campaign_id: str, draft_id: str, updater) -> EmailDraft:
        result = self.load_campaign(campaign_id)
        updated_drafts = []
        updated_draft = None
        for draft in result.drafts:
            if draft.draft_id == draft_id:
                updated_draft = updater(draft)
                updated_drafts.append(updated_draft)
            else:
                updated_drafts.append(draft)
        if updated_draft is None:
            raise KeyError(draft_id)
        self.save_campaign(campaign_id, replace(result, drafts=updated_drafts))
        return updated_draft

    def _with_draft_ids(self, result: CampaignResult) -> CampaignResult:
        drafts = [replace(draft, draft_id=draft.draft_id or f"draft-{index}") for index, draft in enumerate(result.drafts, start=1)]
        return replace(result, drafts=drafts)

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "campaign"
