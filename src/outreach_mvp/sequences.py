"""Follow-up sequences. A stage-N+1 draft is generated ONLY when the stage-N
email was actually sent, has no reply, the recipient is not suppressed, the
offset has elapsed, and no follow-up exists yet. Every follow-up lands in the
review queue unapproved — approval is per stage, never inherited."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any

from .email_agent import EmailPersonalizationAgent
from .storage import JsonCampaignStore
from .suppression import SuppressionStore

MAX_STAGES = 3


def advance_campaign(
    store: JsonCampaignStore,
    campaign_id: str,
    email_agent: EmailPersonalizationAgent,
    suppression: SuppressionStore | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    result = store.load_campaign(campaign_id)
    stages = list(result.campaign.stages)[:MAX_STAGES]
    existing_followups = {draft.followup_of for draft in result.drafts if draft.followup_of}
    created: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    new_drafts = []

    for draft in result.drafts:
        if draft.stage >= len(stages):
            continue
        if not draft.sent_at:
            skipped.append({"draft_id": draft.draft_id, "reason": "not_sent"})
            continue
        if draft.replied:
            skipped.append({"draft_id": draft.draft_id, "reason": "replied"})
            continue
        if draft.draft_id in existing_followups:
            skipped.append({"draft_id": draft.draft_id, "reason": "followup_exists"})
            continue
        if suppression is not None and suppression.contains(draft.lead.email):
            skipped.append({"draft_id": draft.draft_id, "reason": "suppressed"})
            continue
        stage = stages[draft.stage] if isinstance(stages[draft.stage], dict) else {}
        try:
            offset_days = int(stage.get("offset_days", 3))
        except (TypeError, ValueError):
            offset_days = 3
        try:
            sent = datetime.fromisoformat(draft.sent_at)
        except ValueError:
            skipped.append({"draft_id": draft.draft_id, "reason": "bad_sent_at"})
            continue
        if sent.tzinfo is None:
            sent = sent.replace(tzinfo=timezone.utc)
        if now < sent + timedelta(days=offset_days):
            skipped.append({"draft_id": draft.draft_id, "reason": "not_due"})
            continue
        stage_campaign = replace(result.campaign, template=str(stage.get("template", result.campaign.template)))
        followup = email_agent.draft(result.business_profile, stage_campaign, draft.lead, draft.lead_score)
        followup = replace(followup, stage=draft.stage + 1, followup_of=draft.draft_id)
        if followup.compliance.status != "passed":
            skipped.append({"draft_id": draft.draft_id, "reason": "compliance:" + ",".join(followup.compliance.reasons)})
            continue
        new_drafts.append(followup)
        created.append({"followup_of": draft.draft_id, "stage": str(draft.stage + 1)})

    if new_drafts:
        store.append_drafts(campaign_id, new_drafts)
    return {"campaign_id": campaign_id, "created_count": len(created), "created": created, "skipped": skipped}
