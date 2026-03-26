import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { BarChart2, Calendar, Cpu, Music } from 'lucide-react'
import EmptyState from '../components/EmptyState'
import LoadingSkeleton from '../components/LoadingSkeleton'
import StatCard from '../components/StatCard'
import { useToast } from '../hooks/useToast'
import { getAIConfigs } from '../services/aiApi'
import { getAnalyses } from '../services/analysisApi'
import { getSchedules } from '../services/scheduleApi'
import { getSpotifyAccounts } from '../services/spotifyApi'

interface DashboardData {
  spotifyCount: number
  aiConfigCount: number
  analysisCount: number
  activeScheduleCount: number
}

export default function DashboardPage() {
  const { showToast } = useToast()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const [spotify, aiConfigs, analyses, schedules] = await Promise.all([
          getSpotifyAccounts(),
          getAIConfigs(),
          getAnalyses(),
          getSchedules(),
        ])
        setData({
          spotifyCount: spotify.length,
          aiConfigCount: aiConfigs.length,
          analysisCount: analyses.length,
          activeScheduleCount: schedules.filter((s) => s.is_active).length,
        })
      } catch {
        showToast('Failed to load dashboard data.', 'error')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [showToast])

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="mb-6 text-2xl font-bold text-gray-900 dark:text-white">
        Dashboard
      </h1>

      {loading ? (
        <LoadingSkeleton lines={4} />
      ) : data ? (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              title="Spotify Accounts"
              value={data.spotifyCount}
              icon={<Music className="h-6 w-6" />}
              description="Linked accounts"
            />
            <StatCard
              title="AI Configs"
              value={data.aiConfigCount}
              icon={<Cpu className="h-6 w-6" />}
              description="Configured providers"
            />
            <StatCard
              title="Analyses"
              value={data.analysisCount}
              icon={<BarChart2 className="h-6 w-6" />}
              description="Total analyses"
            />
            <StatCard
              title="Active Schedules"
              value={data.activeScheduleCount}
              icon={<Calendar className="h-6 w-6" />}
              description="Running on schedule"
            />
          </div>

          {/* Quick-start call-to-action when nothing is set up */}
          {data.spotifyCount === 0 && (
            <div className="mt-8">
              <EmptyState
                icon={<Music className="h-10 w-10" />}
                title="Get started — link a Spotify account"
                description="Connect your Spotify account to start analysing your music history."
                action={
                  <Link
                    to="/spotify"
                    className="rounded-lg bg-green-500 px-5 py-2.5 text-sm font-semibold text-white shadow transition hover:bg-green-400"
                  >
                    Connect Spotify
                  </Link>
                }
              />
            </div>
          )}

          {/* Quick-nav tiles */}
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Link
              to="/spotify"
              className="flex items-center gap-4 rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 transition hover:ring-brand-400 dark:bg-brand-800/50 dark:ring-brand-700 dark:hover:ring-brand-400"
            >
              <Music className="h-8 w-8 text-green-500" />
              <div>
                <p className="font-semibold text-gray-900 dark:text-white">
                  Spotify Accounts
                </p>
                <p className="text-sm text-gray-500 dark:text-brand-400">
                  Manage linked accounts
                </p>
              </div>
            </Link>

            <Link
              to="/ai-configs"
              className="flex items-center gap-4 rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 transition hover:ring-brand-400 dark:bg-brand-800/50 dark:ring-brand-700 dark:hover:ring-brand-400"
            >
              <Cpu className="h-8 w-8 text-brand-500" />
              <div>
                <p className="font-semibold text-gray-900 dark:text-white">
                  AI Configs
                </p>
                <p className="text-sm text-gray-500 dark:text-brand-400">
                  Manage AI providers
                </p>
              </div>
            </Link>

            <Link
              to="/analyses"
              className="flex items-center gap-4 rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 transition hover:ring-brand-400 dark:bg-brand-800/50 dark:ring-brand-700 dark:hover:ring-brand-400"
            >
              <BarChart2 className="h-8 w-8 text-brand-500" />
              <div>
                <p className="font-semibold text-gray-900 dark:text-white">
                  Analyses
                </p>
                <p className="text-sm text-gray-500 dark:text-brand-400">
                  Create and run analyses
                </p>
              </div>
            </Link>

            <Link
              to="/schedules"
              className="flex items-center gap-4 rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200 transition hover:ring-brand-400 dark:bg-brand-800/50 dark:ring-brand-700 dark:hover:ring-brand-400"
            >
              <Calendar className="h-8 w-8 text-brand-500" />
              <div>
                <p className="font-semibold text-gray-900 dark:text-white">
                  Schedules
                </p>
                <p className="text-sm text-gray-500 dark:text-brand-400">
                  Automate your analyses
                </p>
              </div>
            </Link>
          </div>
        </>
      ) : null}
    </div>
  )
}
