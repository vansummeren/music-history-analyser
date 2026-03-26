import { useCallback, useEffect, useState } from 'react'
import { Cpu, Plus, Trash2 } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { useToast } from '../hooks/useToast'
import type { AIConfig, AIConfigCreate } from '../services/aiApi'
import { createAIConfig, deleteAIConfig, getAIConfigs } from '../services/aiApi'

const PROVIDERS: { value: AIConfig['provider']; label: string }[] = [
  { value: 'claude', label: 'Anthropic Claude' },
  { value: 'perplexity', label: 'Perplexity AI' },
]

export default function AIConfigPage() {
  const { showToast } = useToast()
  const [configs, setConfigs] = useState<AIConfig[]>([])
  const [loading, setLoading] = useState(true)

  // Form state
  const [provider, setProvider] = useState<AIConfig['provider']>('claude')
  const [displayName, setDisplayName] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setConfigs(await getAIConfigs())
    } catch {
      showToast('Failed to load AI configurations.', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    load()
  }, [load])

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
      showToast('AI configuration saved.', 'success')
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
      showToast('Configuration deleted.', 'success')
    } catch {
      showToast('Failed to delete configuration.', 'error')
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold text-gray-900 dark:text-white">
        AI Configurations
      </h1>

      {/* Existing configs */}
      {loading ? (
        <LoadingSkeleton lines={3} className="mb-6" />
      ) : configs.length === 0 ? (
        <EmptyState
          icon={<Cpu className="h-10 w-10" />}
          title="No AI configurations"
          description="Add an AI provider configuration to start running analyses."
          className="mb-6"
        />
      ) : (
        <div className="mb-6 flex flex-col gap-3">
          {configs.map((cfg) => (
            <div
              key={cfg.id}
              className="flex items-center justify-between rounded-xl bg-white p-4 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700"
            >
              <div className="flex items-center gap-3">
                <Cpu className="h-5 w-5 text-brand-500 dark:text-brand-400" />
                <div>
                  <p className="font-semibold text-gray-900 dark:text-white">
                    {cfg.display_name}
                  </p>
                  <p className="text-xs capitalize text-gray-500 dark:text-brand-400">
                    {cfg.provider}
                  </p>
                </div>
              </div>
              <button
                onClick={() => handleDelete(cfg.id)}
                className="rounded p-1.5 text-gray-400 transition hover:text-red-500 dark:text-brand-400 dark:hover:text-red-400"
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
        className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700"
      >
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
          Add AI Configuration
        </h2>

        {formError && (
          <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
            {formError}
          </div>
        )}

        <div className="mb-3">
          <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
            Provider
          </label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as AIConfig['provider'])}
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 focus:border-brand-500 focus:outline-none dark:border-brand-700 dark:bg-brand-800 dark:text-white"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div className="mb-3">
          <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
            Display Name
          </label>
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="e.g. My Claude Key"
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none dark:border-brand-700 dark:bg-brand-800 dark:text-white dark:placeholder-brand-500"
          />
        </div>

        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200">
            API Key
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-…"
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none dark:border-brand-700 dark:bg-brand-800 dark:text-white dark:placeholder-brand-500"
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
  )
}
