import json
import tempfile
import unittest
from pathlib import Path

from outreach_mvp.oauth_clients import GmailOAuthDraftClient, OutlookOAuthDraftClient, create_mailbox_clients_from_env


class FakeGmailDraftsCreate:
    def __init__(self, body):
        self.body = body

    def execute(self):
        return {"id": "real-gmail-draft", "message": {"id": "real-gmail-message"}}


class FakeGmailDrafts:
    def __init__(self):
        self.calls = []

    def create(self, userId, body):
        self.calls.append({"userId": userId, "body": body})
        return FakeGmailDraftsCreate(body)


class FakeGmailUsers:
    def __init__(self, drafts):
        self._drafts = drafts

    def drafts(self):
        return self._drafts


class FakeGmailService:
    def __init__(self):
        self.drafts = FakeGmailDrafts()

    def users(self):
        return FakeGmailUsers(self.drafts)


class FakeHttpResponse:
    def __init__(self, status_code=201, payload=None):
        self.status_code = status_code
        self._payload = payload or {"id": "real-outlook-draft"}
        self.text = json.dumps(self._payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.text)

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(self):
        self.posts = []

    def post(self, url, headers, json):
        self.posts.append({"url": url, "headers": headers, "json": json})
        return FakeHttpResponse()


class OAuthClientTests(unittest.TestCase):
    def test_gmail_oauth_draft_client_calls_users_drafts_create(self):
        service = FakeGmailService()
        client = GmailOAuthDraftClient(service=service)

        result = client.create_draft("raw-gmail-message")

        self.assertEqual(result["id"], "real-gmail-draft")
        self.assertEqual(result["message_id"], "real-gmail-message")
        self.assertEqual(service.drafts.calls[0]["userId"], "me")
        self.assertEqual(service.drafts.calls[0]["body"], {"message": {"raw": "raw-gmail-message"}})

    def test_outlook_oauth_draft_client_posts_to_graph_messages_endpoint(self):
        http_client = FakeHttpClient()
        client = OutlookOAuthDraftClient(access_token="token-123", http_client=http_client)
        message = {"subject": "Hello", "body": {"contentType": "Text", "content": "Body"}, "toRecipients": []}

        result = client.create_draft(message)

        self.assertEqual(result["id"], "real-outlook-draft")
        post = http_client.posts[0]
        self.assertEqual(post["url"], "https://graph.microsoft.com/v1.0/me/messages")
        self.assertEqual(post["headers"]["Authorization"], "Bearer token-123")
        self.assertEqual(post["json"], message)

    def test_create_mailbox_clients_from_env_loads_token_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_path = Path(tmp) / "outlook-token.json"
            token_path.write_text(json.dumps({"access_token": "outlook-token"}), encoding="utf-8")
            clients = create_mailbox_clients_from_env({"OUTLOOK_TOKEN_PATH": str(token_path)})

        self.assertIsNone(clients.gmail)
        self.assertIsNotNone(clients.outlook)


if __name__ == "__main__":
    unittest.main()
