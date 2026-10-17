from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt
from typing import Any, Sequence


def _clean_float(value: Any, default: float = 0.0) -> float:
    if value in (None, "", "N/A"):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_ema(series: Sequence[float], period: int) -> float:
    if not series:
        return 0.0
    if len(series) == 1:
        return float(series[-1])
    multiplier = 2.0 / (period + 1.0)
    ema_value = float(series[0])
    for value in series[1:]:
        ema_value = (float(value) - ema_value) * multiplier + ema_value
    return ema_value


def _sma(values: Sequence[float], period: int | None = None) -> float:
    if not values:
        return 0.0
    window = period or len(values)
    window = min(window, len(values))
    return sum(values[-window:]) / window


def _rsi(values: Sequence[float], period: int = 14) -> float:
    if len(values) < 2:
        return 50.0
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    if len(gains) < period:
        gains = gains[-period:]
        losses = losses[-period:]
    avg_gain = sum(gains[-period:]) / period if len(gains) >= period else sum(gains) / max(len(gains), 1)
    avg_loss = sum(losses[-period:]) / period if len(losses) >= period else sum(losses) / max(len(losses), 1)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _macd(values: Sequence[float]) -> tuple[float, float, float]:
    if len(values) < 26:
        return 0.0, 0.0, 0.0
    ema12 = _safe_ema(values[-26:], 12)
    ema26 = _safe_ema(values[-26:], 26)
    macd_value = ema12 - ema26
    signal = _safe_ema(list(values[-26:]), 9) if len(values[-26:]) >= 9 else macd_value
    return macd_value, signal, macd_value - signal


def _atr(bars: Sequence[dict[str, Any]]) -> float:
    if len(bars) < 2:
        return 0.0
    current = bars[-1]
    prev_close = _clean_float(current.get("previous_close"), _clean_float(current.get("close")))
    true_ranges: list[float] = []
    for index, bar in enumerate(bars[-15:], start=0):
        high = _clean_float(bar.get("high"), _clean_float(bar.get("close")))
        low = _clean_float(bar.get("low"), _clean_float(bar.get("close")))
        close = _clean_float(bar.get("close"), _clean_float(bar.get("price")))
        previous_close = _clean_float(bars[max(index - 1, 0)].get("close"), close)
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    if not true_ranges:
        return 0.0
    return sum(true_ranges) / len(true_ranges)


def _adx(bars: Sequence[dict[str, Any]], period: int = 14) -> float:
    if len(bars) < period + 2:
        return 0.0
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    tr_values: list[float] = []
    for index in range(1, len(bars)):
        current = bars[index]
        previous = bars[index - 1]
        high = _clean_float(current.get("high"), _clean_float(current.get("close")))
        low = _clean_float(current.get("low"), _clean_float(current.get("close")))
        prev_high = _clean_float(previous.get("high"), _clean_float(previous.get("close")))
        prev_low = _clean_float(previous.get("low"), _clean_float(previous.get("close")))
        prev_close = _clean_float(previous.get("close"), _clean_float(previous.get("price")))
        current_close = _clean_float(current.get("close"), _clean_float(current.get("price")))
        up_move = high - prev_high
        down_move = prev_low - low
        plus_dm.append(max(up_move, 0.0) if up_move > down_move else 0.0)
        minus_dm.append(max(down_move, 0.0) if down_move > up_move else 0.0)
        tr_values.append(max(high - low, abs(high - prev_close), abs(low - prev_close), abs(current_close - prev_close)))
    if len(tr_values) < period:
        return 0.0
    smoothed_tr = sum(tr_values[:period])
    smoothed_plus = sum(plus_dm[:period])
    smoothed_minus = sum(minus_dm[:period])
    dx_values: list[float] = []
    for index in range(period, len(tr_values)):
        smoothed_tr = smoothed_tr - (smoothed_tr / period) + tr_values[index]
        smoothed_plus = smoothed_plus - (smoothed_plus / period) + plus_dm[index]
        smoothed_minus = smoothed_minus - (smoothed_minus / period) + minus_dm[index]
        plus_di = 100.0 * (smoothed_plus / smoothed_tr) if smoothed_tr else 0.0
        minus_di = 100.0 * (smoothed_minus / smoothed_tr) if smoothed_tr else 0.0
        dx = 100.0 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) else 0.0
        dx_values.append(dx)
    if not dx_values:
        return 0.0
    return sum(dx_values[-period:]) / min(period, len(dx_values))


