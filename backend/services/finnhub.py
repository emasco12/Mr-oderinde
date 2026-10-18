from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

from backend.services.http import get_json

GOLD_SYMBOL = "OANDA:XAU_USD"


async def _candles(symbol: str, resolution: str, start: int, end: int) -> dict:
    api_key = os.getenv("FINNHUB_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("FINNHUB_API_KEY is not configured.")
    payload = await get_json(
        "https://finnhub.io/api/v1/forex/candle",
        params={
            "symbol": symbol,
            "resolution": resolution,
            "from": str(start),
            "to": str(end),
            "token": api_key,
        },
        provider="Finnhub",
    )
    if (
        payload.get("s") != "ok"
        or not isinstance(payload.get("t"), list)
        or not isinstance(payload.get("c"), list)
        or not payload["t"]
        or len(payload["t"]) != len(payload["c"])
    ):
        raise RuntimeError(f"Finnhub returned no {symbol} candle data.")
    return payload


async def quote(symbol: str = GOLD_SYMBOL) -> dict:
    now = int(time.time())
    candles = await _candles(symbol, "1", now - 600, now)
    return {"c": candles["c"][-1], "t": candles["t"][-1]}


async def daily_candles(symbol: str = GOLD_SYMBOL, days: int = 90) -> dict:
    now = datetime.now(timezone.utc)
    return await _candles(
        symbol,
        "D",
        int((now - timedelta(days=days)).timestamp()),
        int(now.timestamp()),
    )


async def health_check() -> None:
    quote_payload = await quote()
    price = quote_payload.get("c")
    if not isinstance(price, (int, float)) or price <= 0:
        raise RuntimeError("Finnhub returned an invalid XAU/USD price.")
