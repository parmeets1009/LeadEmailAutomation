from __future__ import annotations

import json
import re
from pathlib import Path
from dataclasses import replace

from .models import CampaignResult, EmailDraft, from_campaign_result, to_plain_data


class JsonCampaignStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, result: CampaignResult) -> Path:
        slug = self._slug(result.campaign.name)
        path = self.directory / f"{slug}.json"
        path.write_text(json.dumps(to_plain_data(self._with_draft_ids(result)), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load(self, filename: str) -> CampaignResult:
        path = self.directory / filename
        return self._with_draft_ids(from_campaign_result(json.loads(path.read_text(encoding="utf-8"))))

    def save_campaign(self, campaign_id: str, result: CampaignResult) -> Path:
        path = self.directory / f"{campaign_id}.json"
        path.write_text(json.dumps(to_plain_data(self._with_draft_ids(result)), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load_campaign(self, campaign_id: str) -> CampaignResult:
        return self.load(f"{campaign_id}.json")

    def list_campaigns(self) -> list[dict[str, str | int]]:
        campaigns = []
        for path in sorted(self.directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            result = self.load(path.name)
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

    def _with_draft_ids(self, result: CampaignResult) -> CampaignResult:
        drafts = [replace(draft, draft_id=draft.draft_id or f"draft-{index}") for index, draft in enumerate(result.drafts, start=1)]
        return replace(result, drafts=drafts)

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "campaign"
