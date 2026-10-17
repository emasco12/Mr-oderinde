from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence


def _clean_float(value: Any, default: float = 0.0) -> float:
    if value in (None, "", "N/A"):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ema(values: Sequence[float], period: int) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[-1])
    multiplier = 2.0 / (period + 1.0)
    ema_value = float(values[0])
    for item in values[1:]:
        ema_value = (float(item) - ema_value) * multiplier + ema_value
    return ema_value


def _sma(values: Sequence[float], period: int) -> float:
    if not values:
        return 0.0
    window = values[-period:]
    return sum(window) / len(window)


def _direction_from_values(closes: Sequence[float]) -> str:
    if len(closes) < 20:
        return "neutral"
    ema_20 = _ema(closes, 20)
    ema_50 = _ema(closes, 50)
    current = closes[-1]
    if current > ema_20 and ema_20 > ema_50:
        return "bullish"
    if current < ema_20 and ema_20 < ema_50:
        return "bearish"
    return "neutral"


def _fair_value_gap(candles: Sequence[dict[str, Any]]) -> tuple[bool, str | None, float | None, str]:
    if len(candles) < 3:
        return False, None, None, "No fair value gap is currently visible."
    recent = candles[-3:]
    first = recent[0]
    third = recent[-1]
    first_low = _clean_float(first.get("low"), _clean_float(first.get("close")))
    first_high = _clean_float(first.get("high"), _clean_float(first.get("close")))
    third_high = _clean_float(third.get("high"), _clean_float(third.get("close")))
    third_low = _clean_float(third.get("low"), _clean_float(third.get("close")))
    bullish_gap = first_low > third_high
    bearish_gap = first_high < third_low
    if bullish_gap:
        return True, "bullish", abs(first_low - third_high), "A bullish fair value gap remains open after the prior impulse."
    if bearish_gap:
        return True, "bearish", abs(first_high - third_low), "A bearish fair value gap remains open after the prior impulse."
    return False, None, None, "Price is balanced and no clear fair value gap is active."


