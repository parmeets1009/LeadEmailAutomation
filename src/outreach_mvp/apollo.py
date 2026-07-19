from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

import httpx

from .models import LeadInput

logger = logging.getLogger("outreach_mvp.apollo")

MAX_PAGES = 20  # hard safety bound on pagination


class ApolloSearchClient(Protocol):
    def search_people(self, *, filters: dict[str, Any], page: int, per_page: int) -> dict[str, Any]: ...


class ApolloProviderNotConfigured(RuntimeError):
    pass


class ApolloRateLimited(RuntimeError):
    pass


class ApolloRestClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.apollo.io/api/v1", sleep: Callable[[float], None] = time.sleep):
        self.api_key = api_key or os.getenv("APOLLO_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.sleep = sleep

    def search_people(self, *, filters: dict[str, Any], page: int, per_page: int) -> dict[str, Any]:
        if not self.api_key:
            raise ApolloProviderNotConfigured("APOLLO_API_KEY is not configured")
        payload: dict[str, Any] = {"page": page, "per_page": per_page}
        if filters.get("titles"):
            payload["person_titles"] = filters["titles"]
        if filters.get("locations"):
            payload["person_locations"] = filters["locations"]
        if filters.get("industries"):
            payload["q_organization_keyword_tags"] = filters["industries"]
        if filters.get("company_domains"):
            payload["q_organization_domains"] = filters["company_domains"]
        if filters.get("company_names"):
            payload["organization_names"] = filters["company_names"]
        if filters.get("keywords"):
            payload["q_keywords"] = filters["keywords"]
        for attempt in (1, 2):
            response = httpx.post(
                f"{self.base_url}/mixed_people/search",
                headers={"Cache-Control": "no-cache", "Content-Type": "application/json", "X-Api-Key": self.api_key},
                json=payload,
                timeout=30,
            )
            if response.status_code == 429:
                if attempt == 2:
                    raise ApolloRateLimited("Apollo rate limited — try again later")
                try:
                    wait = int(response.headers.get("retry-after", "60") or "60")
                except ValueError:
                    wait = 60
                logger.warning("Apollo 429; sleeping %ss before one retry", wait)
                self.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        raise ApolloRateLimited("Apollo rate limited — try again later")


@dataclass(frozen=True)
class ApolloSearchResult:
    leads: list[LeadInput] = field(default_factory=list)
    locked_email_count: int = 0
    pages_fetched: int = 0


class ApolloLeadProvider:
    def __init__(self, client: ApolloSearchClient | None = None):
        self.client = client

    @classmethod
    def from_env(cls) -> "ApolloLeadProvider | None":
        if not os.getenv("APOLLO_API_KEY"):
            return None
        return cls(client=ApolloRestClient())

    def search_leads(
        self,
        *,
        titles: list[str] | None = None,
        locations: list[str] | None = None,
        industries: list[str] | None = None,
        company_domains: list[str] | None = None,
        company_names: list[str] | None = None,
        keywords: str = "",
        max_leads: int = 25,
    ) -> ApolloSearchResult:
        if self.client is None:
            raise ApolloProviderNotConfigured("Apollo lead provider is not configured")
        filters = {
            "titles": titles or [],
            "locations": locations or [],
            "industries": industries or [],
            "company_domains": company_domains or [],
            "company_names": company_names or [],
            "keywords": keywords,
        }
        per_page = max(1, min(max_leads, 100))
        leads: list[LeadInput] = []
        seen_emails: set[str] = set()
        locked = 0
        page = 1
        pages_fetched = 0
        while len(leads) < max_leads and page <= MAX_PAGES:
            data = self.client.search_people(filters=filters, page=page, per_page=per_page)
            pages_fetched += 1
            people = data.get("people") or data.get("contacts") or (data.get("data") or {}).get("people") or []
            if not people:
                break
            for person in people:
                if len(leads) >= max_leads:
                    break
                lead = self._person_to_lead(person)
                if not lead.email or lead.email.lower() in seen_emails:
                    continue
                if self._is_locked_email(lead.email):
                    locked += 1
                    continue
                seen_emails.add(lead.email.lower())
                leads.append(lead)
            total_pages = (data.get("pagination") or {}).get("total_pages")
            if isinstance(total_pages, int) and page >= total_pages:
                break
            if len(people) < per_page:
                break  # short page = last page
            page += 1
        return ApolloSearchResult(leads=leads, locked_email_count=locked, pages_fetched=pages_fetched)

    @staticmethod
    def _is_locked_email(email: str) -> bool:
        # Free-tier Apollo returns placeholders instead of real addresses.
        lowered = email.lower()
        return "email_not_unlocked" in lowered or lowered.endswith("@domain.com")

    def _person_to_lead(self, person: dict[str, Any]) -> LeadInput:
        organization = person.get("organization") or person.get("account") or {}
        first_name = str(person.get("first_name") or "").strip()
        last_name = str(person.get("last_name") or "").strip()
        if not first_name and person.get("name"):
            parts = str(person["name"]).split()
            first_name = parts[0] if parts else ""
            last_name = " ".join(parts[1:])
        company_name = str(
            organization.get("name")
            or person.get("organization_name")
            or person.get("company_name")
            or ""
        ).strip()
        website = str(
            organization.get("website_url")
            or organization.get("website")
            or person.get("organization_website_url")
            or person.get("company_website")
            or ""
        ).strip()
        industry = str(
            organization.get("industry")
            or person.get("industry")
            or person.get("organization_industry")
            or ""
        ).strip()
        title = str(person.get("title") or person.get("headline") or "").strip()
        country = str(person.get("country") or person.get("person_country") or organization.get("country") or "").strip()
        context_parts = [part for part in [title, company_name, industry, country] if part]
        # Provenance lives in `source`, never in `context`: context feeds the email
        # body via {{lead_context}}, and a lead with a website gets an empty context
        # so website enrichment can fill it with something worth referencing.
        context = "" if website else " · ".join(context_parts)
        return LeadInput(
            first_name=first_name,
            last_name=last_name,
            email=str(person.get("email") or person.get("email_address") or "").strip(),
            title=title,
            company_name=company_name,
            country=country,
            industry=industry,
            website=website,
            context=context,
            source="apollo",
        )
