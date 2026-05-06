import json
import tempfile
import unittest
from pathlib import Path

from starlette.testclient import TestClient

from outreach_mvp.api import create_app
from outreach_mvp.oauth_setup import OAuthProviderConfig, OAuthSetupService


class FakeTokenResponse:
    def __init__(self, payload=None, status_code=200):
        self.payload = payload or {"access_token": "access-123", "refresh_token": "refresh-456", "expires_in": 3600}
        self.status_code = status_code
        self.text = json.dumps(self.payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.text)

    def json(self):
        return self.payload


class FakeTokenHttpClient:
    def __init__(self):
        self.posts = []

    def post(self, url, data, headers):
        self.posts.append({"url": url, "data": data, "headers": headers})
        return FakeTokenResponse()


class OAuthSetupApiTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.storage_dir = Path(self.tmpdir.name)
        self.http_client = FakeTokenHttpClient()
        self.oauth_service = OAuthSetupService(
            token_dir=self.storage_dir / "oauth_tokens",
            state_dir=self.storage_dir / "oauth_state",
            http_client=self.http_client,
            configs={
                "gmail": OAuthProviderConfig(
                    provider="gmail",
                    client_id="gmail-client-id",
                    client_secret="gmail-client-secret",
                    redirect_uri="http://localhost:8000/oauth/gmail/callback",
                ),
                "outlook": OAuthProviderConfig(
                    provider="outlook",
                    client_id="outlook-client-id",
                    client_secret="outlook-client-secret",
                    redirect_uri="http://localhost:8000/oauth/outlook/callback",
                ),
            },
        )
        self.client = TestClient(create_app(storage_dir=self.storage_dir, oauth_service=self.oauth_service))

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_mailbox_status_reports_configured_and_connected_providers(self):
        response = self.client.get("/mailboxes/status")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["providers"]["gmail"]["configured"])
        self.assertFalse(body["providers"]["gmail"]["connected"])
        self.assertTrue(body["providers"]["outlook"]["configured"])
        self.assertFalse(body["providers"]["outlook"]["connected"])
        self.assertIn("gmail.compose", body["providers"]["gmail"]["scopes"][0])
        self.assertIn("Mail.ReadWrite", body["providers"]["outlook"]["scopes"])

    def test_oauth_start_returns_provider_authorization_urls(self):
        gmail = self.client.get("/oauth/gmail/start")
        outlook = self.client.get("/oauth/outlook/start")

        self.assertEqual(gmail.status_code, 200)
        gmail_body = gmail.json()
        self.assertEqual(gmail_body["provider"], "gmail")
        self.assertIn("https://accounts.google.com/o/oauth2/v2/auth", gmail_body["auth_url"])
        self.assertIn("client_id=gmail-client-id", gmail_body["auth_url"])
        self.assertIn("gmail.compose", gmail_body["auth_url"])

        self.assertEqual(outlook.status_code, 200)
        outlook_body = outlook.json()
        self.assertEqual(outlook_body["provider"], "outlook")
        self.assertIn("https://login.microsoftonline.com/common/oauth2/v2.0/authorize", outlook_body["auth_url"])
        self.assertIn("client_id=outlook-client-id", outlook_body["auth_url"])
        self.assertIn("Mail.ReadWrite", outlook_body["auth_url"])

    def test_oauth_callback_exchanges_code_and_marks_provider_connected(self):
        start = self.client.get("/oauth/gmail/start").json()
        callback = self.client.get("/oauth/gmail/callback", params={"code": "code-123", "state": start["state"]})

        self.assertEqual(callback.status_code, 200)
        self.assertEqual(callback.json()["provider"], "gmail")
        self.assertTrue(callback.json()["connected"])
        self.assertTrue((self.storage_dir / "oauth_tokens" / "gmail_token.json").exists())
        self.assertEqual(self.http_client.posts[0]["url"], "https://oauth2.googleapis.com/token")
        self.assertEqual(self.http_client.posts[0]["data"]["code"], "code-123")

        status = self.client.get("/mailboxes/status").json()
        self.assertTrue(status["providers"]["gmail"]["connected"])

    def test_oauth_start_returns_503_when_provider_not_configured(self):
        unconfigured = TestClient(create_app(storage_dir=self.storage_dir, load_oauth_clients_from_env=False))

        response = unconfigured.get("/oauth/gmail/start")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "gmail OAuth is not configured")


if __name__ == "__main__":
    unittest.main()
