from __future__ import annotations

import re
import urllib.request
from dataclasses import replace
from html import unescape
from typing import Any, Protocol

from .models import LeadInput


class PageFetcher(Protocol):
    def fetch(self, url: str) -> str:
        ...


class StaticPageFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    def fetch(self, url: str) -> str:
        return self.pages.get(url, "")


class ScraplingPageFetcher:
    """Fetch public pages with Scrapling when installed, falling back to urllib.

    Use this only for public, permitted website context. It intentionally starts
    with static fetching and does not use stealth/browser bypass behavior.
    """

    def fetch(self, url: str) -> str:
        try:
            from scrapling.fetchers import Fetcher  # type: ignore

            page = Fetcher.fetch(url)
            return str(page.html if hasattr(page, "html") else page)
        except Exception:
            req = urllib.request.Request(url, headers={"User-Agent": "LeadEmailAutomation/0.1 (+draft-first enrichment)"})
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read().decode("utf-8", errors="replace")


class ScraplingEnrichmentProvider:
    def __init__(
        self,
        fetcher: PageFetcher | None = None,
        max_context_chars: int = 280,
        llm_router: Any | None = None,
        fetch_about_page: bool = True,
    ) -> None:
        self.fetcher = fetcher or ScraplingPageFetcher()
        self.max_context_chars = max_context_chars
        self.llm_router = llm_router
        self.fetch_about_page = fetch_about_page
        # Per-domain cache: 10 leads from one company cost one fetch (and one LLM call).
        self._cache: dict[str, str] = {}

    def enrich(self, lead: LeadInput) -> LeadInput:
        if lead.context or not lead.website:
            return lead
        domain = self._domain(lead.website)
        if domain in self._cache:
            context = self._cache[domain]
            return replace(lead, context=context[: self.max_context_chars]) if context else lead
        html = self._safe_fetch(lead.website)
        if self.fetch_about_page:
            from urllib.parse import urljoin

            about_html = self._safe_fetch(urljoin(lead.website.rstrip("/") + "/", "about"))
            if about_html:
                html = html + "\n" + about_html
        context = self._extract_context(html)
        if context and self.llm_router is not None and getattr(self.llm_router, "enabled", False):
            summary, _error = self.llm_router.summarize_website(self._clean(html)[:4000])
            if summary:
                hook = summary.get("outreach_hook") or summary.get("company_summary") or ""
                if hook:
                    context = hook
        self._cache[domain] = context
        if not context:
            return lead
        return replace(lead, context=context[: self.max_context_chars])

    def _domain(self, website: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(website if "://" in website else f"https://{website}")
        return (parsed.netloc or website).lower()

    def _safe_fetch(self, url: str) -> str:
        try:
            return self.fetcher.fetch(url)
        except Exception:
            return ""

    def _extract_context(self, html: str) -> str:
        parts = []
        title = self._first_match(r"<title[^>]*>(.*?)</title>", html)
        if title:
            parts.append(title)
        description = self._first_match(
            r"<meta[^>]+(?:name|property)=[\"'](?:description|og:description)[\"'][^>]+content=[\"'](.*?)[\"']",
            html,
        ) or self._first_match(
            r"<meta[^>]+content=[\"'](.*?)[\"'][^>]+(?:name|property)=[\"'](?:description|og:description)[\"']",
            html,
        )
        if description:
            parts.append(description)
        h1 = self._first_match(r"<h1[^>]*>(.*?)</h1>", html)
        if h1 and h1 not in parts:
            parts.append(h1)
        return " | ".join(self._clean(part) for part in parts if self._clean(part))

    def _first_match(self, pattern: str, text: str) -> str:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        return match.group(1) if match else ""

    def _clean(self, value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value)
        text = unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
