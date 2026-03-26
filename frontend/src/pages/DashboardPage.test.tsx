import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ToastProvider } from '../hooks/useToast'
import DashboardPage from './DashboardPage'

vi.mock('../services/spotifyApi', () => ({
  getSpotifyAccounts: vi.fn().mockResolvedValue([]),
}))

vi.mock('../services/aiApi', () => ({
  getAIConfigs: vi.fn().mockResolvedValue([]),
}))

vi.mock('../services/analysisApi', () => ({
  getAnalyses: vi.fn().mockResolvedValue([]),
}))

vi.mock('../services/scheduleApi', () => ({
  getSchedules: vi.fn().mockResolvedValue([]),
}))

function renderDashboard() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <DashboardPage />
      </ToastProvider>
    </MemoryRouter>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the Dashboard heading', () => {
    renderDashboard()
    expect(screen.getByText('Dashboard')).toBeInTheDocument()
  })

  it('shows a loading skeleton initially', () => {
    renderDashboard()
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('renders stat cards after loading', async () => {
    renderDashboard()
    // Wait for data to load - multiple elements expected (stat card + quick-nav tile)
    expect(await screen.findAllByText('Spotify Accounts')).toHaveLength(2)
    expect(screen.getAllByText('AI Configs')).toHaveLength(2)
    expect(screen.getAllByText('Analyses')).toHaveLength(2)
    expect(screen.getByText('Active Schedules')).toBeInTheDocument()
  })

  it('shows empty state call-to-action when no Spotify accounts', async () => {
    renderDashboard()
    expect(
      await screen.findByText(/Get started — link a Spotify account/i),
    ).toBeInTheDocument()
  })

  it('renders quick-nav tiles', async () => {
    renderDashboard()
    // Wait for data to load then check for quick-nav descriptions
    expect(
      await screen.findByText('Manage linked accounts'),
    ).toBeInTheDocument()
    expect(screen.getByText('Manage AI providers')).toBeInTheDocument()
  })
})
