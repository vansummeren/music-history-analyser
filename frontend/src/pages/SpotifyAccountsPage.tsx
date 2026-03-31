import { useCallback, useEffect, useState } from 'react'
import { Music, Plus, RefreshCw } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import LoadingSkeleton from '../components/LoadingSkeleton'
import SpotifyAccountCard from '../components/SpotifyAccountCard'
import { useToast } from '../hooks/useToast'
import type { SpotifyAccount } from '../services/spotifyApi'
import { getSpotifyAccounts, initiateSpotifyLink } from '../services/spotifyApi'

const SPOTIFY_ERROR_MESSAGES: Record<string, string> = {
  access_denied: 'Spotify authorisation was denied. Please try again.',
  server_error: 'Spotify encountered a server error. Please try again later.',
  temporarily_unavailable: 'Spotify is temporarily unavailable. Please try again later.',
  state_mismatch: 'The authorisation request expired or was tampered with. Please try again.',
  token_exchange_failed: 'Could not complete the Spotify connection. Please try again.',
  profile_fetch_failed: 'Could not retrieve your Spotify profile. Please try again.',
  no_refresh_token:
    'Spotify did not issue a refresh token. If you previously disconnected this Spotify account, please go to your Spotify account settings (spotify.com/account/apps), remove this app, then try connecting again.',
  unknown: 'An unexpected error occurred while connecting Spotify. Please try again.',
}

export default function SpotifyAccountsPage() {
  const { showToast } = useToast()
  const [accounts, setAccounts] = useState<SpotifyAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(false)

  const loadAccounts = useCallback(async () => {
    setLoading(true)
    try {
      const data = await getSpotifyAccounts()
      setAccounts(data)
    } catch {
      showToast('Failed to load Spotify accounts.', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    // Show a toast for any error redirected back from the Spotify OAuth callback.
    const params = new URLSearchParams(window.location.search)
    const error = params.get('error')
    if (error) {
      const message = SPOTIFY_ERROR_MESSAGES[error] ?? SPOTIFY_ERROR_MESSAGES.unknown
      showToast(message, 'error')
      // Remove the error param from the URL without reloading the page.
      params.delete('error')
      const newSearch = params.toString()
      const newUrl = window.location.pathname + (newSearch ? `?${newSearch}` : '')
      window.history.replaceState(null, '', newUrl)
    }
  }, [showToast])

  useEffect(() => {
    loadAccounts()
  }, [loadAccounts])

  async function handleConnect() {
    setConnecting(true)
    try {
      const authUrl = await initiateSpotifyLink()
      window.location.href = authUrl
    } catch {
      showToast('Failed to start Spotify connection. Please try again.', 'error')
      setConnecting(false)
    }
  }

  function handleUnlinked(id: string) {
    setAccounts((prev) => prev.filter((a) => a.id !== id))
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Spotify Accounts
        </h1>
        <button
          onClick={loadAccounts}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition hover:text-gray-700 disabled:opacity-50 dark:text-brand-400 dark:hover:text-white"
          title="Refresh"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading ? (
        <LoadingSkeleton lines={3} />
      ) : accounts.length === 0 ? (
        <EmptyState
          icon={<Music className="h-10 w-10" />}
          title="No Spotify accounts linked"
          description="Connect a Spotify account to start analysing your music history."
          action={
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="flex items-center gap-2 rounded-lg bg-green-500 px-5 py-2.5 text-sm font-semibold text-white shadow transition hover:bg-green-400 disabled:opacity-50"
            >
              <Plus className="h-4 w-4" />
              {connecting ? 'Redirecting to Spotify…' : 'Connect Spotify Account'}
            </button>
          }
        />
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {accounts.map((account) => (
              <SpotifyAccountCard
                key={account.id}
                account={account}
                onUnlinked={handleUnlinked}
              />
            ))}
          </div>
          <div className="mt-6">
            <button
              onClick={handleConnect}
              disabled={connecting}
              className="flex items-center gap-2 rounded-lg bg-green-500 px-5 py-2.5 font-semibold text-white shadow transition hover:bg-green-400 disabled:opacity-50"
            >
              <Plus className="h-5 w-5" />
              {connecting ? 'Redirecting to Spotify…' : 'Connect Another Account'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
