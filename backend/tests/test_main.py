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
