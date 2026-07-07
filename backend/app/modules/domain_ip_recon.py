"""
Domain and IP reconnaissance using only public, read-only data sources:
  - RDAP (rdap.org bootstrap) for registration data
  - DNS resolution (A/AAAA/MX/NS/TXT/CNAME)
  - crt.sh Certificate Transparency logs for subdomain discovery
  - ip-api.com for coarse IP geolocation (no key required)
  - Shodan (optional, only if SHODAN_API_KEY is configured)
"""
from __future__ import annotations

import ipaddress
import re

import dns.resolver
import httpx

from .. import config

HEADERS = {"User-Agent": config.USER_AGENT}
DOMAIN_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})+$")


def is_ip(subject: str) -> bool:
    try:
        ipaddress.ip_address(subject)
        return True
    except ValueError:
        return False


async def _rdap(subject: str, kind: str) -> dict:
    url = f"https://rdap.org/{kind}/{subject}"
    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS, timeout=config.HTTP_TIMEOUT)
        if resp.status_code == 404:
            return {"found": False, "error": "No RDAP record found"}
        if resp.status_code != 200:
            return {"found": False, "error": f"RDAP HTTP {resp.status_code}"}
        data = resp.json()
        entities = []
        for ent in data.get("entities", []):
            roles = ent.get("roles", [])
            name = None
            vcard = ent.get("vcardArray")
            if vcard and len(vcard) > 1:
                for field in vcard[1]:
                    if field[0] == "fn":
                        name = field[3]
            entities.append({"roles": roles, "name": name, "handle": ent.get("handle")})
        return {
            "found": True,
            "handle": data.get("handle"),
            "ldh_name": data.get("ldhName") or data.get("name"),
            "status": data.get("status", []),
            "events": [{"action": e.get("eventAction"), "date": e.get("eventDate")} for e in data.get("events", [])],
            "nameservers": [ns.get("ldhName") for ns in data.get("nameservers", [])] if "nameservers" in data else [],
            "country": data.get("country"),
            "entities": entities,
            "raw_notice": [n.get("title") for n in data.get("notices", [])],
        }
    except Exception as e:  # noqa: BLE001
        return {"found": False, "error": str(e)}


def _dns_records(domain: str) -> dict:
    out = {}
    for rtype in ["A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA"]:
        try:
            answers = dns.resolver.resolve(domain, rtype, lifetime=config.HTTP_TIMEOUT)
            out[rtype] = [str(r).strip('"') for r in answers]
        except dns.resolver.NoAnswer:
            out[rtype] = []
        except dns.resolver.NXDOMAIN:
            out["error"] = "NXDOMAIN - domain does not resolve"
            break
        except Exception as e:  # noqa: BLE001
            out[rtype] = []
            out.setdefault("_errors", {})[rtype] = str(e)
    return out


async def _crtsh_subdomains(domain: str) -> dict:
    url = f"https://crt.sh/?q=%.{domain}&output=json"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=HEADERS, timeout=max(config.HTTP_TIMEOUT, 20))
        if resp.status_code != 200:
            return {"count": 0, "subdomains": [], "error": f"crt.sh HTTP {resp.status_code}"}
        certs = resp.json()
        subs = set()
        for cert in certs:
            for name in cert.get("name_value", "").split("\n"):
                name = name.strip().lower()
                if name and "*" not in name:
                    subs.add(name)
        sorted_subs = sorted(subs)
        return {"count": len(sorted_subs), "subdomains": sorted_subs[:500]}
    except Exception as e:  # noqa: BLE001
        return {"count": 0, "subdomains": [], "error": str(e)}


async def _geolocate_ip(ip: str) -> dict:
    url = f"http://ip-api.com/json/{ip}"
    params = {"fields": "status,message,country,regionName,city,zip,lat,lon,isp,org,as,reverse,query"}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=HEADERS, timeout=config.HTTP_TIMEOUT)
        data = resp.json()
        if data.get("status") != "success":
            return {"found": False, "error": data.get("message", "lookup failed")}
        return {"found": True, **{k: v for k, v in data.items() if k != "status"}}
    except Exception as e:  # noqa: BLE001
        return {"found": False, "error": str(e)}


async def _shodan_lookup(ip: str) -> dict:
    if not config.SHODAN_API_KEY:
        return {"checked": False, "reason": "SHODAN_API_KEY not configured - skipped"}
    url = f"https://api.shodan.io/shodan/host/{ip}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params={"key": config.SHODAN_API_KEY}, timeout=config.HTTP_TIMEOUT)
        if resp.status_code == 404:
            return {"checked": True, "found": False}
        if resp.status_code != 200:
            return {"checked": False, "reason": f"Shodan HTTP {resp.status_code}"}
        data = resp.json()
        return {
            "checked": True,
            "found": True,
            "org": data.get("org"),
            "os": data.get("os"),
            "ports": data.get("ports", []),
            "hostnames": data.get("hostnames", []),
            "vulns": list(data.get("vulns", [])) if data.get("vulns") else [],
            "tags": data.get("tags", []),
        }
    except Exception as e:  # noqa: BLE001
        return {"checked": False, "reason": f"Shodan lookup failed: {e}"}


async def recon_domain_async(domain: str) -> dict:
    domain = domain.strip().lower().rstrip(".")
    result = {"subject": domain, "type": "domain"}
    result["rdap"] = await _rdap(domain, "domain")
    result["dns"] = _dns_records(domain)
    result["certificate_transparency"] = await _crtsh_subdomains(domain)

    a_records = result["dns"].get("A", [])
    if a_records:
        result["primary_ip_geolocation"] = await _geolocate_ip(a_records[0])

    subs = result["certificate_transparency"].get("count", 0)
    result["summary"] = (
        f"RDAP {'found' if result['rdap'].get('found') else 'not found'}; "
        f"{len(a_records)} A record(s); {subs} subdomain(s) via CT logs."
    )
    return result


async def recon_ip_async(ip: str) -> dict:
    ip = ip.strip()
    result = {"subject": ip, "type": "ip"}
    result["rdap"] = await _rdap(ip, "ip")
    result["geolocation"] = await _geolocate_ip(ip)
    result["shodan"] = await _shodan_lookup(ip)

    geo = result["geolocation"]
    loc = f"{geo.get('city', '?')}, {geo.get('country', '?')}" if geo.get("found") else "geolocation unavailable"
    result["summary"] = f"RDAP {'found' if result['rdap'].get('found') else 'not found'}; located near {loc}."
    return result


async def recon_async(subject: str) -> dict:
    if is_ip(subject):
        return await recon_ip_async(subject)
    return await recon_domain_async(subject)
