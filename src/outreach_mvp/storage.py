from __future__ import annotations

import json
import re
from pathlib import Path

from .models import CampaignResult, from_campaign_result, to_plain_data


class JsonCampaignStore:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, result: CampaignResult) -> Path:
        slug = self._slug(result.campaign.name)
        path = self.directory / f"{slug}.json"
        path.write_text(json.dumps(to_plain_data(result), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def load(self, filename: str) -> CampaignResult:
        path = self.directory / filename
        return from_campaign_result(json.loads(path.read_text(encoding="utf-8")))

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "campaign"
