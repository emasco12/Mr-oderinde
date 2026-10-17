from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence


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


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def analyze_news_intelligence(headlines: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not headlines:
        return {
            "status": "unavailable",
            "sentiment": {
                "score": 0.0,
                "bias": "neutral",
                "article_count": 0,
                "source": "unavailable",
                "method": "No market headlines available.",
            },
            "prediction": {
                "direction": "neutral",
                "probability": 0,
                "confidence": "low",
                "rationale": "No recent gold headlines are available for a directional read.",
            },
            "headline_focus": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    scored = []
    for headline in headlines:
        title = str(headline.get("title") or "").strip() or "Market headline"
        score, bias, impact = score_headline(title)
        scored.append({
            "title": title,
            "score": score,
            "bias": bias,
            "impact": impact,
        })

    score_average = sum(item["score"] for item in scored) / len(scored)
    bullish_count = sum(1 for item in scored if item["bias"] == "bullish")
    bearish_count = sum(1 for item in scored if item["bias"] == "bearish")
    neutral_count = sum(1 for item in scored if item["bias"] == "neutral")

    if bullish_count > bearish_count and bullish_count >= neutral_count:
        bias = "bullish"
    elif bearish_count > bullish_count and bearish_count >= neutral_count:
        bias = "bearish"
    else:
        bias = "neutral"

    probability = round(_clamp(50 + (bullish_count - bearish_count) * 10 + abs(score_average) * 35, 0, 95))
    if bias == "neutral":
        probability = max(40, min(60, probability))

    if probability >= 70:
        confidence = "high"
    elif probability >= 55:
        confidence = "moderate"
    else:
        confidence = "low"

    ranked = sorted(scored, key=lambda item: abs(item["score"]), reverse=True)
    primary = ranked[0]
    if bias == "bullish":
        rationale = f"Headline momentum is skewed toward supportive gold factors, led by '{primary['title']}' and a {primary['impact']} impact read."
    elif bias == "bearish":
        rationale = f"Headline flow is leaning toward pressure on gold, led by '{primary['title']}' and a {primary['impact']} impact read."
    else:
        rationale = f"Headline flow is mixed; the market is balancing between supportive and restrictive catalysts around '{primary['title']}'."

    return {
        "status": "live",
        "sentiment": {
            "score": round(score_average, 3),
            "bias": bias,
            "article_count": len(scored),
            "source": "NewsAPI",
            "method": "Transparent headline scoring; not financial advice.",
        },
        "prediction": {
            "direction": bias,
            "probability": probability,
            "confidence": confidence,
            "rationale": rationale,
        },
        "headline_focus": primary["title"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
