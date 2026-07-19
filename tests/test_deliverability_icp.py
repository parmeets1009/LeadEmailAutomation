import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from starlette.testclient import TestClient

from outreach_mvp.api import create_app
from outreach_mvp.deliverability import check_domain, is_valid_domain

from env_helpers import HERMETIC_ENV

NO_LLM_KEYS = dict(HERMETIC_ENV)


class FakeResolver:
    def __init__(self, txt=None, records=None):
        self.txt = txt or {}
        self.records = records or set()

    def txt_records(self, name):
        if name not in self.txt:
            raise LookupError(name)
        return self.txt[name]

    def has_record(self, name):
        return name in self.records


class DeliverabilityTests(unittest.TestCase):
    def test_domain_validation(self):
        self.assertTrue(is_valid_domain("acme-pumps.example.com"))
        self.assertFalse(is_valid_domain("not a domain"))
        self.assertFalse(is_valid_domain("nodots"))

    def test_all_records_present(self):
        resolver = FakeResolver(
            txt={
                "acme.com": ["v=spf1 include:_spf.google.com ~all"],
                "_dmarc.acme.com": ["v=DMARC1; p=none; rua=mailto:x@acme.com"],
            },
            records={"google._domainkey.acme.com"},
        )
        result = check_domain("acme.com", resolver=resolver)
        self.assertTrue(result["spf"]["found"])
        self.assertTrue(result["dmarc"]["found"])
        self.assertTrue(result["dkim"]["google"])
        self.assertTrue(result["ready"])

    def test_missing_records_reported(self):
        result = check_domain("acme.com", resolver=FakeResolver())
        self.assertFalse(result["spf"]["found"])
        self.assertFalse(result["dmarc"]["found"])
        self.assertFalse(result["ready"])

    def test_endpoint_rejects_invalid_domain(self):
        with tempfile.TemporaryDirectory() as tmpdir, mock.patch.dict(os.environ, NO_LLM_KEYS):
            client = TestClient(create_app(storage_dir=Path(tmpdir)))
            self.assertEqual(client.get("/deliverability/not%20a%20domain").status_code, 400)


class IcpEndpointTests(unittest.TestCase):
    def setUp(self):
        self.env_patcher = mock.patch.dict(os.environ, NO_LLM_KEYS)
        self.env_patcher.start()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = TestClient(create_app(storage_dir=Path(self.tmpdir.name)))

    def tearDown(self):
        self.env_patcher.stop()
        self.tmpdir.cleanup()

    def test_icp_roundtrip(self):
        self.assertEqual(self.client.get("/icp").status_code, 404)
        response = self.client.post("/icp", json={
            "company": {"name": "Acme", "website": "", "description": "Industrial pumps manufacturer.", "details": {}},
            "exclusions": [" Rival@competitor.com ", "competitor.com"],
        })
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["exclusions"], ["rival@competitor.com", "competitor.com"])
        self.assertIn("buyer_personas", body["profile"])

        fetched = self.client.get("/icp")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["exclusions"], ["rival@competitor.com", "competitor.com"])


if __name__ == "__main__":
    unittest.main()
