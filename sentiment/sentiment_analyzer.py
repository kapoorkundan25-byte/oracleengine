"""
sentiment/sentiment_analyzer.py — NLP-based sentiment scoring + combined signal.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sentiment.news_fetcher import NewsFetcher

logger = logging.getLogger(__name__)

# ── Sentiment labels ───────────────────────────────────────────────────────────
POSITIVE = "POSITIVE"
NEGATIVE = "NEGATIVE"
NEUTRAL = "NEUTRAL"

# ── Combined signal labels ─────────────────────────────────────────────────────
STRONG_BUY = "STRONG_BUY"
STRONG_SELL = "STRONG_SELL"
LEAN_BUY = "LEAN_BUY"
LEAN_SELL = "LEAN_SELL"
COMBINED_NEUTRAL = "NEUTRAL"


@dataclass
class SentimentReport:
    score: float = 0.0          # average polarity (-1 to +1)
    label: str = NEUTRAL
    article_count: int = 0
    headlines: list[str] = field(default_factory=list)


@dataclass
class CombinedSignal:
    trend_signal: str = ""
    sentiment_label: str = ""
    combined: str = COMBINED_NEUTRAL


class SentimentAnalyzer:
    """Score news sentiment using TextBlob (primary) or HuggingFace (optional)."""

    def __init__(
        self,
        news_fetcher: NewsFetcher | None = None,
        use_transformers: bool = False,
        positive_threshold: float = 0.1,
        negative_threshold: float = -0.1,
        top_headlines: int = 5,
    ) -> None:
        self._fetcher = news_fetcher or NewsFetcher()
        self._use_transformers = use_transformers
        self._pos_thresh = positive_threshold
        self._neg_thresh = negative_threshold
        self._top_headlines = top_headlines
        self._pipeline = None  # lazy load

    # ── public API ─────────────────────────────────────────────────────────────

    def analyze(self, query: str) -> SentimentReport:
        """
        Fetch headlines for *query* and return a :class:`SentimentReport`.
        """
        headlines = self._fetcher.fetch(query)
        if not headlines:
            return SentimentReport(article_count=0)

        if self._use_transformers:
            scores = self._score_transformers(headlines)
        else:
            scores = self._score_textblob(headlines)

        avg_score = sum(scores) / len(scores) if scores else 0.0

        if avg_score > self._pos_thresh:
            label = POSITIVE
        elif avg_score < self._neg_thresh:
            label = NEGATIVE
        else:
            label = NEUTRAL

        return SentimentReport(
            score=round(avg_score, 4),
            label=label,
            article_count=len(headlines),
            headlines=headlines[: self._top_headlines],
        )

    def combined_signal(
        self,
        trend_signal: str,
        sentiment_report: SentimentReport,
    ) -> CombinedSignal:
        """
        Merge a trend signal string with a sentiment label into a :class:`CombinedSignal`.

        Mapping:
        - BULLISH + POSITIVE  → STRONG_BUY
        - OVERSOLD + POSITIVE → STRONG_BUY
        - BEARISH + NEGATIVE  → STRONG_SELL
        - OVERBOUGHT + NEGATIVE → STRONG_SELL
        - BULLISH + NEUTRAL   → LEAN_BUY
        - BEARISH + NEUTRAL   → LEAN_SELL
        - * + POSITIVE        → LEAN_BUY
        - * + NEGATIVE        → LEAN_SELL
        - otherwise           → NEUTRAL
        """
        t = trend_signal.upper()
        s = sentiment_report.label.upper()

        if t in ("BULLISH", "OVERSOLD") and s == POSITIVE:
            combined = STRONG_BUY
        elif t in ("BEARISH", "OVERBOUGHT") and s == NEGATIVE:
            combined = STRONG_SELL
        elif t in ("BULLISH", "OVERSOLD") and s == NEUTRAL:
            combined = LEAN_BUY
        elif t in ("BEARISH", "OVERBOUGHT") and s == NEUTRAL:
            combined = LEAN_SELL
        elif s == POSITIVE:
            combined = LEAN_BUY
        elif s == NEGATIVE:
            combined = LEAN_SELL
        else:
            combined = COMBINED_NEUTRAL

        return CombinedSignal(
            trend_signal=trend_signal,
            sentiment_label=sentiment_report.label,
            combined=combined,
        )

    # ── scoring back-ends ──────────────────────────────────────────────────────

    def _score_textblob(self, headlines: list[str]) -> list[float]:
        try:
            from textblob import TextBlob  # type: ignore[import]
            return [TextBlob(h).sentiment.polarity for h in headlines]
        except ImportError:
            logger.warning("textblob not installed; using zero scores")
            return [0.0] * len(headlines)

    def _score_transformers(self, headlines: list[str]) -> list[float]:
        try:
            from transformers import pipeline as hf_pipeline  # type: ignore[import]
            if self._pipeline is None:
                self._pipeline = hf_pipeline(
                    "sentiment-analysis",
                    model="distilbert-base-uncased-finetuned-sst-2-english",
                )
            results = self._pipeline(headlines, truncation=True, max_length=512)
            scores: list[float] = []
            for r in results:
                polarity = r["score"] if r["label"] == "POSITIVE" else -r["score"]
                scores.append(polarity)
            return scores
        except Exception as exc:
            logger.warning("transformers scoring failed (%s); falling back to TextBlob", exc)
            return self._score_textblob(headlines)
