import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ToastProvider } from '../hooks/useToast'
import LogsPage from './LogsPage'
import * as adminApi from '../services/adminApi'

const mockLogs = {
  total: 3,
  items: [
    { id: '1', created_at: '2026-01-01T00:00:00Z', level: 'INFO', service: 'backend', logger_name: 'app.test', message: 'Hello' },
    { id: '2', created_at: '2026-01-01T00:00:01Z', level: 'ERROR', service: 'worker', logger_name: 'app.test', message: 'Oh no' },
    { id: '3', created_at: '2026-01-01T00:00:02Z', level: 'INFO', service: 'backend', logger_name: 'app.test', message: 'World' },
  ],
}

vi.mock('../services/adminApi', () => ({
  getAdminLogs: vi.fn(),
  getAdminLogServices: vi.fn(),
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <LogsPage />
      </ToastProvider>
    </MemoryRouter>,
  )
}

describe('LogsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(adminApi.getAdminLogs).mockResolvedValue(mockLogs)
    vi.mocked(adminApi.getAdminLogServices).mockResolvedValue(['backend', 'worker'])
  })

  it('renders the Application Logs heading', () => {
    renderPage()
    expect(screen.getByText('Application Logs')).toBeInTheDocument()
  })

  it('shows loading skeleton initially', () => {
    renderPage()
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('shows log rows after loading', async () => {
    renderPage()
    expect(await screen.findByText('Hello')).toBeInTheDocument()
    expect(screen.getByText('Oh no')).toBeInTheDocument()
    expect(screen.getByText('3 records found')).toBeInTheDocument()
  })

  it('calls getAdminLogServices on mount', async () => {
    renderPage()
    await waitFor(() => expect(adminApi.getAdminLogServices).toHaveBeenCalledOnce())
  })

  it('displays service dropdown with available service names', async () => {
    renderPage()
    const trigger = await screen.findByRole('button', { name: /all services/i })
    fireEvent.click(trigger)
    expect(await screen.findByRole('button', { name: /^backend$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^worker$/ })).toBeInTheDocument()
  })

  it('calls getAdminLogs with selected service when a service is chosen', async () => {
    renderPage()

    const trigger = await screen.findByRole('button', { name: /all services/i })
    fireEvent.click(trigger)

    const backendOption = await screen.findByRole('button', { name: /^backend$/ })
    fireEvent.click(backendOption)

    await waitFor(() => {
      const calls = vi.mocked(adminApi.getAdminLogs).mock.calls
      const lastCall = calls[calls.length - 1]
      expect(lastCall[0]).toMatchObject({ service: ['backend'] })
    })
  })

  it('calls getAdminLogs without service filter when selection is cleared', async () => {
    renderPage()

    // Select backend
    const trigger = await screen.findByRole('button', { name: /all services/i })
    fireEvent.click(trigger)
    const backendOption = await screen.findByRole('button', { name: /^backend$/ })
    fireEvent.click(backendOption)

    await waitFor(() => {
      const lastCall = vi.mocked(adminApi.getAdminLogs).mock.lastCall
      expect(lastCall?.[0]).toMatchObject({ service: ['backend'] })
    })

    // Dropdown remains open after toggling — click "All services" item to clear
    // (trigger now shows "backend", so the only "All services" button is inside the dropdown)
    const clearButton = screen.getByRole('button', { name: /all services/i })
    fireEvent.click(clearButton)

    await waitFor(() => {
      const lastCall = vi.mocked(adminApi.getAdminLogs).mock.lastCall
      expect(lastCall?.[0].service).toBeUndefined()
    })
  })
})

