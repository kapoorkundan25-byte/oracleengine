"""
polymarket/utils.py — General helper utilities.
"""
from __future__ import annotations

import time
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_outcome_prices(raw: Any) -> tuple[float, float]:
    """
    Parse the outcomePrices field returned by the Gamma API.

    It may be a JSON-encoded list like '["0.73","0.27"]' or a plain list.
    Returns ``(yes_price, no_price)``.
    """
    import json

    if raw is None:
        return 0.5, 0.5
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return 0.5, 0.5
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return safe_float(raw[0], 0.5), safe_float(raw[1], 0.5)
    return 0.5, 0.5


def extract_token_ids(raw: Any) -> list[str]:
    """
    Extract token ids from the ``clobTokenIds`` field (may be a JSON string).
    """
    import json

    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return []
    if isinstance(raw, (list, tuple)):
        return [str(t) for t in raw]
    return []


class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, calls_per_second: float = 5.0) -> None:
        self._interval = 1.0 / calls_per_second
        self._last_call = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        wait = self._interval - (now - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()
