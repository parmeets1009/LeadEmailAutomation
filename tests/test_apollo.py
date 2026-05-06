import unittest

from outreach_mvp.apollo import ApolloLeadProvider


class FakeApolloClient:
    def __init__(self):
        self.calls = []

    def search_people(self, *, filters, page, per_page):
        self.calls.append({"filters": filters, "page": page, "per_page": per_page})
        return {
            "people": [
                {
                    "first_name": "Ahmed",
                    "last_name": "Khan",
                    "email": "ahmed@example.ae",
                    "title": "Procurement Manager",
                    "organization": {
                        "name": "Gulf Industrial Supplies",
                        "website_url": "https://gulf.example",
                        "industry": "Industrial",
                    },
                    "country": "United Arab Emirates",
                },
                {
                    "name": "Sara Noor",
                    "email": "sara@example.ae",
                    "headline": "Sourcing Manager at BuildRight UAE",
                    "organization_name": "BuildRight UAE",
                    "organization_website_url": "https://buildright.example",
                    "industry": "Construction",
                    "country": "UAE",
                },
            ]
        }


class ApolloLeadProviderTests(unittest.TestCase):
    def test_search_normalizes_apollo_people_to_lead_inputs(self):
        client = FakeApolloClient()
        provider = ApolloLeadProvider(client=client)

        leads = provider.search_leads(
            titles=["Procurement Manager", "Sourcing Manager"],
            locations=["United Arab Emirates"],
            industries=["Industrial", "Construction"],
            max_leads=5,
        )

        self.assertEqual(len(leads), 2)
        self.assertEqual(leads[0].first_name, "Ahmed")
        self.assertEqual(leads[0].last_name, "Khan")
        self.assertEqual(leads[0].email, "ahmed@example.ae")
        self.assertEqual(leads[0].title, "Procurement Manager")
        self.assertEqual(leads[0].company_name, "Gulf Industrial Supplies")
        self.assertEqual(leads[0].country, "United Arab Emirates")
        self.assertEqual(leads[0].industry, "Industrial")
        self.assertEqual(leads[0].website, "https://gulf.example")
        self.assertIn("Apollo", leads[0].context)

        self.assertEqual(leads[1].first_name, "Sara")
        self.assertEqual(leads[1].last_name, "Noor")
        self.assertEqual(leads[1].title, "Sourcing Manager at BuildRight UAE")
        self.assertEqual(leads[1].company_name, "BuildRight UAE")

        self.assertEqual(client.calls[0]["filters"]["titles"], ["Procurement Manager", "Sourcing Manager"])
        self.assertEqual(client.calls[0]["filters"]["locations"], ["United Arab Emirates"])
        self.assertEqual(client.calls[0]["per_page"], 5)

    def test_search_skips_people_without_email(self):
        class MissingEmailClient:
            def search_people(self, *, filters, page, per_page):
                return {"people": [{"first_name": "No", "last_name": "Email", "title": "Buyer"}]}

        leads = ApolloLeadProvider(client=MissingEmailClient()).search_leads(titles=["Buyer"], max_leads=10)

        self.assertEqual(leads, [])


if __name__ == "__main__":
    unittest.main()
