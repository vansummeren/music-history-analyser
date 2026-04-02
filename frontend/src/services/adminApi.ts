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
