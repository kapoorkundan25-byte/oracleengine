"""
sentiment/news_fetcher.py — Fetch news headlines via NewsAPI or RSS fallback.
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx
import feedparser

import config

logger = logging.getLogger(__name__)

# Fallback RSS feeds when NewsAPI is unavailable
_RSS_FEEDS = [
    "https://feeds.reuters.com/reuters/topNews",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://rss.ap.org/articles/APNews",
]


class NewsFetcher:
    """Fetch news headlines relevant to a given *query* string."""

    def __init__(
        self,
        newsapi_key: str = config.NEWSAPI_KEY,
        max_headlines: int = 20,
        language: str = "en",
    ) -> None:
        self._key = newsapi_key
        self.max_headlines = max_headlines
        self.language = language

    def fetch(self, query: str) -> list[str]:
        """
        Return up to *max_headlines* headline strings for *query*.

        Tries NewsAPI first; falls back to RSS if unavailable.
        """
        if self._key:
            headlines = self._fetch_newsapi(query)
            if headlines:
                return headlines
        return self._fetch_rss(query)

    def _fetch_newsapi(self, query: str) -> list[str]:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": self.language,
            "sortBy": "publishedAt",
            "pageSize": self.max_headlines,
            "apiKey": self._key,
        }
        try:
            resp = httpx.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles") or []
            return [
                a.get("title") or a.get("description") or ""
                for a in articles
                if a.get("title") or a.get("description")
            ]
        except Exception as exc:
            logger.debug("NewsAPI fetch failed: %s", exc)
            return []

    def _fetch_rss(self, query: str) -> list[str]:
        """Parse RSS feeds and return headlines containing any word from *query*."""
        keywords = {w.lower() for w in query.split() if len(w) > 3}
        headlines: list[str] = []
        for feed_url in _RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries:
                    title: str = entry.get("title", "")
                    summary: str = entry.get("summary", "")
                    text = (title + " " + summary).lower()
                    if not keywords or any(kw in text for kw in keywords):
                        headlines.append(title or summary)
                    if len(headlines) >= self.max_headlines:
                        break
            except Exception as exc:
                logger.debug("RSS fetch failed for %s: %s", feed_url, exc)
            if len(headlines) >= self.max_headlines:
                break
        return headlines
