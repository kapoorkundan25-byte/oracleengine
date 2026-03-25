"""
main.py — CLI entry point for OracleEngine.

Usage
-----
::

    python main.py fetch    --limit 10
    python main.py analyze  --market-id <condition_id>
    python main.py backtest --market-id <condition_id> --strategy momentum
    python main.py sentiment --market-id <condition_id> --query "bitcoin ETF"
    python main.py monitor  --interval 60

Run ``python main.py --help`` or ``python main.py <command> --help`` for
full option reference.
"""

from __future__ import annotations

import argparse
import sys

from utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------
def cmd_fetch(args: argparse.Namespace) -> None:
    """Fetch and display live market data."""
    from modules.data_fetcher import get_markets, search_markets
    from utils.helpers import format_currency, format_percentage

    if args.query:
        logger.info("Searching markets for: '%s'", args.query)
        markets = search_markets(args.query)
    else:
        logger.info("Fetching top %d markets…", args.limit)
        markets = get_markets(limit=args.limit, active_only=not args.all)

    if not markets:
        print("No markets found.")
        return

    print(f"\n{'─'*80}")
    print(f"  {'ID':<12}  {'Question':<45}  {'Price':>7}  {'Vol 24h':>12}")
    print(f"{'─'*80}")
    for m in markets:
        price = m.outcome_prices[0] if m.outcome_prices else 0.0
        print(
            f"  {m.id[:12]:<12}  {m.question[:45]:<45}  "
            f"{format_percentage(price):>7}  {format_currency(m.volume_24h):>12}"
        )
    print(f"{'─'*80}\n")


def cmd_analyze(args: argparse.Namespace) -> None:
    """Run trend analysis on a market."""
    from modules.data_fetcher import get_market_price_history, get_market_trades
    from modules.trend_analyzer import get_market_summary

    logger.info("Analyzing market: %s", args.market_id)
    try:
        history = get_market_price_history(args.market_id)
        trades = get_market_trades(args.market_id)
        prices = [p.price for p in history]
        trade_dicts = [{"size": t.size, "price": t.price} for t in trades]

        if not prices:
            print(f"No price history found for market {args.market_id!r}")
            return

        summary = get_market_summary(args.market_id, prices, trade_dicts)

        print(f"\n{'─'*60}")
        print(f"  Market Analysis: {args.market_id}")
        print(f"{'─'*60}")
        for key, value in summary.items():
            if key == "breakout":
                print(f"  {'breakout':<20}: {value}")
            elif key == "volume":
                print(f"  {'volume':<20}: {value}")
            elif isinstance(value, float):
                print(f"  {key:<20}: {value:.4f}")
            else:
                print(f"  {key:<20}: {value}")
        print(f"{'─'*60}\n")
    except Exception as exc:
        logger.error("Analysis failed: %s", exc)
        sys.exit(1)


def cmd_backtest(args: argparse.Namespace) -> None:
    """Run backtesting on a strategy."""
    from datetime import datetime, timezone

    from modules.backtester import (
        Backtester,
        BreakoutStrategy,
        MomentumStrategy,
        RSIMeanReversionStrategy,
    )

    strategy_map = {
        "momentum": MomentumStrategy(),
        "rsi": RSIMeanReversionStrategy(),
        "breakout": BreakoutStrategy(),
    }

    strategy = strategy_map.get(args.strategy.lower())
    if strategy is None:
        print(f"Unknown strategy '{args.strategy}'. Choose from: {list(strategy_map)}")
        sys.exit(1)

    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc) if args.start else None
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc) if args.end else None

    bt = Backtester()
    try:
        result = bt.run(
            strategy=strategy,
            market_id=args.market_id,
            start_date=start,
            end_date=end,
            initial_capital=args.capital,
        )
        if args.plot:
            path = bt.plot_equity_curve(result)
            if path:
                print(f"Equity curve saved to: {path}")
    except Exception as exc:
        logger.error("Backtest failed: %s", exc)
        sys.exit(1)


