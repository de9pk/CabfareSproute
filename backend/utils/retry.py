"""Retry helpers for transient scraper failures."""

import time
import logging
from typing import Callable, TypeVar

T = TypeVar("T")
logger = logging.getLogger(__name__)


def with_retries(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    backoff_sec: float = 2.0,
    retry_if: Callable[[T], bool] | None = None,
    label: str = "operation",
) -> T:
    """
    Run fn up to `attempts` times.

    If retry_if is set, a returned value is retried when retry_if(result) is True.
    Exceptions always retry until attempts are exhausted.
    """
    last_exc: Exception | None = None
    last_result: T | None = None

    for i in range(1, attempts + 1):
        try:
            result = fn()
            last_result = result
            if retry_if is not None and retry_if(result):
                logger.warning(
                    "%s attempt %s/%s returned a retryable result: %s",
                    label,
                    i,
                    attempts,
                    result.get("error_msg") if isinstance(result, dict) else result,
                )
                if i < attempts:
                    time.sleep(backoff_sec * i)
                    continue
            return result
        except Exception as exc:
            last_exc = exc
            logger.warning("%s attempt %s/%s failed: %s", label, i, attempts, exc)
            if i < attempts:
                time.sleep(backoff_sec * i)

    if last_exc is not None and last_result is None:
        raise last_exc
    return last_result  # type: ignore[return-value]
