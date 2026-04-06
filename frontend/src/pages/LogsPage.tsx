import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, RefreshCw, Search } from 'lucide-react'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { useToast } from '../hooks/useToast'
import type { AppLogEntry, LogsFilter } from '../services/adminApi'
import { getAdminLogs } from '../services/adminApi'

const LEVELS = ['', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
const PAGE_SIZE = 100

const LEVEL_COLOURS: Record<string, string> = {
  DEBUG: 'text-gray-400 dark:text-brand-500',
  INFO: 'text-blue-600 dark:text-blue-400',
  WARNING: 'text-yellow-600 dark:text-yellow-400',
  ERROR: 'text-red-600 dark:text-red-400',
  CRITICAL: 'text-red-700 font-bold dark:text-red-300',
}

export default function LogsPage() {
  const { showToast } = useToast()
  const [logs, setLogs] = useState<AppLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(0)

  // Filter state
  const [level, setLevel] = useState('')
  const [service, setService] = useState('')
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const load = useCallback(
    async (currentPage: number, filter: LogsFilter) => {
      setLoading(true)
      try {
        const result = await getAdminLogs({
          ...filter,
          limit: PAGE_SIZE,
          offset: currentPage * PAGE_SIZE,
        })
        setLogs(result.items)
        setTotal(result.total)
      } catch {
        showToast('Failed to load logs.', 'error')
      } finally {
        setLoading(false)
      }
    },
    [showToast],
  )

  // Debounce search input
  function handleSearchChange(value: string) {
    setSearchInput(value)
    if (searchRef.current) clearTimeout(searchRef.current)
    searchRef.current = setTimeout(() => {
      setSearch(value)
      setPage(0)
    }, 400)
  }

  useEffect(() => {
    load(page, { level: level || undefined, service: service || undefined, search: search || undefined })
  }, [load, page, level, service, search])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Application Logs</h1>
        <button
          onClick={() => load(page, { level: level || undefined, service: service || undefined, search: search || undefined })}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-500 transition hover:text-gray-700 disabled:opacity-50 dark:text-brand-400 dark:hover:text-white"
          title="Refresh"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        {/* Level filter */}
        <select
          value={level}
          onChange={(e) => { setLevel(e.target.value); setPage(0) }}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-brand-700 dark:bg-brand-800 dark:text-brand-200"
        >
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {l || 'All levels'}
            </option>
          ))}
        </select>

        {/* Service filter */}
        <input
          type="text"
          placeholder="Service (e.g. backend)"
          value={service}
          onChange={(e) => { setService(e.target.value); setPage(0) }}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-brand-700 dark:bg-brand-800 dark:text-brand-200 dark:placeholder-brand-500"
        />

        {/* Search */}
        <div className="relative flex-1 min-w-48">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400 dark:text-brand-500" />
          <input
            type="text"
            placeholder="Search message or logger…"
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
            className="w-full rounded-lg border border-gray-300 bg-white py-1.5 pl-9 pr-3 text-sm text-gray-700 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-brand-700 dark:bg-brand-800 dark:text-brand-200 dark:placeholder-brand-500"
          />
        </div>
      </div>

      {/* Results summary */}
      <p className="text-sm text-gray-500 dark:text-brand-400">
        {loading ? 'Loading…' : `${total.toLocaleString()} record${total !== 1 ? 's' : ''} found`}
      </p>

      {/* Log table */}
      {loading ? (
        <LoadingSkeleton lines={8} />
      ) : logs.length === 0 ? (
        <p className="rounded-xl border border-gray-200 bg-white p-6 text-center text-sm text-gray-400 dark:border-brand-700 dark:bg-brand-800/50 dark:text-brand-500">
          No log entries match the current filters.
        </p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-gray-200 bg-white dark:border-brand-700 dark:bg-brand-800/50">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-brand-700 bg-gray-50 dark:bg-brand-800">
                <th className="px-4 py-2 text-left font-semibold text-gray-700 dark:text-brand-200 whitespace-nowrap">
                  Time
                </th>
                <th className="px-4 py-2 text-left font-semibold text-gray-700 dark:text-brand-200">
                  Level
                </th>
                <th className="px-4 py-2 text-left font-semibold text-gray-700 dark:text-brand-200">
                  Service
                </th>
                <th className="px-4 py-2 text-left font-semibold text-gray-700 dark:text-brand-200">
                  Logger
                </th>
                <th className="px-4 py-2 text-left font-semibold text-gray-700 dark:text-brand-200 w-full">
                  Message
                </th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr
                  key={log.id}
                  className="border-b border-gray-100 last:border-0 dark:border-brand-800 hover:bg-gray-50 dark:hover:bg-brand-700/20"
                >
                  <td className="px-4 py-2 tabular-nums text-gray-500 dark:text-brand-400 whitespace-nowrap">
                    {new Date(log.created_at).toLocaleString()}
                  </td>
                  <td className={`px-4 py-2 font-mono font-semibold whitespace-nowrap ${LEVEL_COLOURS[log.level] ?? ''}`}>
                    {log.level}
                  </td>
                  <td className="px-4 py-2 text-gray-600 dark:text-brand-300 whitespace-nowrap">
                    {log.service}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-gray-500 dark:text-brand-400 whitespace-nowrap max-w-48 truncate">
                    {log.logger_name}
                  </td>
                  <td className="px-4 py-2 text-gray-800 dark:text-brand-100">
                    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed">
                      {log.message}
                    </pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-500 dark:text-brand-400">
            Page {page + 1} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
              className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-600 transition hover:bg-gray-50 disabled:opacity-40 dark:border-brand-700 dark:text-brand-300 dark:hover:bg-brand-700"
            >
              <ChevronLeft className="h-4 w-4" />
              Previous
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1 || loading}
              className="flex items-center gap-1 rounded-lg border border-gray-300 px-3 py-1.5 text-sm text-gray-600 transition hover:bg-gray-50 disabled:opacity-40 dark:border-brand-700 dark:text-brand-300 dark:hover:bg-brand-700"
            >
              Next
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
