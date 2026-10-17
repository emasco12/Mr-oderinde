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
        if (path === '/api/calendar') {
          return makeJsonResponse({ events: [{ title: 'US CPI', date: '2026-10-18', impact: 'high' }] })
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
})
