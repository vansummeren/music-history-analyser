import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import StatCard from './StatCard'
import { BarChart2 } from 'lucide-react'

describe('StatCard', () => {
  it('renders title and value', () => {
    render(<StatCard title="Analyses" value={5} />)
    expect(screen.getByText('Analyses')).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(<StatCard title="Schedules" value={3} description="Active schedules" />)
    expect(screen.getByText('Active schedules')).toBeInTheDocument()
  })

  it('renders icon when provided', () => {
    render(
      <StatCard
        title="Analyses"
        value={10}
        icon={<BarChart2 data-testid="icon" />}
      />,
    )
    expect(screen.getByTestId('icon')).toBeInTheDocument()
  })

  it('renders string value', () => {
    render(<StatCard title="Status" value="OK" />)
    expect(screen.getByText('OK')).toBeInTheDocument()
  })
})
