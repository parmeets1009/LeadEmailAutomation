"""Shared JSON-file persistence: in-process locks + atomic writes + loud corruption.

Rules (learned the hard way, see ROADMAP review log):
- A MISSING or empty file means "empty store". A CORRUPT file raises — returning
  an empty container and then saving over it silently wipes the store, which for
  the suppression list would make every opted-out address reachable again.
- Writes go to a temp file then os.replace(), so a crash mid-write can never
  leave a half-written file.
- Mutations take a per-path in-process lock (the app runs as a single uvicorn
  process; cross-process locking is out of scope and documented).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


class StoreCorruptError(RuntimeError):
    pass


def lock_for(path: Path) -> threading.Lock:
    key = str(Path(path).resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.Lock())


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise StoreCorruptError(f"{path} is corrupt ({exc}); refusing to overwrite it — inspect/restore the file") from exc


def atomic_write_json(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
