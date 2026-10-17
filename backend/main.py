from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import AsyncIterator, Generator, Literal

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pwdlib import PasswordHash
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, create_engine, func, inspect, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from backend.config import validate_required_api_keys
from backend.services import alpha_vantage, finnhub, newsapi


logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./gold_intelligence.db")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    side: Mapped[str] = mapped_column(String(4))
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    quantity_ounces: Mapped[float] = mapped_column(Float)
    thesis: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    direction: Mapped[str] = mapped_column(String(8))
    target_price: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("price_alerts.id", ondelete="SET NULL"), nullable=True)
    message: Mapped[str] = mapped_column(String(500))
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)
if "user_id" not in {column["name"] for column in inspect(engine).get_columns("journal_entries")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE journal_entries ADD COLUMN user_id INTEGER REFERENCES users(id)"))

password_hasher = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"
SESSION_COOKIE = "aurum_session"
SESSION_TTL = timedelta(days=7)

@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    validate_required_api_keys()
    if os.getenv("APP_ENV", "development").lower() == "production":
        if os.getenv("AUTH_COOKIE_SECURE", "false").lower() != "true":
            raise RuntimeError("AUTH_COOKIE_SECURE must be true in production.")
        if "*" in os.getenv("CORS_ORIGINS", ""):
            raise RuntimeError("CORS_ORIGINS must not contain '*' in production.")
    yield


app = FastAPI(title="Gold Intelligence API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

quote_cache: tuple[float, dict] | None = None
history_cache: tuple[float, dict] | None = None
news_cache: tuple[float, dict] | None = None
provider_health_cache: tuple[float, dict] | None = None
calendar_cache: tuple[float, dict] | None = None
auth_attempts: dict[str, deque[float]] = defaultdict(deque)
auth_attempt_lock = Lock()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AuthRequest(BaseModel):
    email: str = Field(min_length=5, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=128)


class JournalCreate(BaseModel):
    side: str = Field(pattern="^(BUY|SELL)$")
    entry_price: float = Field(gt=0)
    exit_price: float | None = Field(default=None, gt=0)
    quantity_ounces: float = Field(gt=0)
    thesis: str = Field(default="", max_length=1000)


class AlertCreate(BaseModel):
    direction: str = Field(pattern="^(above|below)$")
    target_price: float = Field(gt=0)


def create_session_token(user: User) -> str:
    secret = os.environ["JWT_SECRET_KEY"]
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": now + SESSION_TTL},
        secret,
        algorithm=JWT_ALGORITHM,
    )


def set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(user),
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true",
        samesite="strict",
        path="/",
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET_KEY"], algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account no longer exists.")
    return user


def serialize_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "created_at": user.created_at.isoformat()}


def enforce_auth_rate_limit(request: Request) -> None:
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with auth_attempt_lock:
        attempts = auth_attempts[client_ip]
        while attempts and now - attempts[0] > 900:
            attempts.popleft()
        if len(attempts) >= 10:
            raise HTTPException(status_code=429, detail="Too many authentication attempts. Try again later.")
        attempts.append(now)


