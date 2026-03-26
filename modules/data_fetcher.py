"""
modules/data_fetcher.py — Polymarket Data Fetcher.

Fetches live market data from:
* Gamma API  — ``https://gamma-api.polymarket.com``
* CLOB API   — ``https://clob.polymarket.com``

Features
--------
* Pagination helpers (``get_markets``, ``search_markets``).
* Single-market and order-book lookups.
* Recent-trade and price-history retrieval.
* TTL caching via :mod:`cachetools`.
* Exponential-backoff retry logic on transient HTTP errors.
* All responses are modelled as Pydantic v2 dataclasses.
"""

from __future__ import annotations

import time
from typing import Any

import requests
from cachetools import TTLCache, cached
from pydantic import BaseModel, Field

import config
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Internal HTTP session
# ---------------------------------------------------------------------------
_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})

# ---------------------------------------------------------------------------
# Caches (key → response)
# ---------------------------------------------------------------------------
_markets_cache: TTLCache[str, Any] = TTLCache(
    maxsize=256, ttl=config.CACHE_TTL_SECONDS
)
_orderbook_cache: TTLCache[str, Any] = TTLCache(
    maxsize=256, ttl=30  # order books are short-lived
)
_trades_cache: TTLCache[str, Any] = TTLCache(
    maxsize=256, ttl=60
)
_history_cache: TTLCache[str, Any] = TTLCache(
    maxsize=128, ttl=config.CACHE_TTL_SECONDS
)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class Market(BaseModel):
    """Represents a single Polymarket prediction market."""

    id: str
    condition_id: str = Field(default="", alias="conditionId")
    question: str = ""
    description: str = ""
    active: bool = True
    volume: float = 0.0
    volume_24h: float = Field(default=0.0, alias="volume24hr")
    liquidity: float = 0.0
    outcome_prices: list[float] = Field(default_factory=list)
    end_date: str = ""

    model_config = {"populate_by_name": True}


class OrderBookLevel(BaseModel):
    """A single price level in an order book."""

    price: float
    size: float


class OrderBook(BaseModel):
    """Live order book for a market token."""

    token_id: str
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)


class Trade(BaseModel):
    """A single executed trade."""

    trade_id: str = Field(default="", alias="id")
    price: float = 0.0
    size: float = 0.0
    side: str = ""
    timestamp: int = 0

    model_config = {"populate_by_name": True}


class PricePoint(BaseModel):
    """A historical price observation."""

    timestamp: int
    price: float