def _bollinger_bands(values: Sequence[float], period: int = 20, num_std: float = 2.0) -> tuple[float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0
    window = values[-period:]
    mean = sum(window) / len(window)
    variance = sum((point - mean) ** 2 for point in window) / len(window)
    std_dev = sqrt(variance)
    upper = mean + (num_std * std_dev)
    lower = mean - (num_std * std_dev)
    return upper, mean, lower


def _vwap(bars: Sequence[dict[str, Any]]) -> float:
    if not bars:
        return 0.0
    numerator = 0.0
    denominator = 0.0
    for bar in bars[-20:]:
        high = _clean_float(bar.get("high"), _clean_float(bar.get("close")))
        low = _clean_float(bar.get("low"), _clean_float(bar.get("close")))
        close = _clean_float(bar.get("close"), _clean_float(bar.get("price")))
        typical_price = (high + low + close) / 3.0
        volume = _clean_float(bar.get("volume"), 1.0)
        numerator += typical_price * volume
        denominator += volume
    if denominator == 0:
        return _sma([_clean_float(bar.get("close"), _clean_float(bar.get("price"))) for bar in bars[-20:]], 20)
    return numerator / denominator


def _stochastic_rsi(values: Sequence[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0
    rsi_values = [_rsi(values[max(0, index - period):index + 1], period) for index in range(period, len(values))]
    if not rsi_values:
        return 50.0
    current_rsi = rsi_values[-1]
    rsi_window = rsi_values[-period:]
    lowest = min(rsi_window)
    highest = max(rsi_window)
    if highest == lowest:
        return 50.0
    return ((current_rsi - lowest) / (highest - lowest)) * 100.0


def _status_from_value(value: float, bullish_threshold: float = 55, bearish_threshold: float = 45) -> str:
    if value >= bullish_threshold:
        return "bullish"
    if value <= bearish_threshold:
        return "bearish"
    return "neutral"


def _value_label(name: str, value: float | None) -> str:
    if value is None:
        return "—"
    label = f"{value:,.2f}"
    if name in {"EMA 20", "EMA 50", "EMA 200", "SMA 20", "VWAP", "ATR"}:
        return f"${label}"
    if name in {"RSI (14)", "MACD", "ADX", "Bollinger Upper", "Bollinger Mid", "Bollinger Lower", "Stochastic RSI"}:
        return f"{value:,.2f}"
    return f"{value:,.2f}"


def analyze_market(candles: Sequence[dict[str, Any]], provider: str = "Alpha Vantage") -> dict:
    if not candles:
        return {
            "symbol": "XAU/USD",
            "provider": provider,
            "status": "unavailable",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "overall_bias": "neutral",
                "overall_score": 0,
                "trend_strength": "neutral",
                "volatility": "low",
                "momentum": "neutral",
                "quality": "limited",
            },
            "indicators": [],
        }

    normalized = []
    for index, item in enumerate(candles):
        close = _clean_float(item.get("close"), _clean_float(item.get("price")))
        open_price = _clean_float(item.get("open"), close)
        high = _clean_float(item.get("high"), max(open_price, close))
        low = _clean_float(item.get("low"), min(open_price, close))
        volume = _clean_float(item.get("volume"), 0.0)
        entry = {
            "date": item.get("date") or item.get("timestamp") or item.get("datetime") or str(index),
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "price": close,
        }
        normalized.append(entry)

    closes = [_clean_float(item.get("close"), _clean_float(item.get("price"))) for item in normalized]
    highs = [_clean_float(item.get("high"), _clean_float(item.get("close"))) for item in normalized]
    lows = [_clean_float(item.get("low"), _clean_float(item.get("close"))) for item in normalized]
    volumes = [_clean_float(item.get("volume"), 0.0) for item in normalized]

    current_close = closes[-1] if closes else 0.0
    ema_20 = _safe_ema(closes, 20)
    ema_50 = _safe_ema(closes, 50)
    ema_200 = _safe_ema(closes, 200)
    sma_20 = _sma(closes, 20)
    rsi_14 = _rsi(closes, 14)
    macd_value, macd_signal, macd_histogram = _macd(closes)
    atr_value = _atr(normalized)
    adx_value = _adx(normalized, 14)
    upper_band, mid_band, lower_band = _bollinger_bands(closes, 20, 2.0)
    vwap_value = _vwap(normalized)
    stoch_rsi_value = _stochastic_rsi(closes, 14)

    signals = [
        {
            "name": "EMA 20",
            "value": ema_20,
            "status": "bullish" if current_close > ema_20 else "bearish" if current_close < ema_20 else "neutral",
            "interpretation": "Price is trading above the 20-period EMA." if current_close > ema_20 else "Price is below the 20-period EMA." if current_close < ema_20 else "Price is near the 20-period EMA.",
        },
        {
            "name": "EMA 50",
            "value": ema_50,
            "status": "bullish" if current_close > ema_50 else "bearish" if current_close < ema_50 else "neutral",
            "interpretation": "The medium-term trend remains constructive." if current_close > ema_50 else "The medium-term trend is under pressure." if current_close < ema_50 else "The market is consolidating around the 50 EMA.",
        },
        {
            "name": "EMA 200",
            "value": ema_200,
            "status": "bullish" if current_close > ema_200 else "bearish" if current_close < ema_200 else "neutral",
            "interpretation": "Long-term trend is positive." if current_close > ema_200 else "Long-term trend is bearish." if current_close < ema_200 else "Price is near the 200 EMA.",
        },
        {
            "name": "SMA 20",
            "value": sma_20,
            "status": "bullish" if current_close > sma_20 else "bearish" if current_close < sma_20 else "neutral",
            "interpretation": "Short-term average support is intact." if current_close > sma_20 else "Short-term average resistance is holding." if current_close < sma_20 else "Price is balanced with the short-term average.",
        },
        {
            "name": "RSI (14)",
            "value": rsi_14,
            "status": _status_from_value(rsi_14, 55, 45),
            "interpretation": "Momentum is supportive with RSI above neutral territory." if rsi_14 > 55 else "Momentum is weak with RSI below neutral territory." if rsi_14 < 45 else "Momentum is balanced and range-bound.",
        },
        {
            "name": "MACD",
            "value": macd_value,
            "status": "bullish" if macd_histogram > 0 else "bearish" if macd_histogram < 0 else "neutral",
            "interpretation": "MACD histogram is positive and expanding." if macd_histogram > 0 else "MACD histogram is negative and fading." if macd_histogram < 0 else "MACD is flat and trendless.",
        },
        {
            "name": "ATR",
            "value": atr_value,
            "status": "bullish" if atr_value > 0 else "neutral",
            "interpretation": "Volatility is elevated, increasing the probability of directional movement." if atr_value > 0 else "Volatility is minimal.",
        },
        {
            "name": "ADX",
            "value": adx_value,
            "status": "bullish" if adx_value > 25 else "neutral" if adx_value < 20 else "bearish",
            "interpretation": "Trend strength is clearly established." if adx_value > 25 else "Trend is moderate and less directional." if adx_value < 20 else "Trend strength is building but not fully confirmed.",
        },
        {
            "name": "Bollinger Upper",
            "value": upper_band,
            "status": "bullish" if current_close > mid_band else "bearish" if current_close < mid_band else "neutral",
            "interpretation": "Price is holding above the bollinger midpoint, implying strength." if current_close > mid_band else "Price is below the bollinger midpoint, suggesting softness." if current_close < mid_band else "Price is centered within the Bollinger envelope.",
        },
        {
            "name": "Bollinger Mid",
            "value": mid_band,
            "status": "bullish" if current_close > mid_band else "bearish" if current_close < mid_band else "neutral",
            "interpretation": "Mid-band support is being respected." if current_close > mid_band else "Mid-band resistance is active." if current_close < mid_band else "Price is trading laterally around the moving average.",
        },
        {
            "name": "Bollinger Lower",
            "value": lower_band,
            "status": "bullish" if current_close > lower_band else "bearish" if current_close < lower_band else "neutral",
            "interpretation": "Price remains above lower-band support." if current_close > lower_band else "Price is testing lower-band support." if current_close < lower_band else "Price is near the lower band.",
        },
        {
            "name": "VWAP",
            "value": vwap_value,
            "status": "bullish" if current_close > vwap_value else "bearish" if current_close < vwap_value else "neutral",
            "interpretation": "Price is holding above session VWAP." if current_close > vwap_value else "Price is below session VWAP." if current_close < vwap_value else "Price is trading around VWAP.",
        },
        {
            "name": "Stochastic RSI",
            "value": stoch_rsi_value,
            "status": _status_from_value(stoch_rsi_value, 70, 30),
            "interpretation": "Momentum is extended to the upside." if stoch_rsi_value > 70 else "Momentum is extended to the downside." if stoch_rsi_value < 30 else "Momentum is balanced and not yet stretched.",
        },
    ]

    bullish_count = sum(1 for item in signals if item["status"] == "bullish")
    bearish_count = sum(1 for item in signals if item["status"] == "bearish")
    neutral_count = len(signals) - bullish_count - bearish_count
    overall_score = int(round((bullish_count * 100 + neutral_count * 50) / max(len(signals), 1)))
    if bullish_count > bearish_count:
        overall_bias = "bullish"
    elif bearish_count > bullish_count:
        overall_bias = "bearish"
    else:
        overall_bias = "neutral"

    trend_strength = (
        "strong" if current_close > ema_50 and ema_50 > ema_200 else
        "moderate" if current_close > ema_50 or ema_50 > ema_200 else
        "weak"
    )
    volatility_pct = (atr_value / current_close) * 100 if current_close else 0.0
    volatility = "elevated" if volatility_pct > 1.3 else "moderate" if volatility_pct > 0.7 else "compressed"
    momentum = "positive" if rsi_14 > 55 and macd_histogram > 0 else "negative" if rsi_14 < 45 and macd_histogram < 0 else "neutral"
    quality = "high" if len(normalized) >= 200 else "medium" if len(normalized) >= 50 else "limited"

    return {
        "symbol": "XAU/USD",
        "provider": provider,
        "status": "live",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "overall_bias": overall_bias,
            "overall_score": overall_score,
            "trend_strength": trend_strength,
            "volatility": volatility,
            "momentum": momentum,
            "quality": quality,
        },
        "indicators": [
            {
                "name": item["name"],
                "value": item["value"],
                "status": item["status"],
                "interpretation": item["interpretation"],
                "unit": "USD" if item["name"] in {"EMA 20", "EMA 50", "EMA 200", "SMA 20", "VWAP", "Bollinger Upper", "Bollinger Mid", "Bollinger Lower", "ATR"} else "%",
            }
            for item in signals
        ],
        "data_points": len(normalized),
    }
