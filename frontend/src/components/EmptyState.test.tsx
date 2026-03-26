import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { Music } from 'lucide-react'
import EmptyState from './EmptyState'

describe('EmptyState', () => {
  it('renders title', () => {
    render(<EmptyState title="Nothing here yet" />)
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(
      <EmptyState
        title="No items"
        description="Add some items to get started."
      />,
    )
    expect(screen.getByText('Add some items to get started.')).toBeInTheDocument()
  })

  it('renders icon when provided', () => {
    render(
      <EmptyState
        title="No music"
        icon={<Music data-testid="music-icon" />}
      />,
    )
    expect(screen.getByTestId('music-icon')).toBeInTheDocument()
  })

  it('renders action when provided', () => {
    render(
      <EmptyState
        title="No items"
        action={<button>Add item</button>}
      />,
    )
    expect(screen.getByRole('button', { name: 'Add item' })).toBeInTheDocument()
  })

  it('does not render description or action when absent', () => {
    render(<EmptyState title="Empty" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })
})