@app.post("/api/auth/register", status_code=201)
def register(
    request: AuthRequest,
    response: Response,
    client_request: Request,
    db: Session = Depends(get_db),
) -> dict:
    enforce_auth_rate_limit(client_request)
    email = request.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    user = User(email=email, password_hash=password_hasher.hash(request.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists.") from None
    db.refresh(user)
    set_session_cookie(response, user)
    return serialize_user(user)


@app.post("/api/auth/login")
def login(
    request: AuthRequest,
    response: Response,
    client_request: Request,
    db: Session = Depends(get_db),
) -> dict:
    enforce_auth_rate_limit(client_request)
    email = request.email.lower().strip()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not password_hasher.verify(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    set_session_cookie(response, user)
    return serialize_user(user)


@app.get("/api/auth/me")
def current_user(user: User = Depends(get_current_user)) -> dict:
    return serialize_user(user)


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true", samesite="strict")


def score_headline(text_value: str) -> tuple[float, str, str]:
    text_value = text_value.lower()
    bullish_terms = (
        "inflation", "war", "conflict", "uncertainty", "safe haven", "rate cut",
        "dovish", "weak dollar", "recession", "gold rises", "gold gains",
    )
    bearish_terms = (
        "rate hike", "hawkish", "strong dollar", "yields rise", "ceasefire",
        "risk appetite", "inflation cools", "gold falls", "gold drops",
    )
    bullish = sum(term in text_value for term in bullish_terms)
    bearish = sum(term in text_value for term in bearish_terms)
    score = (bullish - bearish) / max(bullish + bearish, 1)
    bias = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"
    impact = "high" if bullish + bearish >= 2 else "medium" if bullish + bearish else "low"
    return score, bias, impact


def notify_price_alerts(price: float) -> None:
    try:
        with SessionLocal() as db:
            alerts = db.scalars(select(PriceAlert).where(PriceAlert.active.is_(True))).all()
            for alert in alerts:
                triggered = price >= alert.target_price if alert.direction == "above" else price <= alert.target_price
                if triggered:
                    alert.active = False
                    db.add(
                        Notification(
                            user_id=alert.user_id,
                            alert_id=alert.id,
                            message=f"Gold reached ${price:,.2f}, {alert.direction} your ${alert.target_price:,.2f} alert.",
                        )
                    )
            db.commit()
    except SQLAlchemyError:
        logger.exception("Failed to evaluate price alerts")


def serialize_alert(alert: PriceAlert) -> dict:
    return {
        "id": alert.id,
        "direction": alert.direction,
        "target_price": alert.target_price,
        "active": alert.active,
        "created_at": alert.created_at.isoformat(),
    }


def serialize_notification(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "message": notification.message,
        "read": notification.read,
        "created_at": notification.created_at.isoformat(),
    }


@app.get("/api/health")
async def health() -> dict:
    global provider_health_cache
    now = time.time()
    if provider_health_cache and now - provider_health_cache[0] < 60:
        return provider_health_cache[1]

    async def check_provider(name: str, priority: str, check) -> tuple[str, dict]:
        try:
            await check()
            return name, {
                "status": "available",
                "priority": priority,
                "warning": None,
            }
        except (RuntimeError, httpx.HTTPError, KeyError, TypeError, ValueError, OSError) as error:
            warning = f"{name} is unavailable: {error}"
            logger.warning("%s provider health check failed: %s", name, error)
            return name, {
                "status": "unavailable",
                "priority": priority,
                "warning": warning,
            }

    checked = await asyncio.gather(
        check_provider("Alpha Vantage", "primary", alpha_vantage.health_check),
        check_provider("Finnhub", "secondary", finnhub.health_check),
    )
    providers = dict(checked)
    warnings = [provider["warning"] for provider in providers.values() if provider["warning"]]
    result = {
        "status": "ok",
        "service": "gold-intelligence-api",
        "providers": providers,
        "warnings": warnings,
    }
    provider_health_cache = (now, result)
    return result


@app.get("/api/health/live")
def liveness() -> dict:
    return {"status": "ok"}


@app.get("/api/market/gold")
async def gold_quote() -> dict:
    global quote_cache
    now = time.time()
    if quote_cache and now - quote_cache[0] < 5400:
        logger.info("Serving cached XAU/USD quote from %s", quote_cache[1]["source"])
        if quote_cache[1]["price"] is not None:
            notify_price_alerts(quote_cache[1]["price"])
        return quote_cache[1]
    try:
        quote = await alpha_vantage.fetch("GOLD_SILVER_SPOT", symbol="GOLD")
        result = {
            "symbol": "XAU/USD",
            "price": float(quote["price"]),
            "updated_at": quote.get("timestamp"),
            "source": "Alpha Vantage",
            "status": "live",
            "note": None,
        }
        quote_cache = (now, result)
        logger.info("Serving XAU/USD quote from Alpha Vantage")
        notify_price_alerts(result["price"])
        return result
    except (RuntimeError, httpx.HTTPError, KeyError, TypeError, ValueError, OSError) as alpha_error:
        logger.warning("Alpha Vantage quote unavailable: %s", alpha_error)
        try:
            quote = await finnhub.quote()
            result = {
                "symbol": "XAU/USD",
                "price": float(quote["c"]),
                "updated_at": datetime.fromtimestamp(quote["t"], timezone.utc).isoformat(),
                "source": "Finnhub",
                "status": "live",
                "note": None,
            }
            quote_cache = (now, result)
            logger.info("Serving XAU/USD quote from Finnhub")
            notify_price_alerts(result["price"])
            return result
        except (RuntimeError, httpx.HTTPError, KeyError, TypeError, ValueError, OSError) as finnhub_error:
            logger.warning("Finnhub quote unavailable: %s", finnhub_error)
            return {
                "symbol": "XAU/USD",
                "price": None,
                "updated_at": None,
                "source": "unavailable",
                "status": "unavailable",
                "note": "Gold quote is unavailable from Alpha Vantage and Finnhub.",
            }


@app.get("/api/market/history")
async def gold_history() -> dict:
    global history_cache
    now = time.time()
    if history_cache and now - history_cache[0] < 86400:
        logger.info("Serving cached XAU/USD history from %s", history_cache[1]["source"])
        return history_cache[1]
    try:
        data = await alpha_vantage.fetch(
            "GOLD_SILVER_HISTORY", symbol="GOLD", interval="daily"
        )
        candles = [
            {"date": point["date"], "close": float(point["price"])}
            for point in sorted(data["data"], key=lambda point: point["date"])
        ]
        result = {"candles": candles, "source": "Alpha Vantage", "status": "live"}
        history_cache = (now, result)
        logger.info("Serving XAU/USD history from Alpha Vantage")
        return result
    except (RuntimeError, httpx.HTTPError, KeyError, TypeError, ValueError, OSError) as alpha_error:
        logger.warning("Alpha Vantage history unavailable: %s", alpha_error)
        try:
            data = await finnhub.daily_candles()
            candles = [
                {
                    "date": datetime.fromtimestamp(timestamp, timezone.utc).date().isoformat(),
                    "close": float(close),
                }
                for timestamp, close in zip(data["t"], data["c"], strict=True)
            ]
            result = {"candles": candles, "source": "Finnhub", "status": "live"}
            history_cache = (now, result)
            logger.info("Serving XAU/USD history from Finnhub")
            return result
        except (RuntimeError, httpx.HTTPError, KeyError, TypeError, ValueError, OSError) as finnhub_error:
            logger.warning("Finnhub history unavailable: %s", finnhub_error)
            return {
                "candles": [],
                "source": "unavailable",
                "status": "unavailable",
                "note": "Gold history is unavailable from Alpha Vantage and Finnhub.",
            }


@app.get("/api/calendar")
async def economic_calendar() -> dict:
    global calendar_cache
    now = time.time()
    if calendar_cache and now - calendar_cache[0] < 3600:
        return calendar_cache[1]
    url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    try:
        async with httpx.AsyncClient(timeout=10, headers={"User-Agent": "GoldIntelligence/1.0"}) as client:
            response = await client.get(url)
            response.raise_for_status()
        events = response.json()
        if not isinstance(events, list):
            raise ValueError("Calendar provider returned an unexpected response.")
        usd_events = [
            {
                "title": event.get("title", "Economic release"),
                "country": event.get("country", "USD"),
                "date": event.get("date"),
                "impact": event.get("impact", ""),
                "forecast": event.get("forecast"),
                "previous": event.get("previous"),
            }
            for event in events
            if event.get("country") == "USD"
        ]
        result = {"events": usd_events, "source": "Forex Factory calendar", "status": "live"}
        calendar_cache = (now, result)
        return result
    except (httpx.HTTPError, ValueError, TypeError) as error:
        return {"events": [], "source": "unavailable", "status": "unavailable", "note": str(error)}


@app.get("/api/news")
async def gold_news() -> dict:
    global news_cache
    now = time.time()
    if news_cache and now - news_cache[0] < 3600:
        return news_cache[1]
    try:
        data = await newsapi.gold_headlines()
        articles = data.get("articles")
        if not isinstance(articles, list):
            raise RuntimeError("NewsAPI returned an unexpected article list.")
        items = [
            {
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "published_at": article.get("publishedAt", ""),
                "source": (
                    article.get("source", {}).get("name", "NewsAPI")
                    if isinstance(article.get("source"), dict)
                    else "NewsAPI"
                ),
                "sentiment_score": score_headline(str(article.get("title") or ""))[0],
                "bias": score_headline(str(article.get("title") or ""))[1],
                "impact": score_headline(str(article.get("title") or ""))[2],
            }
            for article in articles
            if isinstance(article, dict)
        ]
        result = {"items": items, "source": "NewsAPI", "status": "live"}
        news_cache = (now, result)
        return result
    except (RuntimeError, httpx.HTTPError, KeyError, ValueError, TypeError) as error:
        return {"items": [], "source": "unavailable", "status": "unavailable", "note": str(error)}


@app.get("/api/news/sentiment")
async def news_sentiment() -> dict:
    news = await gold_news()
    items = news["items"]
    if not items:
        return {
            "score": 0,
            "bias": "neutral",
            "article_count": 0,
            "source": news["source"],
            "status": news["status"],
            "note": news.get("note", "No headlines are available for sentiment analysis."),
        }
    score = sum(item["sentiment_score"] for item in items) / len(items)
    return {
        "score": round(score, 3),
        "bias": "bullish" if score > 0.1 else "bearish" if score < -0.1 else "neutral",
        "article_count": len(items),
        "source": news["source"],
        "status": news["status"],
        "method": "Transparent local keyword scoring; not investment advice.",
    }


class AnalysisRequest(BaseModel):
    headline: str = Field(min_length=5, max_length=1000)


class AnalysisResult(BaseModel):
    bias: Literal["bullish", "bearish", "neutral"]
    impact: Literal["low", "medium", "high"]
    confidence: int = Field(ge=0, le=100)
    rationale: str = Field(min_length=1, max_length=500)


@app.post("/api/news/analyze")
async def analyze_news(
    request: AnalysisRequest,
    user: User = Depends(get_current_user),
) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": "Assess this headline's likely short-term impact on spot gold (XAU/USD). Return JSON with bias (bullish, bearish, or neutral), impact (low, medium, high), confidence (0-100), and rationale (one sentence). Do not give financial advice."},
                            {"role": "user", "content": request.headline},
                        ],
                    },
                )
                response.raise_for_status()
            import json

            result = json.loads(response.json()["choices"][0]["message"]["content"])
            validated = AnalysisResult.model_validate(result)
            return {**validated.model_dump(), "method": "OpenAI", "headline": request.headline}
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as error:
            logger.warning("OpenAI analysis unavailable; using local screening: %s", error)

    score, bias, impact = score_headline(request.headline)
    return {
        "bias": bias,
        "impact": impact,
        "confidence": round(35 + abs(score) * 40) if bias != "neutral" else 35,
        "rationale": "Keyword-based screening only; verify the source and confirm with market pricing.",
        "method": "heuristic",
        "headline": request.headline,
    }


