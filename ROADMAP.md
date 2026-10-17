# AI Gold Intelligence Platform — Product Roadmap

## Vision
Aurum is evolving from a working research dashboard into a production-grade XAU/USD intelligence platform for traders, analysts, and researchers. The platform combines live market data, technical analysis, macro context, and decision support while remaining transparent about data quality, model assumptions, and provider limitations.

The strategic direction is to:
- preserve the current FastAPI + React + SQLite architecture
- add features incrementally and safely
- keep the product useful even when external providers are degraded or unavailable
- prioritize real reliability, testing, and production-readiness over feature sprawl
- avoid predictive claims or misleading certainty in signal generation

---

## Status Overview

### Completed
- Market data provider integration and health monitoring
- Live Gold quote + daily history retrieval
- News and economic calendar integration
- Driver heat map and market context panels
- Professional dashboard UI with dark terminal-inspired design
- Technical Analysis Engine
- Signal Intelligence Engine
- Password reset flow
- Database migration support
- Email verification flow
- Core backend/frontend test coverage for significant flows

### In Progress
- No active milestone is currently underway.
- The next milestone will begin only after approval.

### Remaining / Planned
- Signal Intelligence Engine
- Smart Money Concepts (SMC)
- ICT Concepts
- Institutional Order Flow
- Economic Calendar Intelligence
- News Sentiment & News Outcome Prediction
- AI Decision Engine
- Institutional Heat Map
- Risk Management Suite
- Alerts & Notifications
- Backtesting Engine
- Performance Analytics
- Multi-timeframe Analysis
- Strategy Builder
- Production Hardening & Reliability
- Deployment & Monitoring

---

## Delivery Phases

### Phase 0 — Foundation and Production Readiness (Complete)
Focus: stabilize the base product and make it safe for iterative feature delivery.

Milestones:
- Project architecture review and roadmap alignment
- Product baseline validation
- Provider abstraction and graceful fallback behavior
- Database migration handling
- Auth security improvements
- Password reset and email verification support
- Core test coverage and regression checks

Outcome:
The platform now has a stable MVP foundation and a better production posture than earlier iterations.

---

### Phase 1 — Professional Market Dashboard (Complete)
Focus: deliver a modern trading terminal experience for Gold analysis.

Completed work:
- Professional dark terminal dashboard UI
- Live XAU/USD quote display
- Daily high / low / open / previous close
- Provider status indicators
- Economic calendar panel
- News panel
- Heat map panel
- Market sentiment gauge
- Responsive desktop/mobile layouts
- Loading, empty, and error states

Outcome:
The dashboard is functional, visually coherent, and suitable as the core front-end shell for later intelligence features.

---

### Phase 2 — Technical Analysis Engine (Complete)
Focus: provide objective, data-driven technical interpretation.

Completed indicators:
- EMA 20
- EMA 50
- EMA 200
- SMA 20
- RSI (14)
- MACD
- ATR
- ADX
- Bollinger Bands
- VWAP
- Stochastic RSI

Delivered outputs:
- indicator cards with bullish / neutral / bearish states
- overall technical score
- trend strength, volatility, momentum, and quality summaries
- endpoint at GET /api/analysis/technical
- professional frontend technical panel

Outcome:
The app now has a reusable technical analysis layer that supports downstream signal generation and research workflows.

---

### Phase 3 — Signal Intelligence Engine (Complete)
Focus: generate analytical trade ideas based on existing technical structure and live data.

Completed work:
- dedicated signal engine service
- BUY / SELL / HOLD logic
- confidence scoring
- entry, stop, and take-profit levels
- risk / reward ratio calculations
- reasoned “why this signal?” payloads
- GET /api/signals/current endpoint
- signal panel in the frontend
- safety disclaimer and explanatory UI
- backend/frontend test coverage for buy / sell / hold / provider fail / missing data cases

Outcome:
The platform now offers a transparent, non-guaranteed signal layer that is grounded in technicals and market conditions.

---

### Phase 4 — Production Hardening and Reliability (Planned)
Focus: make the platform resilient enough for broader team and deployment use.

Milestones:
- centralized logging and request correlation
- structured error handling across providers and UI states
- API rate-limit monitoring and provider timeout tuning
- caching strategy for quote and news data
- stricter validation and schema governance
- deployment environment hardening
- improved health dashboards and monitoring
- observability for technical analysis and signal generation failures

Priority:
High
Dependencies:
- stable production environment
- robust provider health handling
- release-level QA

---

### Phase 5 — Advanced Macro Intelligence (Planned)
Focus: enrich the dashboard with deeper macro context beyond basic headline and event feeds.

Planned features:
- macro regime classification
- real-rate / yield / dollar correlation overlays
- stronger sentiment aggregation by asset and event type
- cross-asset risk context for XAU/USD
- improved model explanation layers

Priority:
High
Dependencies:
- Phase 4 hardening
- provider resilience and data-quality validation

