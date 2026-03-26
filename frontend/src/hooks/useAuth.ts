import { useCallback, useEffect, useState } from 'react'
import { fetchMe, logout as apiLogout, type UserProfile } from '../services/authApi'

interface AuthState {
  user: UserProfile | null
  loading: boolean
  error: string | null
}

export function useAuth() {
  const [state, setState] = useState<AuthState>({
    user: null,
    loading: true,
    error: null,
  })

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (!token) {
      setState({ user: null, loading: false, error: null })
      return
    }

    fetchMe()
      .then((user) => setState({ user, loading: false, error: null }))
      .catch(() => {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
        setState({ user: null, loading: false, error: null })
      })
  }, [])

  const logout = useCallback(async () => {
    const refreshToken = localStorage.getItem('refresh_token')
    await apiLogout(refreshToken)
    setState({ user: null, loading: false, error: null })
  }, [])

  return { ...state, logout }
}
