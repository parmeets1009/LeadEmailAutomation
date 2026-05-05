from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .models import BusinessProfile, CampaignInput, CompanyInput, LeadInput


SUPPORTED_PROVIDERS = {"deterministic", "codex", "openai-codex", "gemini"}
DEFAULT_MODELS = {
    "deterministic": "deterministic-v1",
    "codex": "gpt-5.5",
    "openai-codex": "gpt-5.5",
    "gemini": "gemini-3.1-pro-preview",
}
PROMPT_VERSION = "draft-first-v1"


class LLMClient(Protocol):
    def complete_json(self, *, provider: str, model: str, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class StaticLLMClient:
    profile_response: dict[str, Any] | None = None
    draft_response: dict[str, Any] | None = None

    def complete_json(self, *, provider: str, model: str, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task == "business_profile" and self.profile_response is not None:
            return dict(self.profile_response)
        if task == "email_draft" and self.draft_response is not None:
            return dict(self.draft_response)
        return {}


class OpenAICompatibleClient:
    """Tiny stdlib OpenAI-compatible JSON client for future real LLM calls.

    The MVP keeps deterministic fallback behavior if credentials are absent or
    the provider call fails. This prevents LLM outages from bypassing compliance
    or blocking draft-first workflows.
    """

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def complete_json(self, *, provider: str, model: str, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        system = (
            "You are an email outreach assistant. Return only valid JSON. "
            "Do not include markdown. Do not claim emails were sent."
        )
        user = json.dumps({"task": task, "payload": payload}, ensure_ascii=False)
        request_body = json.dumps(
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=request_body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)


class LLMRouter:
    def __init__(self, provider: str = "deterministic", model: str | None = None, client: LLMClient | None = None) -> None:
        normalized = (provider or "deterministic").strip().lower()
        if normalized not in SUPPORTED_PROVIDERS:
            raise ValueError(f"Unsupported LLM provider '{provider}'. Use one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}.")
        self.provider = "codex" if normalized == "openai-codex" else normalized
        self.model = model or DEFAULT_MODELS.get(normalized, DEFAULT_MODELS["deterministic"])
        self.prompt_version = PROMPT_VERSION
        self._client = client or self._client_from_environment(self.provider)

    @property
    def enabled(self) -> bool:
        return self._client is not None and self.provider != "deterministic"

    def describe(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "available_providers": ["deterministic", "codex", "gemini"],
        }

    def profile_company(self, company: CompanyInput) -> BusinessProfile | None:
        if not self.enabled:
            return None
        data = self._safe_complete(
            "business_profile",
            {
                "company": {
                    "name": company.name,
                    "website": company.website,
                    "description": company.description,
                    "details": company.details,
                },
                "required_keys": [
                    "summary",
                    "product_categories",
                    "buyer_personas",
                    "target_industries",
                    "value_propositions",
                    "suggested_apollo_filters",
                ],
            },
        )
        if not data:
            return None
        return BusinessProfile(
            company_name=company.name,
            website=company.website,
            summary=str(data.get("summary") or company.description),
            product_categories=_list(data.get("product_categories"), ["Products/services"]),
            buyer_personas=_list(data.get("buyer_personas"), ["Procurement Manager"]),
            target_industries=_list(data.get("target_industries"), ["Industrial"]),
            value_propositions=_list(data.get("value_propositions"), ["reliable supply and responsive service"]),
            suggested_apollo_filters=_dict(data.get("suggested_apollo_filters")),
        )

    def draft_email(self, profile: BusinessProfile, campaign: CampaignInput, lead: LeadInput) -> dict[str, str] | None:
        if not self.enabled:
            return None
        data = self._safe_complete(
            "email_draft",
            {
                "business_profile": _plain_profile(profile),
                "campaign": campaign.__dict__,
                "lead": lead.__dict__,
                "requirements": [
                    "Return subject, body, and personalization_reason.",
                    "Do not add unsubscribe/opt-out footer; compliance code will add it deterministically.",
                    "Do not say the email was sent.",
                ],
            },
        )
        if not data:
            return None
        return {
            "subject": str(data.get("subject") or "").strip(),
            "body": str(data.get("body") or "").strip(),
            "personalization_reason": str(data.get("personalization_reason") or "Generated by LLM.").strip(),
        }

    def _safe_complete(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._client is None:
            return {}
        try:
            return self._client.complete_json(provider=self.provider, model=self.model, task=task, payload=payload)
        except Exception:
            return {}

    def _client_from_environment(self, provider: str) -> LLMClient | None:
        if provider == "gemini":
            key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            if key:
                return OpenAICompatibleClient(key, os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"))
        if provider == "codex":
            key = os.getenv("OPENAI_API_KEY")
            if key:
                return OpenAICompatibleClient(key, os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
        return None


def _list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or fallback
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback


def _dict(value: Any) -> dict[str, list[str] | str]:
    return value if isinstance(value, dict) else {}


def _plain_profile(profile: BusinessProfile) -> dict[str, Any]:
    return {
        "company_name": profile.company_name,
        "website": profile.website,
        "summary": profile.summary,
        "product_categories": profile.product_categories,
        "buyer_personas": profile.buyer_personas,
        "target_industries": profile.target_industries,
        "value_propositions": profile.value_propositions,
    }
