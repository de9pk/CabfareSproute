"""
SQLite storage for fare quotes.

SQLite is the default so the project runs locally without a MySQL server.
Set DB_PATH in .env if you want a different file location.
The schema is close to the MySQL plan so it can be migrated later.
"""

from __future__ import annotations

import csv
import hashlib
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from utils.config import DATA_DIR, DB_PATH, DEDUP_WINDOW_MINUTES

logger = logging.getLogger(__name__)

HISTORY_CSV = DATA_DIR / "fare_history.csv"

SCHEMA = """
CREATE TABLE IF NOT EXISTS routes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    pickup_text TEXT NOT NULL,
    dest_text   TEXT NOT NULL,
    route_hash  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    route_id    INTEGER NOT NULL,
    started_at  TEXT NOT NULL,
    finished_at TEXT,
    mode        TEXT NOT NULL DEFAULT 'real',
    status      TEXT NOT NULL,
    FOREIGN KEY (route_id) REFERENCES routes(id)
);

CREATE TABLE IF NOT EXISTS fare_quotes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scrape_run_id INTEGER NOT NULL,
    platform      TEXT NOT NULL,
    ride_type     TEXT,
    fare_min      INTEGER,
    fare_max      INTEGER,
    fare_display  TEXT,
    eta           TEXT,
    status        TEXT NOT NULL,
    error_msg     TEXT,
    scraped_at    TEXT NOT NULL,
    duration_ms   INTEGER,
    parser        TEXT,
    FOREIGN KEY (scrape_run_id) REFERENCES scrape_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_quotes_run ON fare_quotes(scrape_run_id, platform);
CREATE INDEX IF NOT EXISTS idx_quotes_platform_time ON fare_quotes(platform, scraped_at);
CREATE INDEX IF NOT EXISTS idx_quotes_status ON fare_quotes(status, scraped_at);
CREATE INDEX IF NOT EXISTS idx_runs_started ON scrape_runs(started_at);
"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """UTC timestamp stored as naive string so SQLite datetime() works."""
    return utc_now().strftime("%Y-%m-%d %H:%M:%S")


def route_hash(pickup: str, destination: str) -> str:
    key = f"{pickup.strip().lower()}|{destination.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_DB_READY = False
_MIGRATING = False


def init_db() -> None:
    global _DB_READY
    with _connect() as conn:
        conn.executescript(SCHEMA)
    if not _DB_READY and not _MIGRATING:
        _maybe_migrate_csv()
    _DB_READY = True


def _maybe_migrate_csv() -> None:
    """One-time import of legacy fare_history.csv if the DB is empty."""
    global _MIGRATING
    if not HISTORY_CSV.exists():
        return
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM fare_quotes").fetchone()[0]
        if n > 0:
            return
    logger.info("Migrating existing CSV history into SQLite...")
    try:
        df = pd.read_csv(HISTORY_CSV)
    except Exception as exc:
        logger.error("CSV migrate skipped: %s", exc)
        return

    grouped: dict[tuple, list] = {}
    for _, row in df.iterrows():
        ts = str(row.get("timestamp", utc_now_iso()))
        pickup = str(row.get("pickup", ""))
        dest = str(row.get("destination", ""))
        grouped.setdefault((ts, pickup, dest), []).append(row)

    _MIGRATING = True
    try:
        for (ts, pickup, dest), rows in grouped.items():
            results = []
            for row in rows:
                try:
                    fare_min = int(float(row.get("fare_min") or 0))
                    fare_max = int(float(row.get("fare_max") or 0))
                except (TypeError, ValueError):
                    fare_min, fare_max = 0, 0
                results.append({
                    "platform": row.get("platform", ""),
                    "ride_type": row.get("ride_type", ""),
                    "fare": row.get("fare", ""),
                    "fare_min": fare_min,
                    "fare_max": fare_max,
                    "eta": row.get("eta", ""),
                    "status": row.get("status", "error"),
                    "error_msg": "",
                })
            log_fares(
                pickup, dest, results,
                mode="imported", scraped_at=ts, dedupe=False, skip_csv=True,
            )
        logger.info("CSV migration complete.")
    finally:
        _MIGRATING = False


def _get_or_create_route(conn: sqlite3.Connection, pickup: str, dest: str) -> int:
    h = route_hash(pickup, dest)
    row = conn.execute("SELECT id FROM routes WHERE route_hash = ?", (h,)).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute(
        "INSERT INTO routes (pickup_text, dest_text, route_hash) VALUES (?, ?, ?)",
        (pickup, dest, h),
    )
    return int(cur.lastrowid)


def _recent_duplicate(
    conn: sqlite3.Connection,
    route_id: int,
    platform: str,
    fare_min: int,
    status: str,
    window_minutes: int,
) -> bool:
    if window_minutes <= 0 or status != "success":
        return False
    row = conn.execute(
        """
        SELECT fq.id
        FROM fare_quotes fq
        JOIN scrape_runs sr ON sr.id = fq.scrape_run_id
        WHERE sr.route_id = ?
          AND fq.platform = ?
          AND fq.status = 'success'
          AND fq.fare_min = ?
          AND datetime(fq.scraped_at) >= datetime('now', ?)
        LIMIT 1
        """,
        (route_id, platform, fare_min, f"-{window_minutes} minutes"),
    ).fetchone()
    return row is not None


def log_fares(
    pickup: str,
    destination: str,
    results: list[dict],
    *,
    mode: str = "real",
    scraped_at: str | None = None,
    dedupe: bool = True,
    skip_csv: bool = False,
) -> str:
    """
    Persist a scrape batch. Returns scrape_run_id as string.
    Duplicate successful quotes within DEDUP_WINDOW_MINUTES are skipped.
    """
    init_db()
    started = scraped_at or utc_now_iso()
    run_key = str(uuid.uuid4())[:8]

    successes = [r for r in results if r.get("status") == "success" and (r.get("fare_min") or 0) > 0]
    if not results:
        run_status = "failed"
    elif len(successes) == len(results):
        run_status = "success"
    elif successes:
        run_status = "partial"
    else:
        run_status = "failed"

    with _connect() as conn:
        route_id = _get_or_create_route(conn, pickup, destination)
        cur = conn.execute(
            """
            INSERT INTO scrape_runs (route_id, started_at, finished_at, mode, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (route_id, started, utc_now_iso(), mode, run_status),
        )
        run_id = int(cur.lastrowid)

        written = 0
        for r in results:
            platform = r.get("platform", "")
            fare_min = int(r.get("fare_min") or 0)
            status = r.get("status") or "error"
            if dedupe and _recent_duplicate(
                conn, route_id, platform, fare_min, status, DEDUP_WINDOW_MINUTES
            ):
                logger.info("Skipping duplicate %s quote for this route", platform)
                continue
            parser = "fallback" if "(fallback" in str(r.get("error_msg") or "") else "primary"
            conn.execute(
                """
                INSERT INTO fare_quotes (
                    scrape_run_id, platform, ride_type, fare_min, fare_max,
                    fare_display, eta, status, error_msg, scraped_at, duration_ms, parser
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    platform,
                    r.get("ride_type") or "",
                    fare_min,
                    int(r.get("fare_max") or 0),
                    r.get("fare") or "",
                    r.get("eta") or "",
                    status,
                    r.get("error_msg") or "",
                    r.get("scraped_at") or started,
                    r.get("duration_ms"),
                    parser,
                ),
            )
            written += 1

        if not skip_csv:
            _append_csv(pickup, destination, results, started, mode)

    logger.info(
        "Logged scrape run %s (%s): %s quote(s) written, batch=%s",
        run_id,
        run_status,
        written,
        run_key,
    )
    return str(run_id)


def _append_csv(pickup: str, destination: str, results: list[dict], timestamp: str, mode: str) -> None:
    columns = [
        "timestamp", "pickup", "destination", "platform", "ride_type",
        "fare", "fare_min", "fare_max", "eta", "status", "error_msg", "mode",
    ]
    file_exists = HISTORY_CSV.exists()
    try:
        with open(HISTORY_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            if not file_exists:
                writer.writeheader()
            for r in results:
                writer.writerow({
                    "timestamp": timestamp,
                    "pickup": pickup,
                    "destination": destination,
                    "platform": r.get("platform", ""),
                    "ride_type": r.get("ride_type", ""),
                    "fare": r.get("fare", ""),
                    "fare_min": r.get("fare_min", 0),
                    "fare_max": r.get("fare_max", 0),
                    "eta": r.get("eta", ""),
                    "status": r.get("status", ""),
                    "error_msg": r.get("error_msg", ""),
                    "mode": mode,
                })
    except Exception as exc:
        logger.warning("CSV append failed (SQLite is source of truth): %s", exc)


def load_history() -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                fq.scraped_at AS timestamp,
                r.pickup_text AS pickup,
                r.dest_text AS destination,
                fq.platform,
                fq.ride_type,
                fq.fare_display AS fare,
                fq.fare_min,
                fq.fare_max,
                fq.eta,
                fq.status,
                fq.error_msg,
                sr.mode,
                fq.duration_ms,
                fq.parser,
                sr.id AS scrape_run_id
            FROM fare_quotes fq
            JOIN scrape_runs sr ON sr.id = fq.scrape_run_id
            JOIN routes r ON r.id = sr.route_id
            ORDER BY fq.scraped_at DESC
            """,
            conn,
        )
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    return df


def clear_history() -> None:
    init_db()
    with _connect() as conn:
        conn.execute("DELETE FROM fare_quotes")
        conn.execute("DELETE FROM scrape_runs")
        conn.execute("DELETE FROM routes")
    if HISTORY_CSV.exists():
        HISTORY_CSV.unlink()
    logger.info("Fare history cleared")


def history_exists() -> bool:
    if not DB_PATH.exists():
        return HISTORY_CSV.exists() and HISTORY_CSV.stat().st_size > 0
    init_db()
    with _connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM fare_quotes").fetchone()[0]
    return n > 0
