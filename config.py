"""
config.py — Centralised configuration loaded from environment variables.

All secrets and tunable parameters are read from a ``.env`` file (or from
real environment variables in production).  Copy ``.env.example`` to ``.env``
and fill in your values before running the application.
"""

import os
from dotenv import load_dotenv

# Load .env file if present (silently ignored when not found)
load_dotenv()


def _get_int(key: str, default: int) -> int:
    """Return an env variable cast to int, falling back to *default*."""
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# ---------------------------------------------------------------------------
# Polymarket / CLOB
# ---------------------------------------------------------------------------
POLYMARKET_API_KEY: str = os.getenv("POLYMARKET_API_KEY", "")
GAMMA_API_BASE: str = "https://gamma-api.polymarket.com"
CLOB_API_BASE: str = "https://clob.polymarket.com"

# ---------------------------------------------------------------------------
# News API
# ---------------------------------------------------------------------------
NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")

# ---------------------------------------------------------------------------
# SMTP (email alerts)
# ---------------------------------------------------------------------------
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = _get_int("SMTP_PORT", 587)
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASS: str = os.getenv("SMTP_PASS", "")

# ---------------------------------------------------------------------------
# Webhook alerts
# ---------------------------------------------------------------------------
ALERT_WEBHOOK_URL: str = os.getenv("ALERT_WEBHOOK_URL", "")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------
CACHE_TTL_SECONDS: int = _get_int("CACHE_TTL_SECONDS", 300)
SENTIMENT_CACHE_TTL: int = 900  # 15 minutes — not user-configurable

# ---------------------------------------------------------------------------
# Backtesting defaults
# ---------------------------------------------------------------------------
DEFAULT_INITIAL_CAPITAL: float = 1_000.0
DEFAULT_SLIPPAGE: float = 0.02   # 2 %
DEFAULT_FEE: float = 0.01        # 1 % per trade
