import { useState } from 'react'
import { ChevronDown, ChevronUp, Music, Plus, Trash2, Unlink } from 'lucide-react'
import type { PollScheduleRule, SpotifyAccount } from '../services/spotifyApi'
import { unlinkSpotifyAccount, updateSpotifyPolling } from '../services/spotifyApi'

interface Props {
  account: SpotifyAccount
  onUnlinked: (id: string) => void
  onUpdated: (account: SpotifyAccount) => void
}

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const INTERVAL_OPTIONS = [
  { label: '15 min', value: 15 },
  { label: '30 min', value: 30 },
  { label: '1 hour', value: 60 },
  { label: '2 hours', value: 120 },
  { label: '3 hours', value: 180 },
  { label: '4 hours', value: 240 },
  { label: '6 hours', value: 360 },
  { label: '12 hours', value: 720 },
  { label: '24 hours', value: 1440 },
]

const HOUR_OPTIONS = Array.from({ length: 25 }, (_, i) => i) // 0..24

function formatInterval(minutes: number): string {
  const opt = INTERVAL_OPTIONS.find((o) => o.value === minutes)
  if (opt) return opt.label
  if (minutes < 60) return `${minutes} min`
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return m === 0 ? `${h}h` : `${h}h ${m}m`
}

function formatHour(h: number): string {
  if (h === 24) return '00:00'
  return `${String(h).padStart(2, '0')}:00`
}

