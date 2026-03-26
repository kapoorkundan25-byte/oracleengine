"""
modules/sentiment_analyzer.py — Sentiment Analysis for OracleEngine.

Fetches news headlines via **NewsAPI** and scores them with **VADER**
(Valence Aware Dictionary for Sentiment Reasoning).

Public API
----------
* :func:`fetch_news_headlines` — Pull recent news via NewsAPI.
* :func:`fetch_twitter_trends` — Stub / placeholder (see TODOs).
* :func:`analyze_sentiment` — Score a single text string.
* :func:`get_market_sentiment_score` — Aggregate score for a market.
* :func:`correlate_sentiment_with_price` — Pearson r vs price change.
* :class:`SentimentReport` — Typed result dataclass.
"""

from __future__ import annotations

import datetime
import statistics
import time
from dataclasses import dataclass, field
from typing import Any

import config
from utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# TTL cache: avoid redundant API calls for 15 minutes
# ---------------------------------------------------------------------------
_sentiment_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = config.SENTIMENT_CACHE_TTL  # 900 s = 15 min


def _cache_get(key: str) -> Any | None:
    entry = _sentiment_cache.get(key)
    if entry and (time.monotonic() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value: Any) -> None:
    _sentiment_cache[key] = (time.monotonic(), value)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class SentimentReport:
    """Aggregated sentiment result for a Polymarket market.

    Attributes:
        market_id:  Polymarket condition ID.
        score:      Composite sentiment score in [-1.0, +1.0].
        label:      ``"POSITIVE"``, ``"NEGATIVE"``, or ``"NEUTRAL"``.
        headlines:  List of news headline strings used to derive *score*.
        timestamp:  UTC datetime when the report was generated.
    """

    market_id: str
    score: float
    label: str
    headlines: list[str] = field(default_factory=list)
    timestamp: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(tz=datetime.timezone.utc)
    )


# ---------------------------------------------------------------------------
# VADER loader (lazy)
# ---------------------------------------------------------------------------
_vader: Any = None


def _get_vader() -> Any:
    """Lazy-load the VADER sentiment analyser."""
    global _vader
    if _vader is None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

            _vader = SentimentIntensityAnalyzer()
            logger.debug("VADER SentimentIntensityAnalyzer loaded")
        except ImportError:
            logger.warning("vaderSentiment is not installed — sentiment scoring disabled")
    return _vader


# ---------------------------------------------------------------------------
# NewsAPI
# ---------------------------------------------------------------------------
def fetch_news_headlines(query: str, limit: int = 10) -> list[str]:
    """Fetch recent news headlines related to *query* via NewsAPI.

    Args:
        query: Search string (typically the market question).
        limit: Maximum number of headlines to return.

    Returns:
        List of headline strings (may be empty if the API key is missing
        or the API returns no results).
    """
    cache_key = f"news:{query}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    if not config.NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set — skipping news fetch")
        return []

    try:
        from newsapi import NewsApiClient

        client = NewsApiClient(api_key=config.NEWS_API_KEY)
        response = client.get_everything(
            q=query,
            language="en",
            sort_by="relevancy",
            page_size=min(limit, 100),
        )
        articles = response.get("articles", [])
        headlines = [
            a.get("title", "") or a.get("description", "")
            for a in articles
            if a.get("title") or a.get("description")
        ]
        result = headlines[:limit]
        _cache_set(cache_key, result)
        logger.debug("Fetched %d headlines for query '%s'", len(result), query)
        return result
    except Exception as exc:
        logger.error("NewsAPI fetch failed: %s", exc)
        return []


def fetch_twitter_trends(query: str) -> list[str]:
    """Placeholder for Twitter/X API integration (not yet implemented).

    This function is a stub.  It always returns an empty list.
    To add Twitter/X support:

    1. Install ``tweepy``: ``pip install tweepy``.
    2. Obtain a developer bearer token from
       `developer.twitter.com <https://developer.twitter.com>`_.
    3. Use ``tweepy.Client(bearer_token=...)`` with the
       ``GET /2/tweets/search/recent`` endpoint.

    Args:
        query: Search string.

    Returns:
        Empty list (placeholder — Twitter/X integration not yet implemented).
    """
    # TODO: Implement using tweepy + Twitter API v2 bearer token.
    logger.info("fetch_twitter_trends: Twitter/X integration not yet implemented")
    return []


