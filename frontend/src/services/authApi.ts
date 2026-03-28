import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface UserProfile {
  id: string
  sub: string
  provider: string
  email: string | null
  display_name: string | null
  /** Role assigned by the IdP: "user" or "admin". */
  role: 'user' | 'admin'
  created_at: string
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function fetchMe(): Promise<UserProfile> {
  const resp = await api.get<UserProfile>('/auth/me', {
    headers: authHeaders(),
  })
  return resp.data
}

export async function logout(refreshToken: string | null): Promise<void> {
  await api.post(
    '/auth/logout',
    { refresh_token: refreshToken },
    { headers: authHeaders() },
  )
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

/** URL that starts the configured IdP login flow (OIDC or SAML). */
export function getLoginUrl(): string {
  return '/api/auth/login'
}
