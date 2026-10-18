from __future__ import annotations

import asyncio

import httpx


async def get_json(
    url: str,
    *,
    params: dict[str, str],
    headers: dict[str, str] | None = None,
    timeout: float = 12,
    attempts: int = 3,
    min_retry_delay: float = 0.25,
    provider: str,
) -> dict:
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
                response = await client.get(url, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 < attempts:
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = max(float(retry_after), min_retry_delay) if retry_after else max(
                            min_retry_delay, 0.25 * (2**attempt)
                        )
                    except ValueError:
                        delay = max(min_retry_delay, 0.25 * (2**attempt))
                    await asyncio.sleep(delay)
                    continue
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RuntimeError(f"{provider} returned an unexpected response.")
            return payload
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status == 429:
                raise RuntimeError(f"{provider} rate limit reached (HTTP 429).") from None
            raise RuntimeError(f"{provider} request failed with HTTP {status}.") from None
        except httpx.RequestError:
            if attempt + 1 == attempts:
                raise RuntimeError(f"{provider} request failed after {attempts} attempts.") from None
            await asyncio.sleep(max(min_retry_delay, 0.25 * (2**attempt)))
        except ValueError:
            raise RuntimeError(f"{provider} returned invalid JSON.") from None
    raise RuntimeError(f"{provider} request failed after {attempts} attempts.")
