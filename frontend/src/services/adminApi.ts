import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export interface TrackItem {
  title: string
  artist: string
  album: string
  played_at: string
}

export interface TableRow {
  table: string
  row_count: number
}

export interface TablesResponse {
  tables: TableRow[]
}

export interface TestEmailResponse {
  message: string
  recipient: string
}

export interface TestSpotifyResponse {
  account_id: string
  display_name: string | null
  tracks: TrackItem[]
  count: number
}

export interface TestAIResponse {
  config_id: string
  provider: string
  model: string
  input_tokens: number
  output_tokens: number
  text: string
}

export interface AdminUserSummary {
  id: string
  display_name: string | null
  email: string | null
  role: string
  created_at: string
  spotify_accounts_count: number
  analyses_count: number
  schedules_count: number
  play_events_count: number
}

export interface AdminSpotifyAccountSummary {
  id: string
  spotify_user_id: string
  display_name: string | null
  polling_enabled: boolean
  last_polled_at: string | null
  play_events_count: number
}

export interface AdminAnalysisSummary {
  id: string
  name: string
  prompt: string
  run_count: number
  last_run_at: string | null
  last_run_status: string | null
}

export interface AdminScheduleSummary {
  id: string
  analysis_id: string
  analysis_name: string | null
  cron: string
  time_window_days: number
  recipient_email: string
  is_active: boolean
  last_run_at: string | null
  next_run_at: string
}

export interface AdminUserDetail {
  id: string
  display_name: string | null
  email: string | null
  role: string
  created_at: string
  spotify_accounts: AdminSpotifyAccountSummary[]
  analyses: AdminAnalysisSummary[]
  schedules: AdminScheduleSummary[]
}

/** Send a test email to verify SMTP connectivity. */
export async function adminTestEmail(recipient: string): Promise<TestEmailResponse> {
  const resp = await api.post<TestEmailResponse>(
    '/admin/test-email',
    { recipient },
    { headers: authHeaders() },
  )
  return resp.data
}

/** Fetch recent Spotify tracks for a connected account. */
export async function adminTestSpotify(accountId: string): Promise<TestSpotifyResponse> {
  const resp = await api.post<TestSpotifyResponse>(
    `/admin/test-spotify/${accountId}`,
    {},
    { headers: authHeaders() },
  )
  return resp.data
}

/** Fetch row counts for all main database tables (admin only). */
export async function getTableStats(): Promise<TablesResponse> {
  const resp = await api.get<TablesResponse>('/admin/tables', {
    headers: authHeaders(),
  })
  return resp.data
}

/** Send a test prompt to a configured AI provider. */
export async function adminTestAI(configId: string, prompt?: string): Promise<TestAIResponse> {
  const resp = await api.post<TestAIResponse>(
    `/admin/test-ai/${configId}`,
    prompt ? { prompt } : {},
    { headers: authHeaders() },
  )
  return resp.data
}

/** Fetch a summary list of all users (admin only). */
export async function getAdminUsers(): Promise<AdminUserSummary[]> {
  const resp = await api.get<AdminUserSummary[]>('/admin/users', {
    headers: authHeaders(),
  })
  return resp.data
}

/** Fetch detailed information about a single user (admin only). */
export async function getAdminUserDetail(userId: string): Promise<AdminUserDetail> {
  const resp = await api.get<AdminUserDetail>(`/admin/users/${userId}`, {
    headers: authHeaders(),
  })
  return resp.data
}
