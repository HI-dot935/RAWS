<img width="1366" height="768" alt="Screenshot 2026-07-09 at 10 14 26 AM" src="https://github.com/user-attachments/assets/7d0a5193-8f5c-4254-bf99-156e6ee11c54" />
# RAWS — Read-only OSINT Workstation

A self-hosted, local-first OSINT investigation dashboard styled as a case
file workspace. Create a case, run checks from the tool nav on the left,
and every result is automatically logged to the case file on the right.
Export the whole case as a Markdown or PDF report when you're done.

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

## Requirements

- Python 3.9 or newer (works fine on 3.9 through 3.13)
- No Node.js, no build step — the frontend is static HTML/CSS/JS

## Quick start — clone, venv, run

This is the fastest path: clone (or copy) the folder, then use the
included launcher, which creates the virtual environment, installs
requirements, and starts the local server for you.

**macOS / Linux:**

```bash
git clone <this repo, or just copy the RAWS folder> RAWS
cd RAWS
chmod +x run.sh
./run.sh
```

**Windows:**

```bat
git clone <this repo, or just copy the RAWS folder> RAWS
cd RAWS
run.bat
```

Then open **http://127.0.0.1:8420** in your browser. That's the local
host address the app binds to — nothing leaves your machine except the
individual lookups each tool performs against the public services listed
above.

Stop the server anytime with `Ctrl+C`. Run the same script again later —
it reuses the existing virtual environment and only re-installs anything
that changed.

### Doing it by hand instead

If you'd rather run the steps yourself instead of using `run.sh`/`run.bat`:

```bash
cd RAWS/backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
OSINT_DB_PATH=./data/cases.db uvicorn app.main:app --host 127.0.0.1 --port 8420
```

The frontend is plain static HTML/CSS/JS served by FastAPI directly — no
build step, no Node, no bundler required.

### Optional: Docker instead of venv

```bash
cd RAWS
cp .env.example .env      # optional: add HIBP_API_KEY / SHODAN_API_KEY
docker compose up --build
```

Open **http://localhost:8420**. Data persists in a Docker volume
(`raws_data`) mounted at `/data`. To fully reset: `docker compose down -v`.

### A note on PDF export without Docker

If you're running the venv path (not Docker) and want PDF export, WeasyPrint
needs a few system libraries: `libpango-1.0-0`, `libpangocairo-1.0-0`,
`libcairo2`, `libgdk-pixbuf2.0-0` (Debian/Ubuntu package names — macOS via
Homebrew: `brew install pango`). Markdown export always works with no
extra dependencies, so you're never blocked on reporting.

## Configuration

All configuration is via environment variables (see `.env.example`):

- `HIBP_API_KEY` — optional. Have I Been Pwned's authenticated API now
  requires a paid subscription key for the breach-lookup endpoint. Leave
  blank and the Email Intel tool simply reports the lookup as skipped.
- `SHODAN_API_KEY` — optional. Enables host enrichment for IP recon.
- `OSINT_DB_PATH` — where the SQLite case database lives (defaults to
  `./data/cases.db` when run via `run.sh`/`run.bat`, `/data/cases.db`
  inside the Docker container).
- `PORT` — optional, only used by `run.sh`/`run.bat`, defaults to `8420`.

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
  locally on disk and the temp copy is discarded after processing.
- All batch jobs are capped at 25 subjects per run to keep things
  responsive and to avoid hammering the public services this app depends
  on. Please use reasonable request pacing and respect the terms of
  service of any site you check.

## Project layout

```
RAWS/
├── run.sh                      # one-command launcher (macOS/Linux)
├── run.bat                     # one-command launcher (Windows)
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

##Here's what RAWS can do, tool by tool:
Case Management

Create/open/close investigation cases
Every check you run auto-logs into the active case (right-side panel)
Add manual notes to a case
Mark case status (open/closed)

<img width="1366" height="768" alt="Screenshot 2026-07-09 at 10 14 39 AM" src="https://github.com/user-attachments/assets/bd21f6ee-ecce-4716-875d-ddf33541dd03" />

Username Check

Checks a username against ~40 major platforms (social media, forums, dev sites, etc.)
Returns found / not_found / unknown for each
Gives you a direct clickable profile link for each platform
<img width="1366" height="768" alt="Screenshot 2026-07-09 at 10 16 18 AM" src="https://github.com/user-attachments/assets/9df519c8-3651-4095-9277-a79e97b32d16" />
<img width="1366" height="768" alt="Screenshot 2026-07-09 at 10 16 27 AM" src="https://github.com/user-attachments/assets/5ced04d3-d552-4477-a003-670302b2a575" />

Email Intel

Validates email syntax
Looks up MX records (is the domain actually set up to receive mail)
Checks against a disposable/throwaway email domain list
Optional: Have I Been Pwned breach lookup (only if you add your own HIBP API key)

Domain / IP Recon

RDAP lookup (who registered the domain/IP, when)
DNS records (A, AAAA, MX, NS, TXT, CNAME)
Certificate Transparency search (finds subdomains via crt.sh)
IP geolocation (city/ISP level, not precise address)
Optional: Shodan enrichment (open ports, banners) if you add your own Shodan API key

Phone Intel

Fully offline, no internet needed
Tells you: valid or not, number type (mobile/landline/voip), country/region, timezone, likely carrier family
Cannot tell you who owns the number

File Metadata

Computes MD5/SHA1/SHA256 hashes of any uploaded file
For images: extracts EXIF data (camera info, GPS coordinates if present, timestamps)
For PDFs: extracts document metadata (author, creation date, software used, etc.)
Nothing is uploaded anywhere — all local

Dork Builder

Generates ready-to-click Google/Bing/DuckDuckGo search links for a name, username, email, domain, or phone number
Doesn't run the search itself, just builds the links

Reverse Image Search

Generates clickable reverse-image-search links (Google Lens, TinEye, Yandex, Bing) from an image URL

Batch Mode

Run Username / Email / Domain-IP / Phone checks on up to 25 subjects at once in one go

Report Export

Export the whole case (all findings + your notes) as a Markdown file
Export the whole case as a PDF

## Extending it

- Add more platforms to `backend/app/data/platforms.json` — each entry is
  just a URL template and a detection strategy (`status` or
  `status_or_text`).
- Swap `ip-api.com` for a local MaxMind GeoLite2 database if you'd rather
  not make an outbound call per IP lookup.
- The SQLite schema (`backend/app/database.py`) is intentionally simple;
  point `OSINT_DB_PATH` at any writable path if you want to manage backups
  yourself.
