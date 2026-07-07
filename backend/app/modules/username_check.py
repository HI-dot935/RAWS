"""
Username availability / presence check across major public platforms.

This performs simple, read-only HTTP requests (HEAD/GET) against public
profile URLs and classifies the result as found / not_found / unknown.
No login, scraping of private data, or ToS-violating automation is
performed - it purely checks whether a public profile page resolves.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import httpx

from .. import config

PLATFORMS_PATH = Path(__file__).resolve().parent.parent / "data" / "platforms.json"
with open(PLATFORMS_PATH, "r", encoding="utf-8") as f:
    PLATFORMS = json.load(f)

_SAFE_USERNAME = re.compile(r"^[A-Za-z0-9_.\-@]{1,64}$")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0 Safari/537.36 " + config.USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


async def _check_one(client: httpx.AsyncClient, platform: dict, username: str) -> dict:
    url = platform["url"].format(username)
    profile_url = platform.get("profile_url", platform["url"]).format(username)
    result = {
        "platform": platform["name"],
        "url": profile_url,
        "status": "unknown",
        "note": platform.get("note", ""),
    }
    try:
        resp = await client.get(url, headers=HEADERS, timeout=config.HTTP_TIMEOUT, follow_redirects=True)
        code = resp.status_code
        check_mode = platform.get("check", "status")

        if code == 404:
            result["status"] = "not_found"
        elif code in (403, 429, 999, 451):
            result["status"] = "unknown"
            result["note"] = (result["note"] + " (blocked automated request, verify manually)").strip()
        elif 200 <= code < 300:
            if check_mode == "status_or_text":
                needle = platform.get("not_found_text", "")
                body = resp.text[:20000] if needle else ""
                if needle and needle.lower() in body.lower():
                    result["status"] = "not_found"
                else:
                    result["status"] = "found"
            else:
                result["status"] = "found"
        elif 300 <= code < 400:
            result["status"] = "found"
        else:
            result["status"] = "unknown"
    except (httpx.TimeoutException, httpx.TransportError):
        result["status"] = "unknown"
        result["note"] = (result["note"] + " (request timed out or failed)").strip()
    except Exception as e:  # noqa: BLE001
        result["status"] = "unknown"
        result["note"] = f"error: {e}"
    return result


async def check_username_async(username: str, platforms: list | None = None) -> dict:
    if not _SAFE_USERNAME.match(username):
        return {
            "username": username,
            "error": "Username contains characters unsafe for a URL path segment.",
            "results": [],
        }

    manifest = platforms if platforms is not None else PLATFORMS
    async with httpx.AsyncClient(http2=False) as client:
        tasks = [_check_one(client, p, username) for p in manifest]
        results = await asyncio.gather(*tasks)

    found = [r for r in results if r["status"] == "found"]
    not_found = [r for r in results if r["status"] == "not_found"]
    unknown = [r for r in results if r["status"] == "unknown"]

    return {
        "username": username,
        "checked_platforms": len(manifest),
        "found_count": len(found),
        "results": results,
        "summary": f"{len(found)} likely matches, {len(not_found)} not found, "
                   f"{len(unknown)} need manual verification out of {len(manifest)} platforms.",
    }


def check_username(username: str) -> dict:
    """Sync wrapper for use in non-async contexts (e.g. batch worker threads)."""
    return asyncio.run(check_username_async(username))
