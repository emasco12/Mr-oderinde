from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_bias(value: Any) -> str:
    if value is None:
        return "neutral"
    bias = str(value).strip().lower()
    if bias in {"bullish", "buy", "positive"}:
        return "bullish"
    if bias in {"bearish", "sell", "negative"}:
        return "bearish"
    return "neutral"


def generate_ai_decision(
    *,
    quote: dict[str, Any] | None = None,
    technical: dict[str, Any] | None = None,
    signal: dict[str, Any] | None = None,
    news: dict[str, Any] | None = None,
    calendar: dict[str, Any] | None = None,
    provider_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score = 0.0
    drivers: list[dict[str, str]] = []

    if quote:
        change = _safe_float(quote.get("change_percent"), 0.0)
        score += min(10.0, max(-10.0, change * 1.2))
        if change > 0:
            drivers.append({"label": "Price trend", "value": "Positive", "detail": f"Price is up {change:.2f}% over the session."})
        elif change < 0:
            drivers.append({"label": "Price trend", "value": "Negative", "detail": f"Price is down {abs(change):.2f}% over the session."})

    if signal:
        signal_name = str(signal.get("signal", "HOLD")).upper()
        if signal_name == "BUY":
            score += 22.0
            drivers.append({"label": "Signal", "value": "BUY", "detail": "The technical signal stack is favoring upside continuation."})
        elif signal_name == "SELL":
            score -= 22.0
            drivers.append({"label": "Signal", "value": "SELL", "detail": "The technical signal stack is favoring downside continuation."})
        else:
            drivers.append({"label": "Signal", "value": "HOLD", "detail": "Signal quality is mixed and requires confirmation."})

    if technical:
        summary = technical.get("summary", {}) or {}
        bias = _normalize_bias(summary.get("overall_bias"))
        overall_score = _safe_float(summary.get("overall_score"), 50.0)
        if bias == "bullish":
            score += max(0.0, (overall_score - 50.0) * 0.35) + 8.0
            drivers.append({"label": "Technical structure", "value": "Bullish", "detail": f"The technical engine scored {overall_score:.0f}/100 with constructive trend structure."})
        elif bias == "bearish":
            score -= max(0.0, (50.0 - overall_score) * 0.35) + 8.0
            drivers.append({"label": "Technical structure", "value": "Bearish", "detail": f"The technical engine scored {overall_score:.0f}/100 with softening trend structure."})
        else:
            drivers.append({"label": "Technical structure", "value": "Neutral", "detail": "The technical engine is balanced and not yet decisive."})

    if news:
        sentiment = news.get("sentiment", {}) or {}
        prediction = news.get("prediction", {}) or {}
        news_bias = _normalize_bias(prediction.get("direction"))
        probability = _safe_float(prediction.get("probability"), 0.0)
        if news_bias == "bullish":
            score += 12.0 + (probability * 0.08)
            drivers.append({"label": "News flow", "value": "Bullish", "detail": f"Headline momentum is supportive, with {probability:.0f}% bullish probability."})
        elif news_bias == "bearish":
            score -= 12.0 + (probability * 0.08)
            drivers.append({"label": "News flow", "value": "Bearish", "detail": f"Headline momentum is defensive, with {probability:.0f}% bearish probability."})
        else:
            drivers.append({"label": "News flow", "value": "Neutral", "detail": "Headline flow is mixed and not yet directional."})

    if calendar:
        market_bias = _normalize_bias(calendar.get("market_bias"))
        risk_bucket = str(calendar.get("risk_bucket", "Low")).lower()
        if market_bias == "bullish":
            score += 8.0 if risk_bucket in {"moderate", "high"} else 4.0
            drivers.append({"label": "Macro backdrop", "value": "Bullish", "detail": "The macro calendar is supportive, helping the broader gold setup."})
        elif market_bias == "bearish":
            score -= 8.0 if risk_bucket in {"moderate", "high"} else 4.0
            drivers.append({"label": "Macro backdrop", "value": "Bearish", "detail": "The macro calendar is adding defensive pressure to gold."})
        else:
            drivers.append({"label": "Macro backdrop", "value": "Neutral", "detail": "The macro backdrop is balanced and not currently a primary driver."})

    if provider_status:
        unavailable = sum(1 for provider in provider_status.values() if provider.get("status") == "unavailable")
        if unavailable:
            score -= min(5.0, unavailable * 2.5)
            drivers.append({"label": "Data quality", "value": "Cautious", "detail": "One or more providers are degraded, so the read should be treated conservatively."})

    decision = "bullish" if score > 12.0 else "bearish" if score < -12.0 else "neutral"
    confidence = max(35, min(96, int(round(50 + abs(score) * 1.4))))
    watch_points = [
        "Monitor trend continuation above the short-term moving average band.",
        "Watch volatility and risk appetite for confirmation before extending exposure.",
        "Reassess the macro and news regime if the catalyst set changes direction.",
    ]
    if decision == "bullish":
        narrative = "Bullish confluence is forming across price, trend structure, and macro drivers, but the setup remains conditional on continued confirmation."
    elif decision == "bearish":
        narrative = "The setup is leaning defensive, with momentum and macro context softening. Risk should remain controlled and confirmation should be monitored." 
    else:
        narrative = "The decision engine sees a balanced market: trend, news, and macro context are not aligned enough to force a directional call."

    return {
        "status": "live" if any(item.get("status") == "available" for item in (provider_status or {}).values()) else "unavailable",
        "decision": decision,
        "score": round(score, 1),
        "confidence": confidence,
        "narrative": narrative,
        "drivers": drivers[:4],
        "watch_points": watch_points,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": "Alpha Vantage + Analytics",
    }