---

### Phase 6 — Smart Money Concepts (Planned)
Focus: add a higher-order market structure and liquidity narrative.

Planned features:
- trend structure analysis
- liquidity sweeps and reversal zones
- session high / low interpretation
- order block and displacement context
- institutional bias overlays

Priority:
High
Dependencies:
- Technical Analysis Engine
- market structure data quality
- research validation

---

### Phase 7 — ICT Analysis (Planned)
Focus: offer a second layer of trading-concept interpretation for advanced users.

Planned features:
- London / New York session analysis
- intraday pivot and liquidity model views
- fair value gap interpretation
- sweep and mitigation context
- institutional execution narrative

Priority:
Medium-High
Dependencies:
- Phase 5 and Phase 6
- careful UX design to avoid overcomplicating the UI

---

### Phase 8 — AI Research & Prediction Layer (Planned)
Focus: build a transparent AI layer that augments analysis without overstating certainty.

Planned features:
- AI-assisted headline and macro summarization
- scenario-based market outlooks
- narrative explanations for technical and signal outputs
- confidence-scored research notes
- human-readable reasoning with clear caveats

Priority:
Medium
Dependencies:
- provider and model access
- reliable data pipeline
- risk and compliance guardrails

---

### Phase 9 — Alerts, Automation, and Execution Readiness (Planned)
Focus: move from informational monitoring into actionable alerting and workflow support.

Planned features:
- configurable price alert logic
- notification channels and escalation flows
- automated signal watchlists
- event-based monitoring for price / trend / volatility triggers
- alert health and acknowledgements

Priority:
High
Dependencies:
- Phase 4 hardening
- user workflow and notification UX

---

### Phase 10 — Advanced Analytics and Portfolio Intelligence (Planned)
Focus: extend the platform beyond spot analysis into broader trading intelligence.

Planned features:
- account-level portfolio analytics
- win rate and trade quality analysis
- journal insights and behavior trends
- risk metrics and exposure summaries
- performance benchmarking

Priority:
Medium
Dependencies:
- journal and account maturity
- quality of stored trade data

---

### Phase 11 — Multi-Asset Expansion and Platformization (Planned)
Focus: evolve Aurum into a broader intelligence platform beyond XAU/USD.

Planned features:
- multi-asset market coverage
- cross-market correlation analysis
- institutional dashboard modules
- user management and role-based access
- admin and operations tooling

Priority:
Medium-Low
Dependencies:
- core platform stability
- broader data-provider strategy

---

## Milestone Prioritization

| Priority | Milestone | Status | Difficulty | Dependencies |
| --- | --- | --- | --- | --- |
| P1 | Signal Intelligence Engine | Complete | Medium | Technical Analysis Engine + market data |
| P2 | Smart Money Concepts (SMC) | Planned | High | Technical analysis + market structure validation |
| P2 | ICT Concepts | Planned | High | SMC + intra-session structure validation |
| P2 | Institutional Order Flow | Planned | High | Order-flow data + trade context |
| P2 | Economic Calendar Intelligence | Planned | Medium | Calendar feed quality + macro interpretation |
| P2 | News Sentiment & News Outcome Prediction | Planned | Medium | News provider quality + model reasoning |
| P2 | AI Decision Engine | Planned | Medium-High | Data pipeline + model access + guardrails |
| P3 | Institutional Heat Map | Planned | Medium | Macro, news, and calendar integration |
| P3 | Risk Management Suite | Planned | Medium | Trade/account data + user workflows |
| P3 | Alerts & Notifications | Planned | Medium | Price alert logic + user notifications |
| P3 | Backtesting Engine | Planned | High | Signal + strategy definitions + historical data |
| P3 | Performance Analytics | Planned | Medium | Trade data + analytics workflows |
| P3 | Multi-timeframe Analysis | Planned | Medium-High | Cross-timeframe aggregation + UX |
| P3 | Strategy Builder | Planned | High | Signal logic + backtesting + analytics |
| P4 | Production Hardening & Reliability | Planned | Medium-High | Current platform stability |
| P4 | Deployment & Monitoring | Planned | Medium | Production environment + operational tooling |

---

## Execution Policy
From this point forward, the roadmap will be implemented one milestone at a time.

Rules:
- complete one milestone before starting the next
- run all relevant tests for the milestone
- fix any failing tests before proceeding
- commit each milestone with a clear descriptive message
- wait for explicit approval before beginning the next feature set

---

## Recommended Next Milestone
The approved next milestone is:
- Signal Intelligence Engine

Why this is the correct next step:
- it is the first remaining milestone in the priority stack
- it builds directly on the Technical Analysis Engine already in place
- it adds decision-support value without introducing broad platform churn
- it is already aligned with the project’s current architecture and test coverage

This milestone is already represented in the repository and validated against the existing technical and frontend test suite. No additional code changes are required unless you specifically want a new implementation pass for this milestone before moving on.
