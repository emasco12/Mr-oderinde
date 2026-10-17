# Aurum | Gold Intelligence

Aurum is an XAU/USD research dashboard built with React, TypeScript and FastAPI. It combines sourced gold prices and history, macro headlines, a USD economic calendar, a transparent trend signal, position sizing, private trading journals, account dashboards and in-app price alerts.

## Market-data providers

- **Alpha Vantage** is the primary gold spot and daily history provider. Create a key at [Alpha Vantage](https://www.alphavantage.co/support/#api-key).
- **Finnhub** is an optional secondary provider. Its [forex symbol directory](https://finnhub.io/docs/api/forex-symbols) lists `OANDA:XAU_USD` as Oanda Gold (`XAU/USD`); the integration uses its [forex candles endpoint](https://finnhub.io/docs/api/forex-candles). Symbol availability does not guarantee account entitlement. If the key is missing, the plan denies access, or a request fails, Alpha Vantage remains primary and the dashboard reports a warning.
- **NewsAPI** provides gold-related headlines. Register at [NewsAPI](https://newsapi.org/register); its free plan has strict quotas and may delay results.
- **OpenAI** is optional for model-assisted headline analysis. Without it, the app uses a clearly labeled local keyword heuristic.

`GET /api/health` checks Alpha Vantage and Finnhub independently. Provider health warnings do not take the API offline. Gold spot and history requests try Alpha Vantage first, then Finnhub, and return a graceful unavailable result if both fail. The backend logs the provider serving the data. A provider being healthy does not mean its plan includes every symbol.

## Configuration

Copy the example configuration, then edit `backend/.env`:

```bash
cp backend/.env.example backend/.env
chmod 600 backend/.env
```

Set `ALPHA_VANTAGE_API_KEY`, `NEWSAPI_API_KEY` and a random `JWT_SECRET_KEY` with at least 32 characters. `FINNHUB_API_KEY` and `OPENAI_API_KEY` are optional. The application refuses to start if a required provider key or valid JWT secret is missing. `.env` is ignored by Git and excluded from the Docker build context; never put provider keys in frontend variables or commit secrets. `.env.example` contains placeholders only.

Generate a suitable JWT secret, then paste the output into `backend/.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

If API credentials have been shared outside your private deployment environment, rotate them with the provider before deploying.

## Run locally

Use Python 3.10+ and Node.js 20+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

In a second terminal:

```bash
npm install --prefix frontend
npm run dev --prefix frontend
```

Open `http://localhost:5173`; the API and interactive docs are at `http://localhost:8000` and `http://localhost:8000/docs`. Register an account to use the private journal, dashboard and alert features.

## Docker Compose

```bash
docker compose up --build
```

Compose loads provider credentials from `backend/.env`, builds the frontend as a static Nginx site and proxies `/api` requests to the backend. Visit `http://localhost:5173`; the API is not published directly to the host. The backend runs as a non-root user, has a liveness health check, and stores SQLite data in the persistent `journal-data` volume.

For production, terminate TLS at a trusted ingress/reverse proxy and set `APP_ENV=production`, `AUTH_COOKIE_SECURE=true`, a strong unique `JWT_SECRET_KEY`, and `CORS_ORIGINS` to the exact allowed origins in `backend/.env`. For example:

```env
APP_ENV=production
AUTH_COOKIE_SECURE=true
CORS_ORIGINS=https://aurum.example.com
```

Start Compose with `APP_ENV=production docker compose up --build`. Do not expose the backend port publicly. Configure the ingress to forward the original client IP and scheme headers; only private-network proxies are trusted by Uvicorn. Back up the `journal-data` volume. Account registration is open; use an external identity/email-verification system if your deployment needs verified accounts or account recovery. The built-in authentication throttle is in-memory and per process, so deployments with multiple replicas should also enforce centralized edge rate limits.

## Platform modules and limitations

- **Dashboard:** Account-scoped trade count, open positions, realized P&L, win rate and sentiment overview.
- **Gold spot and chart:** Alpha Vantage primary, optional Finnhub fallback, and a visibly labeled simulated preview when demo mode is enabled. Free-tier provider limits mean prices/history may be delayed or cached.
- **Economic calendar:** USD releases from the Forex Factory weekly JSON feed, including impact and forecast when supplied.
- **News impact:** NewsAPI headlines with locally computed, transparent keyword sentiment. Authenticated users can request OpenAI analysis when configured; failed model calls fall back to the local heuristic.
- **Driver heat map:** Uses only sourced Gold momentum, recent headline sentiment and upcoming high-impact USD calendar events. It does not fabricate live dollar-index or real-yield inputs and is contextual, not a forecast.
- **Signal monitor:** A simple 20-day SMA and prior-day momentum rule. Informational only.
- **Risk calculator:** Dollar risk, XAU/USD ounces and standard lots (one lot is assumed to be 100 troy ounces).
- **Trading journal:** Authenticated, account-scoped SQLite entries and realized P&L. Legacy unowned entries are not exposed to user accounts.
- **Price alerts and notifications:** In-app alerts are checked when the backend serves a Gold quote, and the signed-in dashboard refreshes feeds every minute. Provider quote caching and free-plan quotas can delay alert evaluation; this is not a guaranteed real-time push service.
- **Authentication:** Email/password accounts, Argon2 password hashes and seven-day HttpOnly, SameSite=Strict JWT cookies. Production requires secure cookies over HTTPS. Password reset and email verification are not implemented.

## Configuration reference

| Variable | Required | Purpose |
| --- | --- | --- |
| `ALPHA_VANTAGE_API_KEY` | Yes | Primary Gold spot and daily history |
| `NEWSAPI_API_KEY` | Yes | Gold-related headlines |
| `FINNHUB_API_KEY` | No | Secondary XAU/USD provider; account entitlement applies |
| `OPENAI_API_KEY` | No | Model-assisted headline analysis |
| `OPENAI_MODEL` | No | OpenAI chat-completions model (default `gpt-4o-mini`) |
| `JWT_SECRET_KEY` | Yes | Random session-signing secret, minimum 32 characters |
| `AUTH_COOKIE_SECURE` | Production | Set to `true` when served over HTTPS |
| `APP_ENV` | No | Set to `production` to enforce secure-cookie configuration |
| `DATABASE_URL` | No | SQLAlchemy URL; default `sqlite:///./gold_intelligence.db` |
| `CORS_ORIGINS` | No | Comma-separated exact allowed origins |
| `VITE_API_URL` | No | Frontend API base; Compose uses same-origin `/api` proxy |
| `VITE_DEMO_MODE` | No | Defaults to `true`; set to `false` to hide simulated preview values |

## Checks

```bash
python -m pytest backend/tests
npm run build --prefix frontend
docker compose config
docker compose build
```

External feeds have independent availability and rate limits. Failed feeds return an unavailable status rather than invented live data. Aurum is for informational and educational use only, not financial advice.
