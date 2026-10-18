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


def _structure_trend(closes: Sequence[float]) -> str:
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
        return False, None, None, "No clear fair value gap present."
    recent = candles[-3:]
    first = recent[0]
    second = recent[1]
    third = recent[2]
    candle_a_high = _clean_float(first.get("high"), _clean_float(first.get("close")))
    candle_a_low = _clean_float(first.get("low"), _clean_float(first.get("close")))
    candle_c_high = _clean_float(third.get("high"), _clean_float(third.get("close")))
    candle_c_low = _clean_float(third.get("low"), _clean_float(third.get("close")))
    bullish_gap = candle_a_low > candle_c_high
    bearish_gap = candle_a_high < candle_c_low
    if bullish_gap:
        return True, "bullish", abs(candle_a_low - candle_c_high), "Price is leaving a bullish gap between the prior impulse and the current reaction."
    if bearish_gap:
        return True, "bearish", abs(candle_a_high - candle_c_low), "Price is leaving a bearish gap between the prior impulse and the current reaction."
    return False, None, None, "No clear fair value gap present."


def analyze_smc(candles: Sequence[dict[str, Any]], provider: str = "Alpha Vantage") -> dict[str, Any]:
    if not candles:
        return {
            "symbol": "XAU/USD",
            "provider": provider,
            "status": "unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market_structure": {
                "trend": "neutral",
                "break_of_structure": "No structure available",
                "change_of_character": "No character change available",
                "swing_high": None,
                "swing_low": None,
            },
            "liquidity": {
                "sweep": "none",
                "interpretation": "No liquidity data is currently available.",
            },
            "order_block": {
                "type": "neutral",
                "top": None,
                "bottom": None,
                "strength": "weak",
                "interpretation": "No order block is available.",
            },
            "fair_value_gap": {
                "present": False,
                "direction": None,
                "gap": None,
                "interpretation": "No fair value gap is available.",
            },
            "session_bias": "Neutral",
            "risk_context": {
                "trend": "Neutral",
                "volatility": "Low",
                "momentum": "Neutral",
                "liquidity": "Unclear",
            },
        }

    closes = [_clean_float(item.get("close"), _clean_float(item.get("price"))) for item in candles]
    highs = [_clean_float(item.get("high"), _clean_float(item.get("close"))) for item in candles]
    lows = [_clean_float(item.get("low"), _clean_float(item.get("close"))) for item in candles]

    recent_high = max(highs[-20:]) if highs else 0.0
    recent_low = min(lows[-20:]) if lows else 0.0
    current_close = closes[-1] if closes else 0.0
    ema_20 = _ema(closes, 20)
    ema_50 = _ema(closes, 50)
    trend = _structure_trend(closes)

    if trend == "bullish":
        break_of_structure = "Bullish break of structure remains intact above recent local highs."
        change_of_character = "Momentum is constructive and the short-term trend is still positive."
    elif trend == "bearish":
        break_of_structure = "Bearish break of structure remains intact beneath recent local lows."
        change_of_character = "Momentum is weaker and the short-term trend is losing support."
    else:
        break_of_structure = "Price is range-bound and structure is undecided."
        change_of_character = "The market is consolidating without a decisive directional break."

    if current_close > recent_high:
        liquidity_sweep = "bullish"
        liquidity_text = "Buy-side liquidity has been absorbed and price is holding above the recent premium range."
    elif current_close < recent_low:
        liquidity_sweep = "bearish"
        liquidity_text = "Sell-side liquidity has been absorbed and price is holding below the recent discount range."
    else:
        liquidity_sweep = "none"
        liquidity_text = "No clear sweep is active; liquidity remains balanced near the recent swing area."

    order_block_type = "bullish" if trend == "bullish" else "bearish" if trend == "bearish" else "neutral"
    if order_block_type == "bullish":
        top = max(highs[-5:])
        bottom = min(lows[-5:])
        order_block_strength = "strong" if current_close > ema_20 and current_close > ema_50 else "moderate"
        order_block_text = "Bullish order block is forming where prior consolidation met a fresh impulse."
    elif order_block_type == "bearish":
        top = max(highs[-5:])
        bottom = min(lows[-5:])
        order_block_strength = "strong" if current_close < ema_20 and current_close < ema_50 else "moderate"
        order_block_text = "Bearish order block remains active where prior supply was defended."
    else:
        top = None
        bottom = None
        order_block_strength = "weak"
        order_block_text = "Order block context is neutral as the market remains balanced."

    fvg_present, fvg_direction, fvg_gap, fvg_text = _fair_value_gap(candles)

    if trend == "bullish":
        session_bias = "Bullish"
    elif trend == "bearish":
        session_bias = "Bearish"
    else:
        session_bias = "Neutral"

    risk_context = {
        "trend": "Bullish" if trend == "bullish" else "Bearish" if trend == "bearish" else "Neutral",
        "volatility": "Elevated" if (max(highs[-10:]) - min(lows[-10:])) / max(current_close, 1.0) > 0.008 else "Moderate" if (max(highs[-10:]) - min(lows[-10:])) / max(current_close, 1.0) > 0.004 else "Low",
        "momentum": "Positive" if current_close > ema_20 and current_close > ema_50 else "Negative" if current_close < ema_20 and current_close < ema_50 else "Neutral",
        "liquidity": "Premium" if current_close > recent_high else "Discount" if current_close < recent_low else "Balanced",
    }

    return {
        "symbol": "XAU/USD",
        "provider": provider,
        "status": "live",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "market_structure": {
            "trend": session_bias.lower(),
            "break_of_structure": break_of_structure,
            "change_of_character": change_of_character,
            "swing_high": recent_high,
            "swing_low": recent_low,
        },
        "liquidity": {
            "sweep": liquidity_sweep,
            "interpretation": liquidity_text,
        },
        "order_block": {
            "type": order_block_type,
            "top": top,
            "bottom": bottom,
            "strength": order_block_strength,
            "interpretation": order_block_text,
        },
        "fair_value_gap": {
            "present": fvg_present,
            "direction": fvg_direction,
            "gap": fvg_gap,
            "interpretation": fvg_text,
        },
        "session_bias": session_bias,
        "risk_context": risk_context,
    }
