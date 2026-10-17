import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

function makeJsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('App', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => makeJsonResponse({ detail: 'Unauthorized' }, 401)),
    )
  })

  it('renders the authentication shell without crashing', async () => {
    render(<App />)

    await waitFor(() => {
      expect(screen.getByText('Welcome back')).toBeInTheDocument()
    })

    expect(screen.getByRole('button', { name: 'SIGN IN' })).toBeInTheDocument()
  })
})
