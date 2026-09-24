"""
Console + rotating file logs so scrape failures are visible after the run.
"""

import logging
from logging.handlers import RotatingFileHandler

from utils.config import LOGS_DIR, LOG_LEVEL

_CONFIGURED = False


def setup_logging(name: str = "cab_fare") -> logging.Logger:
    global _CONFIGURED
    logger = logging.getLogger(name)
    if _CONFIGURED:
        return logger

    level = getattr(logging, LOG_LEVEL, logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(fmt)

    log_file = LOGS_DIR / "app.log"
    file_handler = RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(console)
        root.addHandler(file_handler)

    _CONFIGURED = True
    logger.setLevel(level)
    return logger
