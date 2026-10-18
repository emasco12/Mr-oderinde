from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence


IMPACT_ORDER = {"high": 3, "medium": 2, "low": 1, "": 0}


def _impact_weight(event: dict[str, Any]) -> int:
    impact = str(event.get("impact", "")).lower()
    return IMPACT_ORDER.get(impact, 0)


def _title_tone(title: str) -> str:
    lowered = title.lower()
    if any(token in lowered for token in ["cpi", "inflation", "ppi", "fed", "rate", "yields", "jobs", "payroll", "nfp", "retail sales", "gdp", "cpi"]):
        if "inflation" in lowered or "cpi" in lowered or "ppi" in lowered:
            return "hawkish"
        if "jobs" in lowered or "payroll" in lowered or "nfp" in lowered:
            return "bullish"
        if "fed" in lowered or "rate" in lowered or "yields" in lowered:
            return "mixed"
        if "gdp" in lowered:
            return "neutral"
    return "neutral"


def analyze_calendar_intelligence(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {
            "status": "unavailable",
            "risk_bucket": "Low",
            "market_bias": "Neutral",
            "next_event": None,
            "upcoming_events": [],
            "summary": "No economic release data is available right now.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    normalized = []
    for event in events:
        title = str(event.get("title") or "Economic release")
        impact = str(event.get("impact") or "").lower()
        date_value = event.get("date") or event.get("datetime") or event.get("published_at")
        normalized.append({
            "title": title,
            "country": event.get("country", "USD"),
            "date": date_value,
            "impact": impact,
            "forecast": event.get("forecast"),
            "previous": event.get("previous"),
            "weight": _impact_weight(event),
            "tone": _title_tone(title),
        })

    upcoming = sorted(normalized, key=lambda item: (str(item["date"] or "9999-12-31"), -item["weight"]))
    top_event = upcoming[0] if upcoming else None
    high_impact = [item for item in upcoming if item["weight"] >= 3][:3]
    bullish_count = sum(1 for item in upcoming if item["tone"] == "bullish")
    bearish_count = sum(1 for item in upcoming if item["tone"] == "hawkish")
    neutral_count = sum(1 for item in upcoming if item["tone"] == "neutral" or item["tone"] == "mixed")

    if bullish_count > bearish_count and bullish_count >= neutral_count:
        market_bias = "Bullish"
    elif bearish_count > bullish_count and bearish_count >= neutral_count:
        market_bias = "Bearish"
    else:
        market_bias = "Neutral"

    if top_event and top_event["weight"] >= 3:
        risk_bucket = "High"
    elif top_event and top_event["weight"] >= 2:
        risk_bucket = "Medium"
    else:
        risk_bucket = "Low"

    summary = (
        f"The next major macro catalyst is {top_event['title']} with {top_event['impact']} impact. "
        f"The near-term macro bias is {market_bias.lower()} as event risk rotates around the upcoming data stream."
    ) if top_event else "No upcoming economic catalyst has been identified."

    return {
        "status": "live",
        "risk_bucket": risk_bucket,
        "market_bias": market_bias,
        "next_event": {
            "title": top_event["title"] if top_event else None,
            "date": top_event["date"] if top_event else None,
            "impact": (top_event["impact"] or "low").upper() if top_event else None,
            "country": top_event["country"] if top_event else None,
            "forecast": top_event["forecast"] if top_event else None,
            "previous": top_event["previous"] if top_event else None,
        },
        "upcoming_events": [
            {
                "title": item["title"],
                "date": item["date"],
                "impact": item["impact"].upper() if item["impact"] else "LOW",
                "country": item["country"],
                "forecast": item["forecast"],
                "previous": item["previous"],
            }
            for item in high_impact
        ],
        "summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
