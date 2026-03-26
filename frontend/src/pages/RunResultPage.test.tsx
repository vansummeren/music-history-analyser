import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, it, expect, vi } from 'vitest'
import { ToastProvider } from '../hooks/useToast'
import RunResultPage from './RunResultPage'

vi.mock('../services/analysisApi', () => ({
  getRun: vi.fn().mockResolvedValue({
    id: 'run-1',
    analysis_id: 'analysis-1',
    status: 'completed',
    result_text: 'You love indie rock.',
    model: 'claude-3-haiku',
    input_tokens: 100,
    output_tokens: 50,
    error: null,
    started_at: '2024-01-01T10:00:00Z',
    completed_at: '2024-01-01T10:00:05Z',
    created_at: '2024-01-01T09:59:00Z',
  }),
}))

function renderRunResult() {
  return render(
    <MemoryRouter
      initialEntries={['/analyses/analysis-1/runs/run-1']}
    >
      <ToastProvider>
        <Routes>
          <Route
            path="/analyses/:analysisId/runs/:runId"
            element={<RunResultPage />}
          />
        </Routes>
      </ToastProvider>
    </MemoryRouter>,
  )
}

describe('RunResultPage', () => {
  it('renders the Run Result heading', () => {
    renderRunResult()
    expect(screen.getByText('Run Result')).toBeInTheDocument()
  })

  it('shows a loading skeleton initially', () => {
    renderRunResult()
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('renders the run status after loading', async () => {
    renderRunResult()
    // "Completed" appears in status badge and metadata label
    const elements = await screen.findAllByText('Completed')
    expect(elements.length).toBeGreaterThanOrEqual(1)
  })

  it('renders the result text', async () => {
    renderRunResult()
    expect(await screen.findByText('You love indie rock.')).toBeInTheDocument()
  })

  it('renders model name', async () => {
    renderRunResult()
    expect(await screen.findByText('claude-3-haiku')).toBeInTheDocument()
  })

  it('renders token counts', async () => {
    renderRunResult()
    expect(await screen.findByText('100')).toBeInTheDocument()
    expect(await screen.findByText('50')).toBeInTheDocument()
  })

  it('renders a link back to analyses', () => {
    renderRunResult()
    expect(
      screen.getByRole('link', { name: /Back to Analyses/i }),
    ).toBeInTheDocument()
  })
})
