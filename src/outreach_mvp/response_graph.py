from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import CampaignResult, EmailDraft

VALID_RESPONSE_EVENT_TYPES = {"reply", "bounce", "unsubscribe", "conversion", "not_interested", "out_of_office"}
_EVENT_METRIC_KEYS = {
    "reply": "replies",
    "bounce": "bounces",
    "unsubscribe": "unsubscribes",
    "conversion": "conversions",
    "not_interested": "not_interested",
    "out_of_office": "out_of_office",
}
_EDGE_BY_EVENT_TYPE = {
    "reply": "REPLIED_TO",
    "bounce": "BOUNCED",
    "unsubscribe": "UNSUBSCRIBED",
    "conversion": "CONVERTED",
    "not_interested": "NOT_INTERESTED",
    "out_of_office": "OUT_OF_OFFICE",
}


@dataclass(frozen=True)
class ResponseEvent:
    event_id: str
    campaign_id: str
    draft_id: str
    email: str
    event_type: str
    classification: str = ""
    notes: str = ""
    occurred_at: str = ""
    source: str = "manual"

    def normalized(self) -> "ResponseEvent":
        event_type = self.event_type.strip().lower()
        if event_type not in VALID_RESPONSE_EVENT_TYPES:
            raise ValueError(f"unsupported response event type '{self.event_type}'")
        return ResponseEvent(
            event_id=self.event_id or f"evt-{uuid4().hex}",
            campaign_id=self.campaign_id,
            draft_id=self.draft_id,
            email=self.email.lower(),
            event_type=event_type,
            classification=self.classification.strip(),
            notes=self.notes.strip(),
            occurred_at=self.occurred_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            source=self.source.strip() or "manual",
        )


class ResponseEventStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: ResponseEvent) -> ResponseEvent:
        normalized = event.normalized()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(normalized), ensure_ascii=False) + "\n")
        return normalized

    def list_events(self, campaign_id: str | None = None) -> list[ResponseEvent]:
        if not self.path.exists():
            return []
        events = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = ResponseEvent(**json.loads(line)).normalized()
            if campaign_id is None or event.campaign_id == campaign_id:
                events.append(event)
        return events

    def events_for_draft(self, campaign_id: str, draft_id: str) -> list[ResponseEvent]:
        return [event for event in self.list_events(campaign_id) if event.draft_id == draft_id]