def cmd_sentiment(args: argparse.Namespace) -> None:
    """Get sentiment report for a market."""
    from modules.sentiment_analyzer import get_market_sentiment_score

    logger.info("Fetching sentiment for market: %s", args.market_id)
    try:
        report = get_market_sentiment_score(args.market_id, query=args.query or "")

        print(f"\n{'─'*60}")
        print(f"  Sentiment Report: {args.market_id}")
        print(f"{'─'*60}")
        print(f"  Score    : {report.score:+.4f}")
        print(f"  Label    : {report.label}")
        print(f"  Generated: {report.timestamp.isoformat()}")
        if report.headlines:
            print(f"\n  Top Headlines:")
            for i, h in enumerate(report.headlines[:5], 1):
                print(f"    {i}. {h[:75]}")
        print(f"{'─'*60}\n")
    except Exception as exc:
        logger.error("Sentiment analysis failed: %s", exc)
        sys.exit(1)


def cmd_monitor(args: argparse.Namespace) -> None:
    """Start alert monitoring daemon."""
    import signal

    from modules.alert_system import AlertManager

    manager = AlertManager()
    active = manager.get_active_alerts()
    if not active:
        print(
            "No alerts configured. Add alerts programmatically via AlertManager.add_alert()."
        )
        return

    print(f"Starting monitoring with {len(active)} active alert(s). Press Ctrl+C to stop.")
    manager.start_monitoring(interval_seconds=args.interval)

    def _shutdown(sig: int, frame: object) -> None:  # noqa: ANN001
        print("\nStopping monitor…")
        manager.stop_monitoring()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Block main thread
    import time

    while True:
        time.sleep(1)


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="oracleengine",
        description="OracleEngine — Polymarket Analytics & Research Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py fetch --limit 20
  python main.py fetch --query "bitcoin"
  python main.py analyze --market-id 0xabc123
  python main.py backtest --market-id 0xabc123 --strategy momentum --capital 1000
  python main.py sentiment --market-id 0xabc123 --query "bitcoin ETF"
  python main.py monitor --interval 60
        """,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # fetch
    p_fetch = sub.add_parser("fetch", help="Fetch and display live market data")
    p_fetch.add_argument("--limit", type=int, default=20, help="Number of markets to fetch")
    p_fetch.add_argument("--query", default="", help="Search markets by keyword")
    p_fetch.add_argument("--all", action="store_true", help="Include closed markets")

    # analyze
    p_analyze = sub.add_parser("analyze", help="Run trend analysis on a market")
    p_analyze.add_argument("--market-id", required=True, dest="market_id", help="Condition ID")

    # backtest
    p_bt = sub.add_parser("backtest", help="Run backtesting on a strategy")
    p_bt.add_argument("--market-id", required=True, dest="market_id")
    p_bt.add_argument(
        "--strategy",
        default="momentum",
        choices=["momentum", "rsi", "breakout"],
        help="Strategy to test",
    )
    p_bt.add_argument("--start", default="", help="Start date ISO-8601 (e.g. 2024-01-01)")
    p_bt.add_argument("--end", default="", help="End date ISO-8601")
    p_bt.add_argument("--capital", type=float, default=1000.0, help="Initial capital in USD")
    p_bt.add_argument("--plot", action="store_true", help="Save equity curve PNG")

    # sentiment
    p_sent = sub.add_parser("sentiment", help="Get sentiment report for a market")
    p_sent.add_argument("--market-id", required=True, dest="market_id")
    p_sent.add_argument("--query", default="", help="Override search query")

    # monitor
    p_mon = sub.add_parser("monitor", help="Start alert monitoring daemon")
    p_mon.add_argument(
        "--interval", type=int, default=60, help="Polling interval in seconds"
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Parse CLI arguments and dispatch to the appropriate handler."""
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "fetch": cmd_fetch,
        "analyze": cmd_analyze,
        "backtest": cmd_backtest,
        "sentiment": cmd_sentiment,
        "monitor": cmd_monitor,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    handler(args)


if __name__ == "__main__":
    main()
