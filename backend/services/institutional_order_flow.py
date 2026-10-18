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


def _direction_signal(closes: Sequence[float]) -> str:
    if len(closes) < 10:
        return "neutral"
    recent = closes[-10:]
    prior = closes[-20:-10] if len(closes) >= 20 else closes[:-10]
    recent_avg = sum(recent) / len(recent)
    prior_avg = sum(prior) / len(prior) if prior else recent_avg
    if recent_avg > prior_avg and closes[-1] > recent_avg:
        return "bullish"
    if recent_avg < prior_avg and closes[-1] < recent_avg:
        return "bearish"
    return "neutral"


def analyze_order_flow(candles: Sequence[dict[str, Any]], provider: str = "Alpha Vantage") -> dict[str, Any]:
    if not candles:
        return {
            "symbol": "XAU/USD",
            "provider": provider,
            "status": "unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_flow": {
                "trend": "Neutral",
                "pressure": "Balanced",
                "absorption": "Low",
                "participation": "Low",
                "imbalance": 0.0,
                "interpretation": "No institutional order-flow data is available right now.",
            },
            "market_context": {
                "volatility": "Low",
                "bias": "Neutral",
                "execution_quality": "Limited",
            },
            "signals": [
                {"name": "Pressure", "value": "Neutral", "status": "neutral", "interpretation": "Institutional flow is unavailable."},
            ],
        }

    closes = [_clean_float(item.get("close"), _clean_float(item.get("price"))) for item in candles]
    opens = [_clean_float(item.get("open"), close) for item, close in zip(candles, closes, strict=True)]
    highs = [_clean_float(item.get("high"), close) for item, close in zip(candles, closes, strict=True)]
    lows = [_clean_float(item.get("low"), close) for item, close in zip(candles, closes, strict=True)]
    volumes = [_clean_float(item.get("volume"), 1.0) for item in candles]

    total_buy_pressure = 0.0
    total_sell_pressure = 0.0
    for open_price, close_price, high, low, volume in zip(opens, closes, highs, lows, volumes, strict=True):
        range_size = max(high - low, 1e-6)
        directional_move = close_price - open_price
        if directional_move >= 0:
            total_buy_pressure += (directional_move / range_size) * volume
        else:
            total_sell_pressure += ((open_price - close_price) / range_size) * volume

    total_flow = total_buy_pressure + total_sell_pressure
    imbalance = 0.0 if total_flow == 0 else (total_buy_pressure - total_sell_pressure) / total_flow
    ema_20 = _ema(closes, 20)
    trend = _direction_signal(closes)
    current_close = closes[-1]
    avg_volume = sum(volumes[-10:]) / len(volumes[-10:]) if volumes else 1.0
    recent_volume = sum(volumes[-5:]) / len(volumes[-5:]) if volumes else avg_volume
    participation = "High" if recent_volume > avg_volume * 1.15 else "Moderate" if recent_volume > avg_volume * 0.9 else "Low"

    if imbalance > 0.12 and trend == "bullish":
        pressure = "Bullish"
        absorption = "Strong"
        bias = "Bullish"
        interpretation = "Institutional participants are driving price higher with sustained aggressive buying and healthy absorption above recent value."
    elif imbalance < -0.12 and trend == "bearish":
        pressure = "Bearish"
        absorption = "Strong"
        bias = "Bearish"
        interpretation = "Institutional participants are defending downside with sustained selling pressure and weak absorption."
    elif abs(imbalance) > 0.04:
        pressure = "Bullish" if imbalance > 0 else "Bearish"
        absorption = "Moderate"
        bias = "Neutral" if trend == "neutral" else ("Bullish" if trend == "bullish" else "Bearish")
        interpretation = "Volume is skewed in one direction, but directional commitment is not yet decisive enough to confirm a clean institutional trend."
    else:
        pressure = "Balanced"
        absorption = "Low"
        bias = "Neutral"
        interpretation = "Price action is balanced and institutional participation is not yet clearly directional."

    volatility = "Elevated" if max(highs[-10:]) - min(lows[-10:]) > 0.02 * current_close else "Moderate" if current_close > ema_20 else "Low"

    return {
        "symbol": "XAU/USD",
        "provider": provider,
        "status": "live",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_flow": {
            "trend": bias,
            "pressure": pressure,
            "absorption": absorption,
            "participation": participation,
            "imbalance": round(imbalance, 4),
            "interpretation": interpretation,
        },
        "market_context": {
            "volatility": volatility,
            "bias": bias,
            "execution_quality": "High" if absorption in {"Strong", "Moderate"} else "Limited",
        },
        "signals": [
            {"name": "Pressure", "value": pressure, "status": "bullish" if pressure == "Bullish" else "bearish" if pressure == "Bearish" else "neutral", "interpretation": interpretation},
            {"name": "Participation", "value": participation, "status": "bullish" if participation == "High" else "neutral", "interpretation": f"Recent participation is {participation.lower()} relative to the trailing volume baseline."},
            {"name": "Absorption", "value": absorption, "status": "bullish" if absorption == "Strong" else "neutral", "interpretation": f"Absorption quality is {absorption.lower()} on the current order-flow profile."},
        ],
    }
