from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _indicator_value(indicators: list[dict[str, Any]], name: str) -> float | None:
    for item in indicators:
        if item.get("name") == name:
            value = item.get("value")
            return None if value is None else _safe_float(value)
    return None


def _quality_from_confidence(confidence: int) -> str:
    if confidence >= 75:
        return "High"
    if confidence >= 50:
        return "Medium"
    return "Low"


def generate_signal(
    quote: dict[str, Any] | None,
    technical: dict[str, Any] | None,
    market_tone: str | None = None,
    volatility: str | None = None,
    momentum: str | None = None,
    provider_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not quote or not technical or quote.get("status") == "unavailable" or technical.get("status") == "unavailable":
        return {
            "status": "unavailable",
            "signal": "HOLD",
            "confidence": 0,
            "entry": None,
            "stop_loss": None,
            "take_profit": [],
            "risk_reward": "1:0",
            "trend": "Neutral",
            "quality": "Low",
            "reasons": [
                {
                    "indicator": "Market data",
                    "value": None,
                    "interpretation": "Live signal data is temporarily unavailable.",
                }
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": quote.get("source") if quote else "Unavailable",
            "note": "Signals are analytical estimates generated from market data and technical indicators. They are not financial advice and do not guarantee future market performance.",
        }

    price = _safe_float(quote.get("price"))
    technical_summary = technical.get("summary", {})
    indicators = technical.get("indicators", [])
    overall_bias = str(technical_summary.get("overall_bias", "neutral")).lower()
    trend_strength = str(technical_summary.get("trend_strength", "neutral")).lower()
    momentum_value = str(technical_summary.get("momentum", "neutral")).lower()
    volatility_value = str(technical_summary.get("volatility", "low")).lower()

    ema_20 = _indicator_value(indicators, "EMA 20")
    ema_50 = _indicator_value(indicators, "EMA 50")
    vwap = _indicator_value(indicators, "VWAP")
    rsi = _indicator_value(indicators, "RSI (14)")
    macd = _indicator_value(indicators, "MACD")
    atr = _indicator_value(indicators, "ATR")

    bullish_score = 0
    bearish_score = 0

    if overall_bias == "bullish":
        bullish_score += 3
    elif overall_bias == "bearish":
        bearish_score += 3

    if trend_strength in {"strong", "moderate"}:
        bullish_score += 2 if overall_bias == "bullish" else 0
        bearish_score += 2 if overall_bias == "bearish" else 0

    if momentum_value == "positive":
        bullish_score += 2
    elif momentum_value == "negative":
        bearish_score += 2

    if price is not None and ema_20 is not None and price > ema_20:
        bullish_score += 2
    elif price is not None and ema_20 is not None and price < ema_20:
        bearish_score += 2

    if price is not None and vwap is not None and price > vwap:
        bullish_score += 1
    elif price is not None and vwap is not None and price < vwap:
        bearish_score += 1

    if rsi is not None:
        if rsi > 55:
            bullish_score += 1
        elif rsi < 45:
            bearish_score += 1

    if macd is not None:
        if macd > 0:
            bullish_score += 1
        elif macd < 0:
            bearish_score += 1

    if overall_bias == "bullish" and bullish_score >= bearish_score:
        signal = "BUY"
        trend = "Bullish"
    elif overall_bias == "bearish" and bearish_score > bullish_score:
        signal = "SELL"
        trend = "Bearish"
    else:
        signal = "HOLD"
        trend = "Neutral"

    if signal == "HOLD" and bullish_score > bearish_score + 1:
        signal = "BUY"
        trend = "Bullish"
    elif signal == "HOLD" and bearish_score > bullish_score + 1:
        signal = "SELL"
        trend = "Bearish"

    if signal == "BUY":
        base_distance = atr if atr is not None else max(price * 0.005, 6.0)
        stop_loss = price - base_distance * 1.15
        take_profit = [
            price + base_distance * 1.8,
            price + base_distance * 2.7,
            price + base_distance * 3.8,
        ]
    elif signal == "SELL":
        base_distance = atr if atr is not None else max(price * 0.005, 6.0)
        stop_loss = price + base_distance * 1.15
        take_profit = [
            price - base_distance * 1.8,
            price - base_distance * 2.7,
            price - base_distance * 3.8,
        ]
    else:
        stop_loss = price
        take_profit = [price, price, price]

    risk_distance = abs(price - stop_loss) if price and stop_loss is not None else 0.0
    first_target = take_profit[0] if take_profit else price
    reward_distance = abs(first_target - price) if price is not None else 0.0
    reward_ratio = reward_distance / risk_distance if risk_distance else 0.0
    risk_reward = f"1:{reward_ratio:.1f}" if risk_distance else "1:0"

    confidence = max(0, min(100, int(round((bullish_score - bearish_score) * 12 + 50))))
    if signal == "HOLD":
        confidence = max(20, min(65, confidence))

    reasons: list[dict[str, Any]] = []
    preferred = [
        "EMA 20",
        "EMA 50",
        "RSI (14)",
        "MACD",
        "VWAP",
        "ATR",
        "ADX",
    ]
    for indicator_name in preferred:
        item = next((entry for entry in indicators if entry.get("name") == indicator_name), None)
        if item is None:
            continue
        value = item.get("value")
        if value is None:
            continue
        reasons.append(
            {
                "indicator": indicator_name,
                "value": _safe_float(value),
                "interpretation": str(item.get("interpretation") or "Indicator confirms the current market tone."),
            }
        )
    if not reasons:
        reasons.append(
            {
                "indicator": "Market data",
                "value": price,
                "interpretation": "Market data confirms the prevailing trend and price structure.",
            }
        )

    return {
        "status": "live",
        "signal": signal,
        "confidence": confidence,
        "entry": round(price, 2) if price is not None else None,
        "stop_loss": round(stop_loss, 2) if stop_loss is not None else None,
        "take_profit": [round(target, 2) for target in take_profit],
        "risk_reward": risk_reward,
        "trend": trend,
        "momentum": momentum_value.capitalize() if momentum_value else "Neutral",
        "volatility": volatility_value.capitalize() if volatility_value else "Moderate",
        "quality": _quality_from_confidence(confidence),
        "reasons": reasons[:5],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": quote.get("source") if quote else "Unavailable",
        "note": "Signals are analytical estimates generated from market data and technical indicators. They are not financial advice and do not guarantee future market performance.",
    }
