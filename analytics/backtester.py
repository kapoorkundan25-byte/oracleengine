"""
analytics/backtester.py — Historical backtesting engine.

Usage
-----
::

    from analytics.backtester import Backtester, MomentumStrategy

    candles = [
        {"timestamp": 0, "open": 0.50, "high": 0.55, "low": 0.48, "close": 0.52, "volume": 1000},
        ...
    ]
    result = Backtester(strategy=MomentumStrategy()).run(candles)
    print(result.total_return_pct, result.sharpe_ratio)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

import config
from analytics.indicators import sma, rsi, bollinger_bands


# ── Signal enum ────────────────────────────────────────────────────────────────

class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


# ── Strategy protocol ──────────────────────────────────────────────────────────

@runtime_checkable
class Strategy(Protocol):
    def generate_signal(self, prices: list[float], index: int) -> Signal:
        ...


# ── Built-in strategies ────────────────────────────────────────────────────────

class MeanReversionStrategy:
    """Buy when price drops ≥ *drop_pct* below SMA; sell when it recovers above SMA."""

    def __init__(self, window: int = 20, drop_pct: float = 0.05) -> None:
        self.window = window
        self.drop_pct = drop_pct

    def generate_signal(self, prices: list[float], index: int) -> Signal:
        if index < self.window:
            return Signal.HOLD
        window_prices = prices[: index + 1]
        sma_vals = sma(window_prices, self.window)
        sma_val = sma_vals[-1]
        if sma_val is None:
            return Signal.HOLD
        price = prices[index]
        if price < sma_val * (1 - self.drop_pct):
            return Signal.BUY
        if price >= sma_val:
            return Signal.SELL
        return Signal.HOLD


class MomentumStrategy:
    """Buy when RSI < 30 (oversold); sell when RSI > 70 (overbought)."""

    def __init__(self, rsi_period: int = 14, oversold: float = 30.0, overbought: float = 70.0) -> None:
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    def generate_signal(self, prices: list[float], index: int) -> Signal:
        if index < self.rsi_period:
            return Signal.HOLD
        window_prices = prices[: index + 1]
        rsi_vals = rsi(window_prices, self.rsi_period)
        rsi_val = rsi_vals[-1]
        if rsi_val is None:
            return Signal.HOLD
        if rsi_val < self.oversold:
            return Signal.BUY
        if rsi_val > self.overbought:
            return Signal.SELL
        return Signal.HOLD


class BreakoutStrategy:
    """Buy when price breaks above the Bollinger Band upper; sell on reversal."""

    def __init__(self, window: int = 20, num_std: float = 2.0) -> None:
        self.window = window
        self.num_std = num_std

    def generate_signal(self, prices: list[float], index: int) -> Signal:
        if index < self.window:
            return Signal.HOLD
        window_prices = prices[: index + 1]
        bb_up, _, bb_low = bollinger_bands(window_prices, self.window, self.num_std)
        upper = bb_up[-1]
        lower = bb_low[-1]
        if upper is None or lower is None:
            return Signal.HOLD
        price = prices[index]
        if price > upper:
            return Signal.BUY
        if price < lower:
            return Signal.SELL
        return Signal.HOLD


# ── Result dataclass ───────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    num_trades: int = 0
    equity_curve: list[float] = field(default_factory=list)
    trades_log: list[dict] = field(default_factory=list)


# ── Backtester ─────────────────────────────────────────────────────────────────

class Backtester:
    """
    Simulate a strategy on historical OHLCV candles.

    Parameters
    ----------
    strategy:
        Any object implementing :class:`Strategy`.
    starting_capital:
        Initial portfolio value in USD.
    position_size_pct:
        Fraction of current portfolio to use per trade (0–1).
    fee_pct:
        One-way transaction cost as a fraction (e.g. 0.005 = 0.5 %).
    """

    def __init__(
        self,
        strategy: Optional[Strategy] = None,
        starting_capital: float = config.BACKTEST_STARTING_CAPITAL,
        position_size_pct: float = 0.5,
        fee_pct: float = config.BACKTEST_TRANSACTION_FEE,
    ) -> None:
        self.strategy = strategy or MomentumStrategy()
        self.starting_capital = starting_capital
        self.position_size_pct = position_size_pct
        self.fee_pct = fee_pct

    def run(self, candles: list[dict]) -> BacktestResult:
        """
        Run the backtest.

        *candles* must be a list of dicts with keys:
        ``timestamp``, ``open``, ``high``, ``low``, ``close``, ``volume``.
        """
        if not candles:
            return BacktestResult()

        closes = [float(c["close"]) for c in candles]
        cash = self.starting_capital
        position_units = 0.0
        entry_price = 0.0
        equity_curve: list[float] = []
        trades_log: list[dict] = []
        wins = 0
        losses = 0

        for i, candle in enumerate(candles):
            price = float(candle["close"])
            signal = self.strategy.generate_signal(closes, i)
            portfolio_value = cash + position_units * price

            if signal == Signal.BUY and position_units == 0:
                spend = portfolio_value * self.position_size_pct
                fee = spend * self.fee_pct
                units_bought = (spend - fee) / price
                cash -= spend
                position_units = units_bought
                entry_price = price
                trades_log.append({"action": "BUY", "price": price, "units": units_bought, "ts": candle.get("timestamp")})

            elif signal == Signal.SELL and position_units > 0:
                proceeds = position_units * price
                fee = proceeds * self.fee_pct
                net = proceeds - fee
                pnl = net - (position_units * entry_price)
                cash += net
                if pnl >= 0:
                    wins += 1
                else:
                    losses += 1
                trades_log.append({"action": "SELL", "price": price, "units": position_units, "pnl": pnl, "ts": candle.get("timestamp")})
                position_units = 0.0
                entry_price = 0.0

            portfolio_value = cash + position_units * price
            equity_curve.append(portfolio_value)

        # close any open position at last price
        if position_units > 0:
            last_price = closes[-1]
            proceeds = position_units * last_price
            fee = proceeds * self.fee_pct
            net = proceeds - fee
            pnl = net - (position_units * entry_price)
            cash += net
            if pnl >= 0:
                wins += 1
            else:
                losses += 1
            equity_curve[-1] = cash

        num_trades = wins + losses
        total_return_pct = ((cash - self.starting_capital) / self.starting_capital) * 100.0
        win_rate = (wins / num_trades * 100.0) if num_trades > 0 else 0.0

        # Sharpe ratio (daily returns, annualised)
        sharpe = _sharpe(equity_curve)

        # Max drawdown
        max_dd = _max_drawdown(equity_curve)

        return BacktestResult(
            total_return_pct=round(total_return_pct, 4),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown_pct=round(max_dd, 4),
            win_rate=round(win_rate, 2),
            num_trades=num_trades,
            equity_curve=equity_curve,
            trades_log=trades_log,
        )


# ── Stat helpers ───────────────────────────────────────────────────────────────

def _sharpe(equity_curve: list[float], risk_free: float = 0.0) -> float:
    if len(equity_curve) < 2:
        return 0.0
    returns = [(equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1] for i in range(1, len(equity_curve))]
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
    std_r = math.sqrt(variance)
    if std_r == 0:
        return 0.0
    return (mean_r - risk_free / 252) / std_r * math.sqrt(252)


def _max_drawdown(equity_curve: list[float]) -> float:
    """Return max drawdown as a positive percentage (e.g. 15.0 = 15 %)."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    max_dd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak * 100.0 if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd
