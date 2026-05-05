from __future__ import annotations

from .llm import LLMRouter
from .models import BusinessProfile, CompanyInput


class BusinessProfileAgent:
    """Deterministic MVP stand-in for the future LLM business profiling agent."""

    def __init__(self, llm_router: LLMRouter | None = None) -> None:
        self.llm_router = llm_router

    def profile(self, company: CompanyInput) -> BusinessProfile:
        if self.llm_router:
            llm_profile = self.llm_router.profile_company(company)
            if llm_profile:
                return llm_profile
        description = company.description.strip()
        lower = description.lower()
        products = self._product_categories(lower)
        industries = self._target_industries(lower)
        personas = self._buyer_personas(lower)
        value_props = self._value_props(lower, company.details)
        summary = self._summary(company, products)
        return BusinessProfile(
            company_name=company.name,
            website=company.website,
            summary=summary,
            product_categories=products,
            buyer_personas=personas,
            target_industries=industries,
            value_propositions=value_props,
            suggested_apollo_filters={
                "person_titles": personas,
                "organization_locations": company.details.get("export_markets", "").split(", ") if company.details.get("export_markets") else [],
                "q_organization_keyword_tags": industries,
            },
        )

    def _product_categories(self, text: str) -> list[str]:
        categories = []
        for keyword, label in [
            ("gasket", "Gaskets"),
            ("seal", "Seals"),
            ("mat", "Rubber mats"),
            ("mold", "Molded rubber parts"),
            ("rubber", "Custom rubber products"),
        ]:
            if keyword in text and label not in categories:
                categories.append(label)
        return categories or ["Products/services"]

    def _buyer_personas(self, text: str) -> list[str]:
        personas = ["Procurement Manager", "Sourcing Manager", "Operations Manager"]
        if "distributor" in text:
            personas.append("Distributor Owner")
        if "oem" in text:
            personas.append("OEM Buyer")
        return personas

    def _target_industries(self, text: str) -> list[str]:
        industries = []
        keyword_map = [
            ("construction", "Construction"),
            ("industrial", "Industrial"),
            ("oem", "Manufacturing"),
            ("automotive", "Automotive"),
            ("distributor", "Wholesale Distribution"),
        ]
        for keyword, label in keyword_map:
            if keyword in text and label not in industries:
                industries.append(label)
        return industries or ["Industrial", "Manufacturing"]

    def _value_props(self, text: str, details: dict[str, str]) -> list[str]:
        props = []
        if "rubber" in text:
            props.append("custom rubber products for industrial buyers")
        if "manufacturer" in text:
            props.append("direct manufacturer supply with consistent quality")
        if details.get("certifications"):
            props.append(f"quality systems including {details['certifications']}")
        return props or ["reliable supply and responsive service"]

    def _summary(self, company: CompanyInput, products: list[str]) -> str:
        product_text = ", ".join(products).lower()
        return f"{company.name} provides {product_text}. {company.description.strip()}"
