"""
analytics/indicators.py — Pure-Python technical indicators.

All functions accept plain Python lists of floats and return lists/tuples so
the module has **no** mandatory dependency on NumPy (though NumPy is used when
available for speed).
"""
from __future__ import annotations

import math
from typing import Optional


# ── Simple Moving Average ──────────────────────────────────────────────────────

def sma(prices: list[float], window: int) -> list[Optional[float]]:
    """Return SMA values aligned with *prices*.  First ``window-1`` entries are None."""
    if window <= 0:
        raise ValueError("window must be > 0")
    result: list[Optional[float]] = [None] * (window - 1)
    for i in range(window - 1, len(prices)):
        result.append(sum(prices[i - window + 1 : i + 1]) / window)
    return result


# ── Exponential Moving Average ─────────────────────────────────────────────────

def ema(prices: list[float], window: int) -> list[Optional[float]]:
    """Return EMA values aligned with *prices*.  First ``window-1`` entries are None."""
    if window <= 0:
        raise ValueError("window must be > 0")
    k = 2.0 / (window + 1)
    result: list[Optional[float]] = [None] * (window - 1)
    if len(prices) < window:
        return [None] * len(prices)
    # seed with first SMA
    seed = sum(prices[:window]) / window
    result.append(seed)
    prev = seed
    for price in prices[window:]:
        val = price * k + prev * (1 - k)
        result.append(val)
        prev = val
    return result


# ── Relative Strength Index ────────────────────────────────────────────────────

def rsi(prices: list[float], period: int = 14) -> list[Optional[float]]:
    """Return RSI (0-100) aligned with *prices*.  First ``period`` entries are None."""
    if len(prices) < period + 1:
        return [None] * len(prices)

    result: list[Optional[float]] = [None] * period
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, period + 1):
        change = prices[i] - prices[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    def _rsi_val(avg_g: float, avg_l: float) -> float:
        if avg_l == 0:
            return 100.0
        rs = avg_g / avg_l
        return 100.0 - (100.0 / (1.0 + rs))

    result.append(_rsi_val(avg_gain, avg_loss))

    for i in range(period + 1, len(prices)):
        change = prices[i] - prices[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        result.append(_rsi_val(avg_gain, avg_loss))

    return result


# ── Bollinger Bands ────────────────────────────────────────────────────────────

def bollinger_bands(
    prices: list[float],
    window: int = 20,
    num_std: float = 2.0,
) -> tuple[list[Optional[float]], list[Optional[float]], list[Optional[float]]]:
    """
    Return ``(upper, middle, lower)`` Bollinger Band series aligned with *prices*.
    First ``window-1`` entries are None in all three series.
    """
    middle = sma(prices, window)
    upper: list[Optional[float]] = []
    lower: list[Optional[float]] = []
    for i, mid in enumerate(middle):
        if mid is None:
            upper.append(None)
            lower.append(None)
        else:
            window_prices = prices[i - window + 1 : i + 1]
            std = math.sqrt(sum((p - mid) ** 2 for p in window_prices) / window)
            upper.append(mid + num_std * std)
            lower.append(mid - num_std * std)
    return upper, middle, lower


# ── Volume-Weighted Average Price ──────────────────────────────────────────────

def vwap(prices: list[float], volumes: list[float]) -> float:
    """Compute VWAP over the full series."""
    if len(prices) != len(volumes):
        raise ValueError("prices and volumes must have the same length")
    total_vol = sum(volumes)
    if total_vol == 0:
        return sum(prices) / len(prices) if prices else 0.0
    return sum(p * v for p, v in zip(prices, volumes)) / total_vol
