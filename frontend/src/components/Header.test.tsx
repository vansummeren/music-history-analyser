import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import type { UserProfile } from '../services/authApi'
import Header from './Header'

const mockUser: UserProfile = {
  id: '1',
  sub: 'google|123',
  provider: 'google',
  email: 'test@example.com',
  display_name: 'Test User',
  role: 'user',
  created_at: '2024-01-01T00:00:00Z',
}

function renderHeader(overrides?: Partial<React.ComponentProps<typeof Header>>) {
  const defaults = {
    user: mockUser,
    darkMode: true,
    onToggleDark: vi.fn(),
    onMenuToggle: vi.fn(),
    onLogout: vi.fn(),
  }
  const props = { ...defaults, ...overrides }
  return { ...render(<Header {...props} />), props }
}

describe('Header', () => {
  it('renders the user display name', () => {
    renderHeader()
    expect(screen.getByText('Test User')).toBeInTheDocument()
  })

  it('renders user role', () => {
    renderHeader()
    expect(screen.getByText('user')).toBeInTheDocument()
  })

  it('renders the log out button', () => {
    renderHeader()
    expect(screen.getByRole('button', { name: /Log out/i })).toBeInTheDocument()
  })

  it('calls onLogout when logout button is clicked', () => {
    const onLogout = vi.fn()
    renderHeader({ onLogout })
    fireEvent.click(screen.getByRole('button', { name: /Log out/i }))
    expect(onLogout).toHaveBeenCalledOnce()
  })

  it('calls onMenuToggle when hamburger is clicked', () => {
    const onMenuToggle = vi.fn()
    renderHeader({ onMenuToggle })
    fireEvent.click(
      screen.getByRole('button', { name: /Toggle navigation menu/i }),
    )
    expect(onMenuToggle).toHaveBeenCalledOnce()
  })

  it('calls onToggleDark when dark mode button is clicked', () => {
    const onToggleDark = vi.fn()
    renderHeader({ onToggleDark })
    fireEvent.click(
      screen.getByRole('button', { name: /Switch to light mode/i }),
    )
    expect(onToggleDark).toHaveBeenCalledOnce()
  })

  it('shows correct aria-label when in light mode', () => {
    renderHeader({ darkMode: false })
    expect(
      screen.getByRole('button', { name: /Switch to dark mode/i }),
    ).toBeInTheDocument()
  })

  it('falls back to email when display_name is null', () => {
    renderHeader({ user: { ...mockUser, display_name: null } })
    expect(screen.getByText('test@example.com')).toBeInTheDocument()
  })
})

