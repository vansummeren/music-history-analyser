import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, CheckCircle, Clock, XCircle } from 'lucide-react'
import LoadingSkeleton from '../components/LoadingSkeleton'
import { useToast } from '../hooks/useToast'
import type { AnalysisRun } from '../services/analysisApi'
import { getRun } from '../services/analysisApi'

const statusConfig = {
  pending: {
    label: 'Pending',
    icon: Clock,
    color: 'text-yellow-500 dark:text-yellow-300',
  },
  running: {
    label: 'Running',
    icon: Clock,
    color: 'text-blue-500 dark:text-blue-300',
  },
  completed: {
    label: 'Completed',
    icon: CheckCircle,
    color: 'text-green-500 dark:text-green-300',
  },
  failed: {
    label: 'Failed',
    icon: XCircle,
    color: 'text-red-500 dark:text-red-300',
  },
}

export default function RunResultPage() {
  const { analysisId, runId } = useParams<{
    analysisId: string
    runId: string
  }>()
  const { showToast } = useToast()
  const [run, setRun] = useState<AnalysisRun | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!analysisId || !runId) return
    setLoading(true)
    getRun(analysisId, runId)
      .then(setRun)
      .catch(() => showToast('Failed to load run result.', 'error'))
      .finally(() => setLoading(false))
  }, [analysisId, runId, showToast])

  const status = run ? statusConfig[run.status] : null

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 flex items-center gap-3">
        <Link
          to="/analyses"
          className="flex items-center gap-1 text-sm text-gray-500 transition hover:text-gray-700 dark:text-brand-300 dark:hover:text-white"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Analyses
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Run Result
        </h1>
      </div>

      {loading ? (
        <LoadingSkeleton lines={5} />
      ) : run && status ? (
        <div className="rounded-xl bg-white p-6 shadow-sm ring-1 ring-gray-200 dark:bg-brand-800/50 dark:ring-brand-700">
          {/* Status */}
          <div className="mb-4 flex items-center gap-2">
            <status.icon className={`h-5 w-5 ${status.color}`} />
            <span className={`font-semibold capitalize ${status.color}`}>
              {status.label}
            </span>
            {run.model && (
              <span className="ml-auto text-xs text-gray-400 dark:text-brand-400">
                {run.model}
              </span>
            )}
          </div>

          {/* Result text */}
          {run.status === 'completed' && run.result_text && (
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <p className="whitespace-pre-wrap text-gray-800 dark:text-brand-100">
                {run.result_text}
              </p>
            </div>
          )}

          {/* Error */}
          {run.status === 'failed' && run.error && (
            <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-900/20 dark:text-red-300">
              {run.error}
            </p>
          )}

          {/* Metadata */}
          <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-gray-100 pt-4 text-sm dark:border-brand-700">
            {run.input_tokens !== null && (
              <>
                <dt className="text-gray-500 dark:text-brand-400">
                  Input tokens
                </dt>
                <dd className="font-medium text-gray-900 dark:text-white">
                  {run.input_tokens}
                </dd>
              </>
            )}
            {run.output_tokens !== null && (
              <>
                <dt className="text-gray-500 dark:text-brand-400">
                  Output tokens
                </dt>
                <dd className="font-medium text-gray-900 dark:text-white">
                  {run.output_tokens}
                </dd>
              </>
            )}
            {run.started_at && (
              <>
                <dt className="text-gray-500 dark:text-brand-400">Started</dt>
                <dd className="font-medium text-gray-900 dark:text-white">
                  {new Date(run.started_at).toLocaleString()}
                </dd>
              </>
            )}
            {run.completed_at && (
              <>
                <dt className="text-gray-500 dark:text-brand-400">
                  Completed
                </dt>
                <dd className="font-medium text-gray-900 dark:text-white">
                  {new Date(run.completed_at).toLocaleString()}
                </dd>
              </>
            )}
          </dl>
        </div>
      ) : (
        <p className="text-gray-500 dark:text-brand-300">Run not found.</p>
      )}
    </div>
  )
}
