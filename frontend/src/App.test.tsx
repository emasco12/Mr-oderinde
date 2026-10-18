import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

function makeJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal('ResizeObserver', ResizeObserverMock)
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        const path = url.replace('http://localhost:8000', '')

        if (path === '/api/auth/me') {
          return makeJsonResponse({ id: 1, email: 'demo@example.com', email_verified: false })
        }
        if (path === '/api/auth/request-email-verification') {
          return makeJsonResponse({ message: 'A verification code has been sent to your email.', verification_token: 'demo-verify-code' })
        }
        if (path === '/api/auth/verify-email') {
          return makeJsonResponse({ message: 'Email verified successfully.' })
        }
        if (path === '/api/market/gold') {
          return makeJsonResponse({
            price: 2345.67,
            status: 'live',
            source: 'Alpha Vantage',
            open: 2334.45,
            daily_high: 2360.1,
            daily_low: 2328.15,
            previous_close: 2320.6,
            change_percent: 1.08,
            updated_at: '2026-10-17T12:00:00Z',
          })
        }
        if (path === '/api/market/history') {
          return makeJsonResponse({ candles: [{ date: '2026-10-01', close: 2334.45 }, { date: '2026-10-17', close: 2345.67 }] })
        }
        if (path === '/api/news') {
          return makeJsonResponse({ items: [{ title: 'Gold demand remains strong', url: '#', published_at: '2026-10-17T11:00:00Z', source: 'Reuters', sentiment_score: 0.4, bias: 'Bullish', impact: 'High' }] })
        }
        if (path === '/api/news/intelligence') {
          return makeJsonResponse({
            status: 'live',
            source: 'NewsAPI',
            sentiment: { score: 0.42, bias: 'bullish', article_count: 1, source: 'NewsAPI', method: 'Transparent headline scoring; not financial advice.' },
            prediction: { direction: 'bullish', probability: 68, confidence: 'moderate', rationale: 'Headline momentum is skewed toward gold-supportive catalysts.' },
            headline_focus: 'Gold demand remains strong',
            timestamp: '2026-10-17T12:00:00Z',
          })
        }
        if (path === '/api/calendar') {
          return makeJsonResponse({ events: [{ title: 'US CPI', date: '2026-10-18', impact: 'high' }] })
        }
        if (path === '/api/analysis/calendar') {
          return makeJsonResponse({
            symbol: 'XAU/USD',
            provider: 'Forex Factory calendar',
            status: 'live',
            timestamp: '2026-10-17T12:00:00Z',
            risk_bucket: 'High',
            market_bias: 'Bullish',
            summary: 'The next major macro catalyst is US CPI and the macro bias is bullish.',
            next_event: { title: 'US CPI', date: '2026-10-18T13:30:00Z', impact: 'high', country: 'USD', forecast: '3.2%', previous: '3.1%' },
            upcoming_events: [{ title: 'US CPI', date: '2026-10-18T13:30:00Z', impact: 'HIGH', country: 'USD', forecast: '3.2%', previous: '3.1%' }],
          })
        }
        if (path === '/api/ai/decision') {
          return makeJsonResponse({
            status: 'live',
            decision: 'bullish',
            score: 18.5,
            confidence: 82,
            narrative: 'Bullish confluence is forming across price, trend structure, and macro drivers.',
            drivers: [
              { label: 'Signal', value: 'BUY', detail: 'The technical signal stack is favoring upside continuation.' },
              { label: 'Technical structure', value: 'Bullish', detail: 'The technical engine is constructive.' },
            ],
            watch_points: ['Monitor trend continuation above the short-term moving average band.', 'Watch volatility and risk appetite for confirmation.'],
            timestamp: '2026-10-17T12:00:00Z',
            provider: 'Alpha Vantage + Analytics',
          })
        }
        if (path === '/api/signals/current') {
          return makeJsonResponse({ status: 'live', signal: 'BUY', confidence: 72, entry: 2345.67, stop_loss: 2320.0, take_profit: [2368.0, 2390.0, 2415.0], risk_reward: '1:2.1', quality: 'High', reasons: [{ indicator: 'EMA 20', value: 2338.12, interpretation: 'Price is trading above the short-term EMA.' }], note: 'Signals are analytical estimates generated from market data and technical indicators. They are not financial advice and do not guarantee future market performance.' })
        }
        if (path === '/api/journal') {
          return makeJsonResponse([])
        }
        if (path === '/api/health') {
          return makeJsonResponse({ warnings: [], providers: { 'Alpha Vantage': { status: 'available', priority: 'primary', warning: null }, NewsAPI: { status: 'available', priority: 'primary', warning: null }, Finnhub: { status: 'unavailable', priority: 'secondary', warning: 'Finnhub unavailable' } } })
        }
        if (path === '/api/risk') {
          return makeJsonResponse({ risk_amount: 250, stop_distance: 40, position_ounces: 6.25, standard_lots: 0.0625, risk_status: 'Controlled', risk_reward_ratio: 2.0, target_price: 4420, risk_budget_percent: 1, position_size_rating: 'Conservative', interpretation: 'This trade risks 1.00% of the account while preserving a disciplined 2:1 reward profile.' })
        }
        if (path === '/api/market/heatmap') {
          return makeJsonResponse({ factors: [{ name: 'US Dollar', ticker: 'DXY', score: 42, bias: 'Bearish', reading: 'soft', source: 'Macro' }] })
        }
        if (path === '/api/alerts') {
          return makeJsonResponse([])
        }
        if (path === '/api/notifications') {
          return makeJsonResponse([])
        }
        if (path === '/api/dashboard') {
          return makeJsonResponse({ trade_count: 0, open_positions: 0, closed_pnl: 0, win_rate: null, active_alerts: 0, unread_notifications: 0 })
        }
        if (path === '/api/analysis/technical') {
          return makeJsonResponse({
            symbol: 'XAU/USD',
            provider: 'Alpha Vantage',
            status: 'live',
            timestamp: '2026-10-17T12:00:00Z',
            summary: { overall_bias: 'bullish', overall_score: 70, trend_strength: 'strong', volatility: 'moderate', momentum: 'positive', quality: 'high' },
            indicators: [{ name: 'EMA 20', value: 2337.39, status: 'bullish', interpretation: 'Price is strengthened above the short-term EMA.', unit: 'USD' }],
          })
        }
        if (path === '/api/analysis/smc') {
          return makeJsonResponse({
            symbol: 'XAU/USD',
            provider: 'Alpha Vantage',
            status: 'live',
            timestamp: '2026-10-17T12:00:00Z',
            market_structure: { trend: 'bullish', break_of_structure: 'Bullish break of structure remains intact above recent local highs.', change_of_character: 'Momentum is constructive and the short-term trend is still positive.', swing_high: 2350, swing_low: 2320 },
            liquidity: { sweep: 'bullish', interpretation: 'Buy-side liquidity has been absorbed and price is holding above the recent premium range.' },
            order_block: { type: 'bullish', top: 2348, bottom: 2336, strength: 'strong', interpretation: 'Bullish order block remains active.' },
            fair_value_gap: { present: true, direction: 'bullish', gap: 12.6, interpretation: 'A bullish fair value gap is in play.' },
            session_bias: 'Bullish',
            risk_context: { trend: 'Bullish', volatility: 'Moderate', momentum: 'Positive', liquidity: 'Premium' },
          })
        }
        if (path === '/api/analysis/ict') {
          return makeJsonResponse({
            symbol: 'XAU/USD',
            provider: 'Alpha Vantage',
            status: 'live',
            timestamp: '2026-10-17T12:00:00Z',
            session_bias: 'Bullish',
            liquidity: { sweep: 'bullish', interpretation: 'Buy-side liquidity has been swept and price is holding above the session high.' },
            fair_value_gap: { present: true, direction: 'bullish', size: 11.4, interpretation: 'A bullish fair value gap remains open.' },
            displacement: { direction: 'bullish', magnitude: 0.74, interpretation: 'Price is extending with clear directional expansion.' },
            market_regime: { trend: 'Bullish', volatility: 'Moderate', institutional_flow: 'Bullish' },
            narrative: 'The market is showing a bullish ICT narrative with clean directional expansion and a valid fair value gap.',
            indicators: [{ name: 'Session Bias', value: 'Bullish', status: 'bullish', interpretation: 'Current structure remains bullish.' }],
          })
        }
        if (path === '/api/analysis/order-flow') {
          return makeJsonResponse({
            symbol: 'XAU/USD',
            provider: 'Alpha Vantage',
            status: 'live',
            timestamp: '2026-10-17T12:00:00Z',
            order_flow: { trend: 'Bullish', pressure: 'Bullish', absorption: 'Strong', participation: 'High', imbalance: 0.18, interpretation: 'Institutional buying is absorbing supply and expanding the trend.' },
            market_context: { volatility: 'Moderate', bias: 'Bullish', execution_quality: 'High' },
            signals: [{ name: 'Pressure', value: 'Bullish', status: 'bullish', interpretation: 'Buying pressure is stronger than selling pressure.' }],
          })
        }

        return makeJsonResponse({}, 404)
      }),
    )
  })

  it('renders the technical analysis panel with overall market structure data', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Gold intelligence')).toBeInTheDocument()
    })

    expect(screen.getByText('Market structure')).toBeInTheDocument()
    expect(screen.getByText('Overall Technical Score')).toBeInTheDocument()
    expect(screen.getByText('Trend Strength')).toBeInTheDocument()
  })

  it('renders the macro calendar intelligence panel', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Economic calendar')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText('The next major macro catalyst is US CPI and the macro bias is bullish.')).toBeInTheDocument()
    })
    expect(screen.getAllByText('Bullish').length).toBeGreaterThan(0)
  })

  it('renders the news intelligence prediction panel', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Headlines provide context, not trade instructions.')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getAllByText(/BULLISH/i).length).toBeGreaterThan(0)
    })
    expect(screen.getByText(/Headline momentum is skewed toward gold-supportive catalysts/i)).toBeInTheDocument()
  })

  it('renders the AI decision engine panel', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Decision synthesis')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText('AI DECISION ENGINE')).toBeInTheDocument()
    })

    await waitFor(() => {
      expect(screen.getByText(/Bullish confluence is forming across price, trend structure, and macro drivers/i)).toBeInTheDocument()
    })
  })

  it('renders the risk management suite panel', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Risk management suite')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: 'CALCULATE POSITION' }))

    await waitFor(() => {
      expect(screen.getByText('Controlled')).toBeInTheDocument()
    })
    expect(screen.getByText('1:2.0')).toBeInTheDocument()
  })

  it('allows a user to verify their email address', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Verify your email')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Verification code'), { target: { value: 'demo-verify-code' } })
    fireEvent.click(screen.getByRole('button', { name: 'VERIFY EMAIL' }))

    await waitFor(() => {
      expect(screen.queryByText('Verify your email')).not.toBeInTheDocument()
    })
  })

  it('renders the Smart Money Concepts panel', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Smart Money')).toBeInTheDocument()
    })

    expect(screen.getByText('Smart money structure')).toBeInTheDocument()
    expect(screen.getAllByText('Session bias').length).toBeGreaterThan(0)
  })

  it('renders the ICT Concepts panel', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('ICT analysis')).toBeInTheDocument()
    })

    expect(screen.getAllByText('Session bias').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Displacement').length).toBeGreaterThan(0)
  })

  it('renders the Institutional Order Flow panel', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Institutional order flow')).toBeInTheDocument()
    })

    expect(screen.getByText('Pressure')).toBeInTheDocument()
    expect(screen.getByText('Participation')).toBeInTheDocument()
  })
})
