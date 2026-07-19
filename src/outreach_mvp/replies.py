"""Reply sync: poll a connected mailbox, match senders against the contacted
store, classify with the LLM (keyword fallback), and act — suppression is
applied instantly on any unsubscribe intent."""
from __future__ import annotations

import logging
import re
from typing import Any, Protocol

from .contacted import ContactedStore
from .suppression import SuppressionStore
from .llm import LLMRouter
from .storage import JsonCampaignStore

logger = logging.getLogger("outreach_mvp.replies")

# Hard keywords match anywhere; the soft phrase "not relevant" (our own opt-out
# instruction) only counts in a SHORT reply — a long positive reply that happens
# to contain the phrase must never be auto-suppressed.
HARD_UNSUBSCRIBE_KEYWORDS = ["unsubscribe", "stop emailing", "remove me", "do not contact", "take me off"]
SOFT_UNSUBSCRIBE_PHRASE = "not relevant"
SOFT_UNSUBSCRIBE_MAX_CHARS = 160
OOO_KEYWORDS = ["out of office", "auto-reply", "autoreply", "on leave", "annual leave"]
NOT_INTERESTED_KEYWORDS = ["not interested", "no thanks", "no thank you", "we already have"]
# Our OWN footer text gets quoted back in reply previews — strip it before
# classifying, or every short reply would look like an unsubscribe request.
OWN_FOOTER_PHRASES = [
    "if this is not relevant, reply 'not relevant' and i will not contact you again.",
    "unsubscribe with one click:",
]


class ReplyClient(Protocol):
    def list_recent_messages(self, newer_than_days: int = 7) -> list[dict[str, Any]]: ...


def extract_email(from_field: str) -> str:
    match = re.search(r"<([^>]+)>", from_field)
    return (match.group(1) if match else from_field).strip().lower()


def strip_own_footer(text: str) -> str:
    lowered = text.lower()
    for phrase in OWN_FOOTER_PHRASES:
        lowered = lowered.replace(phrase, " ")
    # Drop quoted lines (">"-prefixed) — they are OUR email, not their reply.
    lines = [line for line in lowered.splitlines() if not line.lstrip().startswith(">")]
    return re.sub(r"https?://\S+/u/\S+", " ", "\n".join(lines))


def heuristic_classification(text: str) -> dict[str, str]:
    cleaned = strip_own_footer(text)
    if any(keyword in cleaned for keyword in HARD_UNSUBSCRIBE_KEYWORDS):
        return {"category": "unsubscribe", "summary": "Opt-out keywords detected.", "suggested_action": "remove_and_suppress"}
    if SOFT_UNSUBSCRIBE_PHRASE in cleaned and len(cleaned.strip()) <= SOFT_UNSUBSCRIBE_MAX_CHARS:
        return {"category": "unsubscribe", "summary": "Short 'not relevant' opt-out reply.", "suggested_action": "remove_and_suppress"}
    if any(keyword in cleaned for keyword in OOO_KEYWORDS):
        return {"category": "out_of_office", "summary": "Auto-reply detected.", "suggested_action": "retry_later"}
    if any(keyword in cleaned for keyword in NOT_INTERESTED_KEYWORDS):
        return {"category": "not_interested", "summary": "Declined.", "suggested_action": "stop_sequence"}
    return {"category": "other", "summary": "Needs a human read.", "suggested_action": "forward_to_human"}


class ReplySyncService:
    def __init__(
        self,
        store: JsonCampaignStore,
        contacted: ContactedStore,
        suppression: SuppressionStore,
        llm_router: LLMRouter | None = None,
    ) -> None:
        self.store = store
        self.contacted = contacted
        self.suppression = suppression
        self.llm_router = llm_router

    def sync(self, client: ReplyClient, newer_than_days: int = 7) -> dict[str, Any]:
        matched: list[dict[str, Any]] = []
        ignored = 0
        for message in client.list_recent_messages(newer_than_days):
            email = extract_email(str(message.get("from_email", "")))
            entry = self.contacted.lookup(email) if email else None
            if not entry:
                ignored += 1
                continue
            text = f"{message.get('subject', '')}\n{message.get('snippet', '')}"
            classification = self._classify(text, str(message.get("subject", "")))
            action = classification["suggested_action"]
            if action == "remove_and_suppress" or classification["category"] == "unsubscribe":
                self.suppression.add(email, "reply_unsubscribe")
            # An out-of-office auto-reply is not a real reply: marking it replied
            # would permanently kill the follow-up sequence.
            if classification["category"] != "out_of_office":
                self._mark_replied(entry, classification)
            matched.append({"email": email, **classification, "campaign_id": entry.get("campaign_id", ""), "draft_id": entry.get("draft_id", "")})
        return {"matched": matched, "matched_count": len(matched), "ignored_count": ignored}

    def _classify(self, text: str, subject: str) -> dict[str, str]:
        if self.llm_router is not None and getattr(self.llm_router, "enabled", False):
            result, error = self.llm_router.classify_reply(text, subject)
            if result:
                return result
            logger.warning("LLM reply classification failed (%s); using keyword fallback", error)
        return heuristic_classification(text)

    def _mark_replied(self, entry: dict[str, Any], classification: dict[str, str]) -> None:
        campaign_id = entry.get("campaign_id", "")
        draft_id = entry.get("draft_id", "")
        if not campaign_id or not draft_id:
            return
        summary = f"{classification['category']}: {classification['summary']}"[:200]
        try:
            self.store.mark_draft_replied(campaign_id, draft_id, summary)
        except (FileNotFoundError, KeyError):
            logger.warning("Reply matched contacted entry but campaign/draft %s/%s no longer exists", campaign_id, draft_id)
