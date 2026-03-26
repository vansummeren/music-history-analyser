import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, Plus } from 'lucide-react'
import CronEditor from '../components/CronEditor'
import EmptyState from '../components/EmptyState'
import LoadingSkeleton from '../components/LoadingSkeleton'
import ScheduleCard from '../components/ScheduleCard'
import { useToast } from '../hooks/useToast'
import type { Analysis } from '../services/analysisApi'
import { getAnalyses } from '../services/analysisApi'
import type { Schedule, ScheduleCreate } from '../services/scheduleApi'
import { createSchedule, getSchedules } from '../services/scheduleApi'

export default function SchedulesPage() {
  const { showToast } = useToast()
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [loading, setLoading] = useState(true)

  // Form state
  const [analysisId, setAnalysisId] = useState('')
  const [cron, setCron] = useState('0 8 * * 1')
  const [timeWindowDays, setTimeWindowDays] = useState(7)
  const [recipientEmail, setRecipientEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [s, a] = await Promise.all([getSchedules(), getAnalyses()])
      setSchedules(s)
      setAnalyses(a)
      if (a.length > 0) setAnalysisId(a[0].id)
    } catch {
      showToast('Failed to load data.', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    if (!analysisId || !cron.trim() || !recipientEmail.trim()) {
      setFormError('All fields are required.')
      return
    }
    setSubmitting(true)
    try {
      const data: ScheduleCreate = {
        analysis_id: analysisId,
        cron: cron.trim(),
        time_window_days: timeWindowDays,
        recipient_email: recipientEmail.trim(),
      }
      const created = await createSchedule(data)
      setSchedules((prev) => [...prev, created])
      setRecipientEmail('')
      showToast('Schedule created.', 'success')
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to create schedule.'
      setFormError(msg)
    } finally {
      setSubmitting(false)
    }
  }

  function handleDeleted(id: string) {
    setSchedules((prev) => prev.filter((s) => s.id !== id))
  }

  function handleUpdated(updated: Schedule) {
    setSchedules((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
  }

  function analysisName(id: string) {
    return analyses.find((a) => a.id === id)?.name
  }

  const inputClass =
    'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none dark:border-brand-700 dark:bg-brand-800 dark:text-white dark:placeholder-brand-500'

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-gray-900 dark:text-white">
        Schedules
      </h1>

      {loading ? (
        <LoadingSkeleton lines={3} className="mb-6" />
      ) : (
        <>
          {/* Existing schedules */}
          {schedules.length === 0 ? (
            <EmptyState
              icon={<Calendar className="h-10 w-10" />}
              title="No schedules yet"
              description="Create a schedule to automatically run analyses and receive email reports."
              className="mb-6"
            />
          ) : (
            <div className="mb-6 flex flex-col gap-3">
              {schedules.map((schedule) => (
                <ScheduleCard
                  key={schedule.id}
                  schedule={schedule}
                  analysisName={analysisName(schedule.analysis_id)}
                  onDeleted={handleDeleted}
                  onUpdated={handleUpdated}
                />
              ))}
            </div>
          )}

          {/* Create schedule form */}
          <form
            onSubmit={handleSubmit}
            className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700"
          >
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              New Schedule
            </h2>

            {formError && (
              <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
                {formError}
              </div>
            )}

            {analyses.length === 0 && (
              <div className="mb-3 rounded-lg bg-yellow-50 px-3 py-2 text-sm text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300">
                You need to{' '}
                <Link to="/analyses" className="underline">
                  create an analysis
                </Link>{' '}
                first.
              </div>
            )}

            <div className="mb-3">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
                Analysis
              </label>
              <select
                value={analysisId}
                onChange={(e) => setAnalysisId(e.target.value)}
                className={inputClass}
              >
                {analyses.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="mb-3">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
                Schedule (cron)
              </label>
              <CronEditor value={cron} onChange={setCron} />
            </div>

            <div className="mb-3">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
                Time window (days)
              </label>
              <input
                type="number"
                min={1}
                max={365}
                value={timeWindowDays}
                onChange={(e) => setTimeWindowDays(Number(e.target.value))}
                className={inputClass}
              />
              <p className="mt-1 text-xs text-gray-400 dark:text-brand-400">
                Number of days of Spotify history to include in the analysis.
              </p>
            </div>

            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
                Recipient email
              </label>
              <input
                type="email"
                value={recipientEmail}
                onChange={(e) => setRecipientEmail(e.target.value)}
                placeholder="you@example.com"
                className={inputClass}
              />
            </div>

            <button
              type="submit"
              disabled={submitting || analyses.length === 0}
              className="flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-2.5 font-semibold text-white shadow transition hover:bg-brand-400 disabled:opacity-50"
            >
              <Plus className="h-5 w-5" />
              {submitting ? 'Creating…' : 'Create Schedule'}
            </button>
          </form>
        </>
      )}
    </div>
  )
}
