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

// ── Application logs ──────────────────────────────────────────────────────────

export interface AppLogEntry {
  id: string
  created_at: string
  level: string
  service: string
  logger_name: string
  message: string
}

export interface AppLogsResponse {
  total: number
  items: AppLogEntry[]
}

export interface LogsFilter {
  level?: string
  service?: string[]
  search?: string
  since?: string
  until?: string
  limit?: number
  offset?: number
}

// ── Database statistics ───────────────────────────────────────────────────────

export interface TableSizeRow {
  table: string
  row_count: number
  total_size_bytes: number | null
  table_size_bytes: number | null
  index_size_bytes: number | null
}

export interface DbStatsResponse {
  database_size_bytes: number | null
  tables: TableSizeRow[]
  log_retention_days: number
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

/** Fetch paginated application log entries (admin only). */
export async function getAdminLogs(filter: LogsFilter = {}, signal?: AbortSignal): Promise<AppLogsResponse> {
  const params: Record<string, string | number | string[]> = {}
  if (filter.level) params.level = filter.level
  if (filter.service && filter.service.length > 0) params.service = filter.service
  if (filter.search) params.search = filter.search
  if (filter.since) params.since = filter.since
  if (filter.until) params.until = filter.until
  if (filter.limit !== undefined) params.limit = filter.limit
  if (filter.offset !== undefined) params.offset = filter.offset

  const resp = await api.get<AppLogsResponse>('/admin/logs', {
    headers: authHeaders(),
    params,
    paramsSerializer: { indexes: null },
    signal,
  })
  return resp.data
}

/** Fetch the distinct service names present in the log table (admin only). */
export async function getAdminLogServices(): Promise<string[]> {
  const resp = await api.get<{ services: string[] }>('/admin/logs/services', {
    headers: authHeaders(),
  })
  return resp.data.services
}

/** Fetch database size statistics (admin only). */
export async function getDbStats(): Promise<DbStatsResponse> {
  const resp = await api.get<DbStatsResponse>('/admin/db-stats', {
    headers: authHeaders(),
  })
  return resp.data
}
