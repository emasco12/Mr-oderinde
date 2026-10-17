import { useEffect, useState } from 'react'
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BarChart3, Bell, BookOpen,
  BrainCircuit, CalendarDays, Check, ChevronDown, CircleDollarSign, Clock3, Crosshair,
  ExternalLink, Gauge, Gem, Globe2, LayoutDashboard, LoaderCircle, Menu, Newspaper,
  Plus, RefreshCw, ShieldAlert, Sparkles, Trash2, X,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const DEMO = import.meta.env.VITE_DEMO_MODE !== 'false'

type Quote = {
  price: number | null
  status: string
  source: string
  symbol?: string
  open?: number | null
  daily_high?: number | null
  daily_low?: number | null
  previous_close?: number | null
  change_percent?: number | null
  updated_at?: string | null
  note?: string | null
}
type Candle = { date: string; close: number }
type NewsItem = { title: string; url: string; published_at: string; source: string; bias?: string; impact?: string; sentiment_score?: number }
type EventItem = { title: string; date: string | null; impact: string; forecast?: string | null; previous?: string | null }
type JournalEntry = { id: number; side: 'BUY' | 'SELL'; entry_price: number; exit_price: number | null; quantity_ounces: number; thesis: string; created_at: string; pnl: number | null }
type SignalReason = { indicator: string; value: number | null; interpretation: string }
type Signal = {
  status?: string
  signal: 'BUY' | 'SELL' | 'HOLD' | 'WAIT'
  confidence: number
  entry?: number | null
  stop_loss?: number | null
  take_profit?: number[]
  risk_reward?: string
  trend?: string
  quality?: string
  reasons?: SignalReason[]
  method?: string
  note?: string
  timestamp?: string | null
  provider?: string | null
}
type ProviderHealth = { warnings: string[]; providers?: Record<string, { status: 'available' | 'unavailable'; warning?: string | null }> }
type User = { id: number; email: string }
type HeatFactor = { name: string; ticker: string; score: number; bias: string; reading: string; source: string }
type PriceAlert = { id: number; direction: 'above' | 'below'; target_price: number; active: boolean }
type Notification = { id: number; message: string; read: boolean; created_at: string }
type DashboardSummary = { trade_count: number; open_positions: number; closed_pnl: number; win_rate: number | null; active_alerts: number; unread_notifications: number }
type TechnicalIndicator = { name: string; value: number | null; status: 'bullish' | 'neutral' | 'bearish'; interpretation: string; unit?: string }
type TechnicalSummary = { overall_bias: string; overall_score: number; trend_strength: string; volatility: string; momentum: string; quality: string }
type TechnicalAnalysis = { symbol: string; provider: string; status: string; timestamp: string | null; summary: TechnicalSummary; indicators: TechnicalIndicator[] }

const demoCandles: Candle[] = Array.from({ length: 42 }, (_, index) => ({
  date: new Date(Date.now() - (41 - index) * 86400000).toISOString().slice(0, 10),
  close: 4318 + index * 3.2 + Math.sin(index * 0.63) * 29 + Math.cos(index * 0.19) * 23,
}))
const demoNews: NewsItem[] = [
  { title: 'Dollar softens as traders reassess the path for rates', url: '#', published_at: new Date(Date.now() - 3600000).toISOString(), source: 'Market Watch', bias: 'Bullish', impact: 'Medium' },
  { title: 'Central-bank buying keeps official gold demand in focus', url: '#', published_at: new Date(Date.now() - 9800000).toISOString(), source: 'Reuters', bias: 'Bullish', impact: 'High' },
  { title: 'Treasury yields climb ahead of key inflation data', url: '#', published_at: new Date(Date.now() - 16400000).toISOString(), source: 'Bloomberg', bias: 'Bearish', impact: 'High' },
]
async function apiFetch(path: string, init: RequestInit = {}) {
  return fetch(`${API}${path}`, { ...init, credentials: 'include' })
}

async function getJson<T>(path: string): Promise<T> {
  const response = await apiFetch(path)
  if (!response.ok) throw new Error(`API ${response.status}`)
  return response.json() as Promise<T>
}