def analyze_ict(candles: Sequence[dict[str, Any]], provider: str = "Alpha Vantage") -> dict[str, Any]:
    if not candles:
        return {
            "symbol": "XAU/USD",
            "provider": provider,
            "status": "unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_bias": "Neutral",
            "liquidity": {
                "sweep": "none",
                "interpretation": "ICT context is unavailable at the moment.",
            },
            "fair_value_gap": {
                "present": False,
                "direction": None,
                "size": None,
                "interpretation": "No fair value gap is available.",
            },
            "displacement": {
                "direction": "neutral",
                "magnitude": None,
                "interpretation": "The market has no clear directional displacement.",
            },
            "market_regime": {
                "trend": "Neutral",
                "volatility": "Low",
                "institutional_flow": "Balanced",
            },
            "narrative": "No ICT structure is available yet.",
            "indicators": [
                {"name": "Session Bias", "value": "Neutral", "status": "neutral", "interpretation": "No session bias available."},
                {"name": "Liquidity Sweep", "value": "None", "status": "neutral", "interpretation": "No liquidity sweep available."},
                {"name": "Displacement", "value": None, "status": "neutral", "interpretation": "Displacement data is unavailable."},
                {"name": "FVG", "value": "None", "status": "neutral", "interpretation": "No fair value gap is available."},
            ],
        }

    closes = [_clean_float(item.get("close"), _clean_float(item.get("price"))) for item in candles]
    highs = [_clean_float(item.get("high"), _clean_float(item.get("close"))) for item in candles]
    lows = [_clean_float(item.get("low"), _clean_float(item.get("close"))) for item in candles]

    current_close = closes[-1]
    sma_20 = _sma(closes, 20)
    ema_20 = _ema(closes, 20)
    ema_50 = _ema(closes, 50)
    trend = _direction_from_values(closes)
    session_high = max(highs[-10:])
    session_low = min(lows[-10:])
    sweep_dir = "bullish" if current_close > session_high else "bearish" if current_close < session_low else "none"
    if sweep_dir == "bullish":
        liquidity_text = "Buy-side liquidity has been swept and price is holding above the session high."
    elif sweep_dir == "bearish":
        liquidity_text = "Sell-side liquidity has been swept and price is holding below the session low."
    else:
        liquidity_text = "Liquidity remains balanced near the session range."

    fvg_present, fvg_direction, fvg_size, fvg_text = _fair_value_gap(candles)
    displacement = current_close - closes[-2] if len(closes) >= 2 else 0.0
    displacement_pct = (displacement / closes[-2]) * 100 if len(closes) >= 2 and closes[-2] else 0.0
    if displacement > 0 and current_close > ema_20:
        displacement_direction = "bullish"
        displacement_text = "Price is extending above the intraday structure with follow-through strength."
    elif displacement < 0 and current_close < ema_20:
        displacement_direction = "bearish"
        displacement_text = "Price is rejecting the recent structure and extending lower."
    else:
        displacement_direction = "neutral"
        displacement_text = "The market is consolidating without a clear directional expansion."

    if trend == "bullish":
        session_bias = "Bullish"
        institutional_flow = "Bullish"
    elif trend == "bearish":
        session_bias = "Bearish"
        institutional_flow = "Bearish"
    else:
        session_bias = "Neutral"
        institutional_flow = "Balanced"

    volatility = "Elevated" if (session_high - session_low) / max(current_close, 1.0) > 0.01 else "Moderate" if (session_high - session_low) / max(current_close, 1.0) > 0.004 else "Low"

    narrative = (
        "The market is showing an ICT-style directional bias with "
        f"{session_bias.lower()} structure, {liquidity_text.lower()} "
        f"and {'a bullish FVG' if fvg_direction == 'bullish' else 'a bearish FVG' if fvg_direction == 'bearish' else 'balanced price action'}."
    )

    return {
        "symbol": "XAU/USD",
        "provider": provider,
        "status": "live",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_bias": session_bias,
        "liquidity": {
            "sweep": sweep_dir,
            "interpretation": liquidity_text,
        },
        "fair_value_gap": {
            "present": fvg_present,
            "direction": fvg_direction,
            "size": fvg_size,
            "interpretation": fvg_text,
        },
        "displacement": {
            "direction": displacement_direction,
            "magnitude": displacement_pct,
            "interpretation": displacement_text,
        },
        "market_regime": {
            "trend": session_bias,
            "volatility": volatility,
            "institutional_flow": institutional_flow,
        },
        "narrative": narrative,
        "indicators": [
            {"name": "Session Bias", "value": session_bias, "status": trend, "interpretation": f"Current structure remains {trend} relative to the 20/50 EMA posture.", "unit": "context"},
            {"name": "Liquidity Sweep", "value": sweep_dir.capitalize() if sweep_dir != "none" else "None", "status": "bullish" if sweep_dir == "bullish" else "bearish" if sweep_dir == "bearish" else "neutral", "interpretation": liquidity_text, "unit": "context"},
            {"name": "Displacement", "value": displacement_pct, "status": "bullish" if displacement_direction == "bullish" else "bearish" if displacement_direction == "bearish" else "neutral", "interpretation": displacement_text, "unit": "%"},
            {"name": "FVG", "value": fvg_direction.capitalize() if fvg_direction else "None", "status": "bullish" if fvg_direction == "bullish" else "bearish" if fvg_direction == "bearish" else "neutral", "interpretation": fvg_text, "unit": "context"},
            {"name": "Session Range", "value": session_high - session_low, "status": "neutral", "interpretation": "The recent range defines the immediate execution context.", "unit": "USD"},
            {"name": "Institutional Flow", "value": institutional_flow, "status": trend, "interpretation": "The market is being interpreted through a session-level institutional bias lens.", "unit": "context"},
        ],
    }
