# RAWS
RAWS is a osint tool
# OSINT Case Desk

A self-hosted, local-first OSINT investigation dashboard styled as a case file
workspace. Create a case, run checks from the tool nav on the left, and every
result is automatically logged to the case file on the right. Export the
whole case as a Markdown or PDF report when you're done.

**Scope, by design:** read-only lookups against public data sources only.
No people-search brokers, no identity-resolution services, no scraping of
private/authenticated data, no exploit or bypass tooling.

## What's included

| Tool | What it does | Data sources |
|---|---|---|
| Username Check | Checks ~40 major platforms for a public profile matching a username, with direct profile links | Public profile URLs (HTTP status/text check) |
| Email Intel | Syntax validation, MX record lookup, disposable-domain detection, optional HIBP breach check | DNS, bundled disposable-domain list, HIBP API v3 (optional key) |
| Domain / IP Recon | RDAP registration data, DNS records, Certificate Transparency subdomain discovery, IP geolocation, optional Shodan | RDAP (rdap.org), DNS, crt.sh, ip-api.com, Shodan (optional key) |
| Phone Intel | Fully offline analysis: validity, type, region, timezone, carrier hint | libphonenumber numbering-plan data (bundled, no network) |
| File Metadata | Hashes (MD5/SHA1/SHA256) plus EXIF (images) or document metadata (PDFs) | Local file only — nothing is uploaded anywhere |
| Dork Builder | Generates clickable search-engine links for names, usernames, emails, domains, and phone numbers | Link construction only — no scraping |
| Reverse Image | Generates reverse image search links (Google Lens, TinEye, Yandex, Bing) from an image URL | Link construction only |
| Batch Mode | Runs Username / Email / Domain-IP / Phone checks across up to 25 subjects at once | Same as above |
| Report Export | Exports the full case (findings + notes) as Markdown or PDF | Local rendering (weasyprint) |

## Quick start (Docker)

```bash
git clone <this folder as a repo, or just copy it as-is>
cd osint-dashboard
cp .env.example .env      # optional: add HIBP_API_KEY / SHODAN_API_KEY
docker compose up --build
```

Open **http://localhost:8420**.

Data persists in a Docker volume (`osint_data`) mounted at `/data`, so cases
survive container restarts. To fully reset, run `docker compose down -v`.

## Running without Docker (Python venv)

```bash
chmod +x run_venv.sh
./run_venv.sh
```

This creates a venv in `backend/venv`, installs dependencies, and starts the
server at **http://localhost:8420**. For manual steps, platform-specific
notes (including PDF export system libraries), troubleshooting, and how to
use a `.env` file in this mode, see **[RUNNING_WITHOUT_DOCKER.md](RUNNING_WITHOUT_DOCKER.md)**.

## Configuration

All configuration is via environment variables (see `.env.example`):

- `HIBP_API_KEY` — optional. Have I Been Pwned's authenticated API now
  requires a paid subscription key for the breach-lookup endpoint. Leave
  blank and the Email Intel tool simply reports the lookup as skipped.
- `SHODAN_API_KEY` — optional. Enables host enrichment for IP recon.
- `OSINT_DB_PATH` — where the SQLite case database lives (defaults to
  `/data/cases.db` inside the container).

Nothing else requires configuration. Every lookup that doesn't need a key
(RDAP, DNS, crt.sh, ip-api.com geolocation, the platform username checks)
works out of the box, using only public, unauthenticated endpoints.

## Notes on accuracy and etiquette

- **Username Check** classifies each platform as `found`, `not_found`, or
  `unknown`. Several major sites (LinkedIn, X, Instagram, TikTok, etc.)
  actively block automated requests; those show as `unknown` with a direct
  link so you can verify by hand. Treat `found` as "a public profile page
  exists at this URL," not confirmed identity.
- **Email Intel**'s disposable-domain list is a bundled static file — it
  will not catch brand-new throwaway domains. HIBP's breach API is
  authenticated-only as of v3 and costs money to subscribe to; this app
  never fabricates a key and simply skips the check if none is configured.
- **Domain/IP Recon** relies on public RDAP bootstrapping (`rdap.org`),
  live DNS resolution, `crt.sh` Certificate Transparency logs, and
  `ip-api.com` for coarse geolocation (city/ISP-level, not precise
  location). Shodan enrichment is optional and requires your own key.
- **Phone Intel** is 100% offline — it uses Google's libphonenumber
  numbering-plan metadata bundled with the `phonenumbers` package. It
  cannot tell you who owns a number, only what the number *is* (type,
  region, plausible carrier family, timezone).
- **File Metadata** never uploads your file anywhere — everything happens
  in the container's temp storage and is discarded after processing.
- All batch jobs are capped at 25 subjects per run to keep things
  responsive and to avoid hammering the public services this app depends
  on. Please use reasonable request pacing and respect the terms of
  service of any site you check.

## Project layout

```
osint-dashboard/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py            # FastAPI routes
│       ├── database.py        # SQLite case/finding storage
│       ├── config.py
│       ├── report_export.py   # Markdown + PDF report generation
│       ├── data/
│       │   ├── platforms.json          # username-check platform manifest
│       │   └── disposable_domains.txt  # disposable email domain list
│       └── modules/
│           ├── username_check.py
│           ├── email_check.py
│           ├── domain_ip_recon.py
│           ├── file_metadata.py
│           ├── phone_intel.py
│           └── dork_builder.py
└── frontend/
    ├── index.html
    ├── styles.css
    └── app.js
```

## Extending it

- Add more platforms to `backend/app/data/platforms.json` — each entry is
  just a URL template and a detection strategy (`status` or
  `status_or_text`).
- Swap `ip-api.com` for a local MaxMind GeoLite2 database if you'd rather
  not make an outbound call per IP lookup.
- The SQLite schema (`backend/app/database.py`) is intentionally simple;
  point `OSINT_DB_PATH` at any writable path if you want to manage backups
  yourself.