function formatPrice(price: number | null | undefined) {
  return price == null ? '—' : price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [authReady, setAuthReady] = useState(false)
  const [authMode, setAuthMode] = useState<'login' | 'register'>('login')
  const [authEmail, setAuthEmail] = useState('')
  const [authPassword, setAuthPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [quote, setQuote] = useState<Quote | null>(null)
  const [candles, setCandles] = useState<Candle[]>([])
  const [news, setNews] = useState<NewsItem[]>([])
  const [events, setEvents] = useState<EventItem[]>([])
  const [signal, setSignal] = useState<Signal | null>(null)
  const [signalExpanded, setSignalExpanded] = useState(true)
  const [journal, setJournal] = useState<JournalEntry[]>([])
  const [live, setLive] = useState(false)
  const [providerWarnings, setProviderWarnings] = useState<string[]>([])
  const [providerStatus, setProviderStatus] = useState<Record<string, { status: 'available' | 'unavailable'; warning?: string | null }>>({})
  const [heatDrivers, setHeatDrivers] = useState<HeatFactor[]>([])
  const [alerts, setAlerts] = useState<PriceAlert[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null)
  const [technical, setTechnical] = useState<TechnicalAnalysis | null>(null)
  const [alertPrice, setAlertPrice] = useState('')
  const [alertDirection, setAlertDirection] = useState<'above' | 'below'>('above')
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState<string | null>(null)
  const [analysis, setAnalysis] = useState<{ bias: string; impact: string; rationale: string } | null>(null)
  const [range, setRange] = useState('1M')
  const [showJournalForm, setShowJournalForm] = useState(false)
  const [journalError, setJournalError] = useState('')
  const [risk, setRisk] = useState({ account_balance: '25000', risk_percent: '1', entry_price: '4340', stop_price: '4300' })
  const [riskResult, setRiskResult] = useState<{ risk_amount: number; position_ounces: number; standard_lots: number } | null>(null)
  const [journalForm, setJournalForm] = useState<{ side: 'BUY' | 'SELL'; entry_price: string; exit_price: string; quantity_ounces: string; thesis: string }>({ side: 'BUY', entry_price: '', exit_price: '', quantity_ounces: '', thesis: '' })
  const [notice, setNotice] = useState('')

  async function refresh() {
    setLoading(true)
    const results = await Promise.allSettled([
      getJson<Quote>('/api/market/gold'), getJson<{ candles: Candle[] }>('/api/market/history'),
      getJson<{ items: NewsItem[] }>('/api/news'), getJson<{ events: EventItem[] }>('/api/calendar'),
      getJson<Signal>('/api/signals/current'), getJson<JournalEntry[]>('/api/journal'),
      getJson<ProviderHealth>('/api/health'),
      getJson<{ factors: HeatFactor[] }>('/api/market/heatmap'),
      getJson<PriceAlert[]>('/api/alerts'), getJson<Notification[]>('/api/notifications'),
      getJson<DashboardSummary>('/api/dashboard'), getJson<TechnicalAnalysis>('/api/analysis/technical'),
    ])
    const [quoteResult, historyResult, newsResult, calendarResult, signalResult, journalResult, healthResult, heatmapResult, alertsResult, notificationResult, dashboardResult, technicalResult] = results
    const liveQuote = quoteResult.status === 'fulfilled' ? quoteResult.value : null
    const liveHistory = historyResult.status === 'fulfilled' ? historyResult.value.candles : []
    setLive(Boolean(liveQuote?.status === 'live' && liveHistory.length))
    setQuote(liveQuote?.price != null ? liveQuote : DEMO ? { price: 4341.82, status: 'demo', source: 'Simulated preview', updated_at: null } : liveQuote)
    setCandles(liveHistory.length ? liveHistory : DEMO ? demoCandles : [])
    setNews(newsResult.status === 'fulfilled' && newsResult.value.items.length ? newsResult.value.items : DEMO ? demoNews : [])
    setEvents(calendarResult.status === 'fulfilled' ? calendarResult.value.events : [])
    const nextSignal = signalResult.status === 'fulfilled' ? signalResult.value : null
    setSignal(nextSignal && nextSignal.signal !== 'WAIT' ? nextSignal : DEMO ? { signal: 'BUY', confidence: 72, method: 'Simulated trend preview', note: 'Signals are analytical estimates generated from market data and technical indicators. They are not financial advice and do not guarantee future market performance.' } : nextSignal)
    setJournal(journalResult.status === 'fulfilled' ? journalResult.value : JSON.parse(localStorage.getItem(`aurum-journal:${user?.id}`) ?? '[]') as JournalEntry[])
    setProviderWarnings(healthResult.status === 'fulfilled' ? healthResult.value.warnings : ['Provider health check could not be completed.'])
    setProviderStatus(healthResult.status === 'fulfilled' ? (healthResult.value.providers ?? {}) : {})
    setHeatDrivers(heatmapResult.status === 'fulfilled' ? heatmapResult.value.factors : [])
    setAlerts(alertsResult.status === 'fulfilled' ? alertsResult.value : [])
    setNotifications(notificationResult.status === 'fulfilled' ? notificationResult.value : [])
    setDashboard(dashboardResult.status === 'fulfilled' ? dashboardResult.value : null)
    setTechnical(technicalResult.status === 'fulfilled' ? technicalResult.value : null)
    setLoading(false)
  }

  useEffect(() => {
    void apiFetch('/api/auth/me')
      .then(async response => {
        if (response.ok) setUser(await response.json() as User)
      })
      .catch(() => setAuthError('The API could not be reached.'))
      .finally(() => setAuthReady(true))
  }, [])

  useEffect(() => {
    if (!user) return
    void refresh()
    const interval = window.setInterval(() => void refresh(), 60_000)
    return () => window.clearInterval(interval)
  }, [user])

  const price = quote?.price ?? null
  const firstPrice = candles[0]?.close ?? 0
  const lastPrice = candles[candles.length - 1]?.close ?? 0
  const chartChange = firstPrice ? ((lastPrice - firstPrice) / firstPrice) * 100 : 0
  const average = candles.length ? candles.reduce((sum, item) => sum + item.close, 0) / candles.length : 0
  const totalPnl = journal.reduce((sum, item) => sum + (item.pnl ?? 0), 0)
  const sentimentScore = news.length
    ? news.reduce((sum, item) => sum + (item.sentiment_score ?? 0), 0) / news.length
    : 0
  const chartData = candles.filter((_, index) => range === '1W' ? index >= candles.length - 7 : range === '1M' ? index >= candles.length - 30 : true)

  async function analyze(item: NewsItem) {
    setAnalyzing(item.title)
    setAnalysis(null)
    try {
      const response = await apiFetch('/api/news/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ headline: item.title }) })
      if (!response.ok) throw new Error('Analysis unavailable')
      const result = await response.json()
      setAnalysis({ bias: result.bias, impact: result.impact, rationale: result.rationale })
    } catch {
      setAnalysis({ bias: item.bias ?? 'Neutral', impact: item.impact ?? 'Low', rationale: 'Connect the API to enable headline analysis.' })
    } finally { setAnalyzing(null) }
  }

  async function calculateRisk(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const payload = Object.fromEntries(Object.entries(risk).map(([key, value]) => [key, Number(value)]))
    try {
      const response = await apiFetch('/api/risk', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (!response.ok) throw new Error()
      setRiskResult(await response.json())
    } catch {
      const riskAmount = Number(risk.account_balance) * Number(risk.risk_percent) / 100
      const distance = Math.abs(Number(risk.entry_price) - Number(risk.stop_price))
      setRiskResult(distance ? { risk_amount: riskAmount, position_ounces: riskAmount / distance, standard_lots: riskAmount / distance / 100 } : null)
    }
  }

  async function addJournal(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setJournalError('')
    const payload = { side: journalForm.side, entry_price: Number(journalForm.entry_price), exit_price: journalForm.exit_price ? Number(journalForm.exit_price) : null, quantity_ounces: Number(journalForm.quantity_ounces), thesis: journalForm.thesis }
    try {
      const response = await apiFetch('/api/journal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      if (!response.ok) throw new Error('Journal API unavailable.')
      const entry = await response.json() as JournalEntry
      setJournal(current => [entry, ...current])
    } catch {
      const entry: JournalEntry = { ...payload, id: Date.now(), created_at: new Date().toISOString(), pnl: payload.exit_price == null ? null : (payload.exit_price - payload.entry_price) * payload.quantity_ounces * (payload.side === 'BUY' ? 1 : -1) }
      const next = [entry, ...journal]
      setJournal(next)
      localStorage.setItem(`aurum-journal:${user?.id}`, JSON.stringify(next))
      setNotice('Saved locally. Connect the API to sync journal entries.')
      window.setTimeout(() => setNotice(''), 4000)
    }
    setShowJournalForm(false)
    setJournalForm({ side: 'BUY', entry_price: '', exit_price: '', quantity_ounces: '', thesis: '' })
  }

  async function deleteEntry(entry: JournalEntry) {
    try { await apiFetch(`/api/journal/${entry.id}`, { method: 'DELETE' }) } catch { /* local-only entry */ }
    const next = journal.filter(item => item.id !== entry.id)
    setJournal(next)
    localStorage.setItem(`aurum-journal:${user?.id}`, JSON.stringify(next))
  }

  async function authenticate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAuthError('')
    try {
      const response = await apiFetch(`/api/auth/${authMode === 'register' ? 'register' : 'login'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: authEmail, password: authPassword }),
      })
      const result = await response.json()
      if (!response.ok) {
        setAuthError(typeof result.detail === 'string' ? result.detail : 'Check the email and password requirements.')
        return
      }
      setAuthPassword('')
      setUser(result as User)
    } catch {
      setAuthError('The API could not be reached.')
    }
  }

  async function signOut() {
    await apiFetch('/api/auth/logout', { method: 'POST' })
    setUser(null)
    setJournal([])
    setAlerts([])
    setNotifications([])
    setDashboard(null)
  }

  async function createPriceAlert(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const response = await apiFetch('/api/alerts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ direction: alertDirection, target_price: Number(alertPrice) }),
    })
    if (!response.ok) {
      setNotice('Could not create the price alert.')
      return
    }
    const alert = await response.json() as PriceAlert
    setAlerts(current => [alert, ...current])
    setAlertPrice('')
  }

  async function deletePriceAlert(alert: PriceAlert) {
    const response = await apiFetch(`/api/alerts/${alert.id}`, { method: 'DELETE' })
    if (response.ok) setAlerts(current => current.filter(item => item.id !== alert.id))
  }

  async function markNotificationRead(notification: Notification) {
    const response = await apiFetch(`/api/notifications/${notification.id}/read`, { method: 'PATCH' })
    if (response.ok) {
      setNotifications(current => current.map(item => item.id === notification.id ? { ...item, read: true } : item))
      setDashboard(current => current ? { ...current, unread_notifications: Math.max(0, current.unread_notifications - 1) } : current)
    }
  }

  if (!authReady) return <div className="auth-loading">Loading Aurum Intelligence…</div>

  if (!user) {
    return (
      <main className="auth-shell">
        <form className="auth-card" onSubmit={event => void authenticate(event)}>
          <div className="brand-mark"><Gem size={18} /></div>
          <div className="panel-kicker">AURUM INTELLIGENCE</div>
          <h1>{authMode === 'register' ? 'Create your account' : 'Welcome back'}</h1>
          <p>Sign in to access your private trading journal and alerts.</p>
          <label>Email address<input type="email" autoComplete="email" value={authEmail} onChange={event => setAuthEmail(event.target.value)} required /></label>
          <label>Password<input type="password" autoComplete={authMode === 'register' ? 'new-password' : 'current-password'} minLength={12} maxLength={128} value={authPassword} onChange={event => setAuthPassword(event.target.value)} required /><small>Use at least 12 characters.</small></label>
          {authError && <div className="auth-error" role="alert">{authError}</div>}
          <button className="calculate-button" type="submit">{authMode === 'register' ? 'CREATE ACCOUNT' : 'SIGN IN'}</button>
          <button className="auth-switch" type="button" onClick={() => { setAuthMode(authMode === 'register' ? 'login' : 'register'); setAuthError('') }}>
            {authMode === 'register' ? 'Already have an account? Sign in' : 'New to Aurum? Create an account'}
          </button>
        </form>
      </main>
    )
  }

  return (
    <div className="terminal-shell">
      <aside className="rail">
        <div className="brand-mark"><Gem size={18} strokeWidth={2.2} /></div>
        <div className="rail-divider" />
        <button className="rail-button active" title="Overview"><LayoutDashboard size={18} /></button>
        <button className="rail-button" title="Markets"><BarChart3 size={18} /></button>
        <button className="rail-button" title="Research"><Newspaper size={18} /></button>
        <button className="rail-button" title="Journal"><BookOpen size={18} /></button>
        <div className="rail-bottom"><button className="rail-button" title="Alerts"><Bell size={18} /></button><div className="avatar">AO</div></div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <div className="wordmark">AURUM<span>.</span><span className="wordmark-sub">INTELLIGENCE</span></div>
          <nav className="top-nav"><span className="nav-current">Overview</span><span>Markets</span><span>Research</span><span>Journal</span></nav>
          <div className="top-actions"><span className={`connection ${live ? 'connected' : ''}`}><i />{live ? 'FEED CONNECTED' : 'PREVIEW MODE'}</span><button className="icon-button" title="View alerts" onClick={() => document.getElementById('alerts')?.scrollIntoView({ behavior: 'smooth' })}><Bell size={15} />{dashboard?.unread_notifications ? <span className="notification-count">{dashboard.unread_notifications}</span> : null}</button><button className="icon-button" title="Refresh feeds" onClick={() => void refresh()}><RefreshCw size={15} className={loading ? 'spin' : ''} /></button><span className="account-email">{user.email}</span><button className="icon-button" title="Sign out" onClick={() => void signOut()}><X size={15} /></button><div className="top-date">{new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: '2-digit' })}</div></div>
        </header>

        <div className="page-content">
          <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> PRECIOUS METALS / SPOT MARKET</div><h1>Gold intelligence</h1><p>Macro context. Market structure. One clear view.</p></div><div className="heading-right"><span className="market-open"><i /> MARKET OPEN</span><button className="icon-button mobile-menu" title="Open menu"><Menu size={17} /></button></div></div>

          <section className="quote-strip" aria-label="Gold market quote">
            <div className="instrument"><div className="instrument-icon"><Gem size={17} /></div><div><span className="instrument-name">GOLD SPOT</span><span className="instrument-symbol">XAU / USD <ChevronDown size={12} /></span></div></div>
            <div className="quote-price"><span className="label">LAST PRICE <span className="live-dot" /></span><strong>{loading && !price ? 'Loading…' : formatPrice(price)}</strong><small>USD / TROY OZ</small></div>
            <div className="quote-stat"><span className="label">DAILY CHANGE</span><strong className={((quote?.change_percent ?? 0) >= 0 ? 'positive' : 'negative')}>{(quote?.change_percent ?? 0) >= 0 ? '+' : ''}{(quote?.change_percent ?? 0).toFixed(2)}%</strong><small>{quote?.updated_at ? new Date(quote.updated_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) + ' UTC' : 'Awaiting data'}</small></div>
            <div className="quote-stat"><span className="label">DAY RANGE</span><strong>{quote?.daily_high && quote?.daily_low ? `${formatPrice(quote.daily_low)} — ${formatPrice(quote.daily_high)}` : (candles.length ? `${formatPrice(Math.min(...candles.slice(-1).map(c => c.close)) - 16)} — ${formatPrice(Math.max(...candles.slice(-1).map(c => c.close)) + 18)}` : '—')}</strong><small>{quote?.daily_high && quote?.daily_low ? 'Intraday session' : 'Indicative range'}</small></div>
            <div className="quote-stat quote-source"><span className="label">DATA SOURCE</span><strong>{quote?.source ?? 'Connecting'}</strong><small>{quote?.updated_at ?? 'Refreshes every 60 sec'}</small></div>
          </section>
          <div className="market-overview-grid" aria-label="Gold market snapshot">
            <div className="metric-card"><span>Daily high</span><strong>{formatPrice(quote?.daily_high)}</strong></div>
            <div className="metric-card"><span>Daily low</span><strong>{formatPrice(quote?.daily_low)}</strong></div>
            <div className="metric-card"><span>Open</span><strong>{formatPrice(quote?.open)}</strong></div>
            <div className="metric-card"><span>Previous close</span><strong>{formatPrice(quote?.previous_close)}</strong></div>
          </div>

          <section className="panel technical-panel" aria-label="Technical analysis panel">
            <div className="panel-header"><div><div className="panel-kicker">TECHNICAL ANALYSIS <span className="dot-separator">·</span> XAU/USD</div><h2>Market structure</h2></div><div className="signal-icon"><Gauge size={17} /></div></div>
            <div className="technical-summary-grid">
              <div className="tech-score-card">
                <span>Overall Technical Score</span>
                <strong>{technical?.summary.overall_score ?? 0}</strong>
                <small>{technical?.summary.overall_bias ?? 'neutral'}</small>
              </div>
              <div className="tech-stat-card"><span>Trend Strength</span><strong>{technical?.summary.trend_strength ?? 'neutral'}</strong></div>
              <div className="tech-stat-card"><span>Volatility</span><strong>{technical?.summary.volatility ?? 'low'}</strong></div>
              <div className="tech-stat-card"><span>Momentum</span><strong>{technical?.summary.momentum ?? 'neutral'}</strong></div>
              <div className="tech-stat-card"><span>Quality</span><strong>{technical?.summary.quality ?? 'limited'}</strong></div>
            </div>
            <div className="technical-grid">
              {(technical?.indicators ?? []).map(indicator => (
                <div key={indicator.name} className={`tech-card ${indicator.status}`}>
                  <div className="tech-card-head">
                    <span>{indicator.name}</span>
                    <strong>{indicator.value == null ? '—' : indicator.unit === 'USD' ? `$${indicator.value.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : `${indicator.value.toFixed(2)}${indicator.unit ?? '%'}`}</strong>
                  </div>
                  <p>{indicator.interpretation}</p>
                </div>
              ))}
              {!technical && <div className="tech-card neutral"><div className="tech-card-head"><span>Technical analysis</span><strong>Loading</strong></div><p>Awaiting market data for the technical engine.</p></div>}
            </div>
          </section>

          {!live && <div className="demo-ribbon"><ShieldAlert size={13} /> SIMULATED PREVIEW DATA · Configure an Alpha Vantage key and set <code>VITE_DEMO_MODE=false</code> for live-only display.</div>}
          <div className="provider-status-bar" aria-live="polite">
            {Object.entries(providerStatus).length ? Object.entries(providerStatus).map(([name, info]) => (
              <div key={name} className={`provider-pill ${info.status}`}>
                <span className="provider-dot" />
                <span>{name}</span>
                <strong>{info.status === 'available' ? 'Online' : 'Unavailable'}</strong>
              </div>
            )) : <div className="provider-pill neutral"><span className="provider-dot" /><span>Provider status</span><strong>Checking…</strong></div>}
          </div>
          {providerWarnings.map(warning => <div className="provider-warning" key={warning} role="status" aria-live="polite"><ShieldAlert size={13} /> PROVIDER WARNING · {warning}</div>)}
          <section className="dashboard-summary" aria-label="Account summary">
            <div><span>TRADES</span><strong>{dashboard?.trade_count ?? 0}</strong></div>
            <div><span>OPEN POSITIONS</span><strong>{dashboard?.open_positions ?? 0}</strong></div>
            <div><span>REALIZED P&amp;L</span><strong className={(dashboard?.closed_pnl ?? 0) >= 0 ? 'positive' : 'negative'}>{dashboard ? `${dashboard.closed_pnl >= 0 ? '+' : ''}$${dashboard.closed_pnl.toFixed(2)}` : '—'}</strong></div>
            <div><span>WIN RATE</span><strong>{dashboard?.win_rate == null ? '—' : `${dashboard.win_rate.toFixed(1)}%`}</strong></div>
            <div><span>NEWS SENTIMENT</span><strong className={sentimentScore > 0.1 ? 'positive' : sentimentScore < -0.1 ? 'negative' : ''}>{news.length ? `${sentimentScore > 0 ? '+' : ''}${sentimentScore.toFixed(2)}` : '—'}</strong></div>
          </section>

          <div className="dashboard-grid">
            <section className="panel chart-panel">
              <div className="panel-header"><div><div className="panel-kicker">PRICE ACTION <span className="dot-separator">·</span> XAU/USD</div><div className="chart-headline">Gold spot <span className={chartChange >= 0 ? 'positive' : 'negative'}>{chartChange >= 0 ? '+' : ''}{chartChange.toFixed(2)}%</span></div></div><div className="range-switch">{['1W', '1M', '3M', '1Y'].map(item => <button key={item} className={range === item ? 'selected' : ''} onClick={() => setRange(item)}>{item}</button>)}</div></div>
              <div className="chart-meta"><span><i className="legend-gold" /> XAU / USD</span><span><i className="legend-line" /> 20D SMA <b>{formatPrice(average)}</b></span><span className="chart-delay">{live ? 'DAILY · DELAYED' : 'ILLUSTRATIVE SERIES'}</span></div>
              <div className="chart-area">
                {chartData.length ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={chartData} margin={{ top: 10, right: 4, bottom: 0, left: 0 }}>
                  <defs><linearGradient id="goldFade" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#c9a659" stopOpacity={0.28} /><stop offset="95%" stopColor="#c9a659" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid stroke="#272a24" vertical={false} strokeDasharray="2 5" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: '#73766d', fontSize: 10, fontFamily: 'DM Mono' }} tickFormatter={value => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} minTickGap={42} />
                  <YAxis orientation="right" axisLine={false} tickLine={false} width={53} domain={['dataMin - 35', 'dataMax + 35']} tick={{ fill: '#73766d', fontSize: 10, fontFamily: 'DM Mono' }} tickFormatter={value => value.toLocaleString('en-US', { maximumFractionDigits: 0 })} />
                  <Tooltip contentStyle={{ background: '#171915', border: '1px solid #34372e', borderRadius: 3, fontFamily: 'DM Mono', fontSize: 11 }} labelStyle={{ color: '#9a9d90' }} formatter={(value: number) => [`$${formatPrice(value)}`, 'XAU/USD']} labelFormatter={value => new Date(value).toLocaleDateString()} />
                  <ReferenceLine y={average} stroke="#83877a" strokeDasharray="4 5" />
                  <Area type="monotone" dataKey="close" stroke="#d0ae68" strokeWidth={2} fill="url(#goldFade)" activeDot={{ r: 4, fill: '#d0ae68', stroke: '#10120f', strokeWidth: 2 }} />
                </AreaChart></ResponsiveContainer> : <div className="empty-chart"><Activity size={22} /><span>No live market history</span><small>Configure Alpha Vantage to load the XAU/USD series.</small></div>}
              </div>
              <div className="chart-footer"><span><Clock3 size={12} /> UTC · DAILY CLOSE</span><span>Source: {live ? 'Alpha Vantage' : 'Simulated preview'} <ArrowRight size={11} /></span></div>
            </section>

            <section className="panel signal-panel">
              <div className="panel-header"><div><div className="panel-kicker">QUANT DESK <span className="dot-separator">·</span> 01</div><h2>Signal monitor</h2></div><div className="signal-icon"><Crosshair size={17} /></div></div>
              <div className={`signal-banner ${signal?.signal === 'BUY' ? 'bullish' : signal?.signal === 'SELL' ? 'bearish' : signal?.signal === 'HOLD' ? 'neutral' : ''}`}><div className="signal-orb"><Activity size={17} /></div><div><span className="label">TREND + MOMENTUM</span><strong>{signal?.signal ?? 'WAIT'}</strong></div><span className="signal-conf">{signal?.confidence ?? 0}%<small>CONF.</small></span></div>
              <div className="confidence-line"><span style={{ width: `${signal?.confidence ?? 0}%` }} /></div>
              <div className="signal-metrics">
                <div className="signal-metric"><span>Entry</span><b>{signal?.entry ? `$${signal.entry.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b></div>
                <div className="signal-metric"><span>Stop</span><b>{signal?.stop_loss ? `$${signal.stop_loss.toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b></div>
                <div className="signal-metric"><span>TP1</span><b>{signal?.take_profit && signal.take_profit[0] ? `$${signal.take_profit[0].toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b></div>
                <div className="signal-metric"><span>TP2</span><b>{signal?.take_profit && signal.take_profit[1] ? `$${signal.take_profit[1].toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b></div>
                <div className="signal-metric"><span>TP3</span><b>{signal?.take_profit && signal.take_profit[2] ? `$${signal.take_profit[2].toLocaleString('en-US', { maximumFractionDigits: 2 })}` : '—'}</b></div>
                <div className="signal-metric"><span>R:R</span><b>{signal?.risk_reward ?? '1:0'}</b></div>
                <div className="signal-metric"><span>Quality</span><b>{signal?.quality ?? 'Low'}</b></div>
                <div className="signal-metric"><span>Time</span><b>{signal?.timestamp ? new Date(signal.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) : '—'}</b></div>
              </div>
              <div className="signal-rows"><div><span>Price vs 20D SMA</span><b className={lastPrice > average ? 'positive' : 'negative'}>{lastPrice > average ? 'ABOVE' : 'BELOW'}</b></div><div><span>Daily momentum</span><b className={chartChange >= 0 ? 'positive' : 'negative'}>{chartChange >= 0 ? <ArrowUpRight size={12} /> : <ArrowDownRight size={12} />}{chartChange >= 0 ? '+' : ''}{chartChange.toFixed(2)}%</b></div><div><span>Signal horizon</span><b>SWING · 1D</b></div></div>
              <button className="signal-toggle" type="button" onClick={() => setSignalExpanded(value => !value)}>
                {signalExpanded ? 'Hide rationale' : 'Why this signal?'}
              </button>
              {signalExpanded && (
                <div className="signal-reasons">
                  <div className="signal-disclaimer"><Sparkles size={12} /><span>{signal?.note ?? 'Signals are analytical estimates generated from market data and technical indicators. They are not financial advice and do not guarantee future market performance.'}</span></div>
                  {(signal?.reasons ?? []).length ? (
                    <ul>
                      {signal?.reasons?.map(reason => (
                        <li key={`${reason.indicator}-${reason.interpretation}`}>
                          <strong>{reason.indicator}</strong>: {reason.value != null ? `${reason.value.toFixed(2)}` : '—'} — {reason.interpretation}
                        </li>
                      ))}
                    </ul>
                  ) : <p className="signal-empty">No signal rationale available.</p>}
                </div>
              )}
              <div className="alerts-widget" id="alerts">
                <div className="alerts-heading"><strong><Bell size={13} /> PRICE ALERTS</strong><span>{dashboard?.active_alerts ?? alerts.filter(item => item.active).length} ACTIVE</span></div>
                <form className="alert-form" onSubmit={event => void createPriceAlert(event)}>
                  <select aria-label="Alert direction" value={alertDirection} onChange={event => setAlertDirection(event.target.value as 'above' | 'below')}><option value="above">Above</option><option value="below">Below</option></select>
                  <input aria-label="Gold alert price" type="number" min="0.01" step="any" placeholder="Target USD" value={alertPrice} onChange={event => setAlertPrice(event.target.value)} required />
                  <button type="submit" title="Create gold price alert"><Plus size={13} /></button>
                </form>
                <div className="alert-items">{alerts.filter(item => item.active).slice(0, 3).map(item => <div key={item.id}><span>Gold {item.direction} ${formatPrice(item.target_price)}</span><button aria-label="Delete price alert" onClick={() => void deletePriceAlert(item)}><X size={12} /></button></div>)}</div>
                {notifications.slice(0, 2).map(item => <button className={`notification-item ${item.read ? '' : 'unread'}`} key={item.id} onClick={() => void markNotificationRead(item)}>{item.message}{!item.read && <small>MARK READ</small>}</button>)}
              </div>
            </section>

            <section className="panel heat-panel">
              <div className="panel-header"><div><div className="panel-kicker">MACRO LENS <span className="dot-separator">·</span> GOLD DRIVERS</div><h2>Driver heat map</h2></div><button className="text-button" title="Market driver estimates"><Globe2 size={14} /></button></div>
              <div className="heat-subhead"><span>FACTOR</span><span>GOLD BIAS</span><span>READING</span></div>
              <div className="heat-list">{heatDrivers.map(item => <div className="heat-row" key={item.name}><div className="heat-name"><strong>{item.name}</strong><small>{item.ticker}</small></div><div className={`heat-cell ${item.score > 0.4 ? 'heat-bull' : item.score > 0.05 ? 'heat-soft-bull' : item.score < -0.05 ? 'heat-bear' : ''}`}><span>{item.score > 0 ? '▲' : item.score < 0 ? '▼' : '·'} {Math.abs(item.score * 100).toFixed(0)}</span></div><span className="heat-reading" title={item.source}>{item.reading}</span></div>)}</div>
              {!heatDrivers.length && <div className="calendar-empty"><Globe2 size={18} /><span>No sourced factors yet</span><small>Refresh when provider data is available.</small></div>}
              <div className="heat-legend"><span><i className="legend-bear" /> HEADWIND</span><span><i className="legend-neutral" /> MIXED</span><span><i className="legend-bull" /> TAILWIND</span><small>Price, news and calendar data</small></div>
            </section>

            <section className="panel news-panel">
              <div className="panel-header"><div><div className="panel-kicker">SIGNAL SCAN <span className="dot-separator">·</span> LAST 72H</div><h2>News &amp; impact</h2></div><span className="live-tag"><i /> {live ? 'LIVE FEED' : 'PREVIEW'}</span></div>
              {analysis && <div className="analysis-note"><button className="close-analysis" onClick={() => setAnalysis(null)} aria-label="Close analysis"><X size={13} /></button><div className="analysis-title"><BrainCircuit size={14} /> IMPACT ASSESSMENT <span className={`bias-pill ${analysis.bias.toLowerCase()}`}>{analysis.bias}</span><span className="impact-pill">{analysis.impact} impact</span></div><p>{analysis.rationale}</p></div>}
              <div className="news-list">{news.slice(0, 4).map((item, index) => <article className="news-item" key={`${item.title}-${index}`}><div className="news-timeline"><span className={index === 0 ? 'timeline-now' : ''} />{index < Math.min(news.length, 4) - 1 && <i />}</div><div className="news-copy"><div className="news-source">{item.source || 'Market news'} <span>·</span> {item.published_at ? new Date(item.published_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) + ' UTC' : 'RECENT'}</div><a href={item.url} target="_blank" rel="noreferrer" className="news-title">{item.title} {item.url !== '#' && <ExternalLink size={11} />}</a><div className="news-tags"><span className={`bias-pill ${(item.bias ?? 'watch').toLowerCase()}`}>{item.bias ?? 'Monitor'}</span><span className={`impact-text ${(item.impact ?? 'low').toLowerCase()}`}>{item.impact ?? 'Review'}</span><button className="analyze-button" onClick={() => void analyze(item)} disabled={analyzing === item.title}>{analyzing === item.title ? <LoaderCircle size={11} className="spin" /> : <BrainCircuit size={11} />} ANALYZE</button></div></div></article>)}</div>
              <div className="panel-link"><span>Headlines provide context, not trade instructions.</span><button onClick={() => void refresh()}>REFRESH <RefreshCw size={11} /></button></div>
            </section>

            <section className="panel calendar-panel">
              <div className="panel-header"><div><div className="panel-kicker">MACRO DESK <span className="dot-separator">·</span> USD WATCH</div><h2>Economic calendar</h2></div><CalendarDays size={16} className="muted-icon" /></div>
              {events.length ? <div className="event-list">{events.slice(0, 4).map((event, index) => <div className="event-row" key={`${event.title}-${index}`}><div className="event-time">{event.date ? new Date(event.date).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false }) : '--:--'}<small>{event.date ? new Date(event.date).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }) : 'TBA'}</small></div><i className={`impact-mark ${event.impact.toLowerCase()}`} /><div className="event-name"><strong>{event.title}</strong><small>USD · {event.impact.toUpperCase()} IMPACT</small></div><div className="event-consensus"><span>{event.forecast ?? '—'}</span><small>FCST</small></div></div>)}</div> : <div className="calendar-empty"><CalendarDays size={18} /><span>Calendar feed unavailable</span><small>Connect the API for this week’s USD releases.</small></div>}
              <div className="calendar-foot"><span><i className="impact-mark high" /> HIGH</span><span><i className="impact-mark medium" /> MEDIUM</span><span className="calendar-source">Forex Factory · weekly</span></div>
            </section>

            <section className="panel risk-panel">
              <div className="panel-header"><div><div className="panel-kicker">POSITION PLANNING <span className="dot-separator">·</span> XAU/USD</div><h2>Risk calculator</h2></div><Gauge size={17} className="muted-icon" /></div>
              <form className="risk-form" onSubmit={calculateRisk}>
                <label>ACCOUNT SIZE <div className="input-wrap"><span>$</span><input type="number" min="1" step="any" value={risk.account_balance} onChange={event => setRisk({ ...risk, account_balance: event.target.value })} required /></div></label>
                <label>RISK / TRADE <div className="input-wrap"><input type="number" min="0.01" max="100" step="0.1" value={risk.risk_percent} onChange={event => setRisk({ ...risk, risk_percent: event.target.value })} required /><span>%</span></div></label>
                <label>ENTRY PRICE <div className="input-wrap"><span>$</span><input type="number" min="0.01" step="any" value={risk.entry_price} onChange={event => setRisk({ ...risk, entry_price: event.target.value })} required /></div></label>
                <label>STOP PRICE <div className="input-wrap"><span>$</span><input type="number" min="0.01" step="any" value={risk.stop_price} onChange={event => setRisk({ ...risk, stop_price: event.target.value })} required /></div></label>
                <button className="calculate-button" type="submit"><CircleDollarSign size={14} /> CALCULATE POSITION</button>
              </form>
              {riskResult && <div className="risk-result"><div><span>MAX LOSS</span><strong>${riskResult.risk_amount.toLocaleString()}</strong></div><div><span>POSITION SIZE</span><strong>{riskResult.position_ounces.toFixed(2)} <small>oz</small></strong></div><div><span>STANDARD LOTS</span><strong>{riskResult.standard_lots.toFixed(3)}</strong></div></div>}
              <div className="risk-note"><ShieldAlert size={12} /> Sizing estimate only. Verify contract specs with your broker.</div>
            </section>

            <section className="panel journal-panel">
              <div className="panel-header"><div><div className="panel-kicker">TRADE LOG <span className="dot-separator">·</span> PERSONAL</div><h2>Trading journal <span className="journal-count">{journal.length}</span></h2></div><button className="add-trade" onClick={() => setShowJournalForm(true)}><Plus size={14} /> LOG TRADE</button></div>
              {journal.length ? <><div className="journal-table-wrap"><table className="journal-table"><thead><tr><th>POSITION</th><th>ENTRY / EXIT</th><th>SIZE</th><th>REALIZED P&amp;L</th><th></th></tr></thead><tbody>{journal.slice(0, 5).map(entry => <tr key={entry.id}><td><span className={`side-pill ${entry.side.toLowerCase()}`}>{entry.side}</span><small>{new Date(entry.created_at).toLocaleDateString()}</small></td><td className="mono-cell">${formatPrice(entry.entry_price)}<small>{entry.exit_price ? `$${formatPrice(entry.exit_price)}` : 'OPEN'}</small></td><td className="mono-cell">{entry.quantity_ounces}<small>troy oz</small></td><td className={`mono-cell ${entry.pnl == null ? '' : entry.pnl >= 0 ? 'positive' : 'negative'}`}>{entry.pnl == null ? 'OPEN' : `${entry.pnl >= 0 ? '+' : ''}$${entry.pnl.toFixed(2)}`}</td><td><button className="delete-button" title="Delete trade" onClick={() => void deleteEntry(entry)}><Trash2 size={13} /></button></td></tr>)}</tbody></table></div><div className="journal-summary"><span>{journal.length} recorded {journal.length === 1 ? 'trade' : 'trades'}</span><span>NET REALIZED <strong className={totalPnl >= 0 ? 'positive' : 'negative'}>{totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}</strong></span></div></> : <div className="journal-empty"><BookOpen size={19} /><span>Keep your execution accountable.</span><small>Your first logged trade will appear here.</small><button onClick={() => setShowJournalForm(true)}><Plus size={13} /> ADD FIRST TRADE</button></div>}
            </section>
          </div>

          <footer className="footer"><span>AURUM INTELLIGENCE <span className="dot-separator">·</span> MARKET INFORMATION TERMINAL</span><span><i /> DATA STATUS: {live ? 'ALPHA VANTAGE CONNECTED' : DEMO ? 'SIMULATED PREVIEW' : 'NO LIVE FEED'} <span className="dot-separator">·</span> NOT INVESTMENT ADVICE</span></footer>
        </div>
      </main>

      {showJournalForm && <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) setShowJournalForm(false) }}><form className="modal" onSubmit={addJournal}><div className="modal-head"><div><div className="panel-kicker">PERSONAL TRADE LOG</div><h2>Record a position</h2></div><button type="button" className="icon-button" aria-label="Close" onClick={() => setShowJournalForm(false)}><X size={16} /></button></div><div className="side-selector"><button type="button" className={journalForm.side === 'BUY' ? 'chosen buy' : ''} onClick={() => setJournalForm({ ...journalForm, side: 'BUY' })}><ArrowUpRight size={15} /> BUY / LONG</button><button type="button" className={journalForm.side === 'SELL' ? 'chosen sell' : ''} onClick={() => setJournalForm({ ...journalForm, side: 'SELL' })}><ArrowDownRight size={15} /> SELL / SHORT</button></div><div className="modal-fields"><label>ENTRY PRICE (USD)<input type="number" min="0.01" step="any" value={journalForm.entry_price} onChange={event => setJournalForm({ ...journalForm, entry_price: event.target.value })} required /></label><label>EXIT PRICE (OPTIONAL)<input type="number" min="0.01" step="any" value={journalForm.exit_price} onChange={event => setJournalForm({ ...journalForm, exit_price: event.target.value })} /></label><label>POSITION SIZE (TROY OZ)<input type="number" min="0.001" step="any" value={journalForm.quantity_ounces} onChange={event => setJournalForm({ ...journalForm, quantity_ounces: event.target.value })} required /></label><label>TRADE THESIS<textarea maxLength={1000} rows={3} placeholder="What informed this position?" value={journalForm.thesis} onChange={event => setJournalForm({ ...journalForm, thesis: event.target.value })} /></label></div>{journalError && <p className="form-error">{journalError}</p>}<div className="modal-actions"><button type="button" className="cancel-button" onClick={() => setShowJournalForm(false)}>CANCEL</button><button className="submit-button" type="submit"><Check size={14} /> SAVE TO JOURNAL</button></div></form></div>}
      {notice && <div className="toast"><Check size={14} /> {notice}</div>}
    </div>
  )
}

export default App