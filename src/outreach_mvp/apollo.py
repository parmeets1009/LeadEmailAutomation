from __future__ import annotations

import os
from typing import Any, Protocol

import httpx

from .models import LeadInput


class ApolloSearchClient(Protocol):
    def search_people(self, *, filters: dict[str, Any], page: int, per_page: int) -> dict[str, Any]: ...


class ApolloRestClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.apollo.io/api/v1"):
        self.api_key = api_key or os.getenv("APOLLO_API_KEY", "")
        self.base_url = base_url.rstrip("/")

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
        response = httpx.post(
            f"{self.base_url}/mixed_people/search",
            headers={"Cache-Control": "no-cache", "Content-Type": "application/json", "X-Api-Key": self.api_key},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()


class ApolloProviderNotConfigured(RuntimeError):
    pass


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
    ) -> list[LeadInput]:
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
        data = self.client.search_people(filters=filters, page=1, per_page=max(1, min(max_leads, 100)))
        people = data.get("people") or data.get("contacts") or data.get("data", {}).get("people") or []
        leads: list[LeadInput] = []
        for person in people[:max_leads]:
            lead = self._person_to_lead(person)
            if lead.email:
                leads.append(lead)
        return leads

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
        return LeadInput(
            first_name=first_name,
            last_name=last_name,
            email=str(person.get("email") or person.get("email_address") or "").strip(),
            title=title,
            company_name=company_name,
            country=country,
            industry=industry,
            website=website,
            context="Apollo lead" + (f": {' · '.join(context_parts)}" if context_parts else ""),
        )
