"""
modules/trend_analyzer.py — Market Trend Analyzer.

Computes technical indicators for Polymarket price series using
:mod:`pandas` and :mod:`numpy`.

Exported functions
------------------
* :func:`calculate_price_momentum`
* :func:`calculate_volume_trend`
* :func:`detect_price_breakout`
* :func:`calculate_volatility`
* :func:`calculate_rsi`
* :func:`calculate_moving_averages`
* :func:`get_market_summary`
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from utils.logger import get_logger

logger = get_logger(__name__)

# Trend signal labels
BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"


def _to_series(prices: list[float] | pd.Series) -> pd.Series:
    """Ensure *prices* is a :class:`pandas.Series` of floats."""
    if isinstance(prices, pd.Series):
        return prices.reset_index(drop=True).astype(float)
    return pd.Series(prices, dtype=float)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------
def calculate_price_momentum(
    prices: list[float] | pd.Series,
    window: int = 5,
) -> pd.Series:
    """Calculate rolling rate-of-change (momentum) indicator.

    Momentum at position *i* = ``(prices[i] - prices[i - window]) / prices[i - window]``.

    Args:
        prices: Sequence of price values (oldest first).
        window: Look-back window in periods.

    Returns:
        :class:`pandas.Series` of momentum values (same length as *prices*).
        Leading values are ``NaN`` until the window is filled.
    """
    s = _to_series(prices)
    momentum = s.pct_change(periods=window)
    logger.debug("Momentum (window=%d): last=%.4f", window, momentum.iloc[-1] if len(momentum) else float("nan"))
    return momentum


def calculate_volume_trend(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyse volume over time from a list of trade dictionaries.

    Args:
        trades: List of trade dicts, each containing at least ``"size"``
                and optionally ``"timestamp"`` fields.

    Returns:
        Dictionary with keys:

        * ``total_volume`` – sum of all trade sizes.
        * ``average_volume`` – mean trade size.
        * ``volume_trend`` – ``"INCREASING"``, ``"DECREASING"``, or ``"STABLE"``.
        * ``recent_volume`` – sum of the second (more recent) half of trades.
        * ``older_volume`` – sum of the first (older) half of trades.
    """
    if not trades:
        return {
            "total_volume": 0.0,
            "average_volume": 0.0,
            "volume_trend": "STABLE",
            "recent_volume": 0.0,
            "older_volume": 0.0,
        }

    sizes = [float(t.get("size", t.get("amount", 0))) for t in trades]
    n = len(sizes)
    split = max(1, n // 2)
    older = sum(sizes[:split])
    recent = sum(sizes[split:])
    total = older + recent
    avg = total / n if n else 0.0

    if recent > older * 1.2:
        trend = "INCREASING"
    elif recent < older * 0.8:
        trend = "DECREASING"
    else:
        trend = "STABLE"

    return {
        "total_volume": total,
        "average_volume": avg,
        "volume_trend": trend,
        "recent_volume": recent,
        "older_volume": older,
    }


def detect_price_breakout(
    prices: list[float] | pd.Series,
    threshold: float = 0.05,
) -> dict[str, Any]:
    """Detect significant price movements (breakouts).

    A breakout is defined as the most-recent price being more than
    *threshold* away from the rolling high (bullish) or rolling low
    (bearish) of the preceding window.

    Args:
        prices: Sequence of price values (oldest first).
        threshold: Minimum fractional change to count as a breakout.

    Returns:
        Dictionary with keys:

        * ``breakout`` – ``True`` if a breakout is detected.
        * ``direction`` – ``"UP"``, ``"DOWN"``, or ``"NONE"``.
        * ``magnitude`` – Fractional price change at the breakout point.
        * ``signal`` – One of :data:`BULLISH`, :data:`BEARISH`, :data:`NEUTRAL`.
    """
    s = _to_series(prices)
    if len(s) < 2:
        return {"breakout": False, "direction": "NONE", "magnitude": 0.0, "signal": NEUTRAL}

    last = s.iloc[-1]
    prev = s.iloc[:-1]
    high = prev.max()
    low = prev.min()

    up_magnitude = (last - high) / high if high != 0 else 0.0
    down_magnitude = (low - last) / low if low != 0 else 0.0

    if up_magnitude > threshold:
        return {"breakout": True, "direction": "UP", "magnitude": up_magnitude, "signal": BULLISH}
    if down_magnitude > threshold:
        return {"breakout": True, "direction": "DOWN", "magnitude": down_magnitude, "signal": BEARISH}
    return {"breakout": False, "direction": "NONE", "magnitude": 0.0, "signal": NEUTRAL}


def calculate_volatility(
    prices: list[float] | pd.Series,
    window: int = 14,
) -> pd.Series:
    """Calculate rolling annualised volatility (std dev of log returns).

    Args:
        prices: Sequence of price values (oldest first).
        window: Rolling window in periods.

    Returns:
        :class:`pandas.Series` of volatility values.
    """
    s = _to_series(prices)
    log_returns = np.log(s / s.shift(1))
    vol = log_returns.rolling(window=window).std()
    return vol


def calculate_rsi(
    prices: list[float] | pd.Series,
    period: int = 14,
) -> pd.Series:
    """Calculate the Relative Strength Index (RSI).

    Uses the Wilder smoothing method (EMA with ``com=period - 1``).

    Args:
        prices: Sequence of price values (oldest first).
        period: Look-back period (default 14).

    Returns:
        :class:`pandas.Series` of RSI values (0–100).
    """
    s = _to_series(prices)
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    # Use numpy division so that gain/0 → inf (RSI=100) and 0/0 → nan → 50
    with __import__("numpy").errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain.values / avg_loss.values  # numpy array; 0/0=nan, x/0=inf
    rsi_values = 100.0 - (100.0 / (1.0 + rs))
    rsi = pd.Series(rsi_values, index=s.index)
    # 0/0 case: both gains and losses are zero → price flat → RSI = 50
    rsi = rsi.fillna(50.0)
    return rsi


def calculate_moving_averages(
    prices: list[float] | pd.Series,
    sma_window: int = 20,
    ema_window: int = 20,
) -> dict[str, pd.Series]:
    """Calculate Simple (SMA) and Exponential (EMA) Moving Averages.

    Args:
        prices: Sequence of price values (oldest first).
        sma_window: Period for the SMA.
        ema_window: Period for the EMA.

    Returns:
        Dictionary with keys ``"sma"`` and ``"ema"``.
    """
    s = _to_series(prices)
    return {
        "sma": s.rolling(window=sma_window).mean(),
        "ema": s.ewm(span=ema_window, adjust=False).mean(),
    }


def _rsi_signal(rsi_value: float) -> str:
    """Translate an RSI value to a trend signal string."""
    if np.isnan(rsi_value):
        return NEUTRAL
    if rsi_value < 30:
        return BULLISH  # oversold → expect mean reversion up
    if rsi_value > 70:
        return BEARISH  # overbought → expect mean reversion down
    return NEUTRAL


def get_market_summary(
    market_id: str,
    prices: list[float],
    trades: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a full technical-analysis summary for a market.

    Combines momentum, RSI, volatility, moving averages, and breakout
    detection into a single result dictionary.

    Args:
        market_id: Polymarket condition ID (stored in the result).
        prices: Historical price series (oldest first).
        trades: Optional list of recent trade dicts for volume analysis.

    Returns:
        Dictionary with keys:

        * ``market_id``
        * ``price_count`` — number of price observations.
        * ``last_price`` — most-recent price.
        * ``momentum`` — last momentum value.
        * ``momentum_signal`` — :data:`BULLISH`, :data:`BEARISH`, or :data:`NEUTRAL`.
        * ``rsi`` — last RSI value.
        * ``rsi_signal``
        * ``volatility`` — last rolling volatility value.
        * ``breakout`` — result dict from :func:`detect_price_breakout`.
        * ``sma`` — last SMA value.
        * ``ema`` — last EMA value.
        * ``ma_signal`` — Moving-average crossover signal.
        * ``volume`` — result dict from :func:`calculate_volume_trend`.
        * ``overall_signal`` — Majority-vote across all individual signals.
    """
    if not prices:
        return {"market_id": market_id, "error": "insufficient data"}

    s = _to_series(prices)
    last = float(s.iloc[-1])

    # Momentum
    mom_series = calculate_price_momentum(s)
    mom_val = float(mom_series.iloc[-1]) if not mom_series.empty else float("nan")
    if np.isnan(mom_val):
        mom_signal = NEUTRAL
    elif mom_val > 0.01:
        mom_signal = BULLISH
    elif mom_val < -0.01:
        mom_signal = BEARISH
    else:
        mom_signal = NEUTRAL

    # RSI
    rsi_series = calculate_rsi(s)
    rsi_val = float(rsi_series.iloc[-1]) if not rsi_series.empty else float("nan")
    rsi_sig = _rsi_signal(rsi_val)

    # Volatility
    vol_series = calculate_volatility(s)
    vol_val = float(vol_series.iloc[-1]) if not vol_series.empty else float("nan")

    # Breakout
    breakout = detect_price_breakout(s)

    # MAs
    ma = calculate_moving_averages(s)
    sma_val = float(ma["sma"].iloc[-1])
    ema_val = float(ma["ema"].iloc[-1])
    if not np.isnan(sma_val) and not np.isnan(ema_val):
        ma_signal = BULLISH if last > sma_val and last > ema_val else (
            BEARISH if last < sma_val and last < ema_val else NEUTRAL
        )
    else:
        ma_signal = NEUTRAL

    # Volume
    volume = calculate_volume_trend(trades or [])

    # Majority vote
    signals = [mom_signal, rsi_sig, breakout["signal"], ma_signal]
    bull_count = signals.count(BULLISH)
    bear_count = signals.count(BEARISH)
    if bull_count > bear_count:
        overall = BULLISH
    elif bear_count > bull_count:
        overall = BEARISH
    else:
        overall = NEUTRAL

    return {
        "market_id": market_id,
        "price_count": len(prices),
        "last_price": last,
        "momentum": mom_val,
        "momentum_signal": mom_signal,
        "rsi": rsi_val,
        "rsi_signal": rsi_sig,
        "volatility": vol_val,
        "breakout": breakout,
        "sma": sma_val,
        "ema": ema_val,
        "ma_signal": ma_signal,
        "volume": volume,
        "overall_signal": overall,
    }
