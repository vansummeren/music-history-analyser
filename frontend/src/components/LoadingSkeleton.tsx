const LINE_WIDTHS = ['100%', '80%', '55%'] as const

interface Props {
  lines?: number
  className?: string
}

export default function LoadingSkeleton({ lines = 3, className = '' }: Props) {
  return (
    <div
      className={`animate-pulse space-y-3 ${className}`}
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-4 rounded bg-gray-200 dark:bg-brand-700/60"
          style={{ width: LINE_WIDTHS[i % LINE_WIDTHS.length] }}
        />
      ))}
    </div>
  )
}
