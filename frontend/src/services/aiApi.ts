import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface AIConfig {
  id: string
  user_id: string
  provider: 'claude' | 'perplexity'
  display_name: string
  created_at: string
}

export interface AIConfigCreate {
  provider: 'claude' | 'perplexity'
  display_name: string
  api_key: string
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Create a new AI configuration. */
export async function createAIConfig(data: AIConfigCreate): Promise<AIConfig> {
  const resp = await api.post<AIConfig>('/ai-configs', data, {
    headers: authHeaders(),
  })
  return resp.data
}

/** Fetch all AI configurations for the current user. */
export async function getAIConfigs(): Promise<AIConfig[]> {
  const resp = await api.get<AIConfig[]>('/ai-configs', {
    headers: authHeaders(),
  })
  return resp.data
}

/** Delete an AI configuration by ID. */
export async function deleteAIConfig(id: string): Promise<void> {
  await api.delete(`/ai-configs/${id}`, { headers: authHeaders() })
}
