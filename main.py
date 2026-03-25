"""
main.py — CLI entry point for the Polymarket Analytics & Research Engine.

Commands
--------
python main.py fetch                        Fetch & display top markets
python main.py analyze --market <slug>      Deep analysis on a single market
python main.py backtest --market <slug>     Run backtesting on a market
python main.py sentiment --query <text>     Sentiment analysis for a query
python main.py alerts                       Show configured alert rules / fire test
python main.py dashboard                    Start the live-updating dashboard
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys

import typer
from rich.console import Console

import config

app = typer.Typer(
    name="oracleengine",
    help="Polymarket Analytics & Research Engine",
    add_completion=False,
)
console = Console()

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


# ── fetch ──────────────────────────────────────────────────────────────────────

@app.command()
def fetch(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of markets to fetch"),
    order: str = typer.Option("volume", "--order", help="Sort field (volume, liquidity)"),
) -> None:
    """Fetch and display top Polymarket markets."""

    async def _run() -> None:
        from polymarket.client import PolymarketClient
        from dashboard.display import Dashboard

        console.print("[bold cyan]🔄 Fetching live Polymarket data…[/bold cyan]")
        async with PolymarketClient() as client:
            markets = await client.get_markets(limit=limit, order=order)

        if not markets:
            console.print("[red]No markets returned.[/red]")
            return

        console.print(f"[green]✓ Fetched {len(markets)} markets.[/green]")
        Dashboard().render_once(markets)

    asyncio.run(_run())


# ── analyze ────────────────────────────────────────────────────────────────────

@app.command()
def analyze(
    market: str = typer.Option(..., "--market", "-m", help="Market slug or keyword"),
    prices_json: str = typer.Option(
        "",
        "--prices",
        help="JSON list of historical YES prices (e.g. '[0.5,0.52,…]').  "
             "If omitted, only live price is used.",
    ),
) -> None:
    """Deep trend analysis for a market."""

    async def _run() -> None:
        from polymarket.client import PolymarketClient
        from analytics.trend_analyzer import TrendAnalyzer
        from dashboard.display import Dashboard

        console.print(f"[bold cyan]🔍 Analyzing market: {market}[/bold cyan]")
        async with PolymarketClient() as client:
            all_markets = await client.get_markets(limit=50)

        # match slug / keyword
        matched = [
            m for m in all_markets
            if market.lower() in (m.slug or "").lower() or market.lower() in m.question.lower()
        ]
        if not matched:
            console.print(f"[red]No market found matching '{market}'[/red]")
            return

        target = matched[0]
        console.print(f"[green]Matched: {target.question}[/green]")

        # parse prices
        prices: list[float] = []
        if prices_json:
            try:
                prices = [float(x) for x in json.loads(prices_json)]
            except Exception:
                console.print("[yellow]Could not parse --prices; using live price only.[/yellow]")

        if not prices:
            prices = [target.yes_price] * 20  # minimal synthetic series

        trend_report = TrendAnalyzer().analyze(prices)
        target.trend_signal = trend_report.signal
        Dashboard().render_market_detail(target, trend_report=trend_report)

    asyncio.run(_run())


# ── sentiment ──────────────────────────────────────────────────────────────────

@app.command()
def sentiment(
    query: str = typer.Argument(..., help="Topic / keyword to search news for"),
    use_transformers: bool = typer.Option(False, "--transformers", help="Use HuggingFace model"),
) -> None:
    """Run sentiment analysis for a news query."""
    from sentiment.sentiment_analyzer import SentimentAnalyzer
    from dashboard.display import Dashboard

    console.print(f"[bold cyan]📰 Fetching news sentiment for: {query}[/bold cyan]")
    analyzer = SentimentAnalyzer(use_transformers=use_transformers)
    report = analyzer.analyze(query)

    console.print(f"  Label   : {report.label}")
    console.print(f"  Score   : {report.score:+.4f}  ({report.article_count} articles)")
    for h in report.headlines:
        console.print(f"  • {h[:120]}")


# ── backtest ───────────────────────────────────────────────────────────────────

@app.command()
def backtest(
    strategy_name: str = typer.Option(
        "momentum",
        "--strategy",
        "-s",
        help="Strategy: momentum | meanreversion | breakout",
    ),
    candles_json: str = typer.Option(
        "",
        "--candles",
        help=(
            "JSON list of OHLCV dicts.  "
            "Each: {timestamp, open, high, low, close, volume}"
        ),
    ),
    capital: float = typer.Option(
        config.BACKTEST_STARTING_CAPITAL,
        "--capital",
        help="Starting capital in USD",
    ),
) -> None:
    """Run a backtest strategy on historical OHLCV data."""
    from analytics.backtester import (
        Backtester,
        MomentumStrategy,
        MeanReversionStrategy,
        BreakoutStrategy,
    )

    strategy_map = {
        "momentum": MomentumStrategy(),
        "meanreversion": MeanReversionStrategy(),
        "breakout": BreakoutStrategy(),
    }
    strat = strategy_map.get(strategy_name.lower())
    if strat is None:
        console.print(f"[red]Unknown strategy '{strategy_name}'. Choose: {list(strategy_map)}[/red]")
        raise typer.Exit(1)

    candles: list[dict] = []
    if candles_json:
        try:
            candles = json.loads(candles_json)
        except Exception:
            console.print("[red]Could not parse --candles JSON.[/red]")
            raise typer.Exit(1)

    if not candles:
        # Demo synthetic candles
        console.print("[yellow]No candles provided — running demo with synthetic data.[/yellow]")
        import math
        candles = [
            {
                "timestamp": i,
                "open": 0.5 + 0.01 * math.sin(i * 0.3),
                "high": 0.55 + 0.01 * math.sin(i * 0.3),
                "low": 0.45 + 0.01 * math.sin(i * 0.3),
                "close": 0.5 + 0.015 * math.sin(i * 0.3 + 0.5),
                "volume": 1000 + 100 * (i % 5),
            }
            for i in range(100)
        ]

    backtester = Backtester(strategy=strat, starting_capital=capital)
    result = backtester.run(candles)

    console.print("\n[bold cyan]📉 Backtest Results[/bold cyan]")
    console.print(f"  Strategy      : {strategy_name}")
    console.print(f"  Starting Cap  : ${capital:,.2f}")
    console.print(f"  Total Return  : [{'green' if result.total_return_pct >= 0 else 'red'}]{result.total_return_pct:+.2f}%[/]")
    console.print(f"  Sharpe Ratio  : {result.sharpe_ratio:.4f}")
    console.print(f"  Max Drawdown  : {result.max_drawdown_pct:.2f}%")
    console.print(f"  Win Rate      : {result.win_rate:.1f}%")
    console.print(f"  # Trades      : {result.num_trades}")


# ── alerts ─────────────────────────────────────────────────────────────────────

@app.command()
def alerts(
    market_id: str = typer.Option("demo", "--market-id", help="Market ID to test alerts on"),
    yes_price: float = typer.Option(0.75, "--yes-price", help="Simulated YES price"),
    rsi_val: float = typer.Option(72.0, "--rsi", help="Simulated RSI value"),
) -> None:
    """Demo the alert engine with sample rules."""
    from alerts.alert_engine import (
        AlertEngine,
        PriceAboveThreshold,
        PriceBelowThreshold,
        RSIAbove,
        RSIBelow,
    )

    engine = AlertEngine(
        rules=[
            PriceAboveThreshold(market_id=market_id, threshold=0.7),
            PriceBelowThreshold(market_id=market_id, threshold=0.2),
            RSIAbove(market_id=market_id, rsi_value=70.0),
            RSIBelow(market_id=market_id, rsi_value=30.0),
        ],
        cooldown_seconds=0,  # no cooldown for demo
    )

    data = {
        "market_id": market_id,
        "yes_price": yes_price,
        "rsi_14": rsi_val,
    }
    fired = engine.evaluate(data)
    if not fired:
        console.print("[dim]No alerts triggered with the provided values.[/dim]")
    else:
        console.print(f"[green]✓ {len(fired)} alert(s) fired.[/green]")


# ── dashboard ──────────────────────────────────────────────────────────────────

@app.command()
def dashboard(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of markets to show"),
    refresh: int = typer.Option(
        config.DASHBOARD_REFRESH_SECONDS, "--refresh", "-r", help="Refresh interval (seconds)"
    ),
) -> None:
    """Start the live-updating CLI dashboard."""

    async def _run() -> None:
        from polymarket.client import PolymarketClient
        from polymarket.models import Market
        from dashboard.display import Dashboard

        dash = Dashboard(refresh_seconds=refresh)

        async def _fetch() -> list[Market]:
            async with PolymarketClient() as client:
                return await client.get_markets(limit=limit)

        console.print(
            f"[bold cyan]🖥  Starting live dashboard (refresh every {refresh}s). "
            "Press Ctrl-C to stop.[/bold cyan]"
        )
        await dash.run_live(_fetch)

    asyncio.run(_run())


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
