import { useCallback, useEffect, useState } from 'react'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { useToast } from '../hooks/useToast'
import type { AIConfig } from '../services/aiApi'
import { getAIConfigs } from '../services/aiApi'
import type { TestAIResponse, TestEmailResponse, TestSpotifyResponse } from '../services/adminApi'
import { adminTestAI, adminTestEmail, adminTestSpotify } from '../services/adminApi'
import type { SpotifyAccount } from '../services/spotifyApi'
import { getSpotifyAccounts } from '../services/spotifyApi'

const inputClass =
  'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 placeholder-gray-400 focus:border-brand-500 focus:outline-none dark:border-brand-700 dark:bg-brand-800 dark:text-white dark:placeholder-brand-500'

const btnClass =
  'rounded-lg bg-brand-500 px-5 py-2.5 font-semibold text-white shadow transition hover:bg-brand-400 disabled:opacity-50'

const cardClass =
  'rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700'

const labelClass = 'mb-1 block text-sm font-medium text-gray-700 dark:text-brand-200'

function ResultBox({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-4 rounded-lg bg-gray-50 p-4 text-sm text-gray-800 dark:bg-brand-900/60 dark:text-brand-100">
      {children}
    </div>
  )
}

export default function AdminPage() {
  const { showToast } = useToast()

  const [spotifyAccounts, setSpotifyAccounts] = useState<SpotifyAccount[]>([])
  const [aiConfigs, setAIConfigs] = useState<AIConfig[]>([])
  const [loading, setLoading] = useState(true)

  // Email state
  const [emailRecipient, setEmailRecipient] = useState('')
  const [emailSending, setEmailSending] = useState(false)
  const [emailResult, setEmailResult] = useState<TestEmailResponse | null>(null)
  const [emailError, setEmailError] = useState<string | null>(null)

  // Spotify state
  const [selectedAccountId, setSelectedAccountId] = useState('')
  const [spotifyTesting, setSpotifyTesting] = useState(false)
  const [spotifyResult, setSpotifyResult] = useState<TestSpotifyResponse | null>(null)
  const [spotifyError, setSpotifyError] = useState<string | null>(null)

  // AI state
  const [selectedConfigId, setSelectedConfigId] = useState('')
  const [aiPrompt, setAIPrompt] = useState('')
  const [aiTesting, setAITesting] = useState(false)
  const [aiResult, setAIResult] = useState<TestAIResponse | null>(null)
  const [aiError, setAIError] = useState<string | null>(null)

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [accounts, configs] = await Promise.all([getSpotifyAccounts(), getAIConfigs()])
      setSpotifyAccounts(accounts)
      setAIConfigs(configs)
      if (accounts.length > 0) setSelectedAccountId(accounts[0].id)
      if (configs.length > 0) setSelectedConfigId(configs[0].id)
    } catch {
      showToast('Failed to load data.', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  // ── Test Email ──────────────────────────────────────────────────────────────

  async function handleTestEmail(e: React.FormEvent) {
    e.preventDefault()
    setEmailError(null)
    setEmailResult(null)
    if (!emailRecipient.trim()) {
      setEmailError('Please enter a recipient email address.')
      return
    }
    setEmailSending(true)
    try {
      const result = await adminTestEmail(emailRecipient.trim())
      setEmailResult(result)
      showToast('Test email sent.', 'success')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to send test email.'
      setEmailError(msg)
    } finally {
      setEmailSending(false)
    }
  }

  // ── Test Spotify ────────────────────────────────────────────────────────────

  async function handleTestSpotify(e: React.FormEvent) {
    e.preventDefault()
    setSpotifyError(null)
    setSpotifyResult(null)
    if (!selectedAccountId) return
    setSpotifyTesting(true)
    try {
      const result = await adminTestSpotify(selectedAccountId)
      setSpotifyResult(result)
      showToast(`Fetched ${result.count} track(s) from Spotify.`, 'success')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load Spotify data.'
      setSpotifyError(msg)
    } finally {
      setSpotifyTesting(false)
    }
  }

  // ── Test AI ─────────────────────────────────────────────────────────────────

  async function handleTestAI(e: React.FormEvent) {
    e.preventDefault()
    setAIError(null)
    setAIResult(null)
    if (!selectedConfigId) return
    setAITesting(true)
    try {
      const result = await adminTestAI(selectedConfigId, aiPrompt.trim() || undefined)
      setAIResult(result)
      showToast('AI query completed.', 'success')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to query AI.'
      setAIError(msg)
    } finally {
      setAITesting(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Diagnostics</h1>

      {loading ? (
        <LoadingSkeleton lines={4} />
      ) : (
        <>
          {/* ── Send Test Email ─────────────────────────────────────────── */}
          <section className={cardClass}>
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Send Test Email
            </h2>
            <p className="mb-4 text-sm text-gray-500 dark:text-brand-400">
              Verify that your SMTP configuration is working by sending a test email.
            </p>

            <form onSubmit={handleTestEmail}>
              {emailError && (
                <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
                  {emailError}
                </div>
              )}

              <div className="mb-4">
                <label className={labelClass}>Recipient email</label>
                <input
                  type="email"
                  value={emailRecipient}
                  onChange={(e) => setEmailRecipient(e.target.value)}
                  placeholder="you@example.com"
                  className={inputClass}
                />
              </div>

              <button type="submit" disabled={emailSending} className={btnClass}>
                {emailSending ? 'Sending…' : 'Send Test Email'}
              </button>
            </form>

            {emailResult && (
              <ResultBox>
                <span className="font-medium text-green-700 dark:text-green-400">✓ </span>
                {emailResult.message}
              </ResultBox>
            )}
          </section>

          {/* ── Test Spotify ────────────────────────────────────────────── */}
          <section className={cardClass}>
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Test Spotify Connector
            </h2>
            <p className="mb-4 text-sm text-gray-500 dark:text-brand-400">
              Load the 10 most recently played tracks from a connected Spotify account.
            </p>

            {spotifyAccounts.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-brand-500">
                No Spotify accounts connected yet.
              </p>
            ) : (
              <form onSubmit={handleTestSpotify}>
                {spotifyError && (
                  <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
                    {spotifyError}
                  </div>
                )}

                <div className="mb-4">
                  <label className={labelClass}>Spotify account</label>
                  <select
                    value={selectedAccountId}
                    onChange={(e) => setSelectedAccountId(e.target.value)}
                    className={inputClass}
                  >
                    {spotifyAccounts.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.display_name ?? a.spotify_user_id}
                      </option>
                    ))}
                  </select>
                </div>

                <button type="submit" disabled={spotifyTesting} className={btnClass}>
                  {spotifyTesting ? 'Loading…' : 'Load Recent Tracks'}
                </button>
              </form>
            )}

            {spotifyResult && (
              <ResultBox>
                <p className="mb-2 font-medium">
                  {spotifyResult.count} track(s) from{' '}
                  <span className="text-brand-600 dark:text-brand-400">
                    {spotifyResult.display_name ?? 'account'}
                  </span>
                </p>
                <ol className="space-y-1 text-xs text-gray-600 dark:text-brand-300">
                  {spotifyResult.tracks.map((t, i) => (
                    <li key={i}>
                      {i + 1}. <span className="font-medium">{t.title}</span> — {t.artist}
                    </li>
                  ))}
                </ol>
              </ResultBox>
            )}
          </section>

          {/* ── Test AI ─────────────────────────────────────────────────── */}
          <section className={cardClass}>
            <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
              Test AI Config
            </h2>
            <p className="mb-4 text-sm text-gray-500 dark:text-brand-400">
              Send a test prompt to your configured AI provider to verify connectivity.
            </p>

            {aiConfigs.length === 0 ? (
              <p className="text-sm text-gray-400 dark:text-brand-500">
                No AI configurations found yet.
              </p>
            ) : (
              <form onSubmit={handleTestAI}>
                {aiError && (
                  <div className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
                    {aiError}
                  </div>
                )}

                <div className="mb-3">
                  <label className={labelClass}>AI configuration</label>
                  <select
                    value={selectedConfigId}
                    onChange={(e) => setSelectedConfigId(e.target.value)}
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
                  <label className={labelClass}>
                    Prompt{' '}
                    <span className="font-normal text-gray-400 dark:text-brand-500">
                      (optional)
                    </span>
                  </label>
                  <input
                    type="text"
                    value={aiPrompt}
                    onChange={(e) => setAIPrompt(e.target.value)}
                    placeholder="Say hello and confirm you are working correctly."
                    className={inputClass}
                  />
                </div>

                <button type="submit" disabled={aiTesting} className={btnClass}>
                  {aiTesting ? 'Querying…' : 'Query AI'}
                </button>
              </form>
            )}

            {aiResult && (
              <ResultBox>
                <p className="mb-1 text-xs text-gray-400 dark:text-brand-500">
                  Model: {aiResult.model} · {aiResult.input_tokens} in / {aiResult.output_tokens} out
                </p>
                <p className="whitespace-pre-wrap">{aiResult.text}</p>
              </ResultBox>
            )}
          </section>
        </>
      )}
    </div>
  )
}
