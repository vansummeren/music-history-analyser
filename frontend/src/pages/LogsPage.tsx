import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, ChevronDown, RefreshCw, Search } from 'lucide-react'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { useToast } from '../hooks/useToast'
import type { AppLogEntry, LogsFilter } from '../services/adminApi'
import { getAdminLogs, getAdminLogServices } from '../services/adminApi'

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
  const [selectedServices, setSelectedServices] = useState<string[]>([])
  const [availableServices, setAvailableServices] = useState<string[]>([])
  const [serviceDropdownOpen, setServiceDropdownOpen] = useState(false)
  const serviceDropdownRef = useRef<HTMLDivElement>(null)
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // AbortController ref — cancels the previous in-flight request before starting a new one
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(
    async (currentPage: number, filter: LogsFilter) => {
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setLoading(true)
      try {
        const result = await getAdminLogs(
          {
            ...filter,
            limit: PAGE_SIZE,
            offset: currentPage * PAGE_SIZE,
          },
          controller.signal,
        )
        setLogs(result.items)
        setTotal(result.total)
      } catch {
        if (controller.signal.aborted) return
        showToast('Failed to load logs.', 'error')
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    },
    [showToast],
  )

  // Fetch distinct service names once on mount
  useEffect(() => {
    getAdminLogServices()
      .then(setAvailableServices)
      .catch(() => { /* non-critical — dropdown stays empty */ })
  }, [])

  // Close service dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (serviceDropdownRef.current && !serviceDropdownRef.current.contains(e.target as Node)) {
        setServiceDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Debounce search input
  function handleSearchChange(value: string) {
    setSearchInput(value)
    if (searchRef.current) clearTimeout(searchRef.current)
    searchRef.current = setTimeout(() => {
      setSearch(value)
      setPage(0)
    }, 400)
  }

  function toggleService(svc: string) {
    setSelectedServices((prev) =>
      prev.includes(svc) ? prev.filter((s) => s !== svc) : [...prev, svc],
    )
    setPage(0)
  }

  function clearServices() {
    setSelectedServices([])
    setPage(0)
  }

  useEffect(() => {
    load(page, {
      level: level || undefined,
      service: selectedServices.length > 0 ? selectedServices : undefined,
      search: search || undefined,
    })
    return () => { abortRef.current?.abort() }
  }, [load, page, level, selectedServices, search])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Application Logs</h1>
        <button
          onClick={() => load(page, {
            level: level || undefined,
            service: selectedServices.length > 0 ? selectedServices : undefined,
            search: search || undefined,
          })}
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

        {/* Service multi-select dropdown */}
        <div className="relative" ref={serviceDropdownRef}>
          <button
            type="button"
            onClick={() => setServiceDropdownOpen((o) => !o)}
            className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-brand-700 dark:bg-brand-800 dark:text-brand-200"
          >
            <span>
              {selectedServices.length === 0
                ? 'All services'
                : selectedServices.length === 1
                  ? selectedServices[0]
                  : `${selectedServices.length} services`}
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-gray-400 dark:text-brand-500" />
          </button>

          {serviceDropdownOpen && (
            <div className="absolute left-0 top-full z-20 mt-1 min-w-48 rounded-lg border border-gray-200 bg-white py-1 shadow-lg dark:border-brand-700 dark:bg-brand-800">
              {availableServices.length === 0 ? (
                <p className="px-3 py-2 text-xs text-gray-400 dark:text-brand-500">No services found</p>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={clearServices}
                    className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 dark:text-brand-200 dark:hover:bg-brand-700"
                  >
                    <span className={`h-4 w-4 rounded border flex items-center justify-center text-xs ${selectedServices.length === 0 ? 'border-brand-500 bg-brand-500 text-white' : 'border-gray-300 dark:border-brand-600'}`}>
                      {selectedServices.length === 0 && '✓'}
                    </span>
                    All services
                  </button>
                  <div className="my-1 border-t border-gray-100 dark:border-brand-700" />
                  {availableServices.map((svc) => (
                    <button
                      key={svc}
                      type="button"
                      onClick={() => toggleService(svc)}
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 dark:text-brand-200 dark:hover:bg-brand-700"
                    >
                      <span className={`h-4 w-4 rounded border flex items-center justify-center text-xs ${selectedServices.includes(svc) ? 'border-brand-500 bg-brand-500 text-white' : 'border-gray-300 dark:border-brand-600'}`}>
                        {selectedServices.includes(svc) && '✓'}
                      </span>
                      {svc}
                    </button>
                  ))}
                </>
              )}
            </div>
          )}
        </div>

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
