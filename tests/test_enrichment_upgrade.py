import unittest

from outreach_mvp.enrichment import ScraplingEnrichmentProvider
from outreach_mvp.llm import LLMRouter, StaticLLMClient
from outreach_mvp.models import LeadInput


class CountingFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        return self.pages.get(url, "")


def make_lead(email="a@gulf.example", website="https://gulf.example"):
    return LeadInput("A", "B", email, "PM", "Gulf", "Oman", "Industrial", website, "")


class EnrichmentUpgradeTests(unittest.TestCase):
    def test_about_page_content_is_merged(self):
        fetcher = CountingFetcher({
            "https://gulf.example": "<title>Gulf Industrial</title>",
            "https://gulf.example/about": "<meta name='description' content='ISO 9001 certified pump distributor since 1998.'>",
        })
        provider = ScraplingEnrichmentProvider(fetcher=fetcher)
        enriched = provider.enrich(make_lead())
        self.assertIn("Gulf Industrial", enriched.context)
        self.assertIn("ISO 9001", enriched.context)

    def test_domain_cache_avoids_refetching(self):
        fetcher = CountingFetcher({"https://gulf.example": "<title>Gulf Industrial</title>"})
        provider = ScraplingEnrichmentProvider(fetcher=fetcher, fetch_about_page=False)
        provider.enrich(make_lead(email="a@gulf.example"))
        calls_after_first = len(fetcher.calls)
        provider.enrich(make_lead(email="b@gulf.example"))
        self.assertEqual(len(fetcher.calls), calls_after_first)

    def test_llm_hook_replaces_meta_context(self):
        fetcher = CountingFetcher({"https://gulf.example": "<title>Gulf Industrial</title>"})
        router = LLMRouter(provider="claude", client=StaticLLMClient(
            enrichment_response={"company_summary": "Pump distributor.", "outreach_hook": "Their new Muscat warehouse opened in 2026."}
        ))
        provider = ScraplingEnrichmentProvider(fetcher=fetcher, llm_router=router, fetch_about_page=False)
        enriched = provider.enrich(make_lead())
        self.assertEqual(enriched.context, "Their new Muscat warehouse opened in 2026.")

    def test_llm_failure_keeps_meta_context(self):
        class Boom:
            def complete_json(self, **kwargs):
                raise RuntimeError("down")

        fetcher = CountingFetcher({"https://gulf.example": "<title>Gulf Industrial</title>"})
        router = LLMRouter(provider="claude", client=Boom())
        provider = ScraplingEnrichmentProvider(fetcher=fetcher, llm_router=router, fetch_about_page=False)
        with self.assertLogs("outreach_mvp.llm", level="WARNING"):
            enriched = provider.enrich(make_lead())
        self.assertIn("Gulf Industrial", enriched.context)


if __name__ == "__main__":
    unittest.main()
