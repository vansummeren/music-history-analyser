import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Plus, RefreshCw } from 'lucide-react'
import SpotifyAccountCard from '../components/SpotifyAccountCard'
import type { SpotifyAccount } from '../services/spotifyApi'
import { getSpotifyAccounts, initiateSpotifyLink } from '../services/spotifyApi'

export default function SpotifyAccountsPage() {
  const [accounts, setAccounts] = useState<SpotifyAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadAccounts()
  }, [])

  async function loadAccounts() {
    setLoading(true)
    setError(null)
    try {
      const data = await getSpotifyAccounts()
      setAccounts(data)
    } catch {
      setError('Failed to load Spotify accounts.')
    } finally {
      setLoading(false)
    }
  }

  async function handleConnect() {
    setConnecting(true)
    setError(null)
    try {
      const authUrl = await initiateSpotifyLink()
      window.location.href = authUrl
    } catch {
      setError('Failed to start Spotify connection. Please try again.')
      setConnecting(false)
    }
  }

  function handleUnlinked(id: string) {
    setAccounts((prev) => prev.filter((a) => a.id !== id))
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-brand-900 to-brand-700 p-6 text-white">
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="flex items-center gap-1 text-sm text-brand-300 transition hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Link>
            <h1 className="text-2xl font-bold">Spotify Accounts</h1>
          </div>
          <button
            onClick={loadAccounts}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-brand-300 transition hover:text-white disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div className="mb-4 rounded-lg bg-red-500/20 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Account list */}
        {loading ? (
          <p className="text-brand-300">Loading…</p>
        ) : accounts.length === 0 ? (
          <p className="text-brand-300">
            No Spotify accounts linked yet. Connect one below.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            {accounts.map((account) => (
              <SpotifyAccountCard
                key={account.id}
                account={account}
                onUnlinked={handleUnlinked}
              />
            ))}
          </div>
        )}

        {/* Connect button */}
        <div className="mt-6">
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="flex items-center gap-2 rounded-lg bg-green-500 px-5 py-2.5 font-semibold text-white shadow transition hover:bg-green-400 disabled:opacity-50"
          >
            <Plus className="h-5 w-5" />
            {connecting ? 'Redirecting to Spotify…' : 'Connect Spotify Account'}
          </button>
        </div>
      </div>
    </main>
  )
}
