import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("OSINT_DB_PATH", str(BASE_DIR / "data" / "cases.db"))

# Optional API keys. If unset, the relevant enrichment is silently skipped
# and the UI reports it as "not configured" rather than erroring.
HIBP_API_KEY = os.environ.get("HIBP_API_KEY", "").strip()
SHODAN_API_KEY = os.environ.get("SHODAN_API_KEY", "").strip()

# Network behaviour
HTTP_TIMEOUT = float(os.environ.get("OSINT_HTTP_TIMEOUT", "8"))
USER_AGENT = "raws/1.0 (self-hosted, read-only, public-sources)"

BATCH_MAX_SUBJECTS = 25
UPLOAD_MAX_BYTES = 25 * 1024 * 1024  # 25 MB
