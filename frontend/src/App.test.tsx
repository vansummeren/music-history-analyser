import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect } from 'vitest'
import App from './App'

describe('App', () => {
  it('renders the login page heading when unauthenticated', () => {
    // With no access_token in localStorage the ProtectedRoute redirects to
    // /login, which renders LoginPage — this test confirms that flow.
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <App />
      </MemoryRouter>,
    )
    expect(screen.getByText('Amadeus')).toBeInTheDocument()
  })
})
