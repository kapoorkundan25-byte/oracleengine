"""
polymarket/models.py — Data-models / dataclasses for Polymarket entities.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Market:
    """Represents a single Polymarket prediction market."""

    id: str
    question: str
    slug: str = ""
    condition_id: str = ""
    end_date: str = ""
    liquidity: float = 0.0
    volume: float = 0.0
    volume_24h: float = 0.0
    yes_price: float = 0.0
    no_price: float = 0.0
    active: bool = True
    closed: bool = False
    token_ids: list[str] = field(default_factory=list)

    # Enriched fields (filled in later)
    trend_signal: str = ""
    sentiment_label: str = ""

    @property
    def spread(self) -> float:
        return abs(self.yes_price - (1.0 - self.no_price))


@dataclass
class PriceLevel:
    price: float
    size: float


@dataclass
class OrderBook:
    market_id: str
    yes_token_id: str
    bids: list[PriceLevel] = field(default_factory=list)
    asks: list[PriceLevel] = field(default_factory=list)

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None


@dataclass
class Trade:
    market_id: str
    token_id: str
    price: float
    size: float
    side: str          # "BUY" | "SELL"
    timestamp: int     # Unix seconds


@dataclass
class MarketResolution:
    market_id: str
    resolved: bool
    resolution: Optional[str]  # "YES" | "NO" | None
    end_date: str