# ---------------------------------------------------------------------------
# Sentiment scoring
# ---------------------------------------------------------------------------
def analyze_sentiment(text: str) -> float:
    """Analyse the sentiment of a single text string using VADER.

    Args:
        text: Arbitrary text (news headline, tweet, etc.).

    Returns:
        Compound sentiment score in [-1.0, +1.0].  Returns ``0.0``
        when VADER is unavailable or *text* is empty.
    """
    if not text:
        return 0.0
    vader = _get_vader()
    if vader is None:
        return 0.0
    scores = vader.polarity_scores(text)
    return float(scores["compound"])


def get_market_sentiment_score(market_id: str, query: str = "") -> SentimentReport:
    """Compute the aggregate sentiment score for a market.

    Fetches news headlines using *query* (or *market_id* as a fallback)
    and averages the per-headline VADER compound scores.

    Args:
        market_id: Polymarket condition ID.
        query: Search string for news — defaults to *market_id*.

    Returns:
        :class:`SentimentReport` with the aggregate result.
    """
    cache_key = f"sentiment:{market_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    search_query = query or market_id
    headlines = fetch_news_headlines(search_query, limit=20)

    # Also try Twitter (currently a stub)
    twitter = fetch_twitter_trends(search_query)
    all_texts = headlines + twitter

    if not all_texts:
        score = 0.0
    else:
        scores = [analyze_sentiment(t) for t in all_texts]
        score = statistics.mean(scores) if scores else 0.0

    if score > 0.05:
        label = "POSITIVE"
    elif score < -0.05:
        label = "NEGATIVE"
    else:
        label = "NEUTRAL"

    report = SentimentReport(
        market_id=market_id,
        score=round(score, 4),
        label=label,
        headlines=headlines,
    )
    _cache_set(cache_key, report)
    return report


def correlate_sentiment_with_price(
    market_id: str,
    sentiment_scores: list[float] | None = None,
    prices: list[float] | None = None,
) -> dict[str, Any]:
    """Compute the Pearson correlation between sentiment scores and prices.

    If *sentiment_scores* and *prices* are not supplied the function will
    attempt to fetch them automatically.  Note: this requires matching
    lists of the same length.

    Args:
        market_id: Polymarket condition ID.
        sentiment_scores: Pre-computed sentiment scores (optional).
        prices: Historical prices aligned with *sentiment_scores* (optional).

    Returns:
        Dictionary with keys:

        * ``correlation`` — Pearson r in [-1.0, +1.0], or ``None``.
        * ``n`` — Number of data points used.
        * ``interpretation`` — Short human-readable description.
    """
    if sentiment_scores is None or prices is None:
        # Auto-fetch prices and generate a single-point sentiment snapshot
        try:
            from modules.data_fetcher import get_market_price_history, get_market_by_id

            market = get_market_by_id(market_id)
            query = market.question if market else market_id
            history = get_market_price_history(market_id)
            prices = [p.price for p in history]
            # Single score — cannot compute correlation with one point
            report = get_market_sentiment_score(market_id, query=query)
            sentiment_scores = [report.score] * len(prices)
        except Exception as exc:
            logger.error("Could not auto-fetch data for correlation: %s", exc)
            return {"correlation": None, "n": 0, "interpretation": "insufficient data"}

    n = min(len(sentiment_scores), len(prices))
    if n < 2:
        return {"correlation": None, "n": n, "interpretation": "insufficient data"}

    x = sentiment_scores[:n]
    y = prices[:n]

    try:
        import numpy as np

        corr = float(np.corrcoef(x, y)[0, 1])
    except Exception:
        corr = 0.0

    if corr > 0.6:
        interpretation = "Strong positive correlation"
    elif corr > 0.3:
        interpretation = "Moderate positive correlation"
    elif corr < -0.6:
        interpretation = "Strong negative correlation"
    elif corr < -0.3:
        interpretation = "Moderate negative correlation"
    else:
        interpretation = "Weak or no correlation"

    return {"correlation": corr, "n": n, "interpretation": interpretation}
