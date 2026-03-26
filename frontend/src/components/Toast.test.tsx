import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { ToastProvider, useToast, type ToastType } from '../hooks/useToast'
import Toast from './Toast'

// A helper component that exposes showToast via a button click
function ToastTrigger({
  message,
  type,
}: {
  message: string
  type?: ToastType
}) {
  const { showToast } = useToast()
  return (
    <button onClick={() => showToast(message, type)}>Trigger toast</button>
  )
}

function setup(message = 'Test message', type?: ToastType) {
  render(
    <ToastProvider>
      <ToastTrigger message={message} type={type} />
      <Toast />
    </ToastProvider>,
  )
}

describe('Toast', () => {
  it('renders nothing when there are no toasts', () => {
    render(
      <ToastProvider>
        <Toast />
      </ToastProvider>,
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a toast message when triggered', () => {
    setup('Something went wrong', 'error')
    fireEvent.click(screen.getByRole('button', { name: 'Trigger toast' }))
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('dismisses a toast when the dismiss button is clicked', () => {
    setup('Click to dismiss me', 'info')
    fireEvent.click(screen.getByRole('button', { name: 'Trigger toast' }))
    expect(screen.getByText('Click to dismiss me')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByText('Click to dismiss me')).not.toBeInTheDocument()
  })

  it('auto-dismisses after 4 seconds', () => {
    vi.useFakeTimers()
    setup('Auto-dismiss me', 'success')
    fireEvent.click(screen.getByRole('button', { name: 'Trigger toast' }))
    expect(screen.getByText('Auto-dismiss me')).toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(4001)
    })
    expect(screen.queryByText('Auto-dismiss me')).not.toBeInTheDocument()
    vi.useRealTimers()
  })

  it('applies correct styling for each toast type', () => {
    setup('Error message', 'error')
    fireEvent.click(screen.getByRole('button', { name: 'Trigger toast' }))
    expect(screen.getByRole('alert')).toHaveClass('bg-red-600')
  })
})