class LeadResponseGraphBuilder:
    def build(self, campaign_id: str, result: CampaignResult, events: list[ResponseEvent] | None = None) -> dict[str, Any]:
        events = [event.normalized() for event in (events or [])]
        nodes: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []

        def add_node(node_id: str, kind: str, label: str, **properties: Any) -> None:
            nodes[node_id] = {"id": node_id, "kind": kind, "label": label, "properties": properties}

        def add_edge(source: str, target: str, kind: str, **properties: Any) -> None:
            edges.append({"source": source, "target": target, "kind": kind, "properties": properties})

        campaign_node = _node_id("campaign", campaign_id)
        profile_node = _node_id("profile", campaign_id)
        add_node(
            campaign_node,
            "Campaign",
            result.campaign.name,
            status=result.status,
            target_country=result.campaign.target_country,
            target_region=result.campaign.target_region,
            llm_provider=result.llm_provider,
            llm_model=result.llm_model,
            prompt_version=result.prompt_version,
        )
        add_node(profile_node, "CompanyProfile", result.business_profile.company_name, website=result.business_profile.website, summary=result.business_profile.summary)
        add_edge(campaign_node, profile_node, "HAS_PROFILE")

        for title in result.campaign.target_titles:
            title_node = _node_id("persona", title)
            add_node(title_node, "BuyerPersona", title)
            add_edge(campaign_node, title_node, "TARGETS_TITLE")
        for industry in result.campaign.target_industries:
            industry_node = _node_id("industry", industry)
            add_node(industry_node, "Industry", industry)
            add_edge(campaign_node, industry_node, "TARGETS_INDUSTRY")

        events_by_draft: dict[str, list[ResponseEvent]] = defaultdict(list)
        for event in events:
            events_by_draft[event.draft_id].append(event)

        for draft in result.drafts:
            self._add_draft_subgraph(campaign_id, campaign_node, draft, events_by_draft.get(draft.draft_id, []), add_node, add_edge)

        return {"campaign_id": campaign_id, "nodes": list(nodes.values()), "edges": edges, "metrics": self._metrics(result, events)}

    def _add_draft_subgraph(self, campaign_id: str, campaign_node: str, draft: EmailDraft, events: list[ResponseEvent], add_node, add_edge) -> None:
        lead = draft.lead
        draft_node = f"draft:{campaign_id}:{draft.draft_id}"
        lead_node = _node_id("lead", lead.email or draft.draft_id)
        organization_node = _node_id("organization", lead.company_name)
        country_node = _node_id("country", lead.country)
        industry_node = _node_id("industry", lead.industry)
        title_node = _node_id("persona", lead.title)

        add_node(draft_node, "EmailDraft", draft.subject, draft_id=draft.draft_id, review_status=draft.review_status, approved=draft.approved, lead_score=draft.lead_score.score, personalization_reason=draft.personalization_reason)
        add_node(lead_node, "Lead", lead.email, first_name=lead.first_name, last_name=lead.last_name, title=lead.title, context=lead.context)
        add_node(organization_node, "Organization", lead.company_name, website=lead.website)
        add_node(country_node, "Country", lead.country)
        add_node(industry_node, "Industry", lead.industry)
        add_node(title_node, "BuyerPersona", lead.title)

        add_edge(campaign_node, draft_node, "GENERATED")
        add_edge(draft_node, lead_node, "DRAFTED_FOR")
        add_edge(lead_node, organization_node, "WORKS_AT")
        add_edge(lead_node, country_node, "LOCATED_IN")
        add_edge(lead_node, industry_node, "IN_INDUSTRY")
        add_edge(lead_node, title_node, "HAS_TITLE")

        for reason in draft.lead_score.reasons:
            reason_node = _node_id("score-reason", reason)
            add_node(reason_node, "LeadScoreReason", reason)
            add_edge(lead_node, reason_node, "SCORED_WITH")

        for event in events:
            event_node = _node_id("event", f"{event.event_id}-{event.event_type}")
            add_node(event_node, "ResponseEvent", event.classification or event.event_type, event_id=event.event_id, event_type=event.event_type, classification=event.classification, occurred_at=event.occurred_at, notes=event.notes, source=event.source)
            add_edge(draft_node, event_node, "HAS_OUTCOME")
            add_edge(lead_node, event_node, _EDGE_BY_EVENT_TYPE[event.event_type])

    def _metrics(self, result: CampaignResult, events: list[ResponseEvent]) -> dict[str, Any]:
        total_drafts = len(result.drafts)
        draft_ids = {draft.draft_id for draft in result.drafts}
        valid_events = [event for event in events if event.draft_id in draft_ids]
        ignored_events = len(events) - len(valid_events)
        event_counts = Counter(event.event_type for event in valid_events)
        unique_outcome_counts = {event_type: len({event.draft_id for event in valid_events if event.event_type == event_type}) for event_type in _EVENT_METRIC_KEYS}
        metrics: dict[str, Any] = {
            "total_drafts": total_drafts,
            "approved": sum(1 for draft in result.drafts if draft.approved),
            "pending": sum(1 for draft in result.drafts if draft.review_status == "pending"),
            "edited": sum(1 for draft in result.drafts if draft.review_status == "edited"),
            "skipped": len(result.skipped),
            "skipped_reasons": dict(Counter(result.skipped.values())),
            "ignored_events": ignored_events,
        }
        for event_type, metric_key in _EVENT_METRIC_KEYS.items():
            metrics[metric_key] = unique_outcome_counts[event_type]
            metrics[f"{event_type}_events"] = event_counts[event_type]
        metrics["reply_rate"] = _rate(metrics["replies"], total_drafts)
        metrics["bounce_rate"] = _rate(metrics["bounces"], total_drafts)
        metrics["unsubscribe_rate"] = _rate(metrics["unsubscribes"], total_drafts)
        metrics["conversion_rate"] = _rate(metrics["conversions"], total_drafts)
        metrics["by_country"] = self._segment_metrics(result.drafts, valid_events, lambda draft: draft.lead.country or "Unknown")
        metrics["by_title"] = self._segment_metrics(result.drafts, valid_events, lambda draft: draft.lead.title or "Unknown")
        metrics["by_industry"] = self._segment_metrics(result.drafts, valid_events, lambda draft: draft.lead.industry or "Unknown")
        return metrics

    def _segment_metrics(self, drafts: list[EmailDraft], events: list[ResponseEvent], segment_for) -> dict[str, dict[str, Any]]:
        draft_by_id = {draft.draft_id: draft for draft in drafts}
        segments: dict[str, dict[str, Any]] = defaultdict(_empty_segment_metrics)
        unique_outcomes: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for draft in drafts:
            segment = segment_for(draft)
            segments[segment]["drafts"] += 1
            if draft.approved:
                segments[segment]["approved"] += 1
        for event in events:
            draft = draft_by_id.get(event.draft_id)
            if draft is None:
                continue
            segment = segment_for(draft)
            metric_key = _EVENT_METRIC_KEYS[event.event_type]
            segments[segment][f"{event.event_type}_events"] += 1
            unique_outcomes[segment][metric_key].add(event.draft_id)
        for segment, values in segments.items():
            for metric_key, draft_id_set in unique_outcomes[segment].items():
                values[metric_key] = len(draft_id_set)
            drafts_count = values["drafts"]
            values["reply_rate"] = _rate(values["replies"], drafts_count)
            values["bounce_rate"] = _rate(values["bounces"], drafts_count)
            values["unsubscribe_rate"] = _rate(values["unsubscribes"], drafts_count)
            values["conversion_rate"] = _rate(values["conversions"], drafts_count)
        return dict(segments)


def _empty_segment_metrics() -> dict[str, Any]:
    values: dict[str, Any] = {"drafts": 0, "approved": 0, "reply_rate": 0.0, "bounce_rate": 0.0, "unsubscribe_rate": 0.0, "conversion_rate": 0.0}
    for event_type, metric_key in _EVENT_METRIC_KEYS.items():
        values[metric_key] = 0
        values[f"{event_type}_events"] = 0
    return values


def _node_id(kind: str, value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return f"{kind}:{normalized or 'unknown'}"


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0
