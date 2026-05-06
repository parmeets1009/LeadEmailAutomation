from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import httpx

from .mailbox import GmailDraftClient, OutlookDraftClient

GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
GRAPH_MESSAGES_ENDPOINT = "https://graph.microsoft.com/v1.0/me/messages"


@dataclass(frozen=True)
class MailboxClients:
    gmail: GmailDraftClient | None = None
    outlook: OutlookDraftClient | None = None


class GmailOAuthDraftClient:
    """OAuth-backed Gmail draft client.

    It accepts an already-built Gmail service for tests. In production, use
    from_authorized_user_file() with a Google authorized-user token JSON that
    has the gmail.compose scope.
    """

    def __init__(self, service: Any) -> None:
        self.service = service

    @classmethod
    def from_authorized_user_file(cls, token_path: str | Path, credentials_path: str | Path | None = None) -> "GmailOAuthDraftClient":
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError(
                "Gmail OAuth dependencies are missing. Install google-api-python-client, google-auth, and google-auth-oauthlib."
            ) from exc

        credentials = Credentials.from_authorized_user_file(str(token_path), scopes=[GMAIL_COMPOSE_SCOPE])
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            Path(token_path).write_text(credentials.to_json(), encoding="utf-8")
        if not credentials.valid:
            raise RuntimeError("Gmail OAuth token is invalid or missing gmail.compose scope")
        service = build("gmail", "v1", credentials=credentials)
        return cls(service=service)

    def create_draft(self, raw_message: str) -> dict[str, Any]:
        draft = {"message": {"raw": raw_message}}
        result = self.service.users().drafts().create(userId="me", body=draft).execute()
        return {"id": result.get("id", ""), "message_id": result.get("message", {}).get("id", "")}


class OutlookOAuthDraftClient:
    """OAuth-backed Microsoft Graph draft client.

    The access token must include Mail.ReadWrite. This client creates a draft in
    the signed-in user's Drafts folder via POST /me/messages. It does not send.
    """

    def __init__(self, access_token: str, http_client: Any | None = None, endpoint: str = GRAPH_MESSAGES_ENDPOINT) -> None:
        self.access_token = access_token
        self.http_client = http_client or httpx.Client(timeout=30)
        self.endpoint = endpoint

    @classmethod
    def from_token_file(cls, token_path: str | Path) -> "OutlookOAuthDraftClient":
        token_data = json.loads(Path(token_path).read_text(encoding="utf-8"))
        access_token = token_data.get("access_token")
        if not access_token:
            raise RuntimeError("Outlook token file does not contain access_token")
        return cls(access_token=access_token)

    def create_draft(self, message: dict[str, Any]) -> dict[str, Any]:
        response = self.http_client.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"},
            json=message,
        )
        response.raise_for_status()
        return response.json()


def create_mailbox_clients_from_env(env: Mapping[str, str] | None = None) -> MailboxClients:
    env = env or os.environ
    gmail: GmailDraftClient | None = None
    outlook: OutlookDraftClient | None = None

    gmail_token_path = env.get("GMAIL_TOKEN_PATH") or env.get("GOOGLE_TOKEN_PATH")
    if gmail_token_path:
        gmail = GmailOAuthDraftClient.from_authorized_user_file(
            gmail_token_path,
            credentials_path=env.get("GOOGLE_CLIENT_SECRET_PATH"),
        )

    outlook_token_path = env.get("OUTLOOK_TOKEN_PATH")
    if outlook_token_path:
        outlook = OutlookOAuthDraftClient.from_token_file(outlook_token_path)
    elif env.get("OUTLOOK_ACCESS_TOKEN"):
        outlook = OutlookOAuthDraftClient(access_token=env["OUTLOOK_ACCESS_TOKEN"])

    return MailboxClients(gmail=gmail, outlook=outlook)
