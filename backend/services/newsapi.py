from __future__ import annotations

import os

from backend.services.http import get_json


async def gold_headlines() -> dict:
    api_key = os.getenv("NEWSAPI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("NEWSAPI_API_KEY is not configured.")
    payload = await get_json(
        "https://newsapi.org/v2/everything",
        params={
            "q": '"gold price" OR XAU/USD',
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": "12",
        },
        headers={"X-Api-Key": api_key},
        timeout=15,
        provider="NewsAPI",
    )
    if payload.get("status") != "ok":
        code = payload.get("code", "unknown error")
        if code == "rateLimited":
            raise RuntimeError("NewsAPI free-plan rate limit reached; try again later.")
        raise RuntimeError(f"NewsAPI rejected the request ({code}).")
    return payload


async def health_check() -> None:
    payload = await gold_headlines()
    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise RuntimeError("NewsAPI did not return an article list.")
