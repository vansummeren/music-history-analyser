import { useState } from 'react'
import { Clock, Mail, Pause, Play, Trash2 } from 'lucide-react'
import type { Schedule, ScheduleUpdate } from '../services/scheduleApi'
import { deleteSchedule, updateSchedule } from '../services/scheduleApi'

interface Props {
  schedule: Schedule
  analysisName?: string
  onDeleted: (id: string) => void
  onUpdated: (schedule: Schedule) => void
}

export default function ScheduleCard({
  schedule,
  analysisName,
  onDeleted,
  onUpdated,
}: Props) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleToggleActive() {
    setBusy(true)
    setError(null)
    try {
      const updated = await updateSchedule(schedule.id, {
        is_active: !schedule.is_active,
      } satisfies ScheduleUpdate)
      onUpdated(updated)
    } catch {
      setError('Failed to update schedule.')
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!confirm('Delete this schedule?')) return
    setBusy(true)
    setError(null)
    try {
      await deleteSchedule(schedule.id)
      onDeleted(schedule.id)
    } catch {
      setError('Failed to delete schedule.')
    } finally {
      setBusy(false)
    }
  }

  const nextRun = new Date(schedule.next_run_at).toLocaleString()
  const lastRun = schedule.last_run_at
    ? new Date(schedule.last_run_at).toLocaleString()
    : 'Never'

  return (
    <div
      className={`rounded-xl border p-4 shadow transition ${
        schedule.is_active
          ? 'border-brand-700 bg-brand-800'
          : 'border-brand-800 bg-brand-900 opacity-60'
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-white">
            {analysisName ?? schedule.analysis_id}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-sm text-brand-300">
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              <code className="font-mono text-xs">{schedule.cron}</code>
            </span>
            <span>· last {schedule.time_window_days}d</span>
            <span className="flex items-center gap-1">
              <Mail className="h-3.5 w-3.5" />
              {schedule.recipient_email}
            </span>
          </div>
          <div className="mt-1 text-xs text-brand-400">
            Next: {nextRun} · Last ran: {lastRun}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <button
            onClick={handleToggleActive}
            disabled={busy}
            title={schedule.is_active ? 'Pause' : 'Resume'}
            className="rounded p-1.5 text-brand-300 transition hover:text-white disabled:opacity-50"
          >
            {schedule.is_active ? (
              <Pause className="h-4 w-4" />
            ) : (
              <Play className="h-4 w-4" />
            )}
          </button>
          <button
            onClick={handleDelete}
            disabled={busy}
            title="Delete"
            className="rounded p-1.5 text-brand-300 transition hover:text-red-400 disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </div>
  )
}
