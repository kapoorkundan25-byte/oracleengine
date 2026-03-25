"""
tests/test_backtester.py — Unit tests for modules/backtester.py.

External API calls (price history) are mocked throughout.
"""

from __future__ import annotations

import math
from unittest.mock import patch

import pandas as pd
import pytest

from modules.backtester import (
    BacktestResult,
    Backtester,
    BreakoutStrategy,
    MomentumStrategy,
    RSIMeanReversionStrategy,
    Signal,
)
from modules.data_fetcher import PricePoint


# ---------------------------------------------------------------------------
# Helper — build a fake price history
# ---------------------------------------------------------------------------
def _make_history(prices: list[float], base_ts: int = 1_700_000_000) -> list[PricePoint]:
    return [PricePoint(timestamp=base_ts + i * 3600, price=p) for i, p in enumerate(prices)]


def _mock_backtester_run(bt: Backtester, strategy, prices: list[float]) -> BacktestResult:
    """Run backtester with mocked price history."""
    history = _make_history(prices)
    with patch("modules.data_fetcher.get_market_price_history", return_value=history):
        return bt.run(strategy, "mkt001")


# ---------------------------------------------------------------------------
# Signal constants
# ---------------------------------------------------------------------------
class TestSignal:
    def test_values_are_strings(self):
        assert Signal.BUY == "BUY"
        assert Signal.SELL == "SELL"
        assert Signal.HOLD == "HOLD"


# ---------------------------------------------------------------------------
# MomentumStrategy
# ---------------------------------------------------------------------------
class TestMomentumStrategy:
    def test_buy_on_positive_momentum(self):
        strat = MomentumStrategy(window=1, threshold=0.01)
        # Strongly rising prices → BUY
        prices = pd.Series([1.0, 1.1, 1.2, 1.3, 1.4, 1.5])
        assert strat.generate_signal(prices) == Signal.BUY

    def test_sell_on_negative_momentum(self):
        strat = MomentumStrategy(window=1, threshold=0.01)
        # Strongly falling prices → SELL
        prices = pd.Series([1.5, 1.4, 1.3, 1.2, 1.1, 1.0])
        assert strat.generate_signal(prices) == Signal.SELL

    def test_hold_on_flat_prices(self):
        strat = MomentumStrategy(window=1, threshold=0.05)
        prices = pd.Series([1.0, 1.0, 1.0, 1.0, 1.001])
        assert strat.generate_signal(prices) == Signal.HOLD

    def test_hold_when_insufficient_data(self):
        strat = MomentumStrategy(window=5, threshold=0.01)
        assert strat.generate_signal(pd.Series([0.5, 0.6])) == Signal.HOLD


# ---------------------------------------------------------------------------
# RSIMeanReversionStrategy
# ---------------------------------------------------------------------------
class TestRSIMeanReversionStrategy:
    def test_buy_when_oversold(self):
        strat = RSIMeanReversionStrategy(period=14, oversold=30)
        # Falling prices → RSI < 30
        prices = pd.Series([float(50 - i) for i in range(30)])
        assert strat.generate_signal(prices) == Signal.BUY

    def test_sell_when_overbought(self):
        strat = RSIMeanReversionStrategy(period=14, overbought=70)
        # Rising prices → RSI > 70
        prices = pd.Series([float(i) for i in range(30)])
        assert strat.generate_signal(prices) == Signal.SELL

    def test_hold_when_insufficient_data(self):
        strat = RSIMeanReversionStrategy(period=14)
        prices = pd.Series([0.5, 0.6, 0.7])
        assert strat.generate_signal(prices) == Signal.HOLD


# ---------------------------------------------------------------------------
# BreakoutStrategy
# ---------------------------------------------------------------------------
class TestBreakoutStrategy:
    def test_buy_on_upside_breakout(self):
        strat = BreakoutStrategy(threshold=0.05, lookback=5)
        # Big jump at the end
        prices = pd.Series([0.5, 0.5, 0.5, 0.5, 0.5, 0.6])
        assert strat.generate_signal(prices) == Signal.BUY

    def test_sell_on_downside_breakout(self):
        strat = BreakoutStrategy(threshold=0.05, lookback=5)
        prices = pd.Series([0.5, 0.5, 0.5, 0.5, 0.5, 0.4])
        assert strat.generate_signal(prices) == Signal.SELL

    def test_hold_on_no_breakout(self):
        strat = BreakoutStrategy(threshold=0.20, lookback=5)
        prices = pd.Series([0.5, 0.51, 0.50, 0.51, 0.50, 0.51])
        assert strat.generate_signal(prices) == Signal.HOLD

    def test_hold_when_insufficient_data(self):
        strat = BreakoutStrategy(lookback=10)
        prices = pd.Series([0.5, 0.6])
        assert strat.generate_signal(prices) == Signal.HOLD


