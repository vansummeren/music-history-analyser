import { useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { useToast } from '../hooks/useToast'
import type {
  AdminUserDetail,
  AdminUserSummary,
  TableRow,
} from '../services/adminApi'
import { getAdminUserDetail, getAdminUsers, getTableStats } from '../services/adminApi'

const cardClass =
  'rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700'

function StatusBadge({ status }: { status: string }) {
  const colours: Record<string, string> = {
    completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
    failed: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
    running: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
    pending: 'bg-gray-100 text-gray-600 dark:bg-brand-700 dark:text-brand-300',
  }
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-medium ${colours[status] ?? colours.pending}`}
    >
      {status}
    </span>
  )
}

function UserDetailPanel({
  detail,
  onBack,
}: {
  detail: AdminUserDetail
  onBack: () => void
}) {
  return (
    <div className="space-y-5">
      {/* Back button */}
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-sm text-brand-500 hover:underline dark:text-brand-400"
      >
        <ChevronLeft className="h-4 w-4" />
        Back to user list
      </button>

      {/* User header */}
      <section className={cardClass}>
        <h2 className="mb-1 text-lg font-semibold text-gray-900 dark:text-white">
          {detail.display_name ?? '(no name)'}
        </h2>
        <p className="text-sm text-gray-500 dark:text-brand-400">{detail.email ?? '—'}</p>
        <div className="mt-2 flex gap-3 text-xs text-gray-400 dark:text-brand-500">
          <span>Role: <strong className="text-gray-700 dark:text-brand-200">{detail.role}</strong></span>
          <span>Joined: {new Date(detail.created_at).toLocaleDateString()}</span>
        </div>
      </section>

      {/* Spotify accounts */}
      <section className={cardClass}>
        <h3 className="mb-3 font-semibold text-gray-900 dark:text-white">
          Spotify Accounts ({detail.spotify_accounts.length})
        </h3>
        {detail.spotify_accounts.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-brand-500">No Spotify accounts linked.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-brand-700">
                <th className="pb-2 text-left font-semibold text-gray-700 dark:text-brand-200">Account</th>
                <th className="pb-2 text-right font-semibold text-gray-700 dark:text-brand-200">Play events</th>
                <th className="pb-2 text-right font-semibold text-gray-700 dark:text-brand-200">Last polled</th>
                <th className="pb-2 text-right font-semibold text-gray-700 dark:text-brand-200">Polling</th>
              </tr>
            </thead>
            <tbody>
              {detail.spotify_accounts.map((acc) => (
                <tr key={acc.id} className="border-b border-gray-100 last:border-0 dark:border-brand-800">
                  <td className="py-2 text-gray-800 dark:text-brand-100">
                    {acc.display_name ?? acc.spotify_user_id}
                  </td>
                  <td className="py-2 text-right tabular-nums text-gray-600 dark:text-brand-300">
                    {acc.play_events_count.toLocaleString()}
                  </td>
                  <td className="py-2 text-right text-gray-500 dark:text-brand-400">
                    {acc.last_polled_at ? new Date(acc.last_polled_at).toLocaleString() : '—'}
                  </td>
                  <td className="py-2 text-right">
                    <span
                      className={acc.polling_enabled
                        ? 'text-green-600 dark:text-green-400'
                        : 'text-gray-400 dark:text-brand-500'}
                    >
                      {acc.polling_enabled ? 'enabled' : 'disabled'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* Analyses */}
      <section className={cardClass}>
        <h3 className="mb-3 font-semibold text-gray-900 dark:text-white">
          Analyses ({detail.analyses.length})
        </h3>
        {detail.analyses.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-brand-500">No analyses configured.</p>
        ) : (
          <div className="space-y-3">
            {detail.analyses.map((an) => (
              <div
                key={an.id}
                className="rounded-lg border border-gray-100 p-3 dark:border-brand-700"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-gray-900 dark:text-white">{an.name}</p>
                  <div className="flex shrink-0 items-center gap-2 text-xs text-gray-500 dark:text-brand-400">
                    <span>{an.run_count} run{an.run_count !== 1 ? 's' : ''}</span>
                    {an.last_run_status && <StatusBadge status={an.last_run_status} />}
                  </div>
                </div>
                <p className="mt-1 line-clamp-2 text-sm text-gray-500 dark:text-brand-400">
                  {an.prompt}
                </p>
                {an.last_run_at && (
                  <p className="mt-1 text-xs text-gray-400 dark:text-brand-500">
                    Last run: {new Date(an.last_run_at).toLocaleString()}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Schedules */}
      <section className={cardClass}>
        <h3 className="mb-3 font-semibold text-gray-900 dark:text-white">
          Schedules ({detail.schedules.length})
        </h3>
        {detail.schedules.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-brand-500">No schedules configured.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-brand-700">
                <th className="pb-2 text-left font-semibold text-gray-700 dark:text-brand-200">Analysis</th>
                <th className="pb-2 text-left font-semibold text-gray-700 dark:text-brand-200">Cron</th>
                <th className="pb-2 text-right font-semibold text-gray-700 dark:text-brand-200">Last ran</th>
                <th className="pb-2 text-right font-semibold text-gray-700 dark:text-brand-200">Active</th>
              </tr>
            </thead>
            <tbody>
              {detail.schedules.map((sc) => (
                <tr key={sc.id} className="border-b border-gray-100 last:border-0 dark:border-brand-800">
                  <td className="py-2 text-gray-800 dark:text-brand-100">
                    {sc.analysis_name ?? sc.analysis_id}
                  </td>
                  <td className="py-2 font-mono text-xs text-gray-600 dark:text-brand-300">
                    {sc.cron}
                  </td>
                  <td className="py-2 text-right text-gray-500 dark:text-brand-400">
                    {sc.last_run_at ? new Date(sc.last_run_at).toLocaleString() : 'Never'}
                  </td>
                  <td className="py-2 text-right">
                    <span
                      className={sc.is_active
                        ? 'text-green-600 dark:text-green-400'
                        : 'text-gray-400 dark:text-brand-500'}
                    >
                      {sc.is_active ? 'yes' : 'no'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

export default function AdminPanelPage() {
  const { showToast } = useToast()
  const [tables, setTables] = useState<TableRow[]>([])
  const [loadingTables, setLoadingTables] = useState(true)
  const [users, setUsers] = useState<AdminUserSummary[]>([])
  const [loadingUsers, setLoadingUsers] = useState(true)
  const [selectedUser, setSelectedUser] = useState<AdminUserDetail | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  useEffect(() => {
    getTableStats()
      .then((data) => setTables(data.tables))
      .catch(() => showToast('Failed to load table stats.', 'error'))
      .finally(() => setLoadingTables(false))

    getAdminUsers()
      .then((data) => setUsers(data))
      .catch(() => showToast('Failed to load user list.', 'error'))
      .finally(() => setLoadingUsers(false))
  }, [showToast])

  async function handleSelectUser(userId: string) {
    setLoadingDetail(true)
    try {
      const detail = await getAdminUserDetail(userId)
      setSelectedUser(detail)
    } catch {
      showToast('Failed to load user details.', 'error')
    } finally {
      setLoadingDetail(false)
    }
  }

  if (selectedUser) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Admin Panel</h1>
        <UserDetailPanel detail={selectedUser} onBack={() => setSelectedUser(null)} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Admin Panel</h1>

      {/* Table row counts */}
      <section className={cardClass}>
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
          Database Tables
        </h2>
        <p className="mb-4 text-sm text-gray-500 dark:text-brand-400">
          Current row counts for all main database tables.
        </p>

        {loadingTables ? (
          <LoadingSkeleton lines={6} />
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-brand-700">
                <th className="pb-2 text-left font-semibold text-gray-700 dark:text-brand-200">
                  Table
                </th>
                <th className="pb-2 text-right font-semibold text-gray-700 dark:text-brand-200">
                  Rows
                </th>
              </tr>
            </thead>
            <tbody>
              {tables.map(({ table, row_count }) => (
                <tr
                  key={table}
                  className="border-b border-gray-100 last:border-0 dark:border-brand-800"
                >
                  <td className="py-2 font-mono text-gray-800 dark:text-brand-100">{table}</td>
                  <td className="py-2 text-right tabular-nums text-gray-600 dark:text-brand-300">
                    {row_count.toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* User list */}
      <section className={cardClass}>
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
          Users
        </h2>
        <p className="mb-4 text-sm text-gray-500 dark:text-brand-400">
          Click a user to view their data.
        </p>

        {loadingUsers ? (
          <LoadingSkeleton lines={4} />
        ) : users.length === 0 ? (
          <p className="text-sm text-gray-400 dark:text-brand-500">No users found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-brand-700">
                <th className="pb-2 text-left font-semibold text-gray-700 dark:text-brand-200">User</th>
                <th className="pb-2 text-right font-semibold text-gray-700 dark:text-brand-200">Accounts</th>
                <th className="pb-2 text-right font-semibold text-gray-700 dark:text-brand-200">Analyses</th>
                <th className="pb-2 text-right font-semibold text-gray-700 dark:text-brand-200">Play events</th>
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr
                  key={u.id}
                  className="cursor-pointer border-b border-gray-100 transition hover:bg-gray-50 last:border-0 dark:border-brand-800 dark:hover:bg-brand-700/30"
                  onClick={() => handleSelectUser(u.id)}
                >
                  <td className="py-2">
                    <p className="font-medium text-gray-900 dark:text-brand-100">
                      {u.display_name ?? '(no name)'}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-brand-500">{u.email ?? '—'}</p>
                  </td>
                  <td className="py-2 text-right tabular-nums text-gray-600 dark:text-brand-300">
                    {u.spotify_accounts_count}
                  </td>
                  <td className="py-2 text-right tabular-nums text-gray-600 dark:text-brand-300">
                    {u.analyses_count}
                  </td>
                  <td className="py-2 text-right tabular-nums text-gray-600 dark:text-brand-300">
                    {u.play_events_count.toLocaleString()}
                  </td>
                  <td className="py-2 pl-2 text-right text-gray-400 dark:text-brand-500">
                    {loadingDetail ? (
                      <span className="text-xs">…</span>
                    ) : (
                      <ChevronRight className="ml-auto h-4 w-4" />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}