@app.get("/api/signals")
async def trading_signal() -> dict:
    history = await gold_history()
    candles = history["candles"]
    if len(candles) < 2:
        return {"signal": "WAIT", "confidence": 0, "source": history["source"], "note": "Price history is unavailable."}
    closes = [candle["close"] for candle in candles]
    average = sum(closes[-20:]) / len(closes[-20:])
    change = (closes[-1] - closes[-2]) / closes[-2] * 100
    if closes[-1] > average and change > 0:
        signal = "BUY"
    elif closes[-1] < average and change < 0:
        signal = "SELL"
    else:
        signal = "WAIT"
    return {
        "signal": signal,
        "confidence": min(85, 50 + round(abs(change) * 12)),
        "change_percent": round(change, 3),
        "sma_20": round(average, 2),
        "source": history["source"],
        "method": "20-day SMA and daily momentum; informational only",
    }


class RiskRequest(BaseModel):
    account_balance: float = Field(gt=0)
    risk_percent: float = Field(gt=0, le=100)
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)


@app.post("/api/risk")
def calculate_risk(request: RiskRequest) -> dict:
    distance = abs(request.entry_price - request.stop_price)
    if distance == 0:
        raise HTTPException(status_code=422, detail="Entry and stop prices must differ.")
    risk_amount = request.account_balance * request.risk_percent / 100
    ounces = risk_amount / distance
    return {
        "risk_amount": round(risk_amount, 2),
        "stop_distance": round(distance, 2),
        "position_ounces": round(ounces, 4),
        "standard_lots": round(ounces / 100, 4),
        "assumption": "1 standard XAU/USD lot = 100 troy ounces",
    }


