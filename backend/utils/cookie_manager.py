"""
cookie_manager.py
─────────────────
Utility functions for managing saved browser session cookies.
Used by the Streamlit dashboard's "Login Manager" tab.
"""

import pickle
from pathlib import Path
import logging

logger = logging.getLogger(__name__)
COOKIES_DIR = Path(__file__).parent.parent / "cookies"
COOKIES_DIR.mkdir(exist_ok=True)

PLATFORMS = ["uber", "ola", "rapido"]


def cookie_status() -> dict:
    """
    Returns dict of {platform: bool} showing which platforms have saved cookies.
    Example: {"uber": True, "ola": False, "rapido": True}
    """
    return {
        platform: (COOKIES_DIR / f"{platform}_cookies.pkl").exists()
        for platform in PLATFORMS
    }


def delete_cookies(platform: str) -> bool:
    """Delete saved cookies for a platform. Returns True if deleted."""
    path = COOKIES_DIR / f"{platform.lower()}_cookies.pkl"
    if path.exists():
        path.unlink()
        logger.info(f"Deleted cookies for {platform}")
        return True
    return False


def delete_all_cookies():
    """Delete all saved cookies."""
    for platform in PLATFORMS:
        delete_cookies(platform)
    logger.info("All cookies deleted")


def get_cookie_info(platform: str) -> dict:
    """Return metadata about saved cookies (count, size)."""
    path = COOKIES_DIR / f"{platform.lower()}_cookies.pkl"
    if not path.exists():
        return {"exists": False, "count": 0, "size_kb": 0}

    try:
        with open(path, "rb") as f:
            cookies = pickle.load(f)
        size_kb = path.stat().st_size / 1024
        return {
            "exists": True,
            "count": len(cookies),
            "size_kb": round(size_kb, 2),
        }
    except Exception as e:
        logger.error(f"Error reading cookies for {platform}: {e}")
        return {"exists": True, "count": 0, "size_kb": 0}
