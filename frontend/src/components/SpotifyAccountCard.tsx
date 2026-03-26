import { useState } from 'react'
import { Music, Unlink } from 'lucide-react'
import type { SpotifyAccount } from '../services/spotifyApi'
import { unlinkSpotifyAccount } from '../services/spotifyApi'

interface Props {
  account: SpotifyAccount
  onUnlinked: (id: string) => void
}

export default function SpotifyAccountCard({ account, onUnlinked }: Props) {
  const [unlinking, setUnlinking] = useState(false)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <div className="flex items-center justify-between rounded-xl border border-brand-700 bg-brand-800 p-4 shadow">
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
        </div>
      </div>

      <div className="flex flex-col items-end gap-1">
        <button
          onClick={handleUnlink}
          disabled={unlinking}
          className="flex items-center gap-1.5 rounded-lg bg-red-600/20 px-3 py-1.5 text-sm font-medium text-red-400 transition hover:bg-red-600/40 disabled:opacity-50"
        >
          <Unlink className="h-4 w-4" />
          {unlinking ? 'Disconnecting…' : 'Disconnect'}
        </button>
        {error && <p className="text-xs text-red-400">{error}</p>}
      </div>
    </div>
  )
}