# ---------------------------------------------------------------------------
# Low-level HTTP helper
# ---------------------------------------------------------------------------
def _get(
    url: str,
    params: dict[str, Any] | None = None,
    retries: int = 3,
    backoff: float = 1.0,
) -> Any:
    """Perform a GET request with exponential-backoff retry logic.

    Args:
        url: Full URL to request.
        params: Optional query-string parameters.
        retries: Maximum number of attempts.
        backoff: Initial backoff interval in seconds (doubles each retry).

    Returns:
        Parsed JSON response.

    Raises:
        requests.HTTPError: After all retries are exhausted.
    """
    headers: dict[str, str] = {}
    if config.POLYMARKET_API_KEY:
        headers["Authorization"] = f"Bearer {config.POLYMARKET_API_KEY}"

    wait = backoff
    for attempt in range(1, retries + 1):
        try:
            resp = _SESSION.get(url, params=params, headers=headers, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            # Do not retry client errors (except 429 rate-limit)
            if status != 429 and 400 <= status < 500:
                logger.error("HTTP %s for %s — not retrying", status, url)
                raise
            logger.warning(
                "HTTP %s on attempt %d/%d for %s — retrying in %.1fs",
                status,
                attempt,
                retries,
                url,
                wait,
            )
        except requests.RequestException as exc:
            logger.warning(
                "Request error on attempt %d/%d for %s: %s",
                attempt,
                retries,
                url,
                exc,
            )
        if attempt < retries:
            time.sleep(wait)
            wait *= 2
    # Final attempt (no sleep)
    resp = _SESSION.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_markets(
    limit: int = 20,
    offset: int = 0,
    active_only: bool = True,
) -> list[Market]:
    """Fetch a paginated list of Polymarket markets.

    Args:
        limit: Number of markets to return (max 100).
        offset: Pagination offset.
        active_only: When *True* only return markets that are still active.

    Returns:
        List of :class:`Market` objects.
    """
    cache_key = f"markets:{limit}:{offset}:{active_only}"
    if cache_key in _markets_cache:
        return _markets_cache[cache_key]  # type: ignore[return-value]

    params: dict[str, Any] = {
        "limit": min(limit, 100),
        "offset": offset,
        "order": "volume",
        "ascending": "false",
    }
    if active_only:
        params["closed"] = "false"

    url = f"{config.GAMMA_API_BASE}/markets"
    logger.debug("Fetching markets: %s", params)
    raw = _get(url, params=params)

    if isinstance(raw, dict):
        raw = raw.get("results", raw.get("markets", [raw]))

    markets: list[Market] = []
    for item in raw:
        try:
            m = Market.model_validate(item)
            # Parse outcome prices from JSON-encoded string if needed
            if not m.outcome_prices and isinstance(
                item.get("outcomePrices"), str
            ):
                import json as _json

                try:
                    m.outcome_prices = [
                        float(p) for p in _json.loads(item["outcomePrices"])
                    ]
                except Exception:
                    pass
            markets.append(m)
        except Exception as exc:
            logger.warning("Skipping malformed market entry: %s", exc)

    _markets_cache[cache_key] = markets
    return markets


def get_market_by_id(market_id: str) -> Market | None:
    """Fetch a specific market by its condition ID.

    Args:
        market_id: Polymarket condition ID.

    Returns:
        :class:`Market` object, or *None* if not found.
    """
    cache_key = f"market:{market_id}"
    if cache_key in _markets_cache:
        return _markets_cache[cache_key]  # type: ignore[return-value]

    url = f"{config.GAMMA_API_BASE}/markets/{market_id}"
    logger.debug("Fetching market by id: %s", market_id)
    try:
        raw = _get(url)
        if isinstance(raw, list):
            raw = raw[0] if raw else None
        if raw is None:
            return None
        market = Market.model_validate(raw)
        _markets_cache[cache_key] = market
        return market
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            logger.info("Market %s not found", market_id)
            return None
        raise


def get_market_orderbook(token_id: str) -> OrderBook:
    """Fetch the live order book for a market token.

    Args:
        token_id: CLOB token ID for the YES or NO side.

    Returns:
        :class:`OrderBook` with current bids and asks.
    """
    cache_key = f"book:{token_id}"
    if cache_key in _orderbook_cache:
        return _orderbook_cache[cache_key]  # type: ignore[return-value]

    url = f"{config.CLOB_API_BASE}/book"
    logger.debug("Fetching order book for token: %s", token_id)
    raw = _get(url, params={"token_id": token_id})

    def _parse_levels(items: list[Any]) -> list[OrderBookLevel]:
        levels = []
        for item in items:
            try:
                levels.append(
                    OrderBookLevel(
                        price=float(item.get("price", 0)),
                        size=float(item.get("size", 0)),
                    )
                )
            except Exception:
                pass
        return levels

    book = OrderBook(
        token_id=token_id,
        bids=_parse_levels(raw.get("bids", [])),
        asks=_parse_levels(raw.get("asks", [])),
    )
    _orderbook_cache[cache_key] = book
    return book


def get_market_trades(market_id: str, limit: int = 50) -> list[Trade]:
    """Fetch recent trades for a market.

    Args:
        market_id: Polymarket condition ID.
        limit: Number of recent trades to fetch.

    Returns:
        List of :class:`Trade` objects ordered newest first.
    """
    cache_key = f"trades:{market_id}:{limit}"
    if cache_key in _trades_cache:
        return _trades_cache[cache_key]  # type: ignore[return-value]

    url = f"{config.CLOB_API_BASE}/trades"
    logger.debug("Fetching trades for market: %s", market_id)
    raw = _get(url, params={"market": market_id, "limit": limit})

    if isinstance(raw, dict):
        raw = raw.get("data", raw.get("trades", []))

    trades: list[Trade] = []
    for item in raw:
        try:
            trades.append(Trade.model_validate(item))
        except Exception as exc:
            logger.warning("Skipping malformed trade: %s", exc)

    _trades_cache[cache_key] = trades
    return trades


def get_market_price_history(market_id: str) -> list[PricePoint]:
    """Fetch historical price data for a market.

    Args:
        market_id: Polymarket condition ID.

    Returns:
        List of :class:`PricePoint` objects ordered oldest first.
    """
    cache_key = f"history:{market_id}"
    if cache_key in _history_cache:
        return _history_cache[cache_key]  # type: ignore[return-value]

    url = f"{config.GAMMA_API_BASE}/markets/{market_id}/history"
    logger.debug("Fetching price history for market: %s", market_id)
    try:
        raw = _get(url)
    except requests.HTTPError:
        # Fall back to the timeseries endpoint
        url = f"{config.CLOB_API_BASE}/prices-history"
        raw = _get(url, params={"market": market_id, "interval": "max"})

    if isinstance(raw, dict):
        raw = raw.get("history", raw.get("prices", []))

    history: list[PricePoint] = []
    for item in raw:
        try:
            ts = int(item.get("t", item.get("timestamp", 0)))
            price = float(item.get("p", item.get("price", 0)))
            history.append(PricePoint(timestamp=ts, price=price))
        except Exception as exc:
            logger.warning("Skipping malformed price point: %s", exc)

    history.sort(key=lambda x: x.timestamp)
    _history_cache[cache_key] = history
    return history


def search_markets(query: str) -> list[Market]:
    """Search for markets by keyword.

    Args:
        query: Search string matched against market questions / descriptions.

    Returns:
        List of matching :class:`Market` objects.
    """
    cache_key = f"search:{query.lower()}"
    if cache_key in _markets_cache:
        return _markets_cache[cache_key]  # type: ignore[return-value]

    url = f"{config.GAMMA_API_BASE}/markets"
    params: dict[str, Any] = {
        "search": query,
        "limit": 50,
        "order": "volume",
        "ascending": "false",
    }
    logger.debug("Searching markets for: '%s'", query)
    raw = _get(url, params=params)

    if isinstance(raw, dict):
        raw = raw.get("results", raw.get("markets", [raw]))

    markets: list[Market] = []
    for item in raw:
        try:
            markets.append(Market.model_validate(item))
        except Exception as exc:
            logger.warning("Skipping malformed market in search: %s", exc)

    _markets_cache[cache_key] = markets
    return markets
