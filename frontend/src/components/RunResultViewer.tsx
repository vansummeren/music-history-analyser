import type { AnalysisRun } from '../services/analysisApi'

interface Props {
  run: AnalysisRun
}

export default function RunResultViewer({ run }: Props) {
  const statusColor = {
    pending: 'text-yellow-300',
    running: 'text-blue-300',
    completed: 'text-green-300',
    failed: 'text-red-300',
  }[run.status]

  return (
    <div className="rounded-lg bg-white/10 p-4 text-sm">
      <div className="mb-2 flex items-center justify-between">
        <span className={`font-semibold capitalize ${statusColor}`}>
          {run.status}
        </span>
        {run.model && (
          <span className="text-xs text-brand-300">{run.model}</span>
        )}
      </div>

      {run.status === 'completed' && run.result_text && (
        <p className="whitespace-pre-wrap text-white">{run.result_text}</p>
      )}

      {run.status === 'failed' && run.error && (
        <p className="text-red-300">Error: {run.error}</p>
      )}

      {(run.input_tokens !== null || run.output_tokens !== null) && (
        <p className="mt-2 text-xs text-brand-400">
          Tokens — in: {run.input_tokens ?? '–'} / out:{' '}
          {run.output_tokens ?? '–'}
        </p>
      )}

      {run.completed_at && (
        <p className="mt-1 text-xs text-brand-400">
          Completed: {new Date(run.completed_at).toLocaleString()}
        </p>
      )}
    </div>
  )
}
