"""SPF / DKIM / DMARC presence checks for the sending domain."""
from __future__ import annotations

import re
from typing import Any, Protocol

DKIM_SELECTORS = ["google", "selector1", "selector2", "default"]
DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$")


class DnsResolver(Protocol):
    def txt_records(self, name: str) -> list[str]:
        """Return TXT record strings for name; raise on NXDOMAIN/timeout."""

    def has_record(self, name: str) -> bool:
        """True when name resolves to any TXT or CNAME record."""


class SystemDnsResolver:
    def __init__(self, lifetime: float = 3.0) -> None:
        import dns.resolver

        self._resolver = dns.resolver.Resolver()
        self._resolver.lifetime = lifetime
        self._dns = __import__("dns.resolver", fromlist=["resolver"])

    def txt_records(self, name: str) -> list[str]:
        answers = self._resolver.resolve(name, "TXT")
        return [b"".join(r.strings).decode("utf-8", errors="replace") for r in answers]

    def has_record(self, name: str) -> bool:
        for rtype in ("TXT", "CNAME"):
            try:
                self._resolver.resolve(name, rtype)
                return True
            except Exception:  # noqa: BLE001 — absence/timeouts all mean "not found"
                continue
        return False


def is_valid_domain(domain: str) -> bool:
    return bool(DOMAIN_RE.match(domain.strip().lower()))


def check_domain(domain: str, resolver: DnsResolver | None = None) -> dict[str, Any]:
    domain = domain.strip().lower()
    resolver = resolver or SystemDnsResolver()

    spf: dict[str, Any] = {"found": False, "record": ""}
    try:
        for record in resolver.txt_records(domain):
            if record.lower().startswith("v=spf1"):
                spf = {"found": True, "record": record}
                break
    except Exception:  # noqa: BLE001
        pass

    dmarc: dict[str, Any] = {"found": False, "record": ""}
    try:
        for record in resolver.txt_records(f"_dmarc.{domain}"):
            if "v=dmarc1" in record.lower():
                dmarc = {"found": True, "record": record}
                break
    except Exception:  # noqa: BLE001
        pass

    dkim = {selector: resolver.has_record(f"{selector}._domainkey.{domain}") for selector in DKIM_SELECTORS}

    return {
        "domain": domain,
        "spf": spf,
        "dmarc": dmarc,
        "dkim": dkim,
        "dkim_found": any(dkim.values()),
        "ready": spf["found"] and dmarc["found"] and any(dkim.values()),
    }
