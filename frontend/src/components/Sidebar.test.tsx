import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import Sidebar from './Sidebar'

vi.mock('../hooks/useAuth', () => ({
  useAuth: () => ({ user: null, loading: false, error: null, logout: vi.fn() }),
}))

function renderSidebar(open = true) {
  return render(
    <MemoryRouter>
      <Sidebar open={open} onClose={() => {}} />
    </MemoryRouter>,
  )
}

describe('Sidebar', () => {
  it('renders the app brand name', () => {
    renderSidebar()
    expect(screen.getByText(/Amadeus/i)).toBeInTheDocument()
  })

  it('renders all navigation links', () => {
    renderSidebar()
    expect(screen.getByRole('link', { name: /Dashboard/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Spotify Accounts/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /AI Configs/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Analyses/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Schedules/i })).toBeInTheDocument()
  })

  it('renders the close button', () => {
    renderSidebar()
    expect(screen.getByRole('button', { name: /Close menu/i })).toBeInTheDocument()
  })

  it('nav links point to the correct paths', () => {
    renderSidebar()
    expect(screen.getByRole('link', { name: /Dashboard/i })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: /Spotify/i })).toHaveAttribute('href', '/spotify')
    expect(screen.getByRole('link', { name: /AI Configs/i })).toHaveAttribute('href', '/ai-configs')
    expect(screen.getByRole('link', { name: /Analyses/i })).toHaveAttribute('href', '/analyses')
    expect(screen.getByRole('link', { name: /Schedules/i })).toHaveAttribute('href', '/schedules')
  })

  it('does not show Admin link for non-admin users', () => {
    renderSidebar()
    expect(screen.queryByRole('link', { name: /Admin/i })).not.toBeInTheDocument()
  })
})
