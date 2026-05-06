from __future__ import annotations

from pathlib import Path


FRONTEND_DIR = Path(__file__).with_name("frontend")


def dashboard_html() -> str:
    return (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
