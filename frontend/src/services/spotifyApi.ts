import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface PollScheduleRule {
  days: number[]          // 0=Mon … 6=Sun
  start_hour: number      // inclusive, 0–23
  end_hour: number        // exclusive, 1–24
  interval_minutes: number
}

export interface SpotifyAccount {
  id: string
  user_id: string
  spotify_user_id: string
  display_name: string | null
  email: string | null
  scopes: string
  poll_interval_minutes: number
  polling_enabled: boolean
  last_polled_at: string | null
  poll_schedule: PollScheduleRule[] | null
  created_at: string
}

export interface Track {
  title: string
  artist: string
  album: string
  played_at: string
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Initiate the Spotify OAuth flow. Returns the auth URL to redirect the user to. */
export async function initiateSpotifyLink(): Promise<string> {
  const resp = await api.post<{ auth_url: string }>(
    '/spotify/link',
    {},
    { headers: authHeaders() },
  )
  return resp.data.auth_url
}

/** Fetch all Spotify accounts linked to the current user. */
export async function getSpotifyAccounts(): Promise<SpotifyAccount[]> {
  const resp = await api.get<SpotifyAccount[]>('/spotify/accounts', {
    headers: authHeaders(),
  })
  return resp.data
}

/** Unlink (delete) a Spotify account by ID. */
export async function unlinkSpotifyAccount(id: string): Promise<void> {
  await api.delete(`/spotify/accounts/${id}`, { headers: authHeaders() })
}

/** Update the polling configuration for a Spotify account. */
export async function updateSpotifyPolling(
  id: string,
  payload: {
    polling_enabled?: boolean
    poll_interval_minutes?: number
    poll_schedule?: PollScheduleRule[] | null
  },
): Promise<SpotifyAccount> {
  const resp = await api.patch<SpotifyAccount>(
    `/spotify/accounts/${id}`,
    payload,
    { headers: authHeaders() },
  )
  return resp.data
}

/** Fetch recent listening history for a linked account. */
export async function getSpotifyHistory(
  accountId: string,
  timeWindow = 7,
): Promise<Track[]> {
  const resp = await api.get<Track[]>(
    `/spotify/accounts/${accountId}/history`,
    {
      headers: authHeaders(),
      params: { time_window: timeWindow },
    },
  )
  return resp.data
}
