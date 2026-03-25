"""
config.py — Centralised configuration loaded from environment / .env file.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env if present (does nothing if absent)
load_dotenv(Path(__file__).parent / ".env", override=False)

# ── Polymarket endpoints ───────────────────────────────────────────────────────
GAMMA_BASE: str = os.getenv("POLYMARKET_GAMMA_BASE", "https://gamma-api.polymarket.com")
CLOB_BASE: str = os.getenv("POLYMARKET_CLOB_BASE", "https://clob.polymarket.com")

# ── NewsAPI ────────────────────────────────────────────────────────────────────
NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")

# ── Alerts ─────────────────────────────────────────────────────────────────────
WEBHOOK_URL: str = os.getenv("WEBHOOK_URL", "")
ALERT_COOLDOWN_SECONDS: int = int(os.getenv("ALERT_COOLDOWN_SECONDS", "600"))
ALERTS_LOG_FILE: str = os.getenv("ALERTS_LOG_FILE", "alerts.log")

# ── Dashboard ──────────────────────────────────────────────────────────────────
DASHBOARD_REFRESH_SECONDS: int = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "60"))

# ── HTTP / Cache ───────────────────────────────────────────────────────────────
CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "60"))
HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "15"))
HTTP_MAX_RETRIES: int = int(os.getenv("HTTP_MAX_RETRIES", "3"))

# ── Backtesting defaults ───────────────────────────────────────────────────────
BACKTEST_STARTING_CAPITAL: float = float(os.getenv("BACKTEST_STARTING_CAPITAL", "1000"))
BACKTEST_TRANSACTION_FEE: float = float(os.getenv("BACKTEST_TRANSACTION_FEE", "0.005"))