export default function SpotifyAccountCard({ account, onUnlinked, onUpdated }: Props) {
  const [unlinking, setUnlinking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showConfig, setShowConfig] = useState(false)
  const [saving, setSaving] = useState(false)

  // Local editable copies of polling settings
  const [pollingEnabled, setPollingEnabled] = useState(account.polling_enabled)
  const [defaultInterval, setDefaultInterval] = useState(account.poll_interval_minutes)
  const [rules, setRules] = useState<PollScheduleRule[]>(account.poll_schedule ?? [])

  async function handleUnlink() {
    if (!confirm(`Disconnect "${account.display_name ?? account.spotify_user_id}"?`)) return
    setUnlinking(true)
    setError(null)
    try {
      await unlinkSpotifyAccount(account.id)
      onUnlinked(account.id)
    } catch {
      setError('Failed to disconnect account. Please try again.')
    } finally {
      setUnlinking(false)
    }
  }

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      const updated = await updateSpotifyPolling(account.id, {
        polling_enabled: pollingEnabled,
        poll_interval_minutes: defaultInterval,
        // Send null to clear the schedule when the list is empty
        poll_schedule: rules.length > 0 ? rules : null,
      })
      onUpdated(updated)
      setShowConfig(false)
    } catch {
      setError('Failed to save polling settings. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  function addRule() {
    setRules((prev) => [
      ...prev,
      { days: [0, 1, 2, 3, 4], start_hour: 0, end_hour: 24, interval_minutes: 60 },
    ])
  }

  function removeRule(idx: number) {
    setRules((prev) => prev.filter((_, i) => i !== idx))
  }

  function updateRule(idx: number, patch: Partial<PollScheduleRule>) {
    setRules((prev) =>
      prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)),
    )
  }

  function toggleDay(ruleIdx: number, day: number) {
    setRules((prev) =>
      prev.map((r, i) => {
        if (i !== ruleIdx) return r
        const days = r.days.includes(day)
          ? r.days.filter((d) => d !== day)
          : [...r.days, day].sort((a, b) => a - b)
        return { ...r, days }
      }),
    )
  }

  return (
    <div className="rounded-xl border border-brand-700 bg-brand-800 shadow">
      {/* ── Account header ── */}
      <div className="flex items-center justify-between p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-500/20 text-green-400">
            <Music className="h-5 w-5" />
          </div>
          <div>
            <p className="font-semibold text-white">
              {account.display_name ?? account.spotify_user_id}
            </p>
            {account.email && (
              <p className="text-sm text-brand-300">{account.email}</p>
            )}
            <p className="mt-0.5 text-xs text-brand-400">
              {account.polling_enabled
                ? `Polling every ${formatInterval(account.poll_interval_minutes)}${account.poll_schedule && account.poll_schedule.length > 0 ? ' (custom schedule)' : ''}`
                : 'Polling paused'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowConfig((v) => !v)}
            className="flex items-center gap-1.5 rounded-lg bg-brand-700 px-3 py-1.5 text-sm font-medium text-brand-200 transition hover:bg-brand-600"
            title="Configure polling"
          >
            {showConfig ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            Configure
          </button>
          <button
            onClick={handleUnlink}
            disabled={unlinking}
            className="flex items-center gap-1.5 rounded-lg bg-red-600/20 px-3 py-1.5 text-sm font-medium text-red-400 transition hover:bg-red-600/40 disabled:opacity-50"
          >
            <Unlink className="h-4 w-4" />
            {unlinking ? 'Disconnecting…' : 'Disconnect'}
          </button>
        </div>
      </div>

      {/* ── Polling configuration panel ── */}
      {showConfig && (
        <div className="border-t border-brand-700 p-4 space-y-4">
          {/* Enable / Pause toggle */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-white">Automatic polling</p>
              <p className="text-xs text-brand-400">
                When paused, history is only collected via manual poll.
              </p>
            </div>
            <button
              onClick={() => setPollingEnabled((v) => !v)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                pollingEnabled ? 'bg-green-500' : 'bg-brand-600'
              }`}
              role="switch"
              aria-checked={pollingEnabled}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  pollingEnabled ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>

          {/* Default interval */}
          <div>
            <label className="mb-1 block text-sm font-medium text-white">
              Default interval
              <span className="ml-1 text-xs font-normal text-brand-400">
                (used when no time-window rule matches)
              </span>
            </label>
            <select
              value={defaultInterval}
              onChange={(e) => setDefaultInterval(Number(e.target.value))}
              className="rounded-lg border border-brand-600 bg-brand-700 px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-green-500"
            >
              {INTERVAL_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Time-window rules */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <p className="text-sm font-medium text-white">
                Time-window rules
                <span className="ml-1 text-xs font-normal text-brand-400">
                  (override the default interval; times are UTC)
                </span>
              </p>
              <button
                onClick={addRule}
                className="flex items-center gap-1 rounded-lg bg-brand-700 px-2.5 py-1 text-xs font-medium text-brand-200 transition hover:bg-brand-600"
              >
                <Plus className="h-3.5 w-3.5" />
                Add rule
              </button>
            </div>

            {rules.length === 0 && (
              <p className="text-xs text-brand-500 italic">
                No rules defined — the default interval applies at all times.
              </p>
            )}

            <div className="space-y-3">
              {rules.map((rule, idx) => (
                <div
                  key={idx}
                  className="rounded-lg border border-brand-600 bg-brand-900/50 p-3 space-y-2"
                >
                  {/* Days */}
                  <div>
                    <p className="mb-1 text-xs text-brand-400">Days of the week</p>
                    <div className="flex flex-wrap gap-1">
                      {DAY_LABELS.map((label, day) => (
                        <button
                          key={day}
                          onClick={() => toggleDay(idx, day)}
                          className={`rounded px-2 py-0.5 text-xs font-medium transition ${
                            rule.days.includes(day)
                              ? 'bg-green-500/30 text-green-300 ring-1 ring-green-500'
                              : 'bg-brand-700 text-brand-400 hover:bg-brand-600'
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Time window + interval */}
                  <div className="flex flex-wrap items-end gap-3">
                    <div>
                      <label className="mb-1 block text-xs text-brand-400">
                        From (UTC)
                      </label>
                      <select
                        value={rule.start_hour}
                        onChange={(e) =>
                          updateRule(idx, { start_hour: Number(e.target.value) })
                        }
                        className="rounded border border-brand-600 bg-brand-700 px-2 py-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-green-500"
                      >
                        {HOUR_OPTIONS.slice(0, 24).map((h) => (
                          <option key={h} value={h}>
                            {formatHour(h)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-brand-400">
                        Until (UTC)
                      </label>
                      <select
                        value={rule.end_hour}
                        onChange={(e) =>
                          updateRule(idx, { end_hour: Number(e.target.value) })
                        }
                        className="rounded border border-brand-600 bg-brand-700 px-2 py-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-green-500"
                      >
                        {HOUR_OPTIONS.slice(1).map((h) => (
                          <option key={h} value={h}>
                            {formatHour(h)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="mb-1 block text-xs text-brand-400">
                        Interval
                      </label>
                      <select
                        value={rule.interval_minutes}
                        onChange={(e) =>
                          updateRule(idx, { interval_minutes: Number(e.target.value) })
                        }
                        className="rounded border border-brand-600 bg-brand-700 px-2 py-1 text-xs text-white focus:outline-none focus:ring-1 focus:ring-green-500"
                      >
                        {INTERVAL_OPTIONS.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <button
                      onClick={() => removeRule(idx)}
                      className="mb-0.5 text-red-400 transition hover:text-red-300"
                      title="Remove rule"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-green-500 px-4 py-1.5 text-sm font-semibold text-white transition hover:bg-green-400 disabled:opacity-50"
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={() => {
                // Reset to current account values
                setPollingEnabled(account.polling_enabled)
                setDefaultInterval(account.poll_interval_minutes)
                setRules(account.poll_schedule ?? [])
                setShowConfig(false)
                setError(null)
              }}
              className="rounded-lg bg-brand-700 px-4 py-1.5 text-sm font-medium text-brand-200 transition hover:bg-brand-600"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

