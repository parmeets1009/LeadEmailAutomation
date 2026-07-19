"""Claude-backed LLM client using the official Anthropic SDK with structured outputs.

Imported lazily by LLMRouter only when the claude provider is active, so
environments without an API key never touch the `anthropic` package at runtime.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel

from .prompts import (
    DRAFT_SYSTEM_PROMPT,
    ENRICHMENT_SYSTEM_PROMPT,
    LEAD_FIT_SYSTEM_PROMPT,
    PROFILE_SYSTEM_PROMPT,
    REPLY_CLASSIFICATION_SYSTEM_PROMPT,
)

logger = logging.getLogger("outreach_mvp.llm")

# Exact model IDs — never edit these to "close enough" names.
CLAUDE_MODEL_DEFAULT = "claude-opus-4-8"
CLAUDE_MODEL_FAST = "claude-haiku-4-5"


class ApolloFilters(BaseModel):
    # Explicit fields, NOT dict[str, list[str]]: structured-output schemas force
    # additionalProperties=false, so an open dict gets transformed into an object
    # with no properties and the model could only ever return {}.
    person_titles: list[str]
    organization_locations: list[str]
    q_organization_keyword_tags: list[str]


class ProfileOutput(BaseModel):
    summary: str
    product_categories: list[str]
    buyer_personas: list[str]
    target_industries: list[str]
    value_propositions: list[str]
    suggested_apollo_filters: ApolloFilters


class DraftOutput(BaseModel):
    subject: str
    body: str
    personalization_reason: str


class LeadFitOutput(BaseModel):
    fit_score: int
    fit_reasons: list[str]
    disqualifiers: list[str]


class EnrichmentOutput(BaseModel):
    company_summary: str
    outreach_hook: str


class ReplyClassificationOutput(BaseModel):
    category: Literal["interested", "not_interested", "unsubscribe", "out_of_office", "wrong_person", "bounce", "other"]
    summary: str
    suggested_action: Literal["reply_personally", "stop_sequence", "remove_and_suppress", "retry_later", "forward_to_human"]


TASK_SPECS: dict[str, tuple[str, type[BaseModel], int]] = {
    "business_profile": (PROFILE_SYSTEM_PROMPT, ProfileOutput, 1500),
    "email_draft": (DRAFT_SYSTEM_PROMPT, DraftOutput, 1000),
    "lead_fit": (LEAD_FIT_SYSTEM_PROMPT, LeadFitOutput, 600),
    "enrichment_summary": (ENRICHMENT_SYSTEM_PROMPT, EnrichmentOutput, 600),
    "reply_classification": (REPLY_CLASSIFICATION_SYSTEM_PROMPT, ReplyClassificationOutput, 600),
}


class ClaudeLLMClient:
    """LLMRouter-compatible client. Raises on failure — the router decides fallback."""

    def __init__(self, model: str = CLAUDE_MODEL_DEFAULT) -> None:
        import anthropic

        self.model = model
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    def complete_json(self, *, provider: str, model: str, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task not in TASK_SPECS:
            raise ValueError(f"Unknown LLM task '{task}'")
        system, schema, max_tokens = TASK_SPECS[task]
        response = self._client.messages.parse(
            model=model or self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            output_format=schema,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            logger.info(
                "claude task=%s model=%s input_tokens=%s output_tokens=%s",
                task, model or self.model, usage.input_tokens, usage.output_tokens,
            )
        if response.parsed_output is None:
            raise RuntimeError(f"Claude returned unparseable output for task={task} (stop_reason={response.stop_reason})")
        return response.parsed_output.model_dump()
