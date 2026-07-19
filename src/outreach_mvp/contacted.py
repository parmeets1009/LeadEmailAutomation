"""Cross-campaign record of everyone we have already reached out to.

Marked when a message actually lands in a mailbox (draft artifact, live draft,
or send) — never at draft-generation time. Fails loud on corruption; atomic,
locked writes (see _jsonfile.py).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._jsonfile import atomic_write_json, load_json, lock_for


def _norm(email: str) -> str:
    return email.strip().lower()


class ContactedStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, dict[str, Any]]:
        return load_json(self.path, {})

    def was_contacted(self, email: str) -> bool:
        return _norm(email) in self._load() if email.strip() else False

    def lookup(self, email: str) -> dict[str, Any] | None:
        return self._load().get(_norm(email))

    def add(self, email: str, campaign_id: str, draft_id: str, ts: str | None = None) -> None:
        if not email.strip():
            return
        with lock_for(self.path):
            data = self._load()
            data[_norm(email)] = {
                "campaign_id": campaign_id,
                "draft_id": draft_id,
                "ts": ts or datetime.now(timezone.utc).isoformat(),
            }
            atomic_write_json(self.path, data)

    def count(self) -> int:
        return len(self._load())
