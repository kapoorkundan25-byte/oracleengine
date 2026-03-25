"""
dashboard/display.py — Rich CLI dashboard for Polymarket analytics.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import config
from analytics.backtester import BacktestResult
from polymarket.models import Market

console = Console()


class Dashboard:
    """
    Renders a live Rich CLI dashboard.

    Parameters
    ----------
    refresh_seconds:
        How often to refresh the display (default: from config).
    """

    def __init__(
        self,
        refresh_seconds: int = config.DASHBOARD_REFRESH_SECONDS,
    ) -> None:
        self.refresh_seconds = refresh_seconds

    # ── rendering helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _signal_color(signal: str) -> str:
        mapping = {
            "BULLISH": "green",
            "OVERSOLD": "bright_green",
            "BEARISH": "red",
            "OVERBOUGHT": "bright_red",
            "NEUTRAL": "yellow",
            "STRONG_BUY": "bold green",
            "STRONG_SELL": "bold red",
            "LEAN_BUY": "cyan",
            "LEAN_SELL": "magenta",
        }
        return mapping.get(signal.upper(), "white")

    def _markets_table(self, markets: list[Market]) -> Table:
        table = Table(title="📊 Top Markets by Volume", expand=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Market", style="bold white", no_wrap=False, min_width=40)
        table.add_column("YES", justify="right", style="green")
        table.add_column("NO", justify="right", style="red")
        table.add_column("Volume", justify="right")
        table.add_column("Liquidity", justify="right")
        table.add_column("Trend", justify="center")
        table.add_column("Sentiment", justify="center")

        for i, m in enumerate(markets[:10], start=1):
            trend = m.trend_signal or "—"
            sentiment = m.sentiment_label or "—"
            t_color = self._signal_color(trend)
            s_color = self._signal_color(sentiment)
            table.add_row(
                str(i),
                m.question[:70],
                f"{m.yes_price:.3f}",
                f"{m.no_price:.3f}",
                f"${m.volume:,.0f}",
                f"${m.liquidity:,.0f}",
                Text(trend, style=t_color),
                Text(sentiment, style=s_color),
            )
        return table

    @staticmethod
    def _alerts_panel(alerts: list[str]) -> Panel:
        if not alerts:
            body = Text("No active alerts.", style="dim")
        else:
            body = Text("\n".join(f"🔔 {a}" for a in alerts[-10:]), style="yellow")
        return Panel(body, title="🔔 Active Alerts", border_style="yellow")

    @staticmethod
    def _portfolio_panel(result: Optional[BacktestResult]) -> Panel:
        if result is None:
            body = Text("No backtest results available.", style="dim")
        else:
            body = Text(
                f"Return: {result.total_return_pct:+.2f}%\n"
                f"Sharpe: {result.sharpe_ratio:.2f}\n"
                f"Max Drawdown: {result.max_drawdown_pct:.2f}%\n"
                f"Win Rate: {result.win_rate:.1f}%  ({result.num_trades} trades)",
                style="cyan",
            )
        return Panel(body, title="💼 Portfolio / Backtest Summary", border_style="blue")

    @staticmethod
    def _footer() -> Text:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return Text(f"Last updated: {ts}", style="dim")

    # ── public API ─────────────────────────────────────────────────────────────

    def render_once(
        self,
        markets: list[Market],
        alerts: Optional[list[str]] = None,
        backtest_result: Optional[BacktestResult] = None,
    ) -> None:
        """Print a single snapshot of the dashboard to stdout."""
        console.print(self._markets_table(markets))
        console.print(self._alerts_panel(alerts or []))
        console.print(self._portfolio_panel(backtest_result))
        console.print(self._footer())

    def render_market_detail(self, market: Market, trend_report=None, sentiment_report=None) -> None:
        """Print detailed view for a single market."""
        console.rule(f"[bold cyan]{market.question}")
        console.print(f"  Slug          : [dim]{market.slug}[/dim]")
        console.print(f"  Condition ID  : [dim]{market.condition_id}[/dim]")
        console.print(f"  End Date      : {market.end_date}")
        console.print(f"  YES Price     : [green]{market.yes_price:.4f}[/green]")
        console.print(f"  NO  Price     : [red]{market.no_price:.4f}[/red]")
        console.print(f"  Volume        : ${market.volume:,.0f}")
        console.print(f"  Liquidity     : ${market.liquidity:,.0f}")

        if trend_report:
            console.print()
            console.rule("[cyan]Trend Analysis")
            console.print(f"  Signal  : [{self._signal_color(trend_report.signal)}]{trend_report.signal}[/]")
            if trend_report.sma_20 is not None:
                console.print(f"  SMA-20  : {trend_report.sma_20:.4f}")
            if trend_report.rsi_14 is not None:
                console.print(f"  RSI-14  : {trend_report.rsi_14:.1f}")
            if trend_report.bb_upper is not None:
                console.print(
                    f"  BB      : {trend_report.bb_lower:.4f} — {trend_report.bb_upper:.4f}"
                )
            if trend_report.vwap_value is not None:
                console.print(f"  VWAP    : {trend_report.vwap_value:.4f}")

        if sentiment_report:
            console.print()
            console.rule("[magenta]Sentiment")
            s_color = self._signal_color(sentiment_report.label)
            console.print(f"  Label   : [{s_color}]{sentiment_report.label}[/]")
            console.print(f"  Score   : {sentiment_report.score:+.4f}  ({sentiment_report.article_count} articles)")
            for h in sentiment_report.headlines:
                console.print(f"  • {h[:100]}")

    async def run_live(
        self,
        fetch_callback,
        alerts: Optional[list[str]] = None,
        backtest_result: Optional[BacktestResult] = None,
    ) -> None:
        """
        Continuously refresh the dashboard every *refresh_seconds*.

        *fetch_callback* is an ``async`` callable returning ``list[Market]``.
        Press Ctrl-C to stop.
        """
        try:
            while True:
                markets = await fetch_callback()
                self.render_once(markets, alerts, backtest_result)
                await asyncio.sleep(self.refresh_seconds)
        except KeyboardInterrupt:
            console.print("\n[dim]Dashboard stopped.[/dim]")
