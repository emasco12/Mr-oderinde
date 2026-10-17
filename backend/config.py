from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")

REQUIRED_API_KEYS = (
    "ALPHA_VANTAGE_API_KEY",
    "NEWSAPI_API_KEY",
)


def validate_required_api_keys() -> None:
    missing = [name for name in REQUIRED_API_KEYS if not os.getenv(name, "").strip()]
    if missing:
        names = ", ".join(missing)
        raise RuntimeError(
            f"Missing required API key(s): {names}. "
            "Add them to backend/.env or the process environment before starting the API."
        )
    jwt_secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if len(jwt_secret) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be set to a random secret at least 32 characters long."
        )
