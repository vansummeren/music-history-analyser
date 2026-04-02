import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import Sidebar from './Sidebar'
import type { UserProfile } from '../services/authApi'

vi.mock('../hooks/useAuth', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '../hooks/useAuth'

function mockAuthUser(role: UserProfile['role']) {
  vi.mocked(useAuth).mockReturnValue({
    user: { role } as UserProfile,
    loading: false,
    error: null,
    logout: vi.fn(),
  })
}

function renderSidebar(open = true) {
  return render(
    <MemoryRouter>
      <Sidebar open={open} onClose={() => {}} />
    </MemoryRouter>,
  )
}

describe('Sidebar', () => {
  beforeEach(() => mockAuthUser('user'))

  it('renders the app brand name', () => {
    renderSidebar()
    expect(screen.getByText(/Amadeus/i)).toBeInTheDocument()
  })

  it('renders standard navigation links for a regular user', () => {
    renderSidebar()
    expect(screen.getByRole('link', { name: /Dashboard/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Spotify Accounts/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /AI Configs/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Analyses/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Schedules/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Diagnostics/i })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /^Admin$/i })).not.toBeInTheDocument()
  })

  it('renders the Admin link for an admin user', () => {
    mockAuthUser('admin')
    renderSidebar()
    expect(screen.getByRole('link', { name: /Diagnostics/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /^Admin$/i })).toBeInTheDocument()
  })

  it('renders the close button', () => {
    renderSidebar()
    expect(screen.getByRole('button', { name: /Close menu/i })).toBeInTheDocument()
  })

  it('Diagnostics link points to /admin for a regular user', () => {
    renderSidebar()
    expect(screen.getByRole('link', { name: /Dashboard/i })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: /Spotify/i })).toHaveAttribute('href', '/spotify')
    expect(screen.getByRole('link', { name: /AI Configs/i })).toHaveAttribute('href', '/ai-configs')
    expect(screen.getByRole('link', { name: /Analyses/i })).toHaveAttribute('href', '/analyses')
    expect(screen.getByRole('link', { name: /Schedules/i })).toHaveAttribute('href', '/schedules')
    expect(screen.getByRole('link', { name: /Diagnostics/i })).toHaveAttribute('href', '/admin')
  })

  it('Admin link points to /admin-panel for an admin user', () => {
    mockAuthUser('admin')
    renderSidebar()
    expect(screen.getByRole('link', { name: /^Admin$/i })).toHaveAttribute('href', '/admin-panel')
  })
})
