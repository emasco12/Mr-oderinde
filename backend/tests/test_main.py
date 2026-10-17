from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4
import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend import main
from backend.main import Base, app, get_db


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "test-alpha-key")
    monkeypatch.setenv("FINNHUB_API_KEY", "test-finnhub-key")
    monkeypatch.setenv("NEWSAPI_API_KEY", "test-newsapi-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-session-signing-key-for-tests-only-123456")
    main.auth_attempts.clear()
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    monkeypatch.setattr(main, "SessionLocal", TestingSessionLocal)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        registered = test_client.post(
            "/api/auth/register",
            json={
                "email": f"trader-{uuid4().hex}@example.test",
                "password": "Correct horse battery staple 42",
            },
        )
        assert registered.status_code == 201
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def test_health(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    main.provider_health_cache = None
    monkeypatch.setattr(main.alpha_vantage, "health_check", AsyncMock())
    monkeypatch.setattr(main.newsapi, "health_check", AsyncMock())
    monkeypatch.setattr(main.finnhub, "health_check", AsyncMock())
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["providers"]["Alpha Vantage"]["status"] == "available"
    assert response.json()["providers"]["NewsAPI"]["status"] == "available"
    assert response.json()["providers"]["Finnhub"]["status"] == "available"


def test_risk_calculation(client: TestClient) -> None:
    response = client.post(
        "/api/risk",
        json={"account_balance": 25000, "risk_percent": 1, "entry_price": 4340, "stop_price": 4300},
    )
    assert response.status_code == 200
    assert response.json()["risk_amount"] == 250
    assert response.json()["position_ounces"] == 6.25
    assert response.json()["standard_lots"] == 0.0625


def test_risk_rejects_zero_stop_distance(client: TestClient) -> None:
    response = client.post(
        "/api/risk",
        json={"account_balance": 25000, "risk_percent": 1, "entry_price": 4340, "stop_price": 4340},
    )
    assert response.status_code == 422


def test_journal_create_list_and_delete(client: TestClient) -> None:
    created = client.post(
        "/api/journal",
        json={"side": "BUY", "entry_price": 4300, "exit_price": 4350, "quantity_ounces": 2, "thesis": "Breakout"},
    )
    assert created.status_code == 201
    entry = created.json()
    assert entry["pnl"] == 100

    listed = client.get("/api/journal")
    assert len(listed.json()) == 1
    assert listed.json()[0]["id"] == entry["id"]

    deleted = client.delete(f"/api/journal/{entry['id']}")
    assert deleted.status_code == 204
    assert client.get("/api/journal").json() == []


def test_journal_requires_authentication(client: TestClient) -> None:
    client.post("/api/auth/logout")
    response = client.get("/api/journal")
    assert response.status_code == 401


def test_journal_is_scoped_to_account(client: TestClient) -> None:
    created = client.post(
        "/api/journal",
        json={"side": "BUY", "entry_price": 4300, "quantity_ounces": 1, "thesis": "Private"},
    )
    assert created.status_code == 201
    assert len(client.get("/api/journal").json()) == 1

    second_account = client.post(
        "/api/auth/register",
        json={"email": "another@example.test", "password": "Different secure password 123"},
    )
    assert second_account.status_code == 201
    assert client.get("/api/journal").json() == []


def test_authentication_sets_secure_session_cookie_and_allows_login(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "true")
    client.post("/api/auth/logout")
    client.post(
        "/api/auth/register",
        json={"email": "cookie@example.test", "password": "Correct horse battery staple 42"},
    )
    client.post("/api/auth/logout")
    response = client.post(
        "/api/auth/login",
        json={"email": "cookie@example.test", "password": "Correct horse battery staple 42"},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=strict" in cookie


def test_authentication_attempts_are_rate_limited(client: TestClient) -> None:
    main.auth_attempts.clear()
    payload = {"email": "unknown@example.test", "password": "Correct horse battery staple 42"}
    for _ in range(10):
        assert client.post("/api/auth/login", json=payload).status_code == 401
    assert client.post("/api/auth/login", json=payload).status_code == 429


def test_password_reset_flow_updates_credentials(client: TestClient) -> None:
    email = "reset@example.test"
    registered = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Correct horse battery staple 42"},
    )
    assert registered.status_code == 201
    request = client.post("/api/auth/request-password-reset", json={"email": email})
    assert request.status_code == 200
    token = request.json()["reset_token"]

    reset = client.post(
        "/api/auth/reset-password",
        json={"email": email, "token": token, "new_password": "New secure password 99"},
    )
    assert reset.status_code == 200

    login = client.post(
        "/api/auth/login",
        json={"email": email, "password": "New secure password 99"},
    )
    assert login.status_code == 200


def test_email_verification_flow_marks_account_verified(client: TestClient) -> None:
    email = "verify@example.test"
    registered = client.post(
        "/api/auth/register",
        json={"email": email, "password": "Correct horse battery staple 42"},
    )
    assert registered.status_code == 201
    assert registered.json()["email_verified"] is False

    request = client.post("/api/auth/request-email-verification")
    assert request.status_code == 200
    token = request.json()["verification_token"]

    verify = client.post(
        "/api/auth/verify-email",
        json={"email": email, "token": token},
    )
    assert verify.status_code == 200
    assert verify.json()["message"] == "Email verified successfully."

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email_verified"] is True


def test_smc_analysis_returns_market_structure_summary(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    candles = [
        {"date": "2026-01-01", "open": 2330, "high": 2338, "low": 2328, "close": 2334, "volume": 1000},
        {"date": "2026-01-02", "open": 2334, "high": 2346, "low": 2332, "close": 2342, "volume": 1100},
        {"date": "2026-01-03", "open": 2342, "high": 2355, "low": 2340, "close": 2350, "volume": 1200},
        {"date": "2026-01-04", "open": 2350, "high": 2362, "low": 2348, "close": 2358, "volume": 1300},
        {"date": "2026-01-05", "open": 2358, "high": 2367, "low": 2352, "close": 2362, "volume": 1400},
    ]
    monkeypatch.setattr(main.alpha_vantage, "fetch", AsyncMock(return_value={"data": candles}))

    response = client.get("/api/analysis/smc")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "live"
    assert payload["session_bias"] in {"Bullish", "Bearish", "Neutral"}
    assert "market_structure" in payload
    assert "liquidity" in payload
    assert "order_block" in payload
    assert "fair_value_gap" in payload


def test_ict_analysis_returns_session_and_liquidity_summary(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    candles = [
        {"date": "2026-01-01", "open": 2330, "high": 2338, "low": 2328, "close": 2334, "volume": 1000},
        {"date": "2026-01-02", "open": 2334, "high": 2346, "low": 2332, "close": 2342, "volume": 1100},
        {"date": "2026-01-03", "open": 2342, "high": 2355, "low": 2340, "close": 2350, "volume": 1200},
        {"date": "2026-01-04", "open": 2350, "high": 2362, "low": 2348, "close": 2358, "volume": 1300},
        {"date": "2026-01-05", "open": 2358, "high": 2367, "low": 2352, "close": 2362, "volume": 1400},
    ]
    monkeypatch.setattr(main.alpha_vantage, "fetch", AsyncMock(return_value={"data": candles}))

    response = client.get("/api/analysis/ict")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "live"
    assert payload["session_bias"] in {"Bullish", "Bearish", "Neutral"}
    assert "liquidity" in payload
    assert "fair_value_gap" in payload
    assert "displacement" in payload
    assert "narrative" in payload
    assert len(payload["indicators"]) >= 4


def test_order_flow_analysis_returns_institutional_pressure_summary(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    candles = [
        {"date": "2026-01-01", "open": 2330, "high": 2338, "low": 2328, "close": 2334, "volume": 1000},
        {"date": "2026-01-02", "open": 2334, "high": 2346, "low": 2332, "close": 2342, "volume": 1100},
        {"date": "2026-01-03", "open": 2342, "high": 2355, "low": 2340, "close": 2350, "volume": 1200},
        {"date": "2026-01-04", "open": 2350, "high": 2362, "low": 2348, "close": 2358, "volume": 1300},
        {"date": "2026-01-05", "open": 2358, "high": 2367, "low": 2352, "close": 2362, "volume": 1400},
    ]
    monkeypatch.setattr(main.alpha_vantage, "fetch", AsyncMock(return_value={"data": candles}))

    response = client.get("/api/analysis/order-flow")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "live"
    assert payload["order_flow"]["pressure"] in {"Bullish", "Bearish", "Balanced"}
    assert payload["order_flow"]["absorption"] in {"Strong", "Moderate", "Low"}
    assert "interpretation" in payload["order_flow"]
    assert len(payload["signals"]) >= 1


def test_production_startup_requires_secure_auth_cookie(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUTH_COOKIE_SECURE", "false")

    async def start_app() -> None:
        async with app.router.lifespan_context(app):
            pass

    with pytest.raises(RuntimeError, match="AUTH_COOKIE_SECURE must be true"):
        asyncio.run(start_app())


def test_price_alert_creates_private_notification_on_quote(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    alert = client.post("/api/alerts", json={"direction": "above", "target_price": 2300})
    assert alert.status_code == 201

    monkeypatch.setattr(
        main.alpha_vantage,
        "fetch",
        AsyncMock(return_value={"price": "2400", "timestamp": "2026-10-17T12:00:00Z"}),
    )
    main.quote_cache = None
    quote = client.get("/api/market/gold")

    assert quote.json()["status"] == "live"
    notifications = client.get("/api/notifications").json()
    assert len(notifications) == 1
    assert "reached $2,400.00" in notifications[0]["message"]
    alert_id = alert.json()["id"]

    second_account = client.post(
        "/api/auth/register",
        json={"email": "notification-owner@example.test", "password": "Different secure password 123"},
    )
    assert second_account.status_code == 201
    assert client.get("/api/notifications").json() == []
    assert client.delete(f"/api/alerts/{alert_id}").status_code == 404


def test_dashboard_summary_uses_only_authenticated_users_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client.post(
        "/api/journal",
        json={"side": "BUY", "entry_price": 2000, "exit_price": 2050, "quantity_ounces": 2},
    )
    client.post(
        "/api/journal",
        json={"side": "SELL", "entry_price": 2100, "quantity_ounces": 1},
    )
    monkeypatch.setattr(
        main,
        "gold_quote",
        AsyncMock(return_value={"price": 2050, "status": "live", "source": "Alpha Vantage"}),
    )

    result = client.get("/api/dashboard").json()

    assert result["trade_count"] == 2
    assert result["open_positions"] == 1
    assert result["closed_pnl"] == 100
    assert result["win_rate"] == 100
    assert result["quote"]["source"] == "Alpha Vantage"


def test_heatmap_only_uses_sourced_market_and_calendar_inputs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = datetime.now(timezone.utc)
    monkeypatch.setattr(
        main,
        "gold_history",
        AsyncMock(return_value={
            "candles": [{"close": close} for close in [2000, 2010, 2020, 2030, 2040, 2050]],
            "source": "Alpha Vantage",
            "status": "live",
        }),
    )
    monkeypatch.setattr(
        main,
        "gold_news",
        AsyncMock(return_value={
            "items": [{"sentiment_score": 0.5}],
            "source": "NewsAPI",
            "status": "live",
        }),
    )
    monkeypatch.setattr(
        main,
        "economic_calendar",
        AsyncMock(return_value={
            "events": [{"date": current.isoformat(), "impact": "High"}],
            "source": "Forex Factory calendar",
            "status": "live",
        }),
    )

    result = client.get("/api/market/heatmap").json()

    assert result["status"] == "live"
    assert [factor["name"] for factor in result["factors"]] == [
        "Gold momentum",
        "News sentiment",
        "USD event risk",
    ]
    assert result["factors"][0]["score"] > 0
    assert result["factors"][1]["score"] == 0.5
    assert "1 high-impact event" in result["factors"][2]["reading"]


def test_economic_calendar_intelligence_aggregates_macro_bias(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "fetch_economic_calendar_data",
        AsyncMock(return_value={
            "events": [
                {"title": "US CPI", "country": "USD", "date": "2026-10-18T13:30:00Z", "impact": "high", "forecast": "3.2%", "previous": "3.1%"},
                {"title": "Fed Statement", "country": "USD", "date": "2026-10-19T18:00:00Z", "impact": "medium", "forecast": "Hold", "previous": "Hold"},
                {"title": "Initial Jobless Claims", "country": "USD", "date": "2026-10-20T08:30:00Z", "impact": "low", "forecast": "220K", "previous": "225K"},
            ],
            "source": "Forex Factory calendar",
            "status": "live",
        }),
    )

    result = client.get("/api/analysis/calendar").json()

    assert result["status"] == "live"
    assert result["market_bias"] in {"Bullish", "Bearish", "Neutral"}
    assert result["next_event"]["title"] == "US CPI"
    assert result["next_event"]["impact"] == "HIGH"
    assert result["upcoming_events"][0]["title"] in {"US CPI", "Fed Statement", "Initial Jobless Claims"}


def test_news_intelligence_predicts_bullish_outcome_for_supportive_headlines(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main.newsapi,
        "gold_headlines",
        AsyncMock(return_value={
            "articles": [
                {"title": "Gold gains as inflation fears intensify", "source": {"name": "Reuters"}, "publishedAt": "2026-10-17T11:00:00Z"},
                {"title": "Fed rate cut bets support safe haven demand", "source": {"name": "Bloomberg"}, "publishedAt": "2026-10-17T10:30:00Z"},
                {"title": "Dollar strength moderates as yields soften", "source": {"name": "Reuters"}, "publishedAt": "2026-10-17T09:00:00Z"},
            ]
        }),
    )

    result = client.get("/api/news/intelligence").json()

    assert result["status"] == "live"
    assert result["sentiment"]["bias"] == "bullish"
    assert result["prediction"]["direction"] == "bullish"
    assert result["prediction"]["probability"] >= 50
    assert result["headline_focus"]


def test_news_intelligence_handles_missing_provider_data(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main.newsapi,
        "gold_headlines",
        AsyncMock(side_effect=RuntimeError("NewsAPI unavailable")),
    )

    result = client.get("/api/news/intelligence").json()

    assert result["status"] == "unavailable"
    assert result["sentiment"]["bias"] == "neutral"
    assert result["prediction"]["direction"] == "neutral"


def test_technical_analysis_returns_indicators_and_summary(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candles = [
        {"date": f"2024-01-{day:02d}", "open": 2200 + day, "high": 2210 + day, "low": 2195 + day, "close": 2205 + day, "volume": 1800}
        for day in range(1, 61)
    ]
    monkeypatch.setattr(
        main.alpha_vantage,
        "fetch",
        AsyncMock(return_value={"data": candles}),
    )

    result = client.get("/api/analysis/technical").json()

    assert result["status"] == "live"
    assert result["provider"] == "Alpha Vantage"
    assert result["summary"]["overall_bias"] in {"bullish", "bearish", "neutral"}
    assert len(result["indicators"]) == 13
    assert {indicator["name"] for indicator in result["indicators"]} >= {"EMA 20", "RSI (14)", "MACD", "VWAP", "Stochastic RSI"}


def test_technical_analysis_fails_gracefully_when_provider_is_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main.alpha_vantage,
        "fetch",
        AsyncMock(side_effect=RuntimeError("Provider unavailable")),
    )

    result = client.get("/api/analysis/technical").json()

    assert result["status"] == "unavailable"
    assert result["summary"]["overall_bias"] == "neutral"
    assert result["indicators"][0]["interpretation"] == "Technical data is temporarily unavailable."


def test_signal_engine_generates_buy_signal_when_market_is_bullish(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "gold_quote",
        AsyncMock(return_value={
            "symbol": "XAU/USD",
            "price": 2350,
            "status": "live",
            "source": "Alpha Vantage",
            "change_percent": 1.5,
        }),
    )
    monkeypatch.setattr(
        main,
        "technical_analysis",
        AsyncMock(return_value={
            "status": "live",
            "provider": "Alpha Vantage",
            "summary": {"overall_bias": "bullish", "trend_strength": "strong", "volatility": "moderate", "momentum": "positive"},
            "indicators": [
                {"name": "EMA 20", "value": 2320.0},
                {"name": "EMA 50", "value": 2305.0},
                {"name": "RSI (14)", "value": 62.0},
                {"name": "MACD", "value": 10.0},
                {"name": "VWAP", "value": 2310.0},
                {"name": "ATR", "value": 12.0},
            ],
        }),
    )

    result = client.get("/api/signals/current").json()

    assert result["status"] == "live"
    assert result["signal"] == "BUY"
    assert 0 <= result["confidence"] <= 100
    assert result["entry"] == 2350.0
    assert result["take_profit"][0] > result["entry"]
    assert len(result["reasons"]) >= 1
    assert result["reasons"][0]["indicator"] in {"EMA 20", "EMA 50", "RSI (14)", "MACD", "VWAP", "ATR"}


def test_signal_engine_generates_sell_signal_when_market_is_bearish(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "gold_quote",
        AsyncMock(return_value={
            "symbol": "XAU/USD",
            "price": 2330,
            "status": "live",
            "source": "Alpha Vantage",
            "change_percent": -1.4,
        }),
    )
    monkeypatch.setattr(
        main,
        "technical_analysis",
        AsyncMock(return_value={
            "status": "live",
            "provider": "Alpha Vantage",
            "summary": {"overall_bias": "bearish", "trend_strength": "weak", "volatility": "moderate", "momentum": "negative"},
            "indicators": [
                {"name": "EMA 20", "value": 2360.0},
                {"name": "EMA 50", "value": 2355.0},
                {"name": "RSI (14)", "value": 39.0},
                {"name": "MACD", "value": -8.0},
                {"name": "VWAP", "value": 2360.0},
                {"name": "ATR", "value": 18.0},
            ],
        }),
    )

    result = client.get("/api/signals/current").json()

    assert result["status"] == "live"
    assert result["signal"] == "SELL"
    assert result["take_profit"][0] < result["entry"]


def test_signal_engine_uses_hold_when_data_is_missing(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "gold_quote",
        AsyncMock(return_value={
            "symbol": "XAU/USD",
            "price": None,
            "status": "unavailable",
            "source": "unavailable",
            "change_percent": None,
        }),
    )
    monkeypatch.setattr(
        main,
        "technical_analysis",
        AsyncMock(return_value={
            "status": "unavailable",
            "provider": "unavailable",
            "summary": {"overall_bias": "neutral", "trend_strength": "neutral", "volatility": "low", "momentum": "neutral"},
            "indicators": [],
        }),
    )

    result = client.get("/api/signals/current").json()

    assert result["signal"] == "HOLD"
    assert result["confidence"] == 0
    assert result["status"] in {"unavailable", "live"}


def test_signal_engine_handles_unavailable_provider_gracefully(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "gold_quote",
        AsyncMock(return_value={
            "symbol": "XAU/USD",
            "price": 2348.0,
            "status": "live",
            "source": "Finnhub",
            "change_percent": 0,
        }),
    )
    monkeypatch.setattr(
        main,
        "technical_analysis",
        AsyncMock(return_value={
            "status": "unavailable",
            "provider": "unavailable",
            "summary": {"overall_bias": "neutral", "trend_strength": "neutral", "volatility": "low", "momentum": "neutral"},
            "indicators": [],
        }),
    )

    result = client.get("/api/signals/current").json()

    assert result["status"] in {"unavailable", "live"}
    assert result["signal"] in {"HOLD", "BUY", "SELL"}
    assert "note" in result


def test_ai_decision_engine_synthesizes_bullish_confluence(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "gold_quote",
        AsyncMock(return_value={
            "symbol": "XAU/USD",
            "price": 2360.0,
            "status": "live",
            "source": "Alpha Vantage",
            "change_percent": 1.8,
        }),
    )
    monkeypatch.setattr(
        main,
        "technical_analysis",
        AsyncMock(return_value={
            "status": "live",
            "provider": "Alpha Vantage",
            "summary": {"overall_bias": "bullish", "overall_score": 76, "trend_strength": "strong", "volatility": "moderate", "momentum": "positive", "quality": "high"},
            "indicators": [
                {"name": "EMA 20", "value": 2348.0},
                {"name": "EMA 50", "value": 2335.0},
                {"name": "RSI (14)", "value": 61.0},
                {"name": "MACD", "value": 3.4},
                {"name": "VWAP", "value": 2341.0},
                {"name": "ATR", "value": 12.0},
            ],
        }),
    )
    monkeypatch.setattr(
        main,
        "news_intelligence",
        AsyncMock(return_value={
            "status": "live",
            "source": "NewsAPI",
            "sentiment": {"score": 0.52, "bias": "bullish", "article_count": 3, "source": "NewsAPI", "method": "headline scoring"},
            "prediction": {"direction": "bullish", "probability": 72, "confidence": "high", "rationale": "Gold demand remains strong."},
            "headline_focus": "Gold demand remains strong",
            "timestamp": "2026-10-17T12:00:00Z",
        }),
    )
    monkeypatch.setattr(
        main,
        "calendar_analysis",
        AsyncMock(return_value={
            "symbol": "XAU/USD",
            "provider": "Forex Factory calendar",
            "status": "live",
            "timestamp": "2026-10-17T12:00:00Z",
            "risk_bucket": "High",
            "market_bias": "Bullish",
            "summary": "Macro catalysts are supportive of gold.",
            "next_event": {"title": "US CPI", "date": "2026-10-18T13:30:00Z"},
            "upcoming_events": [],
        }),
    )

    response = client.get("/api/ai/decision")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "live"
    assert payload["decision"] == "bullish"
    assert 0 <= payload["confidence"] <= 100
    assert "narrative" in payload
    assert payload["drivers"]


def test_ai_decision_engine_handles_missing_data_gracefully(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "gold_quote",
        AsyncMock(return_value={
            "symbol": "XAU/USD",
            "price": None,
            "status": "unavailable",
            "source": "unavailable",
            "change_percent": None,
        }),
    )
    monkeypatch.setattr(
        main,
        "technical_analysis",
        AsyncMock(return_value={
            "status": "unavailable",
            "provider": "unavailable",
            "summary": {"overall_bias": "neutral", "overall_score": 50, "trend_strength": "neutral", "volatility": "low", "momentum": "neutral", "quality": "limited"},
            "indicators": [],
        }),
    )
    monkeypatch.setattr(
        main,
        "news_intelligence",
        AsyncMock(return_value={
            "status": "unavailable",
            "source": "unavailable",
            "sentiment": {"score": 0, "bias": "neutral", "article_count": 0, "source": "unavailable", "method": "No headlines available."},
            "prediction": {"direction": "neutral", "probability": 0, "confidence": "low", "rationale": "No data."},
            "headline_focus": None,
            "timestamp": None,
        }),
    )
    monkeypatch.setattr(
        main,
        "calendar_analysis",
        AsyncMock(return_value={
            "symbol": "XAU/USD",
            "provider": "unavailable",
            "status": "unavailable",
            "timestamp": None,
            "risk_bucket": "Low",
            "market_bias": "Neutral",
            "summary": "No macro data available.",
            "next_event": None,
            "upcoming_events": [],
        }),
    )

    response = client.get("/api/ai/decision")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] in {"live", "unavailable"}
    assert payload["decision"] in {"bullish", "bearish", "neutral"}
    assert 0 <= payload["confidence"] <= 100
    assert "narrative" in payload
