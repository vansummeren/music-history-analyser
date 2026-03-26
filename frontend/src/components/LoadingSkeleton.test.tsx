import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import LoadingSkeleton from './LoadingSkeleton'

describe('LoadingSkeleton', () => {
  it('renders the default number of skeleton lines', () => {
    render(<LoadingSkeleton />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    // default is 3 lines
    const container = screen.getByRole('status')
    expect(container.children).toHaveLength(3)
  })

  it('renders the specified number of lines', () => {
    render(<LoadingSkeleton lines={5} />)
    const container = screen.getByRole('status')
    expect(container.children).toHaveLength(5)
  })

  it('has accessible label', () => {
    render(<LoadingSkeleton />)
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('applies additional className', () => {
    render(<LoadingSkeleton className="mt-4" />)
    const container = screen.getByRole('status')
    expect(container).toHaveClass('mt-4')
  })
})
