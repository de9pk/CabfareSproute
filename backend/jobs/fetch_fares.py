"""
Shared fare-fetch pipeline used by the Streamlit dashboard and the scheduler.

Scrapes one platform at a time (more reliable than 3 Chrome instances at once)
and retries transient failures.
"""

from __future__ import annotations

import logging
import random
import time

from scrapers.ola_scraper import OlaScraper
from scrapers.rapido_scraper import RapidoScraper
from scrapers.uber_scraper import UberScraper
from utils.config import HEADLESS, SCRAPE_RETRIES, SCRAPE_RETRY_BACKOFF_SEC
from utils.retry import with_retries
from utils.storage import log_fares, utc_now_iso

logger = logging.getLogger(__name__)

SCRAPERS = {
    "Uber": UberScraper,
    "Ola": OlaScraper,
    "Rapido": RapidoScraper,
}


def _error_result(platform: str, msg: str, duration_ms: int = 0) -> dict:
    return {
        "platform": platform,
        "fare": "N/A",
        "fare_min": 0,
        "fare_max": 0,
        "eta": "N/A",
        "ride_type": "N/A",
        "status": "error",
        "error_msg": msg,
        "scraped_at": utc_now_iso(),
        "duration_ms": duration_ms,
    }


def _is_retryable(result: dict) -> bool:
    if result.get("status") != "error":
        return False
    msg = (result.get("error_msg") or "").lower()
    if "login failed" in msg or "login_required" in msg:
        return False
    return True


def scrape_platform(
    platform: str,
    pickup: str,
    destination: str,
    *,
    headless: bool | None = None,
) -> dict:
    scraper_class = SCRAPERS[platform]
    use_headless = HEADLESS if headless is None else headless
    started = time.perf_counter()

    def _once() -> dict:
        scraper = scraper_class(headless=use_headless)
        try:
            scraper.start_driver()
            logged_in = scraper.login()
            if not logged_in:
                return scraper._build_error_result(
                    "Login failed — check credentials or save cookies first"
                )
            return scraper.get_fare(pickup, destination)
        finally:
            scraper.quit_driver()

    try:
        result = with_retries(
            _once,
            attempts=SCRAPE_RETRIES,
            backoff_sec=SCRAPE_RETRY_BACKOFF_SEC,
            retry_if=_is_retryable,
            label=f"{platform} scrape",
        )
    except Exception as exc:
        logger.exception("%s scrape crashed", platform)
        return _error_result(platform, str(exc), int((time.perf_counter() - started) * 1000))

    result = dict(result or {})
    result.setdefault("platform", platform)
    result.setdefault("scraped_at", utc_now_iso())
    result["duration_ms"] = int((time.perf_counter() - started) * 1000)
    if result.get("status") != "success":
        logger.error("%s scrape failed: %s", platform, result.get("error_msg"))
    else:
        logger.info(
            "%s scrape ok: %s %s in %sms",
            platform,
            result.get("fare"),
            result.get("ride_type"),
            result["duration_ms"],
        )
    return result


def fetch_demo_fares(pickup: str, destination: str, selected: list[str]) -> list[dict]:
    time.sleep(0.4)
    base_fare = 150 + len(pickup) * 2 + len(destination) * 3
    results = []
    for p in selected:
        if p == "Uber":
            fare = base_fare + random.randint(-15, 5)
            ride_type, eta = "Uber Go", "4 min"
        elif p == "Ola":
            fare = base_fare + random.randint(5, 25)
            ride_type, eta = "Mini", "6 min"
        else:
            fare = max(40, base_fare - random.randint(40, 70))
            ride_type, eta = "Bike", "2 min"
        results.append({
            "platform": p,
            "fare": f"₹{fare}",
            "fare_min": fare,
            "fare_max": fare + 20,
            "eta": eta,
            "ride_type": ride_type,
            "status": "success",
            "error_msg": "",
            "scraped_at": utc_now_iso(),
            "duration_ms": 0,
        })
    return results


def fetch_real_fares(
    pickup: str,
    destination: str,
    selected: list[str],
    *,
    headless: bool | None = None,
) -> list[dict]:
    results = []
    for platform in selected:
        logger.info("Fetching %s: %s → %s", platform, pickup, destination)
        results.append(scrape_platform(platform, pickup, destination, headless=headless))
    return results


def fetch_and_log(
    pickup: str,
    destination: str,
    selected: list[str],
    *,
    mode: str = "real",
    headless: bool | None = None,
) -> list[dict]:
    if mode == "demo":
        results = fetch_demo_fares(pickup, destination, selected)
    else:
        results = fetch_real_fares(pickup, destination, selected, headless=headless)
    log_fares(pickup, destination, results, mode=mode)
    return results
