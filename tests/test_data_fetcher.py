"""
tests/test_data_fetcher.py — Unit tests for modules/data_fetcher.py.

All external HTTP calls are mocked with :mod:`unittest.mock`.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_response(data: object, status_code: int = 200) -> MagicMock:
    """Return a mock requests.Response-like object."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = data
    if status_code >= 400:
        from requests import HTTPError

        mock_resp.raise_for_status.side_effect = HTTPError(response=mock_resp)
    else:
        mock_resp.raise_for_status.return_value = None
    return mock_resp


_SAMPLE_MARKET = {
    "id": "mkt001",
    "conditionId": "cond001",
    "question": "Will BTC reach $100k?",
    "description": "Bitcoin price prediction",
    "active": True,
    "volume": 500000.0,
    "volume24hr": 12000.0,
    "liquidity": 80000.0,
    "outcomePrices": "[0.65, 0.35]",
    "endDate": "2025-12-31T00:00:00Z",
}

_SAMPLE_ORDERBOOK = {
    "bids": [{"price": "0.64", "size": "1000"}, {"price": "0.63", "size": "2000"}],
    "asks": [{"price": "0.66", "size": "1500"}, {"price": "0.67", "size": "800"}],
}

_SAMPLE_TRADES = [
    {"id": "t1", "price": "0.65", "size": "500", "side": "BUY", "timestamp": 1700000000},
    {"id": "t2", "price": "0.64", "size": "300", "side": "SELL", "timestamp": 1700000100},
]

_SAMPLE_HISTORY = [
    {"t": 1699000000, "p": "0.50"},
    {"t": 1699100000, "p": "0.55"},
    {"t": 1699200000, "p": "0.60"},
    {"t": 1699300000, "p": "0.65"},
]


# ---------------------------------------------------------------------------
# get_markets
# ---------------------------------------------------------------------------
class TestGetMarkets:
    def test_returns_list_of_markets(self):
        from modules import data_fetcher

        # Clear cache to avoid stale entries from other tests
        data_fetcher._markets_cache.clear()

        with patch.object(
            data_fetcher._SESSION,
            "get",
            return_value=_make_response([_SAMPLE_MARKET]),
        ):
            markets = data_fetcher.get_markets(limit=5)

        assert len(markets) == 1
        m = markets[0]
        assert m.id == "mkt001"
        assert m.question == "Will BTC reach $100k?"
        assert m.outcome_prices == [0.65, 0.35]

    def test_caching(self):
        from modules import data_fetcher

        data_fetcher._markets_cache.clear()

        mock_get = MagicMock(return_value=_make_response([_SAMPLE_MARKET]))
        with patch.object(data_fetcher._SESSION, "get", mock_get):
            data_fetcher.get_markets(limit=5)
            data_fetcher.get_markets(limit=5)  # second call — should hit cache

        assert mock_get.call_count == 1, "Second call should have used cache"

    def test_empty_response(self):
        from modules import data_fetcher

        data_fetcher._markets_cache.clear()

        with patch.object(
            data_fetcher._SESSION, "get", return_value=_make_response([])
        ):
            markets = data_fetcher.get_markets(limit=5)

        assert markets == []

    def test_malformed_entry_skipped(self):
        from modules import data_fetcher

        data_fetcher._markets_cache.clear()
        bad_entry = {"not_an_id": True}

        with patch.object(
            data_fetcher._SESSION,
            "get",
            return_value=_make_response([bad_entry, _SAMPLE_MARKET]),
        ):
            markets = data_fetcher.get_markets(limit=5)

        # The bad entry is skipped, the valid one is returned
        assert len(markets) == 1


# ---------------------------------------------------------------------------
# get_market_by_id
# ---------------------------------------------------------------------------
class TestGetMarketById:
    def test_found(self):
        from modules import data_fetcher

        data_fetcher._markets_cache.clear()

        with patch.object(
            data_fetcher._SESSION,
            "get",
            return_value=_make_response(_SAMPLE_MARKET),
        ):
            market = data_fetcher.get_market_by_id("cond001")

        assert market is not None
        assert market.id == "mkt001"

    def test_not_found_returns_none(self):
        from modules import data_fetcher

        data_fetcher._markets_cache.clear()

        with patch.object(
            data_fetcher._SESSION,
            "get",
            return_value=_make_response({}, status_code=404),
        ):
            market = data_fetcher.get_market_by_id("nonexistent")

        assert market is None


# ---------------------------------------------------------------------------
# get_market_orderbook
# ---------------------------------------------------------------------------
class TestGetMarketOrderbook:
    def test_parses_bids_and_asks(self):
        from modules import data_fetcher

        data_fetcher._orderbook_cache.clear()

        with patch.object(
            data_fetcher._SESSION,
            "get",
            return_value=_make_response(_SAMPLE_ORDERBOOK),
        ):
            book = data_fetcher.get_market_orderbook("tok001")

        assert len(book.bids) == 2
        assert len(book.asks) == 2
        assert book.bids[0].price == pytest.approx(0.64)
        assert book.asks[0].size == pytest.approx(1500.0)


# ---------------------------------------------------------------------------
# get_market_trades
# ---------------------------------------------------------------------------
class TestGetMarketTrades:
    def test_returns_trade_list(self):
        from modules import data_fetcher

        data_fetcher._trades_cache.clear()

        with patch.object(
            data_fetcher._SESSION,
            "get",
            return_value=_make_response(_SAMPLE_TRADES),
        ):
            trades = data_fetcher.get_market_trades("mkt001", limit=10)

        assert len(trades) == 2
        assert trades[0].trade_id == "t1"
        assert trades[0].price == pytest.approx(0.65)

    def test_dict_response_unwrapped(self):
        from modules import data_fetcher

        data_fetcher._trades_cache.clear()
        wrapped = {"data": _SAMPLE_TRADES}

        with patch.object(
            data_fetcher._SESSION,
            "get",
            return_value=_make_response(wrapped),
        ):
            trades = data_fetcher.get_market_trades("mkt002", limit=10)

        assert len(trades) == 2


# ---------------------------------------------------------------------------
# get_market_price_history
# ---------------------------------------------------------------------------
class TestGetMarketPriceHistory:
    def test_returns_sorted_price_points(self):
        from modules import data_fetcher

        data_fetcher._history_cache.clear()

        with patch.object(
            data_fetcher._SESSION,
            "get",
            return_value=_make_response(_SAMPLE_HISTORY),
        ):
            history = data_fetcher.get_market_price_history("mkt001")

        assert len(history) == 4
        assert history[0].timestamp < history[-1].timestamp
        assert history[-1].price == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# search_markets
# ---------------------------------------------------------------------------
class TestSearchMarkets:
    def test_search_returns_markets(self):
        from modules import data_fetcher

        data_fetcher._markets_cache.clear()

        with patch.object(
            data_fetcher._SESSION,
            "get",
            return_value=_make_response([_SAMPLE_MARKET]),
        ):
            results = data_fetcher.search_markets("bitcoin")

        assert len(results) == 1
        assert results[0].question == "Will BTC reach $100k?"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------
class TestRetryLogic:
    def test_retries_on_429(self):
        from modules import data_fetcher

        data_fetcher._markets_cache.clear()

        resp_429 = _make_response({}, status_code=429)
        resp_ok = _make_response([_SAMPLE_MARKET])

        with patch.object(
            data_fetcher._SESSION,
            "get",
            side_effect=[resp_429, resp_ok],
        ), patch("time.sleep"):
            markets = data_fetcher.get_markets(limit=5)

        assert len(markets) == 1
