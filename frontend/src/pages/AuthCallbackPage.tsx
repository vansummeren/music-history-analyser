import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

/**
 * Handles the post-login redirect from the backend.
 *
 * The backend appends tokens to the URL fragment so they never appear in
 * server logs:  /auth/callback#access_token=...&refresh_token=...
 */
export default function AuthCallbackPage() {
  const navigate = useNavigate()

  useEffect(() => {
    const hash = window.location.hash.substring(1)
    const params = new URLSearchParams(hash)

    const accessToken = params.get('access_token')
    const refreshToken = params.get('refresh_token')

    if (accessToken) {
      localStorage.setItem('access_token', accessToken)
    }
    if (refreshToken) {
      localStorage.setItem('refresh_token', refreshToken)
    }

    navigate('/', { replace: true })
  }, [navigate])

  return (
    <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-900 to-brand-700 text-white">
      <p className="text-brand-200">Completing sign-in…</p>
    </main>
  )
}
