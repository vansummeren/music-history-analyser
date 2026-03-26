import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface Schedule {
  id: string
  user_id: string
  analysis_id: string
  cron: string
  time_window_days: number
  recipient_email: string
  is_active: boolean
  last_run_at: string | null
  next_run_at: string
  created_at: string
  updated_at: string
}

export interface ScheduleCreate {
  analysis_id: string
  cron: string
  time_window_days?: number
  recipient_email: string
}

export interface ScheduleUpdate {
  cron?: string
  time_window_days?: number
  recipient_email?: string
  is_active?: boolean
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/** Create a new schedule. */
export async function createSchedule(data: ScheduleCreate): Promise<Schedule> {
  const resp = await api.post<Schedule>('/schedules', data, {
    headers: authHeaders(),
  })
  return resp.data
}

/** Fetch all schedules for the current user. */
export async function getSchedules(): Promise<Schedule[]> {
  const resp = await api.get<Schedule[]>('/schedules', {
    headers: authHeaders(),
  })
  return resp.data
}

/** Update a schedule (partial). */
export async function updateSchedule(
  id: string,
  data: ScheduleUpdate,
): Promise<Schedule> {
  const resp = await api.patch<Schedule>(`/schedules/${id}`, data, {
    headers: authHeaders(),
  })
  return resp.data
}

/** Delete a schedule by ID. */
export async function deleteSchedule(id: string): Promise<void> {
  await api.delete(`/schedules/${id}`, { headers: authHeaders() })
}