@app.get("/api/market/heatmap")
async def gold_driver_heatmap() -> dict:
    history, news, calendar = await asyncio.gather(
        gold_history(),
        gold_news(),
        economic_calendar(),
    )
    candles = history.get("candles", [])
    closes = [float(candle["close"]) for candle in candles if candle.get("close") is not None]
    momentum = (
        (closes[-1] - closes[-6]) / closes[-6]
        if len(closes) >= 6 and closes[-6]
        else 0.0
    )
    momentum_score = max(-1.0, min(1.0, momentum * 20))
    headlines = news.get("items", [])
    sentiment = (
        sum(item["sentiment_score"] for item in headlines) / len(headlines)
        if headlines
        else 0.0
    )
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(hours=24)
    upcoming = []
    for event in calendar.get("events", []):
        date_value = event.get("date")
        if not date_value:
            continue
        try:
            event_time = datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            if event_time.tzinfo is None:
                event_time = event_time.replace(tzinfo=timezone.utc)
            else:
                event_time = event_time.astimezone(timezone.utc)
        except (AttributeError, ValueError):
            continue
        if event_time < now - timedelta(minutes=5):
            continue
        if event_time <= cutoff:
            upcoming.append(event)
    high_impact_count = sum(event.get("impact", "").lower() == "high" for event in upcoming)
    factors = [
        {
            "name": "Gold momentum",
            "ticker": "XAU/USD",
            "score": round(momentum_score, 3),
            "bias": "bullish" if momentum_score > 0.05 else "bearish" if momentum_score < -0.05 else "neutral",
            "reading": f"{momentum * 100:+.2f}% over five sessions" if len(closes) >= 6 else "Insufficient price history",
            "source": history.get("source", "unavailable"),
        },
        {
            "name": "News sentiment",
            "ticker": "NEWS",
            "score": round(sentiment, 3),
            "bias": "bullish" if sentiment > 0.1 else "bearish" if sentiment < -0.1 else "neutral",
            "reading": f"{len(headlines)} recent headlines" if headlines else "No recent headlines",
            "source": news.get("source", "unavailable"),
        },
        {
            "name": "USD event risk",
            "ticker": "USD CAL",
            "score": 0,
            "bias": "neutral",
            "reading": (
                f"{high_impact_count} high-impact event(s) in next 24h"
                if calendar.get("status") == "live"
                else "Calendar data unavailable"
            ),
            "source": calendar.get("source", "unavailable"),
        },
    ]
    return {
        "factors": factors,
        "status": "live" if history.get("status") == "live" or news.get("status") == "live" else "unavailable",
        "note": "Only sourced price, headline and calendar factors are shown. This is contextual, not a forecast.",
    }


