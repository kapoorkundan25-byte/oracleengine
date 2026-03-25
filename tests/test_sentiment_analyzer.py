"""
tests/test_sentiment_analyzer.py — Unit tests for modules/sentiment_analyzer.py.

All external API calls are mocked with :mod:`unittest.mock`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules.sentiment_analyzer import (
    SentimentReport,
    analyze_sentiment,
    correlate_sentiment_with_price,
    fetch_news_headlines,
    fetch_twitter_trends,
    get_market_sentiment_score,
)


# ---------------------------------------------------------------------------
# analyze_sentiment
# ---------------------------------------------------------------------------
class TestAnalyzeSentiment:
    def test_positive_text(self):
        score = analyze_sentiment("Great news! Bitcoin hits all time high!")
        assert score > 0.0, "Positive headline should yield positive score"

    def test_negative_text(self):
        score = analyze_sentiment("Terrible crash wipes out billions in losses!")
        assert score < 0.0, "Negative headline should yield negative score"

    def test_neutral_text(self):
        score = analyze_sentiment("The market opened at 9:30 AM.")
        # VADER compound of factual text should be close to zero
        assert -0.5 < score < 0.5

    def test_empty_string_returns_zero(self):
        assert analyze_sentiment("") == 0.0

    def test_score_range(self):
        texts = [
            "Incredible bull run pushes prices to record highs",
            "Catastrophic collapse destroys all value",
            "Markets are open today",
        ]
        for text in texts:
            score = analyze_sentiment(text)
            assert -1.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# fetch_news_headlines
# ---------------------------------------------------------------------------
class TestFetchNewsHeadlines:
    def test_returns_headlines_with_valid_key(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        mock_client = MagicMock()
        mock_client.get_everything.return_value = {
            "articles": [
                {"title": "Bitcoin rally continues", "description": "BTC up 10 %"},
                {"title": "ETH upgrade successful", "description": ""},
            ]
        }

        with patch.dict("os.environ", {"NEWS_API_KEY": "fake_key"}), \
             patch("config.NEWS_API_KEY", "fake_key"), \
             patch("newsapi.NewsApiClient", return_value=mock_client):
            headlines = fetch_news_headlines("bitcoin", limit=5)

        assert "Bitcoin rally continues" in headlines
        assert len(headlines) <= 5

    def test_returns_empty_when_no_api_key(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        with patch("config.NEWS_API_KEY", ""):
            headlines = fetch_news_headlines("anything")

        assert headlines == []

    def test_returns_empty_on_api_error(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        with patch("config.NEWS_API_KEY", "fake"), \
             patch("newsapi.NewsApiClient", side_effect=Exception("api down")):
            headlines = fetch_news_headlines("test")

        assert headlines == []

    def test_caching_avoids_duplicate_calls(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        mock_client = MagicMock()
        mock_client.get_everything.return_value = {
            "articles": [{"title": "News A", "description": ""}]
        }

        with patch("config.NEWS_API_KEY", "fake_key"), \
             patch("newsapi.NewsApiClient", return_value=mock_client) as mock_cls:
            fetch_news_headlines("test", limit=5)
            fetch_news_headlines("test", limit=5)  # second call — cached

        # NewsApiClient instantiated only once
        assert mock_cls.call_count == 1


# ---------------------------------------------------------------------------
# fetch_twitter_trends (stub)
# ---------------------------------------------------------------------------
class TestFetchTwitterTrends:
    def test_returns_empty_list(self):
        result = fetch_twitter_trends("any query")
        assert result == []

    def test_returns_list_type(self):
        assert isinstance(fetch_twitter_trends("bitcoin"), list)


# ---------------------------------------------------------------------------
# get_market_sentiment_score
# ---------------------------------------------------------------------------
class TestGetMarketSentimentScore:
    def test_returns_sentiment_report(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        headlines = [
            "Bitcoin bulls are back — prices surge",
            "Crypto market shows strong momentum",
        ]
        with patch(
            "modules.sentiment_analyzer.fetch_news_headlines",
            return_value=headlines,
        ):
            report = get_market_sentiment_score("mkt001", query="bitcoin")

        assert isinstance(report, SentimentReport)
        assert report.market_id == "mkt001"
        assert -1.0 <= report.score <= 1.0
        assert report.label in {"POSITIVE", "NEGATIVE", "NEUTRAL"}

    def test_positive_headlines_yield_positive_label(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        headlines = ["Amazing rally!" * 5, "Outstanding gains!" * 5]
        with patch(
            "modules.sentiment_analyzer.fetch_news_headlines",
            return_value=headlines,
        ):
            report = get_market_sentiment_score("mkt002", query="btc")

        assert report.label == "POSITIVE"
        assert report.score > 0.05

    def test_negative_headlines_yield_negative_label(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        headlines = [
            "Terrible crash destroys portfolios",
            "Catastrophic losses mount as prices collapse",
        ]
        with patch(
            "modules.sentiment_analyzer.fetch_news_headlines",
            return_value=headlines,
        ):
            report = get_market_sentiment_score("mkt003", query="crash")

        assert report.label == "NEGATIVE"
        assert report.score < -0.05

    def test_empty_headlines_neutral(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        with patch("modules.sentiment_analyzer.fetch_news_headlines", return_value=[]):
            report = get_market_sentiment_score("mkt004", query="nothing")

        assert report.label == "NEUTRAL"
        assert report.score == pytest.approx(0.0)

    def test_caching(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        mock_fetch = MagicMock(return_value=["Good news!"])
        with patch("modules.sentiment_analyzer.fetch_news_headlines", mock_fetch):
            get_market_sentiment_score("mkt005", query="q")
            get_market_sentiment_score("mkt005", query="q")  # cached

        assert mock_fetch.call_count == 1

    def test_headlines_included_in_report(self):
        from modules import sentiment_analyzer

        sentiment_analyzer._sentiment_cache.clear()

        headlines = ["Headline A", "Headline B", "Headline C"]
        with patch(
            "modules.sentiment_analyzer.fetch_news_headlines",
            return_value=headlines,
        ):
            report = get_market_sentiment_score("mkt006")

        assert set(headlines).issubset(set(report.headlines))


# ---------------------------------------------------------------------------
# correlate_sentiment_with_price
# ---------------------------------------------------------------------------
class TestCorrelateSentimentWithPrice:
    def test_perfect_positive_correlation(self):
        scores = [0.1, 0.2, 0.3, 0.4, 0.5]
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = correlate_sentiment_with_price("mkt001", scores, prices)
        assert result["correlation"] == pytest.approx(1.0, abs=1e-6)
        assert result["n"] == 5

    def test_perfect_negative_correlation(self):
        scores = [0.5, 0.4, 0.3, 0.2, 0.1]
        prices = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = correlate_sentiment_with_price("mkt001", scores, prices)
        assert result["correlation"] == pytest.approx(-1.0, abs=1e-6)

    def test_insufficient_data(self):
        result = correlate_sentiment_with_price("mkt001", [0.5], [1.0])
        assert result["correlation"] is None
        assert "insufficient" in result["interpretation"].lower()

    def test_returns_interpretation_string(self):
        scores = [0.1, 0.5, 0.9, 0.4, 0.2]
        prices = [0.3, 0.6, 0.7, 0.4, 0.3]
        result = correlate_sentiment_with_price("mkt001", scores, prices)
        assert isinstance(result["interpretation"], str)

    def test_mismatched_lengths_uses_minimum(self):
        scores = [0.1, 0.2, 0.3, 0.4]
        prices = [1.0, 2.0]
        result = correlate_sentiment_with_price("mkt001", scores, prices)
        assert result["n"] == 2
