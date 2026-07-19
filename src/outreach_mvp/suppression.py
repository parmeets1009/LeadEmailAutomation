"""Global, permanent suppression list. Safety invariant 2: entries here must
never be drafted, sent, or followed up — ever. Fails LOUD on corruption
(fail-closed: better to error than to email a suppressed person)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._jsonfile import atomic_write_json, load_json, lock_for


def _norm(email: str) -> str:
    return email.strip().lower()


class SuppressionStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, dict[str, Any]]:
        return load_json(self.path, {})

    def contains(self, email: str) -> bool:
        return _norm(email) in self._load() if email.strip() else False

    def add(self, email: str, reason: str) -> None:
        if not email.strip():
            return
        with lock_for(self.path):
            data = self._load()
            data.setdefault(_norm(email), {"reason": reason, "ts": datetime.now(timezone.utc).isoformat()})
            atomic_write_json(self.path, data)

    def all_emails(self) -> set[str]:
        return set(self._load())