def serialize_entry(entry: JournalEntry) -> dict:
    return {
        "id": entry.id,
        "side": entry.side,
        "entry_price": entry.entry_price,
        "exit_price": entry.exit_price,
        "quantity_ounces": entry.quantity_ounces,
        "thesis": entry.thesis,
        "created_at": entry.created_at.isoformat(),
        "pnl": round((entry.exit_price - entry.entry_price) * entry.quantity_ounces * (1 if entry.side == "BUY" else -1), 2) if entry.exit_price is not None else None,
    }


@app.get("/api/journal")
def list_journal(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    entries = db.scalars(
        select(JournalEntry)
        .where(JournalEntry.user_id == user.id)
        .order_by(JournalEntry.created_at.desc())
    ).all()
    return [serialize_entry(entry) for entry in entries]


@app.post("/api/journal", status_code=201)
def create_journal_entry(
    request: JournalCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    entry = JournalEntry(**request.model_dump(), user_id=user.id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return serialize_entry(entry)


@app.delete("/api/journal/{entry_id}", status_code=204)
def delete_journal_entry(
    entry_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    entry = db.scalar(
        select(JournalEntry).where(JournalEntry.id == entry_id, JournalEntry.user_id == user.id)
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="Journal entry not found.")
    db.delete(entry)
    db.commit()


@app.get("/api/dashboard")
async def dashboard_summary(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    entries = db.scalars(select(JournalEntry).where(JournalEntry.user_id == user.id)).all()
    closed_pnl = [
        (entry.exit_price - entry.entry_price)
        * entry.quantity_ounces
        * (1 if entry.side == "BUY" else -1)
        for entry in entries
        if entry.exit_price is not None
    ]
    active_alerts = db.scalar(
        select(func.count()).select_from(PriceAlert).where(
            PriceAlert.user_id == user.id, PriceAlert.active.is_(True)
        )
    ) or 0
    unread_notifications = db.scalar(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user.id, Notification.read.is_(False)
        )
    ) or 0
    return {
        "email": user.email,
        "quote": await gold_quote(),
        "trade_count": len(entries),
        "open_positions": sum(entry.exit_price is None for entry in entries),
        "closed_pnl": round(sum(closed_pnl), 2),
        "win_rate": round(100 * sum(pnl > 0 for pnl in closed_pnl) / len(closed_pnl), 1)
        if closed_pnl
        else None,
        "active_alerts": active_alerts,
        "unread_notifications": unread_notifications,
    }


@app.get("/api/alerts")
def list_alerts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    alerts = db.scalars(
        select(PriceAlert)
        .where(PriceAlert.user_id == user.id)
        .order_by(PriceAlert.created_at.desc())
    ).all()
    return [serialize_alert(alert) for alert in alerts]


@app.post("/api/alerts", status_code=201)
def create_alert(
    request: AlertCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    alert = PriceAlert(
        user_id=user.id,
        direction=request.direction,
        target_price=request.target_price,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return serialize_alert(alert)


@app.delete("/api/alerts/{alert_id}", status_code=204)
def delete_alert(
    alert_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    alert = db.scalar(
        select(PriceAlert).where(PriceAlert.id == alert_id, PriceAlert.user_id == user.id)
    )
    if alert is None:
        raise HTTPException(status_code=404, detail="Price alert not found.")
    db.delete(alert)
    db.commit()


@app.get("/api/notifications")
def list_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    notifications = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    ).all()
    return [serialize_notification(item) for item in notifications]


@app.patch("/api/notifications/{notification_id}/read", status_code=204)
def mark_notification_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user.id,
        )
    )
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    notification.read = True
    db.commit()