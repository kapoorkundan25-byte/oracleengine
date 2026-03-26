"""
tests/test_trend_analyzer.py — Unit tests for modules/trend_analyzer.py.

Uses known mathematical inputs with pre-computed expected outputs.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from modules.trend_analyzer import (
    BEARISH,
    BULLISH,
    NEUTRAL,
    calculate_moving_averages,
    calculate_price_momentum,
    calculate_rsi,
    calculate_volatility,
    calculate_volume_trend,
    detect_price_breakout,
    get_market_summary,
)


# ---------------------------------------------------------------------------
# calculate_price_momentum
# ---------------------------------------------------------------------------
class TestCalculatePriceMomentum:
    def test_basic_momentum(self):
        prices = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
        mom = calculate_price_momentum(prices, window=1)
        # pct_change(1) at index 5 = (1.5 - 1.4) / 1.4
        assert mom.iloc[-1] == pytest.approx((1.5 - 1.4) / 1.4, rel=1e-6)

    def test_leading_nans(self):
        prices = [0.5, 0.6, 0.7, 0.8, 0.9]
        mom = calculate_price_momentum(prices, window=3)
        # First 3 values should be NaN
        assert all(math.isnan(v) for v in mom.iloc[:3])

    def test_flat_prices_zero_momentum(self):
        prices = [0.5] * 10
        mom = calculate_price_momentum(prices, window=2)
        # pct_change of flat series is 0
        assert mom.dropna().abs().max() == pytest.approx(0.0)

    def test_series_input(self):
        s = pd.Series([0.3, 0.4, 0.5, 0.6, 0.7])
        mom = calculate_price_momentum(s, window=2)
        assert isinstance(mom, pd.Series)
        assert len(mom) == 5


# ---------------------------------------------------------------------------
# calculate_volume_trend
# ---------------------------------------------------------------------------
class TestCalculateVolumeTrend:
    def test_empty_trades_returns_stable(self):
        result = calculate_volume_trend([])
        assert result["volume_trend"] == "STABLE"
        assert result["total_volume"] == 0.0

    def test_increasing_volume(self):
        # Small older, large recent
        trades = [{"size": 1}] * 10 + [{"size": 10}] * 10
        result = calculate_volume_trend(trades)
        assert result["volume_trend"] == "INCREASING"

    def test_decreasing_volume(self):
        trades = [{"size": 10}] * 10 + [{"size": 1}] * 10
        result = calculate_volume_trend(trades)
        assert result["volume_trend"] == "DECREASING"

    def test_total_volume_correct(self):
        trades = [{"size": 5}] * 4
        result = calculate_volume_trend(trades)
        assert result["total_volume"] == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# detect_price_breakout
# ---------------------------------------------------------------------------
class TestDetectPriceBreakout:
    def test_upward_breakout(self):
        prices = [0.5, 0.5, 0.5, 0.5, 0.5, 0.6]  # last price jumps 20 %
        result = detect_price_breakout(prices, threshold=0.05)
        assert result["breakout"] is True
        assert result["direction"] == "UP"
        assert result["signal"] == BULLISH

    def test_downward_breakout(self):
        prices = [0.5, 0.5, 0.5, 0.5, 0.5, 0.4]  # last price drops 20 %
        result = detect_price_breakout(prices, threshold=0.05)
        assert result["breakout"] is True
        assert result["direction"] == "DOWN"
        assert result["signal"] == BEARISH

    def test_no_breakout(self):
        prices = [0.50, 0.51, 0.50, 0.51, 0.50, 0.51]
        result = detect_price_breakout(prices, threshold=0.10)
        assert result["breakout"] is False
        assert result["signal"] == NEUTRAL

    def test_single_price_no_breakout(self):
        result = detect_price_breakout([0.5], threshold=0.05)
        assert result["breakout"] is False


# ---------------------------------------------------------------------------
# calculate_volatility
# ---------------------------------------------------------------------------
class TestCalculateVolatility:
    def test_returns_series(self):
        prices = list(range(1, 30))
        vol = calculate_volatility(prices, window=5)
        assert isinstance(vol, pd.Series)
        assert len(vol) == len(prices)

    def test_constant_price_zero_volatility(self):
        prices = [1.0] * 20
        vol = calculate_volatility(prices, window=5)
        # log(1/1) = 0 for all, so std = 0
        assert vol.dropna().max() == pytest.approx(0.0)

    def test_leading_nans_equal_to_window(self):
        prices = [float(i + 1) for i in range(20)]
        window = 7
        vol = calculate_volatility(prices, window=window)
        assert all(math.isnan(v) for v in vol.iloc[:window])


# ---------------------------------------------------------------------------
# calculate_rsi
# ---------------------------------------------------------------------------
class TestCalculateRSI:
    def test_rsi_range(self):
        # RSI must always be between 0 and 100
        prices = [0.5 + 0.05 * math.sin(i) for i in range(50)]
        rsi = calculate_rsi(prices, period=14)
        valid = rsi.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_rising_prices_above_50(self):
        # Continuously rising prices → RSI should be high
        prices = [float(i) for i in range(1, 30)]
        rsi = calculate_rsi(prices, period=14)
        last = float(rsi.iloc[-1])
        assert last > 50

    def test_rsi_falling_prices_below_50(self):
        prices = [float(30 - i) for i in range(30)]
        rsi = calculate_rsi(prices, period=14)
        last = float(rsi.dropna().iloc[-1])
        assert last < 50

    def test_returns_correct_length(self):
        prices = [0.5] * 30
        rsi = calculate_rsi(prices, period=14)
        assert len(rsi) == 30


# ---------------------------------------------------------------------------
# calculate_moving_averages
# ---------------------------------------------------------------------------
class TestCalculateMovingAverages:
    def test_returns_sma_and_ema_keys(self):
        prices = [0.5 + 0.01 * i for i in range(30)]
        result = calculate_moving_averages(prices, sma_window=10, ema_window=10)
        assert "sma" in result
        assert "ema" in result

    def test_sma_correct_value(self):
        prices = [float(i) for i in range(1, 11)]  # 1..10
        result = calculate_moving_averages(prices, sma_window=5, ema_window=5)
        # SMA(5) of last 5 values (6,7,8,9,10) = 8.0
        assert float(result["sma"].iloc[-1]) == pytest.approx(8.0)

    def test_ema_responds_to_recent_prices(self):
        # EMA should weight recent values more heavily than SMA
        prices = [1.0] * 20 + [2.0] * 5
        result = calculate_moving_averages(prices, sma_window=20, ema_window=20)
        # EMA should be closer to 2.0 than SMA at the end
        ema_last = float(result["ema"].iloc[-1])
        sma_last = float(result["sma"].iloc[-1])
        assert ema_last > sma_last


# ---------------------------------------------------------------------------
# get_market_summary
# ---------------------------------------------------------------------------
class TestGetMarketSummary:
    def test_empty_prices_returns_error(self):
        result = get_market_summary("mkt001", [])
        assert "error" in result

    def test_returns_all_expected_keys(self):
        prices = [0.5 + 0.005 * i for i in range(50)]
        result = get_market_summary("mkt001", prices)
        expected_keys = {
            "market_id", "price_count", "last_price",
            "momentum", "momentum_signal", "rsi", "rsi_signal",
            "volatility", "breakout", "sma", "ema", "ma_signal",
            "volume", "overall_signal",
        }
        assert expected_keys.issubset(result.keys())

    def test_overall_signal_valid(self):
        prices = [0.5 + 0.01 * i for i in range(50)]
        result = get_market_summary("mkt001", prices)
        assert result["overall_signal"] in {BULLISH, BEARISH, NEUTRAL}

    def test_market_id_preserved(self):
        prices = [0.6] * 30
        result = get_market_summary("abc-123", prices)
        assert result["market_id"] == "abc-123"

    def test_with_trade_data(self):
        prices = [0.5 + 0.002 * i for i in range(30)]
        trades = [{"size": 100.0, "price": p} for p in prices]
        result = get_market_summary("mkt002", prices, trades)
        assert result["volume"]["total_volume"] > 0
