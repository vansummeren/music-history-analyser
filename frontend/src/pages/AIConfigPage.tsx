import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2 } from 'lucide-react'
import type { AIConfig, AIConfigCreate } from '../services/aiApi'
import { createAIConfig, deleteAIConfig, getAIConfigs } from '../services/aiApi'

const PROVIDERS: { value: AIConfig['provider']; label: string }[] = [
  { value: 'claude', label: 'Anthropic Claude' },
  { value: 'perplexity', label: 'Perplexity AI' },
]

export default function AIConfigPage() {
  const [configs, setConfigs] = useState<AIConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Form state
  const [provider, setProvider] = useState<AIConfig['provider']>('claude')
  const [displayName, setDisplayName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setConfigs(await getAIConfigs())
    } catch {
      setError('Failed to load AI configurations.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setFormError(null)
    if (!displayName.trim() || !apiKey.trim()) {
      setFormError('Display name and API key are required.')
      return
    }
    setSubmitting(true)
    try {
      const data: AIConfigCreate = {
        provider,
        display_name: displayName.trim(),
        api_key: apiKey.trim(),
      }
      const created = await createAIConfig(data)
      setConfigs((prev) => [...prev, created])
      setDisplayName('')
      setApiKey('')
    } catch {
      setFormError('Failed to save AI configuration. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteAIConfig(id)
      setConfigs((prev) => prev.filter((c) => c.id !== id))
    } catch {
      setError('Failed to delete configuration.')
    }
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
          <h1 className="text-2xl font-bold">AI Configurations</h1>
        </div>

        {error && (
          <div className="mb-4 rounded-lg bg-red-500/20 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Existing configs */}
        {loading ? (
          <p className="text-brand-300">Loading…</p>
        ) : configs.length === 0 ? (
          <p className="text-brand-300">No AI configurations yet. Add one below.</p>
        ) : (
          <div className="mb-6 flex flex-col gap-3">
            {configs.map((cfg) => (
              <div
                key={cfg.id}
                className="flex items-center justify-between rounded-lg bg-white/10 px-4 py-3"
              >
                <div>
                  <p className="font-semibold">{cfg.display_name}</p>
                  <p className="text-xs text-brand-300 capitalize">{cfg.provider}</p>
                </div>
                <button
                  onClick={() => handleDelete(cfg.id)}
                  className="rounded p-1.5 text-brand-300 transition hover:text-red-400"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Add new config form */}
        <form
          onSubmit={handleSubmit}
          className="rounded-lg bg-white/10 p-5"
        >
          <h2 className="mb-4 text-lg font-semibold">Add AI Configuration</h2>

          {formError && (
            <div className="mb-3 rounded bg-red-500/20 px-3 py-2 text-sm text-red-300">
              {formError}
            </div>
          )}

          <div className="mb-3">
            <label className="mb-1 block text-sm text-brand-200">Provider</label>
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as AIConfig['provider'])}
              className="w-full rounded bg-white/10 px-3 py-2 text-white focus:outline-none"
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value} className="text-black">
                  {p.label}
                </option>
              ))}
            </select>
          </div>

          <div className="mb-3">
            <label className="mb-1 block text-sm text-brand-200">Display Name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. My Claude Key"
              className="w-full rounded bg-white/10 px-3 py-2 text-white placeholder-brand-400 focus:outline-none"
            />
          </div>

          <div className="mb-4">
            <label className="mb-1 block text-sm text-brand-200">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-…"
              className="w-full rounded bg-white/10 px-3 py-2 text-white placeholder-brand-400 focus:outline-none"
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="flex items-center gap-2 rounded-lg bg-brand-500 px-5 py-2.5 font-semibold text-white shadow transition hover:bg-brand-400 disabled:opacity-50"
          >
            <Plus className="h-5 w-5" />
            {submitting ? 'Saving…' : 'Add Configuration'}
          </button>
        </form>
      </div>
    </main>
  )
}
