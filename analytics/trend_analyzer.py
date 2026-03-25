"""
analytics/trend_analyzer.py — Price trend analysis and signal detection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from analytics.indicators import sma, ema, rsi, bollinger_bands, vwap


# ── Signal enum ───────────────────────────────────────────────────────────────

BULLISH = "BULLISH"
BEARISH = "BEARISH"
OVERBOUGHT = "OVERBOUGHT"
OVERSOLD = "OVERSOLD"
NEUTRAL = "NEUTRAL"


@dataclass
class TrendReport:
    """Result of a full trend analysis."""

    prices: list[float]
    volumes: list[float]

    # Indicator values (last computed value)
    sma_5: Optional[float] = None
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    ema_10: Optional[float] = None
    ema_20: Optional[float] = None
    rsi_14: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_middle: Optional[float] = None
    bb_lower: Optional[float] = None
    vwap_value: Optional[float] = None

    # Full series (for charting)
    sma_5_series: list[Optional[float]] = field(default_factory=list)
    sma_20_series: list[Optional[float]] = field(default_factory=list)
    rsi_series: list[Optional[float]] = field(default_factory=list)
    bb_upper_series: list[Optional[float]] = field(default_factory=list)
    bb_lower_series: list[Optional[float]] = field(default_factory=list)

    signal: str = NEUTRAL

    def last_price(self) -> Optional[float]:
        return self.prices[-1] if self.prices else None


class TrendAnalyzer:
    """Compute technical indicators and produce a :class:`TrendReport`."""

    def __init__(
        self,
        sma_windows: tuple[int, int, int] = (5, 10, 20),
        ema_windows: tuple[int, int] = (10, 20),
        rsi_period: int = 14,
        bb_window: int = 20,
        bb_std: float = 2.0,
    ) -> None:
        self.sma_windows = sma_windows
        self.ema_windows = ema_windows
        self.rsi_period = rsi_period
        self.bb_window = bb_window
        self.bb_std = bb_std

    def analyze(
        self,
        prices: list[float],
        volumes: Optional[list[float]] = None,
    ) -> TrendReport:
        """Run analysis on *prices* (and optional *volumes*) and return a :class:`TrendReport`."""
        if not prices:
            return TrendReport(prices=[], volumes=[])

        vols = volumes or [1.0] * len(prices)

        report = TrendReport(prices=prices, volumes=vols)

        # SMAs
        s5 = sma(prices, self.sma_windows[0])
        s10 = sma(prices, self.sma_windows[1])
        s20 = sma(prices, self.sma_windows[2])
        report.sma_5_series = s5
        report.sma_20_series = s20
        report.sma_5 = next((v for v in reversed(s5) if v is not None), None)
        report.sma_10 = next((v for v in reversed(s10) if v is not None), None)
        report.sma_20 = next((v for v in reversed(s20) if v is not None), None)

        # EMAs
        e10 = ema(prices, self.ema_windows[0])
        e20 = ema(prices, self.ema_windows[1])
        report.ema_10 = next((v for v in reversed(e10) if v is not None), None)
        report.ema_20 = next((v for v in reversed(e20) if v is not None), None)

        # RSI
        r_series = rsi(prices, self.rsi_period)
        report.rsi_series = r_series
        report.rsi_14 = next((v for v in reversed(r_series) if v is not None), None)

        # Bollinger Bands
        bb_up, bb_mid, bb_low = bollinger_bands(prices, self.bb_window, self.bb_std)
        report.bb_upper_series = bb_up
        report.bb_lower_series = bb_low
        report.bb_upper = next((v for v in reversed(bb_up) if v is not None), None)
        report.bb_middle = next((v for v in reversed(bb_mid) if v is not None), None)
        report.bb_lower = next((v for v in reversed(bb_low) if v is not None), None)

        # VWAP
        report.vwap_value = vwap(prices, vols)

        # Signal detection
        report.signal = self._detect_signal(report)

        return report

    @staticmethod
    def _detect_signal(report: TrendReport) -> str:
        price = report.last_price()
        rsi_val = report.rsi_14
        sma_ref = report.sma_20 or report.sma_10 or report.sma_5

        if rsi_val is not None:
            if rsi_val > 70:
                return OVERBOUGHT
            if rsi_val < 30:
                return OVERSOLD

        if price is not None and sma_ref is not None and rsi_val is not None:
            if price > sma_ref and rsi_val < 70:
                return BULLISH
            if price < sma_ref and rsi_val > 30:
                return BEARISH

        return NEUTRAL
