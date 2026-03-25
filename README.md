# 🔮 OracleEngine — Polymarket Analytics & Research Platform

> ⚠️ **Disclaimer**: OracleEngine is for **educational and research purposes only**.
> Prediction markets carry real financial risk — never invest more than you can afford
> to lose entirely. Nothing in this tool constitutes financial advice.

---

## 📖 Overview

OracleEngine is a production-quality Python platform for analysing
[Polymarket](https://polymarket.com) prediction markets. It provides five
integrated modules covering live data fetching, technical analysis, intelligent
alerts, historical back-testing, and news-sentiment scoring.

---

## ✨ Feature Overview

| Module | File | Description |
|---|---|---|
| 📊 Data Fetcher | `modules/data_fetcher.py` | Live markets, order books, trades & price history via Polymarket APIs |
| 📈 Trend Analyzer | `modules/trend_analyzer.py` | RSI, SMA/EMA, momentum, volatility, breakout detection |
| 🔔 Alert System | `modules/alert_system.py` | Background polling with webhook, e-mail, and console notifications |
| 📉 Backtester | `modules/backtester.py` | Strategy simulation: Sharpe ratio, max drawdown, equity-curve chart |
| 🧠 Sentiment Analyzer | `modules/sentiment_analyzer.py` | VADER sentiment + NewsAPI + price correlation |

---

## 🏗️ Architecture

```
oracleengine/
├── main.py                   ← CLI entry point (argparse)
├── config.py                 ← Environment-based configuration
├── requirements.txt
├── .env.example
│
├── modules/
│   ├── data_fetcher.py       ← Polymarket REST API wrapper (Gamma + CLOB)
│   ├── trend_analyzer.py     ← pandas/numpy technical indicators
│   ├── alert_system.py       ← Background thread alert manager
│   ├── backtester.py         ← Strategy simulation engine
│   └── sentiment_analyzer.py ← VADER + NewsAPI sentiment scoring
│
├── utils/
│   ├── logger.py             ← Colour console + rotating file logger
│   └── helpers.py            ← Format helpers + list chunking
│
└── tests/
    ├── test_data_fetcher.py
    ├── test_trend_analyzer.py
    ├── test_backtester.py
    └── test_sentiment_analyzer.py
```

```
┌─────────────┐   REST/JSON    ┌──────────────────────────┐
│  Polymarket │ ◄────────────► │  data_fetcher.py         │
│  Gamma API  │                │  (TTL cache + retry)      │
│  CLOB API   │                └──────────┬───────────────┘
└─────────────┘                           │
                                          │ price series / trades
              ┌───────────────────────────┼──────────────────────┐
              ▼                           ▼                      ▼
    ┌──────────────────┐    ┌──────────────────────┐  ┌─────────────────────┐
    │ trend_analyzer   │    │ backtester           │  │ sentiment_analyzer  │
    │ RSI / SMA / EMA  │    │ Strategy → signals   │  │ VADER + NewsAPI     │
    │ momentum / vol   │    │ equity curve / stats │  │ Pearson correlation │
    └──────────────────┘    └──────────────────────┘  └─────────────────────┘
              │                                                  │
              └──────────────────────┬───────────────────────────┘
                                     ▼
                          ┌────────────────────┐
                          │  alert_system      │
                          │  AlertManager      │
                          │  (background thread│
                          │   + JSON persist)  │
                          └────────────────────┘
                                     │
                          ┌──────────┴─────────┐
                          │ console / webhook  │
                          │ / e-mail callbacks │
                          └────────────────────┘
```

---

## 🚀 Installation

### Prerequisites

* Python 3.10 or later
* A [NewsAPI](https://newsapi.org) key (free tier available) for sentiment analysis

```bash
# 1. Clone the repository
git clone https://github.com/kapoorkundan25-byte/oracleengine.git
cd oracleengine

# 2. (Recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## ⚙️ Configuration

Copy the example file and fill in your secrets:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `POLYMARKET_API_KEY` | No | Bearer token for authenticated endpoints (most are public) |
| `NEWS_API_KEY` | Yes (sentiment) | [newsapi.org](https://newsapi.org) key |
| `SMTP_HOST` | No | SMTP server hostname for e-mail alerts |
| `SMTP_PORT` | No | SMTP port (default 587) |
| `SMTP_USER` | No | SMTP login username / sender address |
| `SMTP_PASS` | No | SMTP password or app-password |
| `ALERT_WEBHOOK_URL` | No | Slack / Discord webhook for alert notifications |
| `LOG_LEVEL` | No | `DEBUG` / `INFO` / `WARNING` / `ERROR` (default `INFO`) |
| `CACHE_TTL_SECONDS` | No | API response cache duration in seconds (default 300) |

---

## 💻 CLI Usage

```
python main.py <command> [options]
python main.py --help
```

### `fetch` — Live market data

```bash
# Top 20 active markets by volume
python main.py fetch --limit 20

# Search for specific markets
python main.py fetch --query "bitcoin"

# Include closed markets
python main.py fetch --limit 10 --all
```

### `analyze` — Trend analysis

```bash
python main.py analyze --market-id 0xabc123def456...
```

Output includes: momentum signal, RSI, volatility, SMA/EMA crossover, breakout
detection, and an overall `BULLISH` / `BEARISH` / `NEUTRAL` signal.

### `backtest` — Strategy back-testing

```bash
# Test Momentum strategy with default $1,000 capital
python main.py backtest --market-id 0xabc123 --strategy momentum

# RSI mean-reversion with custom capital and date range
python main.py backtest \
    --market-id 0xabc123 \
    --strategy rsi \
    --start 2024-01-01 \
    --end 2024-06-30 \
    --capital 5000

# Save equity curve chart
python main.py backtest --market-id 0xabc123 --strategy breakout --plot
```

Available strategies: `momentum`, `rsi`, `breakout`

### `sentiment` — News sentiment report

```bash
python main.py sentiment --market-id 0xabc123

# Override the search query (defaults to market question)
python main.py sentiment --market-id 0xabc123 --query "bitcoin ETF approval"
```

### `monitor` — Alert daemon

```bash
# Start monitoring every 60 seconds (Ctrl+C to stop)
python main.py monitor --interval 60
```

Configure alerts programmatically before starting the daemon:

```python
from modules.alert_system import AlertManager, AlertCondition, webhook_callback

mgr = AlertManager()
mgr.add_alert(AlertCondition(
    market_id="0xabc123",
    condition_type="PRICE_ABOVE",
    threshold=0.80,
    callback=webhook_callback("https://hooks.slack.com/..."),
))
```

---

## 📚 Module API Reference

### `modules.data_fetcher`

```python
from modules.data_fetcher import (
    get_markets,               # list[Market]
    get_market_by_id,          # Market | None
    get_market_orderbook,      # OrderBook
    get_market_trades,         # list[Trade]
    get_market_price_history,  # list[PricePoint]
    search_markets,            # list[Market]
)
```

### `modules.trend_analyzer`

```python
from modules.trend_analyzer import (
    calculate_price_momentum,  # pd.Series
    calculate_volume_trend,    # dict
    detect_price_breakout,     # dict
    calculate_volatility,      # pd.Series
    calculate_rsi,             # pd.Series
    calculate_moving_averages, # dict[str, pd.Series]
    get_market_summary,        # dict  (BULLISH / BEARISH / NEUTRAL)
)
```

### `modules.alert_system`

```python
from modules.alert_system import (
    AlertCondition,  # dataclass
    AlertManager,    # class
    console_callback,
    webhook_callback,
    email_callback,
)
```

### `modules.backtester`

```python
from modules.backtester import (
    Signal,                    # BUY / SELL / HOLD
    Strategy,                  # ABC
    MomentumStrategy,
    RSIMeanReversionStrategy,
    BreakoutStrategy,
    BacktestResult,            # frozen dataclass
    Backtester,
)
```

### `modules.sentiment_analyzer`

```python
from modules.sentiment_analyzer import (
    SentimentReport,
    fetch_news_headlines,
    analyze_sentiment,
    get_market_sentiment_score,
    correlate_sentiment_with_price,
)
```

---

## 🧪 Running Tests

```bash
# All tests
pytest tests/ -v

# Individual suites
pytest tests/test_data_fetcher.py -v
pytest tests/test_trend_analyzer.py -v
pytest tests/test_backtester.py -v
pytest tests/test_sentiment_analyzer.py -v
```

All external HTTP calls are mocked — no API keys are required to run the tests.

---

## 📋 Requirements

See [requirements.txt](requirements.txt).

Key dependencies:

| Package | Purpose |
|---|---|
| `requests` | HTTP client for Polymarket + NewsAPI |
| `pandas` / `numpy` | Numerical computation for indicators |
| `pydantic` | Typed data models for API responses |
| `vaderSentiment` | Rule-based sentiment scoring |
| `cachetools` | TTL caching for API responses |
| `matplotlib` | Equity-curve charting |
| `python-dotenv` | `.env` file loading |
| `newsapi-python` | Official NewsAPI client |

---

## ⚠️ Disclaimer

OracleEngine is a **research and educational tool**.

* Polymarket involves real financial risk — you can lose everything you invest.
* Prediction markets are zero-sum games; for every winner there is a loser.
* Past back-test performance does not guarantee future results.
* Automated trading bots may violate Polymarket's Terms of Service.
* Consult a qualified financial adviser before making any investment decisions.
* The authors accept no liability for financial losses arising from use of this software.
