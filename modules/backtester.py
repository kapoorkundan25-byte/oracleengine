"""
modules/backtester.py — Historical Backtesting for OracleEngine.

Simulates trading strategies against a historical price series and
produces detailed performance metrics.

Classes
-------
* :class:`Signal` — Enum-like constants for strategy signals.
* :class:`Strategy` — Abstract base class all strategies must extend.
* :class:`MomentumStrategy` — Buy on positive momentum, sell on negative.
* :class:`RSIMeanReversionStrategy` — Buy oversold, sell overbought.
* :class:`BreakoutStrategy` — Enter on price breakout above resistance.
* :class:`BacktestResult` — Immutable result dataclass.
* :class:`Backtester` — Orchestrates runs and comparisons.
"""

from __future__ import annotations

import abc
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

import config
from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Signal constants
# ---------------------------------------------------------------------------
class Signal:
    """Strategy signal constants."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# ---------------------------------------------------------------------------
# Abstract Strategy
# ---------------------------------------------------------------------------
class Strategy(abc.ABC):
    """Abstract base class for all trading strategies.

    Sub-classes must implement :meth:`generate_signal`.
    """

    @property
    def name(self) -> str:
        """Human-readable name for this strategy."""
        return self.__class__.__name__

    @abc.abstractmethod
    def generate_signal(self, market_data: pd.Series) -> str:
        """Generate a trading signal for the current market state.

        Args:
            market_data: A :class:`pandas.Series` of prices up to and
                         including the current bar (oldest first).

        Returns:
            One of :data:`Signal.BUY`, :data:`Signal.SELL`, or
            :data:`Signal.HOLD`.
        """


# ---------------------------------------------------------------------------
# Built-in strategies
# ---------------------------------------------------------------------------
class MomentumStrategy(Strategy):
    """Buy when momentum crosses above *threshold*, sell when it drops below.

    Args:
        window: Look-back window for momentum calculation.
        threshold: Minimum momentum value to trigger a BUY signal.
    """

    def __init__(self, window: int = 5, threshold: float = 0.02) -> None:
        self.window = window
        self.threshold = threshold

    def generate_signal(self, market_data: pd.Series) -> str:  # noqa: D102
        from modules.trend_analyzer import calculate_price_momentum

        if len(market_data) < self.window + 1:
            return Signal.HOLD
        mom = calculate_price_momentum(market_data, window=self.window)
        latest = float(mom.iloc[-1])
        if math.isnan(latest):
            return Signal.HOLD
        if latest > self.threshold:
            return Signal.BUY
        if latest < -self.threshold:
            return Signal.SELL
        return Signal.HOLD


class RSIMeanReversionStrategy(Strategy):
    """Buy oversold (RSI < *oversold*), sell overbought (RSI > *overbought*).

    Args:
        period: RSI look-back period.
        oversold: RSI level below which a BUY signal is generated.
        overbought: RSI level above which a SELL signal is generated.
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
    ) -> None:
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signal(self, market_data: pd.Series) -> str:  # noqa: D102
        from modules.trend_analyzer import calculate_rsi

        if len(market_data) < self.period + 1:
            return Signal.HOLD
        rsi = calculate_rsi(market_data, period=self.period)
        latest = float(rsi.iloc[-1])
        if math.isnan(latest):
            return Signal.HOLD
        if latest < self.oversold:
            return Signal.BUY
        if latest > self.overbought:
            return Signal.SELL
        return Signal.HOLD


class BreakoutStrategy(Strategy):
    """Enter on a price breakout above resistance.

    Args:
        threshold: Minimum fractional move above the rolling high to
                   trigger a BUY signal.
        lookback: Window used to determine the prior high.
    """

    def __init__(self, threshold: float = 0.03, lookback: int = 10) -> None:
        self.threshold = threshold
        self.lookback = lookback

    def generate_signal(self, market_data: pd.Series) -> str:  # noqa: D102
        from modules.trend_analyzer import detect_price_breakout

        if len(market_data) < self.lookback + 1:
            return Signal.HOLD
        result = detect_price_breakout(market_data, threshold=self.threshold)
        if result["direction"] == "UP":
            return Signal.BUY
        if result["direction"] == "DOWN":
            return Signal.SELL
        return Signal.HOLD


