import type { ReactNode } from 'react'

interface Props {
  title: string
  value: string | number
  icon?: ReactNode
  description?: string
}

export default function StatCard({ title, value, icon, description }: Props) {
  return (
    <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-gray-500 dark:text-brand-300">
            {title}
          </p>
          <p className="mt-1 text-3xl font-bold text-gray-900 dark:text-white">
            {value}
          </p>
          {description && (
            <p className="mt-1 text-xs text-gray-400 dark:text-brand-400">
              {description}
            </p>
          )}
        </div>
        {icon && (
          <div className="text-brand-500 dark:text-brand-400">{icon}</div>
        )}
      </div>
    </div>
  )
}
