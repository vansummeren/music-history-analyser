import { useEffect, useState } from 'react'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { useToast } from '../hooks/useToast'
import type { TableRow } from '../services/adminApi'
import { getTableStats } from '../services/adminApi'

const cardClass =
  'rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700'

export default function AdminPanelPage() {
  const { showToast } = useToast()
  const [tables, setTables] = useState<TableRow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getTableStats()
      .then((data) => setTables(data.tables))
      .catch(() => showToast('Failed to load table stats.', 'error'))
      .finally(() => setLoading(false))
  }, [showToast])

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Admin Panel</h1>

      <section className={cardClass}>
        <h2 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
          Database Tables
        </h2>
        <p className="mb-4 text-sm text-gray-500 dark:text-brand-400">
          Current row counts for all main database tables.
        </p>

        {loading ? (
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
    </div>
  )
}
