from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from .models import CampaignInput, CompanyInput, LeadInput, to_plain_data
from .orchestrator import DraftFirstOrchestrator
from .storage import JsonCampaignStore


def _load_leads(path: Path) -> list[LeadInput]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        return [
            LeadInput(
                first_name=row.get("first_name", ""),
                last_name=row.get("last_name", ""),
                email=row.get("email", ""),
                title=row.get("title", ""),
                company_name=row.get("company_name", ""),
                country=row.get("country", ""),
                industry=row.get("industry", ""),
                website=row.get("website", ""),
                context=row.get("context", ""),
            )
            for row in rows
        ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate draft-first outreach campaign JSON from a lead CSV")
    parser.add_argument("--company-name", required=True)
    parser.add_argument("--company-website", default="")
    parser.add_argument("--company-description", required=True)
    parser.add_argument("--campaign-name", required=True)
    parser.add_argument("--target-country", required=True)
    parser.add_argument("--target-region", required=True)
    parser.add_argument("--sender-name", required=True)
    parser.add_argument("--sender-email", required=True)
    parser.add_argument("--template", required=True)
    parser.add_argument("--leads-csv", required=True, type=Path)
    parser.add_argument("--out", default="campaign_runs", type=Path)
    parser.add_argument("--max-drafts", default=10, type=int)
    args = parser.parse_args(argv)

    company = CompanyInput(args.company_name, args.company_website, args.company_description, {})
    campaign = CampaignInput(
        name=args.campaign_name,
        target_country=args.target_country,
        target_region=args.target_region,
        max_drafts=args.max_drafts,
        sender_name=args.sender_name,
        sender_email=args.sender_email,
        template=args.template,
        target_titles=["Procurement Manager", "Sourcing Manager", "Operations Manager"],
        target_industries=["Industrial", "Construction", "Manufacturing"],
    )
    result = DraftFirstOrchestrator().create_draft_campaign(company, campaign, _load_leads(args.leads_csv))
    saved = JsonCampaignStore(args.out).save(result)
    print(json.dumps({"saved": str(saved), "draft_count": len(result.drafts), "skipped": result.skipped}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
