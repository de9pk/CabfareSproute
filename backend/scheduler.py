"""
Scheduled fare collection — runs independently of the Streamlit dashboard.

Usage:
  python scheduler.py              # interval job using .env defaults
  python scheduler.py --once       # single fetch then exit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from apscheduler.schedulers.blocking import BlockingScheduler

from jobs.fetch_fares import fetch_and_log
from utils.config import (
    DEFAULT_DESTINATION,
    DEFAULT_PICKUP,
    HEADLESS,
    SCHEDULE_INTERVAL_MINUTES,
)
from utils.logging_config import setup_logging

logger = setup_logging("scheduler")

PLATFORMS = ["Uber", "Ola", "Rapido"]


def run_job(pickup: str, destination: str, platforms: list[str], headless: bool) -> None:
    logger.info("Scheduled fetch: %s → %s (%s)", pickup, destination, ", ".join(platforms))
    results = fetch_and_log(
        pickup, destination, platforms, mode="real", headless=headless
    )
    for r in results:
        logger.info(
            "  %s: %s %s",
            r.get("platform"),
            r.get("status"),
            r.get("fare") if r.get("status") == "success" else r.get("error_msg"),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Cab fare scheduled scraper")
    parser.add_argument("--once", action="store_true", help="Run a single fetch and exit")
    parser.add_argument("--pickup", default=DEFAULT_PICKUP)
    parser.add_argument("--destination", default=DEFAULT_DESTINATION)
    parser.add_argument(
        "--platforms",
        default="Uber,Ola,Rapido",
        help="Comma-separated platform names",
    )
    parser.add_argument("--interval", type=int, default=SCHEDULE_INTERVAL_MINUTES)
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show the browser (overrides HEADLESS=true)",
    )
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    headless = False if args.headed else HEADLESS

    if args.once:
        run_job(args.pickup, args.destination, platforms, headless)
        return

    scheduler = BlockingScheduler()
    scheduler.add_job(
        run_job,
        "interval",
        minutes=max(1, args.interval),
        args=[args.pickup, args.destination, platforms, headless],
        id="fare_fetch",
    )
    logger.info(
        "APScheduler started — every %s min for %s → %s",
        args.interval,
        args.pickup,
        args.destination,
    )
    logger.info("Press Ctrl+C to stop.")
    # Run immediately, then on the interval
    run_job(args.pickup, args.destination, platforms, headless)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
