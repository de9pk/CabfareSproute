"""
data_logger.py
──────────────
Backwards-compatible fare history API. SQLite is the source of truth;
CSV is still written as an export.
"""

from utils.storage import (  # noqa: F401
    clear_history,
    history_exists,
    load_history,
    log_fares,
)
