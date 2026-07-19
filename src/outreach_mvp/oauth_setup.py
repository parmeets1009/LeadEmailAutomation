from __future__ import annotations

import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

import httpx

# compose = draft creation; send = Mode B auto-send; readonly = reply sync.
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]
OUTLOOK_SCOPES = ["offline_access", "Mail.ReadWrite", "Mail.Send", "Mail.Read"]


class OAuthSetupError(Exception):
    pass


class OAuthConfigurationError(OAuthSetupError):
    pass


class OAuthStateError(OAuthSetupError):
    pass


@dataclass(frozen=True)
class OAuthProviderConfig:
    provider: str
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    auth_url: str = ""
    token_url: str = ""
    scopes: list[str] = field(default_factory=list)

    def normalized(self) -> "OAuthProviderConfig":
        provider = self.provider.lower()
        if provider == "gmail":
            return OAuthProviderConfig(
                provider="gmail",
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                auth_url=self.auth_url or "https://accounts.google.com/o/oauth2/v2/auth",
                token_url=self.token_url or "https://oauth2.googleapis.com/token",
                scopes=self.scopes or GMAIL_SCOPES,
            )
        if provider == "outlook":
            return OAuthProviderConfig(
                provider="outlook",
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                auth_url=self.auth_url or "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                token_url=self.token_url or "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                scopes=self.scopes or OUTLOOK_SCOPES,
            )
        return self

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.redirect_uri)


class OAuthSetupService:
    def __init__(
        self,
        token_dir: Path | str,
        state_dir: Path | str,
        configs: Mapping[str, OAuthProviderConfig] | None = None,
        http_client: Any | None = None,
    ) -> None:
        self.token_dir = Path(token_dir)
        self.state_dir = Path(state_dir)
        self.token_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.http_client = http_client or httpx.Client(timeout=30)
        base = configs or configs_from_env()
        self.configs = {name.lower(): config.normalized() for name, config in base.items()}
        for provider in ["gmail", "outlook"]:
            self.configs.setdefault(provider, OAuthProviderConfig(provider=provider).normalized())

    def status(self) -> dict[str, Any]:
        return {
            "providers": {
                provider: {
                    "provider": provider,
                    "configured": config.configured,
                    "connected": self.token_path(provider).exists(),
                    "scopes": config.scopes,
                    "token_path": str(self.token_path(provider)),
                }
                for provider, config in self.configs.items()
                if provider in {"gmail", "outlook"}
            }
        }

    def start(self, provider: str) -> dict[str, str]:
        provider = provider.lower()
        config = self._configured(provider)
        state = secrets.token_urlsafe(24)
        self._state_path(provider, state).write_text(
            json.dumps({"provider": provider, "created_at": int(time.time())}, indent=2),
            encoding="utf-8",
        )
        query = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "state": state,
        }
        if provider == "gmail":
            query.update({"access_type": "offline", "prompt": "consent"})
        auth_url = f"{config.auth_url}?{urlencode(query)}"
        return {"provider": provider, "auth_url": auth_url, "state": state}

    def callback(self, provider: str, code: str, state: str) -> dict[str, Any]:
        provider = provider.lower()
        config = self._configured(provider)
        state_path = self._state_path(provider, state)
        if not state or not state_path.exists():
            raise OAuthStateError("invalid or expired OAuth state")
        payload = {
            "client_id": config.client_id,
            "code": code,
            "redirect_uri": config.redirect_uri,
            "grant_type": "authorization_code",
        }
        if config.client_secret:
            payload["client_secret"] = config.client_secret
        if provider == "outlook":
            payload["scope"] = " ".join(config.scopes)
        response = self.http_client.post(
            config.token_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        token_data = response.json()
        token_data.setdefault("provider", provider)
        token_data.setdefault("created_at", int(time.time()))
        token_path = self.token_path(provider)
        token_path.write_text(json.dumps(token_data, indent=2), encoding="utf-8")
        try:
            token_path.chmod(0o600)
        except OSError:
            pass
        state_path.unlink(missing_ok=True)
        return {"provider": provider, "connected": True, "token_path": str(token_path)}

    def token_path(self, provider: str) -> Path:
        return self.token_dir / f"{provider.lower()}_token.json"

    def _configured(self, provider: str) -> OAuthProviderConfig:
        config = self.configs.get(provider)
        if not config or not config.configured:
            raise OAuthConfigurationError(f"{provider} OAuth is not configured")
        return config

    def _state_path(self, provider: str, state: str) -> Path:
        safe_state = "".join(ch for ch in state if ch.isalnum() or ch in {"-", "_"})
        return self.state_dir / f"{provider.lower()}_{safe_state}.json"


def configs_from_env(env: Mapping[str, str] | None = None) -> dict[str, OAuthProviderConfig]:
    env = env or os.environ
    # Default matches the bridge topology (backend/server.py mounts the API at
    # /api on port 8001); the standalone dev server should set APP_BASE_URL.
    default_base_url = env.get("APP_BASE_URL", "http://127.0.0.1:8001/api").rstrip("/")
    return {
        "gmail": OAuthProviderConfig(
            provider="gmail",
            client_id=env.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            client_secret=env.get("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            redirect_uri=env.get("GOOGLE_OAUTH_REDIRECT_URI", f"{default_base_url}/oauth/gmail/callback"),
        ),
        "outlook": OAuthProviderConfig(
            provider="outlook",
            client_id=env.get("MICROSOFT_OAUTH_CLIENT_ID", ""),
            client_secret=env.get("MICROSOFT_OAUTH_CLIENT_SECRET", ""),
            redirect_uri=env.get("MICROSOFT_OAUTH_REDIRECT_URI", f"{default_base_url}/oauth/outlook/callback"),
        ),
    }


def create_oauth_setup_service_from_env(storage_dir: Path | str, env: Mapping[str, str] | None = None) -> OAuthSetupService:
    root = Path(storage_dir)
    return OAuthSetupService(
        token_dir=root / "oauth_tokens",
        state_dir=root / "oauth_state",
        configs=configs_from_env(env),
    )
