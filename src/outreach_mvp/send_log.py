"""Append-only record of every live send. The per-day cap reads THIS log —
the cap is enforced in code, not in the UI. Fails loud on corruption (a wiped
log would silently reset the cap); atomic, locked writes."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._jsonfile import atomic_write_json, load_json, lock_for

DEFAULT_DAILY_SEND_CAP = 20


class SendLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> list[dict[str, Any]]:
        return load_json(self.path, [])

    def append(self, *, email: str, campaign_id: str, draft_id: str, mailbox: str, ts: str | None = None) -> None:
        with lock_for(self.path):
            entries = self._load()
            entries.append(
                {
                    "email": email.strip().lower(),
                    "campaign_id": campaign_id,
                    "draft_id": draft_id,
                    "mailbox": mailbox,
                    "ts": ts or datetime.now(timezone.utc).isoformat(),
                }
            )
            atomic_write_json(self.path, entries)

    def sends_today(self, mailbox: str, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        today = now.date().isoformat()
        count = 0
        for entry in self._load():
            if entry.get("mailbox") != mailbox:
                continue
            if str(entry.get("ts", "")).startswith(today):
                count += 1
        return count

    def was_sent(self, campaign_id: str, draft_id: str) -> bool:
        return any(e.get("campaign_id") == campaign_id and e.get("draft_id") == draft_id for e in self._load())