# ---------------------------------------------------------------------------
# Backtest result
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BacktestResult:
    """Immutable summary of a completed backtest run.

    Attributes:
        strategy_name:  Name of the strategy that was tested.
        market_id:      Polymarket condition ID that was tested.
        total_return:   Total fractional return (e.g. ``0.15`` → +15 %).
        sharpe_ratio:   Annualised Sharpe ratio (assume 252 trading days).
        max_drawdown:   Maximum peak-to-trough drawdown as a fraction.
        win_rate:       Fraction of closed trades that were profitable.
        total_trades:   Total number of trades executed.
        equity_curve:   :class:`pandas.Series` of portfolio value over time.
        initial_capital: Starting capital in USD.
        final_capital:  Ending capital in USD.
    """

    strategy_name: str
    market_id: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    equity_curve: pd.Series
    initial_capital: float
    final_capital: float


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------
class Backtester:
    """Orchestrates backtesting of one or more strategies.

    Args:
        slippage: Fractional slippage applied to each trade entry/exit.
        fee: Fractional transaction fee applied per trade side.
    """

    def __init__(
        self,
        slippage: float = config.DEFAULT_SLIPPAGE,
        fee: float = config.DEFAULT_FEE,
    ) -> None:
        self.slippage = slippage
        self.fee = fee

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fetch_prices(
        self,
        market_id: str,
        start_date: datetime | None,
        end_date: datetime | None,
    ) -> pd.Series:
        """Fetch and filter price history for *market_id*.

        Returns:
            Filtered price :class:`pandas.Series` indexed by timestamp.
        """
        from modules.data_fetcher import get_market_price_history

        points = get_market_price_history(market_id)
        if not points:
            raise ValueError(f"No price history available for market {market_id!r}")

        ts = [p.timestamp for p in points]
        prices = [p.price for p in points]
        series = pd.Series(prices, index=ts, dtype=float)

        if start_date is not None:
            start_ts = int(start_date.timestamp())
            series = series[series.index >= start_ts]
        if end_date is not None:
            end_ts = int(end_date.timestamp())
            series = series[series.index <= end_ts]

        if series.empty:
            raise ValueError(
                f"No price data for market {market_id!r} in the specified date range"
            )
        return series

    @staticmethod
    def _compute_sharpe(returns: pd.Series, periods_per_year: int = 252) -> float:
        """Compute annualised Sharpe ratio from a series of period returns."""
        if returns.std() == 0:
            return 0.0
        return float(
            returns.mean() / returns.std() * math.sqrt(periods_per_year)
        )

    @staticmethod
    def _compute_max_drawdown(equity: pd.Series) -> float:
        """Compute maximum peak-to-trough drawdown."""
        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max
        return float(drawdown.min())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(
        self,
        strategy: Strategy,
        market_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        initial_capital: float = config.DEFAULT_INITIAL_CAPITAL,
    ) -> BacktestResult:
        """Run a single strategy against historical data.

        Args:
            strategy: A :class:`Strategy` instance.
            market_id: Polymarket condition ID.
            start_date: Optional start of the simulation window.
            end_date: Optional end of the simulation window.
            initial_capital: Starting portfolio value in USD.

        Returns:
            :class:`BacktestResult` with performance metrics.
        """
        prices = self._fetch_prices(market_id, start_date, end_date)
        n = len(prices)
        logger.info(
            "Backtesting %s on %s (%d bars, capital=$%.2f)",
            strategy.name,
            market_id,
            n,
            initial_capital,
        )

        capital = initial_capital
        position: float = 0.0  # current holding in units
        entry_price: float = 0.0
        trades: list[dict[str, Any]] = []
        equity: list[float] = []

        for i in range(1, n):
            window = prices.iloc[: i + 1]
            signal = strategy.generate_signal(window)
            current_price = float(prices.iloc[i])
            equity.append(capital + position * current_price)

            if signal == Signal.BUY and position == 0.0:
                # Enter long
                buy_price = current_price * (1 + self.slippage)
                cost = capital * (1 - self.fee)
                position = cost / buy_price
                entry_price = buy_price
                capital = 0.0
                logger.debug("BUY  @%.4f  pos=%.4f", buy_price, position)

            elif signal == Signal.SELL and position > 0.0:
                # Exit long
                sell_price = current_price * (1 - self.slippage)
                proceeds = position * sell_price * (1 - self.fee)
                pnl = proceeds - (position * entry_price)
                trades.append({"entry": entry_price, "exit": sell_price, "pnl": pnl})
                capital = proceeds
                position = 0.0
                entry_price = 0.0
                logger.debug("SELL @%.4f  pnl=%.4f", sell_price, pnl)

        # Close any open position at last bar
        if position > 0.0:
            last_price = float(prices.iloc[-1]) * (1 - self.slippage)
            proceeds = position * last_price * (1 - self.fee)
            pnl = proceeds - (position * entry_price)
            trades.append({"entry": entry_price, "exit": last_price, "pnl": pnl})
            capital = proceeds

        final_capital = capital
        total_return = (final_capital - initial_capital) / initial_capital
        equity_series = pd.Series(equity, dtype=float)
        period_returns = equity_series.pct_change().dropna()
        sharpe = self._compute_sharpe(period_returns)
        max_dd = self._compute_max_drawdown(equity_series) if len(equity_series) > 1 else 0.0
        win_rate = (
            sum(1 for t in trades if t["pnl"] > 0) / len(trades) if trades else 0.0
        )

        result = BacktestResult(
            strategy_name=strategy.name,
            market_id=market_id,
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            win_rate=win_rate,
            total_trades=len(trades),
            equity_curve=equity_series,
            initial_capital=initial_capital,
            final_capital=final_capital,
        )
        self._print_report(result)
        return result

    def compare_strategies(
        self,
        strategies: list[Strategy],
        market_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        initial_capital: float = config.DEFAULT_INITIAL_CAPITAL,
    ) -> list[BacktestResult]:
        """Run multiple strategies and return their results sorted by return.

        Args:
            strategies: List of :class:`Strategy` instances.
            market_id: Polymarket condition ID.
            start_date: Optional simulation start.
            end_date: Optional simulation end.
            initial_capital: Starting capital shared by all strategies.

        Returns:
            List of :class:`BacktestResult` objects, best return first.
        """
        results = []
        for strat in strategies:
            try:
                result = self.run(strat, market_id, start_date, end_date, initial_capital)
                results.append(result)
            except Exception as exc:
                logger.error("Strategy %s failed: %s", strat.name, exc)
        results.sort(key=lambda r: r.total_return, reverse=True)
        return results

    def plot_equity_curve(self, result: BacktestResult, output_path: str = "") -> str:
        """Save an equity-curve chart as a PNG file.

        Args:
            result: :class:`BacktestResult` to visualise.
            output_path: Destination file path.  Defaults to
                         ``equity_{strategy}_{market}.png``.

        Returns:
            Absolute path to the saved PNG.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.error("matplotlib is not installed — cannot plot equity curve")
            return ""

        if not output_path:
            safe_name = result.strategy_name.replace(" ", "_")
            output_path = f"equity_{safe_name}_{result.market_id[:8]}.png"

        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(result.equity_curve.values, linewidth=1.5, color="royalblue")
        ax.set_title(f"{result.strategy_name} — Equity Curve ({result.market_id[:12]}…)")
        ax.set_xlabel("Bar")
        ax.set_ylabel("Portfolio Value ($)")
        ax.axhline(result.initial_capital, color="grey", linestyle="--", linewidth=0.8, label="Initial capital")
        ax.legend()
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        logger.info("Equity curve saved to %s", output_path)
        return output_path

    @staticmethod
    def _print_report(result: BacktestResult) -> None:
        """Print a formatted performance report to stdout."""
        sep = "─" * 50
        print(f"\n{sep}")
        print(f"  Strategy : {result.strategy_name}")
        print(f"  Market   : {result.market_id}")
        print(f"  Capital  : ${result.initial_capital:,.2f} → ${result.final_capital:,.2f}")
        print(f"  Return   : {result.total_return * 100:+.2f} %")
        print(f"  Sharpe   : {result.sharpe_ratio:.3f}")
        print(f"  Max DD   : {result.max_drawdown * 100:.2f} %")
        print(f"  Win Rate : {result.win_rate * 100:.1f} %")
        print(f"  Trades   : {result.total_trades}")
        print(f"{sep}\n")
