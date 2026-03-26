import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ToastProvider } from '../hooks/useToast'
import AppShell from './AppShell'

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      id: '1',
      sub: 'google|123',
      provider: 'google',
      email: 'test@example.com',
      display_name: 'Test User',
      role: 'user',
      created_at: '2024-01-01T00:00:00Z',
    },
    loading: false,
    error: null,
    logout: vi.fn(),
  }),
}))

function renderAppShell(children = <div>Page content</div>) {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <AppShell>{children}</AppShell>
      </ToastProvider>
    </MemoryRouter>,
  )
}

describe('AppShell', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders sidebar navigation', () => {
    renderAppShell()
    expect(screen.getByRole('navigation', { name: /Sidebar/i })).toBeInTheDocument()
  })

  it('renders the header with user info', () => {
    renderAppShell()
    expect(screen.getByText('Test User')).toBeInTheDocument()
  })

  it('renders children in the main content area', () => {
    renderAppShell(<div>Hello world</div>)
    expect(screen.getByText('Hello world')).toBeInTheDocument()
  })

  it('renders logout button', () => {
    renderAppShell()
    expect(screen.getByRole('button', { name: /Log out/i })).toBeInTheDocument()
  })

  it('renders dark mode toggle button', () => {
    renderAppShell()
    expect(
      screen.getByRole('button', { name: /Switch to light mode|Switch to dark mode/i }),
    ).toBeInTheDocument()
  })
})
