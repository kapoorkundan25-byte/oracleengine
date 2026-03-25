"""
polymarket/client.py — Async Polymarket API client with retry + TTL cache.

Public endpoints used:
  Gamma API  : https://gamma-api.polymarket.com
  CLOB  API  : https://clob.polymarket.com
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

import httpx
from cachetools import TTLCache

import config
from polymarket.models import Market, OrderBook, PriceLevel, Trade, MarketResolution
from polymarket.utils import safe_float, parse_outcome_prices, extract_token_ids

logger = logging.getLogger(__name__)

_MARKET_CACHE: TTLCache = TTLCache(maxsize=256, ttl=config.CACHE_TTL_SECONDS)
_BOOK_CACHE: TTLCache = TTLCache(maxsize=512, ttl=config.CACHE_TTL_SECONDS)
_TRADES_CACHE: TTLCache = TTLCache(maxsize=512, ttl=config.CACHE_TTL_SECONDS)


async def _request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    **kwargs: Any,
) -> Any:
    """Make an HTTP request with exponential-backoff retry."""
    backoff = 1.0
    last_exc: Exception = RuntimeError(
        "HTTP_MAX_RETRIES must be >= 1; no requests were made"
    )
    if config.HTTP_MAX_RETRIES < 1:
        raise last_exc
    for attempt in range(config.HTTP_MAX_RETRIES):
        try:
            resp = await client.request(method, url, timeout=config.HTTP_TIMEOUT, **kwargs)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError, httpx.TimeoutException) as exc:
            last_exc = exc
            if attempt < config.HTTP_MAX_RETRIES - 1:
                await asyncio.sleep(backoff)
                backoff *= 2
    raise last_exc


class PolymarketClient:
    """Async client for Polymarket public REST APIs."""

    def __init__(
        self,
        gamma_base: str = config.GAMMA_BASE,
        clob_base: str = config.CLOB_BASE,
    ) -> None:
        self._gamma = gamma_base.rstrip("/")
        self._clob = clob_base.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    # ── context-manager support ────────────────────────────────────────────────

    async def __aenter__(self) -> "PolymarketClient":
        self._client = httpx.AsyncClient()
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Use 'async with PolymarketClient() as client:'")
        return self._client

    # ── helpers ────────────────────────────────────────────────────────────────

    def _market_from_raw(self, raw: dict) -> Market:
        yes_price, no_price = parse_outcome_prices(raw.get("outcomePrices"))
        return Market(
            id=str(raw.get("id") or raw.get("conditionId") or ""),
            question=raw.get("question") or raw.get("description") or "Unknown",
            slug=raw.get("slug") or "",
            condition_id=raw.get("conditionId") or "",
            end_date=raw.get("endDate") or raw.get("end_date_iso") or "",
            liquidity=safe_float(raw.get("liquidityNum") or raw.get("liquidity")),
            volume=safe_float(raw.get("volumeNum") or raw.get("volume")),
            volume_24h=safe_float(raw.get("volume24hr") or raw.get("volume24h")),
            yes_price=yes_price,
            no_price=no_price,
            active=not raw.get("closed", False),
            closed=bool(raw.get("closed", False)),
            token_ids=extract_token_ids(raw.get("clobTokenIds")),
        )

    # ── public API ─────────────────────────────────────────────────────────────

    async def get_markets(
        self,
        limit: int = 30,
        order: str = "volume",
        ascending: bool = False,
    ) -> list[Market]:
        """Fetch active markets ordered by *order* field."""
        cache_key = f"markets:{limit}:{order}:{ascending}"
        if cache_key in _MARKET_CACHE:
            return _MARKET_CACHE[cache_key]  # type: ignore[return-value]

        params = {
            "closed": "false",
            "limit": limit,
            "order": order,
            "ascending": str(ascending).lower(),
        }
        raw = await _request(self._http, "GET", f"{self._gamma}/markets", params=params)
        markets: list[Market] = []
        if isinstance(raw, list):
            markets = [self._market_from_raw(m) for m in raw if m.get("question")]
        elif isinstance(raw, dict) and "data" in raw:
            markets = [self._market_from_raw(m) for m in raw["data"] if m.get("question")]

        _MARKET_CACHE[cache_key] = markets
        return markets

    async def get_order_book(self, token_id: str) -> OrderBook:
        """Fetch the current order book for *token_id* (the YES-outcome token)."""
        cache_key = f"book:{token_id}"
        if cache_key in _BOOK_CACHE:
            return _BOOK_CACHE[cache_key]  # type: ignore[return-value]

        raw = await _request(
            self._http, "GET", f"{self._clob}/book", params={"token_id": token_id}
        )
        bids = [
            PriceLevel(price=safe_float(b["price"]), size=safe_float(b["size"]))
            for b in (raw.get("bids") or [])
        ]
        asks = [
            PriceLevel(price=safe_float(a["price"]), size=safe_float(a["size"]))
            for a in (raw.get("asks") or [])
        ]
        book = OrderBook(market_id="", yes_token_id=token_id, bids=bids, asks=asks)
        _BOOK_CACHE[cache_key] = book
        return book

    async def get_best_prices(self, token_id: str) -> tuple[float, float]:
        """
        Return ``(best_bid, best_ask)`` for a YES token via CLOB /price endpoint.
        Falls back to order-book midpoint if /price is unavailable.
        """
        cache_key = f"price:{token_id}"
        if cache_key in _BOOK_CACHE:
            return _BOOK_CACHE[cache_key]  # type: ignore[return-value]

        try:
            raw = await _request(
                self._http,
                "GET",
                f"{self._clob}/price",
                params={"token_id": token_id, "side": "BUY"},
            )
            bid = safe_float(raw.get("price"))
            raw2 = await _request(
                self._http,
                "GET",
                f"{self._clob}/price",
                params={"token_id": token_id, "side": "SELL"},
            )
            ask = safe_float(raw2.get("price"))
            result = (bid, ask)
        except Exception:
            book = await self.get_order_book(token_id)
            result = (book.best_bid or 0.0, book.best_ask or 0.0)

        _BOOK_CACHE[cache_key] = result
        return result

    async def get_recent_trades(self, token_id: str, limit: int = 50) -> list[Trade]:
        """Fetch the most recent *limit* trades for a market token."""
        cache_key = f"trades:{token_id}:{limit}"
        if cache_key in _TRADES_CACHE:
            return _TRADES_CACHE[cache_key]  # type: ignore[return-value]

        raw = await _request(
            self._http,
            "GET",
            f"{self._clob}/trades",
            params={"token_id": token_id, "limit": limit},
        )
        rows = raw if isinstance(raw, list) else (raw.get("data") or [])
        trades = [
            Trade(
                market_id="",
                token_id=token_id,
                price=safe_float(t.get("price")),
                size=safe_float(t.get("size") or t.get("amount")),
                side=str(t.get("side", "BUY")).upper(),
                timestamp=int(safe_float(t.get("timestamp") or t.get("matched_time") or 0)),
            )
            for t in rows
        ]
        _TRADES_CACHE[cache_key] = trades
        return trades

    async def get_market_resolution(self, condition_id: str) -> MarketResolution:
        """Fetch resolution status for a market identified by *condition_id*."""
        raw = await _request(
            self._http,
            "GET",
            f"{self._gamma}/markets",
            params={"conditionId": condition_id},
        )
        data = raw if isinstance(raw, list) else (raw.get("data") or [])
        if data:
            m = data[0]
            resolved = bool(m.get("resolved") or m.get("closed"))
            resolution = m.get("resolution") or m.get("resolutionSource")
            return MarketResolution(
                market_id=condition_id,
                resolved=resolved,
                resolution=str(resolution) if resolution else None,
                end_date=m.get("endDate") or "",
            )
        return MarketResolution(
            market_id=condition_id,
            resolved=False,
            resolution=None,
            end_date="",
        )
