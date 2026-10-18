from __future__ import annotations

import asyncio
import os
import time

from backend.services.http import get_json

_request_lock = asyncio.Lock()
_last_request_at = 0.0


async def fetch(function: str, **params: str) -> dict:
    global _last_request_at
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY is not configured.")
    for attempt in range(3):
        async with _request_lock:
            delay = 1.05 - (time.monotonic() - _last_request_at)
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                payload = await get_json(
                    "https://www.alphavantage.co/query",
                    params={"function": function, "apikey": api_key, **params},
                    min_retry_delay=1.05,
                    provider="Alpha Vantage",
                )
            finally:
                _last_request_at = time.monotonic()
        message = payload.get("Error Message") or payload.get("Note") or payload.get("Information")
        if not message:
            return payload
        if "requests per second" in message.lower() and attempt < 2:
            await asyncio.sleep(1.05)
            continue
        raise RuntimeError(f"Alpha Vantage rejected the request: {message}")
    raise RuntimeError("Alpha Vantage request failed after 3 attempts.")


async def health_check() -> None:
    payload = await fetch("GOLD_SILVER_SPOT", symbol="GOLD")
    price = payload.get("price")
    if not isinstance(price, (int, float, str)) or float(price) <= 0:
        raise RuntimeError("Alpha Vantage returned an invalid gold spot price.")
