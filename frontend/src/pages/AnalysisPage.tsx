import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart2, Play, Plus, Trash2 } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import LoadingSkeleton from '../components/LoadingSkeleton'
import RunResultViewer from '../components/RunResultViewer'
import { useToast } from '../hooks/useToast'
import type { AIConfig } from '../services/aiApi'
import { getAIConfigs } from '../services/aiApi'
import type { Analysis, AnalysisCreate, AnalysisRun } from '../services/analysisApi'
import {
  createAnalysis,
  deleteAnalysis,
  getAnalyses,
  getRuns,
  triggerRun,
} from '../services/analysisApi'
import type { SpotifyAccount } from '../services/spotifyApi'
import { getSpotifyAccounts } from '../services/spotifyApi'

export default function AnalysisPage() {
  const { showToast } = useToast()
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [spotifyAccounts, setSpotifyAccounts] = useState<SpotifyAccount[]>([])
  const [aiConfigs, setAIConfigs] = useState<AIConfig[]>([])
  const [loading, setLoading] = useState(true)

  // Runs state: analysisId -> runs
  const [runsByAnalysis, setRunsByAnalysis] = useState<
    Record<string, AnalysisRun[]>
  >({})
  const [runningIds, setRunningIds] = useState<Set<string>>(new Set())

  // Form state
  const [name, setName] = useState('')
  const [spotifyAccountId, setSpotifyAccountId] = useState('')
  const [aiConfigId, setAiConfigId] = useState('')
  const [prompt, setPrompt] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [a, s, c] = await Promise.all([
        getAnalyses(),
        getSpotifyAccounts(),
        getAIConfigs(),
      ])
      setAnalyses(a)
      setSpotifyAccounts(s)
      setAIConfigs(c)
      if (s.length > 0) setSpotifyAccountId(s[0].id)
      if (c.length > 0) setAiConfigId(c[0].id)
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
    if (!name.trim() || !spotifyAccountId || !aiConfigId || !prompt.trim()) {
      setFormError('All fields are required.')
      return
    }
    setSubmitting(true)
    try {
      const data: AnalysisCreate = {
        name: name.trim(),
        spotify_account_id: spotifyAccountId,
        ai_config_id: aiConfigId,
        prompt: prompt.trim(),
      }
      const created = await createAnalysis(data)
      setAnalyses((prev) => [...prev, created])
      setName('')
      setPrompt('')
      showToast('Analysis created.', 'success')
    } catch {
      setFormError('Failed to create analysis. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteAnalysis(id)
      setAnalyses((prev) => prev.filter((a) => a.id !== id))
      showToast('Analysis deleted.', 'success')
    } catch {
      showToast('Failed to delete analysis.', 'error')
    }
  }

  async function handleRun(analysisId: string) {
    setRunningIds((prev) => new Set(prev).add(analysisId))
    try {
      const run = await triggerRun(analysisId)
      setRunsByAnalysis((prev) => ({
        ...prev,
        [analysisId]: [run, ...(prev[analysisId] ?? [])],
      }))
    } catch {
      showToast('Failed to trigger analysis run.', 'error')
    } finally {
      setRunningIds((prev) => {
        const next = new Set(prev)
        next.delete(analysisId)
        return next
      })
    }
  }

  async function handleLoadRuns(analysisId: string) {
    try {
      const runs = await getRuns(analysisId)
      setRunsByAnalysis((prev) => ({ ...prev, [analysisId]: runs }))
    } catch {
      showToast('Failed to load runs.', 'error')
    }
  }

  const inputClass =
    'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none dark:border-brand-700 dark:bg-brand-800 dark:text-white dark:placeholder-brand-500'

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-gray-900 dark:text-white">
        Analyses
      </h1>

      {loading ? (
        <LoadingSkeleton lines={4} className="mb-6" />
      ) : (
        <>
          {/* Existing analyses */}
          {analyses.length === 0 ? (
            <EmptyState
              icon={<BarChart2 className="h-10 w-10" />}
              title="No analyses yet"
              description="Create your first analysis below to start running AI insights on your music."
              className="mb-6"
            />
          ) : (
            <div className="mb-6 flex flex-col gap-4">
              {analyses.map((analysis) => {
                const runs = runsByAnalysis[analysis.id]
                const isRunning = runningIds.has(analysis.id)
                const spotifyAcc = spotifyAccounts.find(
                  (s) => s.id === analysis.spotify_account_id,
                )
                const aiConf = aiConfigs.find(
                  (c) => c.id === analysis.ai_config_id,
                )

                return (
                  <div
                    key={analysis.id}
                    className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700"
                  >
                    <div className="flex items-start justify-between">
                      <div>
                        <p className="font-semibold text-gray-900 dark:text-white">
                          {analysis.name}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-brand-300">
                          {spotifyAcc?.display_name ?? analysis.spotify_account_id} ·{' '}
                          {aiConf?.display_name ?? analysis.ai_config_id}
                        </p>
                        <p className="mt-1 line-clamp-2 text-sm text-gray-600 dark:text-brand-200">
                          {analysis.prompt}
                        </p>
                      </div>
                      <button
                        onClick={() => handleDelete(analysis.id)}
                        className="ml-3 rounded p-1.5 text-gray-400 transition hover:text-red-500 dark:text-brand-400 dark:hover:text-red-400"
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>

                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={() => handleRun(analysis.id)}
                        disabled={isRunning}
                        className="flex items-center gap-1.5 rounded-lg bg-brand-500 px-3 py-1.5 text-sm font-medium text-white transition hover:bg-brand-400 disabled:opacity-50"
                      >
                        <Play className="h-3.5 w-3.5" />
                        {isRunning ? 'Running…' : 'Run Now'}
                      </button>
                      <button
                        onClick={() => handleLoadRuns(analysis.id)}
                        className="rounded-lg bg-gray-100 px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-200 dark:bg-brand-700/50 dark:text-brand-200 dark:hover:bg-brand-700"
                      >
                        View Runs
                      </button>
                    </div>

                    {/* Runs */}
                    {runs && runs.length > 0 && (
                      <div className="mt-3 flex flex-col gap-2">
                        {runs.map((run) => (
                          <RunResultViewer key={run.id} run={run} />
                        ))}
                      </div>
                    )}
                    {runs && runs.length === 0 && (
                      <p className="mt-2 text-xs text-gray-400 dark:text-brand-400">
                        No runs yet.
                      </p>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* Create analysis form */}
          <form
            onSubmit={handleSubmit}
            className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700"
          >
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              New Analysis
            </h2>

            {formError && (
              <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
                {formError}
              </div>
            )}

            {(spotifyAccounts.length === 0 || aiConfigs.length === 0) && (
              <div className="mb-3 rounded-lg bg-yellow-50 px-3 py-2 text-sm text-yellow-800 dark:bg-yellow-900/20 dark:text-yellow-300">
                {spotifyAccounts.length === 0 && (
                  <span>
                    You need to{' '}
                    <Link to="/spotify" className="underline">
                      connect a Spotify account
                    </Link>{' '}
                    first.{' '}
                  </span>
                )}
                {aiConfigs.length === 0 && (
                  <span>
                    You need to{' '}
                    <Link to="/ai-configs" className="underline">
                      add an AI configuration
                    </Link>{' '}
                    first.
                  </span>
                )}
              </div>
            )}

            <div className="mb-3">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
                Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Weekly Taste Report"
                className={inputClass}
              />
            </div>

            <div className="mb-3">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
                Spotify Account
              </label>
              <select
                value={spotifyAccountId}
                onChange={(e) => setSpotifyAccountId(e.target.value)}
                className={inputClass}
              >
                {spotifyAccounts.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.display_name ?? s.spotify_user_id}
                  </option>
                ))}
              </select>
            </div>

            <div className="mb-3">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
                AI Configuration
              </label>
              <select
                value={aiConfigId}
                onChange={(e) => setAiConfigId(e.target.value)}
                className={inputClass}
              >
                {aiConfigs.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.display_name} ({c.provider})
                  </option>
                ))}
              </select>
            </div>

            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
                Prompt
              </label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={4}
                placeholder="Describe my recent music taste in a few sentences…"
                className={inputClass}
              />
            </div>

            <button
              type="submit"
              disabled={
                submitting ||
                spotifyAccounts.length === 0 ||
                aiConfigs.length === 0
              }
              className="flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-2.5 font-semibold text-white shadow transition hover:bg-brand-400 disabled:opacity-50"
            >
              <Plus className="h-5 w-5" />
              {submitting ? 'Creating…' : 'Create Analysis'}
            </button>
          </form>
        </>
      )}
    </div>
  )
}
