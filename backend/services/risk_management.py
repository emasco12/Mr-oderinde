from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_risk_management(account_balance: float, risk_percent: float, entry_price: float, stop_price: float, reward_ratio: float = 2.0) -> dict[str, Any]:
    if entry_price <= 0 or stop_price <= 0:
        raise ValueError("Entry and stop prices must be greater than zero.")

    distance = abs(entry_price - stop_price)
    if distance == 0:
        raise ValueError("Entry and stop prices must differ.")

    risk_amount = account_balance * risk_percent / 100
    position_ounces = risk_amount / distance
    standard_lots = position_ounces / 100
    direction = 1 if entry_price >= stop_price else -1
    target_price = entry_price + (direction * distance * reward_ratio)

    if risk_percent <= 1.0:
        risk_status = "Controlled"
        position_category = "Conservative"
    elif risk_percent <= 2.0:
        risk_status = "Moderate"
        position_category = "Balanced"
    elif risk_percent <= 3.0:
        risk_status = "Elevated"
        position_category = "Active"
    else:
        risk_status = "High"
        position_category = "Aggressive"

    interpretation = (
        f"This trade risks {risk_percent:.2f}% of the account ({risk_amount:.2f}) "
        f"with a {reward_ratio:.1f}:1 target profile. "
        f"The {position_category.lower()} sizing keeps the position within a {risk_status.lower()} risk framework."
    )

    return {
        "risk_amount": round(risk_amount, 2),
        "stop_distance": round(distance, 2),
        "position_ounces": round(position_ounces, 4),
        "standard_lots": round(standard_lots, 4),
        "risk_reward_ratio": round(reward_ratio, 2),
        "target_price": round(target_price, 2),
        "risk_status": risk_status,
        "position_size_rating": position_category,
        "risk_budget_percent": round(risk_percent, 2),
        "interpretation": interpretation,
        "assumption": "1 standard XAU/USD lot = 100 troy ounces",
    }
