"""
Email intelligence: syntax validation, MX record lookup, disposable-domain
detection against a bundled static list, and an optional Have I Been Pwned
breach lookup (only performed if HIBP_API_KEY is configured - HIBP's
authenticated endpoints require a paid subscription key as of API v3).
"""
from __future__ import annotations

import re
from pathlib import Path

import dns.resolver
import httpx

from .. import config

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_DISPOSABLE_PATH = Path(__file__).resolve().parent.parent / "data" / "disposable_domains.txt"
with open(_DISPOSABLE_PATH, "r", encoding="utf-8") as f:
    DISPOSABLE_DOMAINS = {line.strip().lower() for line in f if line.strip() and not line.startswith("#")}


def _mx_lookup(domain: str) -> dict:
    try:
        answers = dns.resolver.resolve(domain, "MX", lifetime=config.HTTP_TIMEOUT)
        records = sorted(
            [{"priority": r.preference, "exchange": str(r.exchange).rstrip(".")} for r in answers],
            key=lambda x: x["priority"],
        )
        return {"has_mx": True, "records": records}
    except dns.resolver.NXDOMAIN:
        return {"has_mx": False, "records": [], "error": "domain does not exist"}
    except dns.resolver.NoAnswer:
        return {"has_mx": False, "records": [], "error": "no MX records"}
    except Exception as e:  # noqa: BLE001
        return {"has_mx": False, "records": [], "error": str(e)}


async def _hibp_lookup(email: str) -> dict:
    if not config.HIBP_API_KEY:
        return {"checked": False, "reason": "HIBP_API_KEY not configured - skipped"}
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}"
    headers = {
        "hibp-api-key": config.HIBP_API_KEY,
        "user-agent": config.USER_AGENT,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params={"truncateResponse": "false"},
                                     timeout=config.HTTP_TIMEOUT)
        if resp.status_code == 404:
            return {"checked": True, "breached": False, "breaches": []}
        if resp.status_code == 200:
            data = resp.json()
            return {"checked": True, "breached": True, "breaches": data}
        if resp.status_code == 401:
            return {"checked": False, "reason": "HIBP API key rejected (unauthorized)"}
        if resp.status_code == 429:
            return {"checked": False, "reason": "HIBP rate limit hit, try again shortly"}
        return {"checked": False, "reason": f"HIBP returned HTTP {resp.status_code}"}
    except Exception as e:  # noqa: BLE001
        return {"checked": False, "reason": f"HIBP lookup failed: {e}"}


async def check_email_async(email: str) -> dict:
    email = email.strip()
    result = {"email": email, "valid_syntax": bool(EMAIL_RE.match(email))}
    if not result["valid_syntax"]:
        result["summary"] = "Invalid email syntax."
        return result

    local, domain = email.rsplit("@", 1)
    domain = domain.lower()
    result["domain"] = domain
    result["mx"] = _mx_lookup(domain)
    result["disposable"] = domain in DISPOSABLE_DOMAINS
    result["hibp"] = await _hibp_lookup(email)

    bits = []
    bits.append("valid syntax")
    bits.append("has MX" if result["mx"]["has_mx"] else "no MX (likely undeliverable)")
    if result["disposable"]:
        bits.append("KNOWN DISPOSABLE DOMAIN")
    if result["hibp"].get("checked") and result["hibp"].get("breached"):
        n = len(result["hibp"]["breaches"])
        bits.append(f"found in {n} known breach(es)")
    result["summary"] = "; ".join(bits)
    return result