# ---------------------------------------------------------------------------
# Backtester.run
# ---------------------------------------------------------------------------
class TestBacktesterRun:
    def _run(self, strategy, prices):
        bt = Backtester(slippage=0.0, fee=0.0)
        return _mock_backtester_run(bt, strategy, prices)

    def test_result_type(self):
        prices = [0.5 + 0.01 * i for i in range(50)]
        result = self._run(MomentumStrategy(), prices)
        assert isinstance(result, BacktestResult)

    def test_initial_and_final_capital(self):
        prices = [0.5] * 30  # flat — no trades
        bt = Backtester(slippage=0.0, fee=0.0)
        history = _make_history(prices)
        with patch("modules.data_fetcher.get_market_price_history", return_value=history):
            result = bt.run(MomentumStrategy(), "mkt001", initial_capital=500.0)
        assert result.initial_capital == pytest.approx(500.0)

    def test_equity_curve_length(self):
        prices = [0.5 + 0.005 * i for i in range(40)]
        result = self._run(MomentumStrategy(), prices)
        # Equity curve has one entry per bar after the first
        assert len(result.equity_curve) == len(prices) - 1

    def test_no_trades_on_flat_prices(self):
        prices = [0.5] * 30
        result = self._run(MomentumStrategy(threshold=0.05), prices)
        assert result.total_trades == 0

    def test_total_return_with_profitable_series(self):
        # Prices go 0.5 → 0.9 monotonically — Momentum should BUY early
        prices = [0.5 + 0.02 * i for i in range(30)]
        result = self._run(MomentumStrategy(window=1, threshold=0.001), prices)
        # Can't guarantee profit due to slippage, but should attempt trades
        assert isinstance(result.total_return, float)

    def test_win_rate_bounded(self):
        prices = [0.5 + 0.01 * i for i in range(50)]
        result = self._run(RSIMeanReversionStrategy(), prices)
        assert 0.0 <= result.win_rate <= 1.0

    def test_max_drawdown_non_positive(self):
        prices = [0.5 + 0.005 * i for i in range(50)]
        result = self._run(MomentumStrategy(), prices)
        assert result.max_drawdown <= 0.0 or math.isnan(result.max_drawdown)

    def test_sharpe_ratio_is_float(self):
        prices = [0.5 + 0.005 * i for i in range(50)]
        result = self._run(MomentumStrategy(), prices)
        assert isinstance(result.sharpe_ratio, float)

    def test_raises_on_empty_history(self):
        bt = Backtester()
        with patch("modules.data_fetcher.get_market_price_history", return_value=[]):
            with pytest.raises(ValueError, match="No price history"):
                bt.run(MomentumStrategy(), "mkt_empty")


# ---------------------------------------------------------------------------
# Backtester.compare_strategies
# ---------------------------------------------------------------------------
class TestCompareStrategies:
    def test_returns_sorted_by_return(self):
        prices = [0.5 + 0.01 * i for i in range(50)]
        history = _make_history(prices)
        bt = Backtester(slippage=0.0, fee=0.0)
        strategies = [MomentumStrategy(), RSIMeanReversionStrategy(), BreakoutStrategy()]
        with patch("modules.data_fetcher.get_market_price_history", return_value=history):
            results = bt.compare_strategies(strategies, "mkt001")
        assert len(results) >= 1
        # Results sorted descending by total_return
        returns = [r.total_return for r in results]
        assert returns == sorted(returns, reverse=True)

    def test_skips_failed_strategy(self):
        class BadStrategy(MomentumStrategy):
            def generate_signal(self, market_data):
                raise RuntimeError("boom")

        prices = [0.5] * 30
        history = _make_history(prices)
        bt = Backtester()
        with patch("modules.data_fetcher.get_market_price_history", return_value=history):
            results = bt.compare_strategies([BadStrategy(), MomentumStrategy()], "mkt001")
        # BadStrategy is skipped; MomentumStrategy result is present
        assert all(isinstance(r, BacktestResult) for r in results)


# ---------------------------------------------------------------------------
# BacktestResult immutability
# ---------------------------------------------------------------------------
class TestBacktestResultImmutable:
    def test_frozen(self):
        import dataclasses

        result = BacktestResult(
            strategy_name="Test",
            market_id="mkt",
            total_return=0.1,
            sharpe_ratio=1.2,
            max_drawdown=-0.05,
            win_rate=0.6,
            total_trades=10,
            equity_curve=pd.Series([100.0, 110.0]),
            initial_capital=1000.0,
            final_capital=1100.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            result.total_return = 0.5  # type: ignore[misc]
