import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface Analysis {
  id: string
  user_id: string
  spotify_account_id: string
  ai_config_id: string
  name: string
  prompt: string
  created_at: string
}

export interface AnalysisCreate {
  name: string
  spotify_account_id: string
  ai_config_id: string
  prompt: string
}

export interface AnalysisUpdate {
  name?: string
  prompt?: string
}

export interface AnalysisRun {
  id: string
  analysis_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  result_text: string | null
  model: string | null
  input_tokens: number | null
  output_tokens: number | null
  error: string | null
  started_at: string | null
  completed_at: string | null
  created_at: string
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Create a new analysis configuration. */
export async function createAnalysis(data: AnalysisCreate): Promise<Analysis> {
  const resp = await api.post<Analysis>('/analyses', data, {
    headers: authHeaders(),
  })
  return resp.data
}

/** Fetch all analyses for the current user. */
export async function getAnalyses(): Promise<Analysis[]> {
  const resp = await api.get<Analysis[]>('/analyses', {
    headers: authHeaders(),
  })
  return resp.data
}

/** Delete an analysis by ID. */
export async function deleteAnalysis(id: string): Promise<void> {
  await api.delete(`/analyses/${id}`, { headers: authHeaders() })
}

/** Update an analysis name and/or prompt. */
export async function updateAnalysis(id: string, data: AnalysisUpdate): Promise<Analysis> {
  const resp = await api.patch<Analysis>(`/analyses/${id}`, data, {
    headers: authHeaders(),
  })
  return resp.data
}

/** Trigger an analysis run and return the run record. */
export async function triggerRun(analysisId: string): Promise<AnalysisRun> {
  const resp = await api.post<AnalysisRun>(
    `/analyses/${analysisId}/run`,
    {},
    { headers: authHeaders() },
  )
  return resp.data
}

/** Fetch all runs for an analysis. */
export async function getRuns(analysisId: string): Promise<AnalysisRun[]> {
  const resp = await api.get<AnalysisRun[]>(`/analyses/${analysisId}/runs`, {
    headers: authHeaders(),
  })
  return resp.data
}

/** Fetch a single run by ID. */
export async function getRun(
  analysisId: string,
  runId: string,
): Promise<AnalysisRun> {
  const resp = await api.get<AnalysisRun>(
    `/analyses/${analysisId}/runs/${runId}`,
    { headers: authHeaders() },
  )
  return resp.data
}
