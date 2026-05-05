from __future__ import annotations

import re
import urllib.request
from dataclasses import replace
from html import unescape
from typing import Protocol

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
    def __init__(self, fetcher: PageFetcher | None = None, max_context_chars: int = 280) -> None:
        self.fetcher = fetcher or ScraplingPageFetcher()
        self.max_context_chars = max_context_chars

    def enrich(self, lead: LeadInput) -> LeadInput:
        if lead.context or not lead.website:
            return lead
        html = self._safe_fetch(lead.website)
        context = self._extract_context(html)
        if not context:
            return lead
        return replace(lead, context=context[: self.max_context_chars])

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
