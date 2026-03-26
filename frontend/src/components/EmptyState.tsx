import type { ReactNode } from 'react'

interface Props {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
  className?: string
}

export default function EmptyState({ icon, title, description, action, className = '' }: Props) {
  return (
    <div className={`flex flex-col items-center justify-center rounded-xl border border-dashed border-gray-300 py-12 text-center dark:border-brand-700 ${className}`}>
      {icon && (
        <div className="mb-3 text-gray-400 dark:text-brand-400">{icon}</div>
      )}
      <p className="text-lg font-semibold text-gray-700 dark:text-brand-200">
        {title}
      </p>
      {description && (
        <p className="mt-1 text-sm text-gray-500 dark:text-brand-400">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
