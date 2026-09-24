"""
Load environment settings used by the dashboard, scrapers, and scheduler.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
COOKIES_DIR = ROOT_DIR / "cookies"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)
COOKIES_DIR.mkdir(exist_ok=True)


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


HEADLESS = _bool("HEADLESS", "false")
REFRESH_INTERVAL_MINUTES = _int("REFRESH_INTERVAL_MINUTES", 5)
SCRAPE_RETRIES = _int("SCRAPE_RETRIES", 3)
SCRAPE_RETRY_BACKOFF_SEC = _int("SCRAPE_RETRY_BACKOFF_SEC", 2)
DEDUP_WINDOW_MINUTES = _int("DEDUP_WINDOW_MINUTES", 2)
SCHEDULE_INTERVAL_MINUTES = _int("SCHEDULE_INTERVAL_MINUTES", 15)

# Default scheduled route (Jaipur presets)
DEFAULT_PICKUP = os.getenv("DEFAULT_PICKUP", "Hawa Mahal, Jaipur, Rajasthan")
DEFAULT_DESTINATION = os.getenv(
    "DEFAULT_DESTINATION", "Jaipur International Airport, Sanganer"
)

DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "fares.db")))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
