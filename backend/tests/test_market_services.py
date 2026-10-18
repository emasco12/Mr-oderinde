from __future__ import annotations

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import config
from backend import main
from backend.services import alpha_vantage, finnhub, http, newsapi


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-alpha-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "test-finnhub-key")
    monkeypatch.setenv("NEWSAPI_API_KEY", "test-newsapi-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-session-signing-key-for-tests-only-123456")
    with TestClient(main.app) as test_client:
        yield test_client


def test_startup_configuration_lists_missing_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for key_name in config.REQUIRED_API_KEYS:
        monkeypatch.delenv(key_name, raising=False)

    with pytest.raises(RuntimeError, match="ALPHA_VANTAGE_API_KEY, NEWSAPI_API_KEY"):
        config.validate_required_api_keys()


def test_finnhub_key_is_optional_for_alpha_vantage_primary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-alpha-key")
    monkeypatch.setenv("NEWSAPI_API_KEY", "test-newsapi-key")
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)

    config.validate_required_api_keys()


def test_http_client_retries_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def respond(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"status": "ok"})

    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(respond)
    monkeypatch.setattr(
        http.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    monkeypatch.setattr(http.asyncio, "sleep", AsyncMock())

    result = asyncio.run(
        http.get_json(
            "https://example.test/data",
            params={},
            attempts=2,
            min_retry_delay=0,
            provider="Test provider",
        )
    )

    assert result == {"status": "ok"}
    assert calls == 2


def test_newsapi_key_is_sent_in_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEWSAPI_API_KEY", "test-newsapi-key")
    request = AsyncMock(return_value={"status": "ok", "articles": []})
    monkeypatch.setattr(newsapi, "get_json", request)

    result = asyncio.run(newsapi.gold_headlines())

    assert result["status"] == "ok"
    assert request.await_args.kwargs["headers"] == {"X-Api-Key": "test-newsapi-key"}
    assert "apiKey" not in request.await_args.kwargs["params"]


def test_gold_quote_uses_alpha_vantage(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    main.quote_cache = None
    monkeypatch.setattr(
        alpha_vantage,
        "fetch",
        AsyncMock(return_value={"price": "2345.67", "timestamp": "2026-10-17"}),
    )

    response = client.get("/api/market/gold")

    assert response.status_code == 200
    assert response.json()["price"] == 2345.67
    assert response.json()["source"] == "Alpha Vantage"


def test_gold_quote_falls_back_to_finnhub(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    main.quote_cache = None
    monkeypatch.setattr(alpha_vantage, "fetch", AsyncMock(side_effect=RuntimeError("unavailable")))
    monkeypatch.setattr(
        finnhub,
        "quote",
        AsyncMock(return_value={"c": 2345.67, "t": 1792260000}),
    )

    response = client.get("/api/market/gold")

    assert response.status_code == 200
    assert response.json()["price"] == 2345.67
    assert response.json()["source"] == "Finnhub"


def test_gold_quote_keeps_alpha_vantage_primary_when_finnhub_is_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    main.quote_cache = None
    monkeypatch.setattr(
        alpha_vantage,
        "fetch",
        AsyncMock(return_value={"price": "2345.67", "timestamp": "2026-10-17"}),
    )
    finnhub_quote = AsyncMock(side_effect=RuntimeError("Finnhub is unavailable"))
    monkeypatch.setattr(finnhub, "quote", finnhub_quote)

    response = client.get("/api/market/gold")

    assert response.status_code == 200
    assert response.json()["status"] == "live"
    assert response.json()["source"] == "Alpha Vantage"
    finnhub_quote.assert_not_awaited()


def test_gold_quote_remains_graceful_when_both_providers_fail(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    main.quote_cache = None
    monkeypatch.setattr(alpha_vantage, "fetch", AsyncMock(side_effect=RuntimeError("Alpha unavailable")))
    monkeypatch.setattr(finnhub, "quote", AsyncMock(side_effect=RuntimeError("Finnhub unavailable")))

    response = client.get("/api/market/gold")

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["price"] is None


def test_gold_history_falls_back_to_finnhub(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    main.history_cache = None
    monkeypatch.setattr(alpha_vantage, "fetch", AsyncMock(side_effect=RuntimeError("Alpha unavailable")))
    monkeypatch.setattr(
        finnhub,
        "daily_candles",
        AsyncMock(return_value={"t": [1792260000], "c": [2345.67]}),
    )

    response = client.get("/api/market/history")

    assert response.status_code == 200
    assert response.json()["status"] == "live"
    assert response.json()["source"] == "Finnhub"
    assert response.json()["candles"][0]["close"] == 2345.67


def test_provider_health_reports_finnhub_unavailable_without_failing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    main.provider_health_cache = None
    monkeypatch.setattr(alpha_vantage, "health_check", AsyncMock())
    monkeypatch.setattr(newsapi, "health_check", AsyncMock())
    monkeypatch.setattr(
        finnhub,
        "health_check",
        AsyncMock(side_effect=RuntimeError("Finnhub request failed with HTTP 403.")),
    )

    response = client.get("/api/health")
    result = response.json()

    assert response.status_code == 200
    assert result["status"] == "ok"
    assert result["providers"]["Alpha Vantage"]["status"] == "available"
    assert result["providers"]["Alpha Vantage"]["priority"] == "primary"
    assert result["providers"]["Finnhub"]["status"] == "unavailable"
    assert result["providers"]["Finnhub"]["priority"] == "secondary"
    assert result["warnings"] == [result["providers"]["Finnhub"]["warning"]]


def test_finnhub_quote_uses_forex_candles_and_listed_gold_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FINNHUB_API_KEY", "test-finnhub-key")
    request = AsyncMock(return_value={"s": "ok", "t": [1792260000], "c": [2345.67]})
    monkeypatch.setattr(finnhub, "_candles", request)

    quote = asyncio.run(finnhub.quote())

    assert quote == {"c": 2345.67, "t": 1792260000}
    request.assert_awaited_once()
    assert request.await_args.args[:2] == ("OANDA:XAU_USD", "1")


def test_finnhub_candles_calls_forex_candle_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINNHUB_API_KEY", "test-finnhub-key")
    request = AsyncMock(return_value={"s": "ok", "t": [1], "c": [2345.67]})
    monkeypatch.setattr(finnhub, "get_json", request)

    result = asyncio.run(finnhub._candles("OANDA:XAU_USD", "1", 100, 200))

    assert result["s"] == "ok"
    assert request.await_args.args[0] == "https://finnhub.io/api/v1/forex/candle"
    assert request.await_args.kwargs["params"]["symbol"] == "OANDA:XAU_USD"
    assert request.await_args.kwargs["params"]["resolution"] == "1"


def test_news_endpoint_maps_newsapi_articles(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    main.news_cache = None
    monkeypatch.setattr(
        newsapi,
        "gold_headlines",
        AsyncMock(
            return_value={
                "articles": [
                    {
                        "title": "Gold markets rise",
                        "url": "https://example.test/article",
                        "publishedAt": "2026-10-17T12:00:00Z",
                        "source": {"name": "Test News"},
                    }
                ]
            }
        ),
    )

    response = client.get("/api/news")

    assert response.status_code == 200
    assert response.json()["source"] == "NewsAPI"
    assert response.json()["items"][0]["title"] == "Gold markets rise"
