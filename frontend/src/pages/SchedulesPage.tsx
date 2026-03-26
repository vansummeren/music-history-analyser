import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Plus } from 'lucide-react'
import CronEditor from '../components/CronEditor'
import ScheduleCard from '../components/ScheduleCard'
import type { Analysis } from '../services/analysisApi'
import { getAnalyses } from '../services/analysisApi'
import type { Schedule, ScheduleCreate } from '../services/scheduleApi'
import { createSchedule, getSchedules } from '../services/scheduleApi'

export default function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [analysisId, setAnalysisId] = useState('')
  const [cron, setCron] = useState('0 8 * * 1')
  const [timeWindowDays, setTimeWindowDays] = useState(7)
  const [recipientEmail, setRecipientEmail] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    loadAll()
  }, [])

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const [s, a] = await Promise.all([getSchedules(), getAnalyses()])
      setSchedules(s)
      setAnalyses(a)
      if (a.length > 0) setAnalysisId(a[0].id)
    } catch {
      setError('Failed to load data.')
    } finally {
      setLoading(false)
    }
  }

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

  return (
    <main className="min-h-screen bg-gradient-to-br from-brand-900 to-brand-700 p-6 text-white">
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-6 flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-1 text-sm text-brand-300 transition hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
          <h1 className="text-2xl font-bold">Schedules</h1>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-500/20 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {loading ? (
          <p className="text-brand-300">Loading…</p>
        ) : (
          <>
            {/* Existing schedules */}
            {schedules.length === 0 ? (
              <p className="mb-6 text-brand-300">
                No schedules yet. Create one below.
              </p>
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
              className="rounded-lg bg-white/10 p-5"
            >
              <h2 className="mb-4 text-lg font-semibold">New Schedule</h2>

              {formError && (
                <div className="mb-3 rounded bg-red-500/20 px-3 py-2 text-sm text-red-300">
                  {formError}
                </div>
              )}

              {analyses.length === 0 && (
                <div className="mb-3 rounded bg-yellow-500/20 px-3 py-2 text-sm text-yellow-300">
                  You need to{' '}
                  <Link to="/analyses" className="underline">
                    create an analysis
                  </Link>{' '}
                  first.
                </div>
              )}

              <div className="mb-3">
                <label className="mb-1 block text-sm text-brand-200">
                  Analysis
                </label>
                <select
                  value={analysisId}
                  onChange={(e) => setAnalysisId(e.target.value)}
                  className="w-full rounded bg-white/10 px-3 py-2 text-white focus:outline-none"
                >
                  {analyses.map((a) => (
                    <option key={a.id} value={a.id} className="text-black">
                      {a.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mb-3">
                <label className="mb-1 block text-sm text-brand-200">
                  Schedule (cron)
                </label>
                <CronEditor value={cron} onChange={setCron} />
              </div>

              <div className="mb-3">
                <label className="mb-1 block text-sm text-brand-200">
                  Time window (days)
                </label>
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={timeWindowDays}
                  onChange={(e) => setTimeWindowDays(Number(e.target.value))}
                  className="w-full rounded bg-white/10 px-3 py-2 text-white focus:outline-none"
                />
                <p className="mt-1 text-xs text-brand-400">
                  Number of days of Spotify history to include in the analysis.
                </p>
              </div>

              <div className="mb-4">
                <label className="mb-1 block text-sm text-brand-200">
                  Recipient email
                </label>
                <input
                  type="email"
                  value={recipientEmail}
                  onChange={(e) => setRecipientEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded bg-white/10 px-3 py-2 text-white placeholder-brand-400 focus:outline-none"
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
    </main>
  )
}
