import { NavLink } from 'react-router-dom'
import { BarChart2, Calendar, Cpu, LayoutDashboard, Music, ShieldCheck, X } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

interface Props {
  open: boolean
  onClose: () => void
}

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard', end: true },
  { to: '/spotify', icon: Music, label: 'Spotify Accounts', end: false },
  { to: '/ai-configs', icon: Cpu, label: 'AI Configs', end: false },
  { to: '/analyses', icon: BarChart2, label: 'Analyses', end: false },
  { to: '/schedules', icon: Calendar, label: 'Schedules', end: false },
]

export default function Sidebar({ open, onClose }: Props) {
  const { user } = useAuth()
  return (
    <>
      {/* Mobile backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-black/50 md:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={`fixed left-0 top-0 z-40 flex h-full w-64 flex-col border-r border-gray-200 bg-white transition-transform duration-200 dark:border-brand-800 dark:bg-brand-900 ${
          open ? 'translate-x-0' : '-translate-x-full'
        } md:translate-x-0`}
      >
        {/* Logo */}
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 dark:border-brand-800">
          <span className="text-lg font-bold text-brand-600 dark:text-white">
            🎵 Amadeus
          </span>
          <button
            onClick={onClose}
            className="rounded p-1 text-gray-500 transition hover:text-gray-700 dark:text-brand-400 dark:hover:text-white md:hidden"
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Nav links */}
        <nav className="flex-1 overflow-y-auto px-3 py-4" aria-label="Sidebar navigation">
          <ul className="space-y-1">
            {navItems.map(({ to, icon: Icon, label, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                      isActive
                        ? 'bg-brand-50 text-brand-700 dark:bg-brand-700/50 dark:text-white'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-brand-300 dark:hover:bg-brand-800 dark:hover:text-white'
                    }`
                  }
                >
                  <Icon className="h-4 w-4 shrink-0" />
                  {label}
                </NavLink>
              </li>
            ))}
            {user?.role === 'admin' && (
              <li>
                <NavLink
                  to="/admin"
                  end={false}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                      isActive
                        ? 'bg-brand-50 text-brand-700 dark:bg-brand-700/50 dark:text-white'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900 dark:text-brand-300 dark:hover:bg-brand-800 dark:hover:text-white'
                    }`
                  }
                >
                  <ShieldCheck className="h-4 w-4 shrink-0" />
                  Admin
                </NavLink>
              </li>
            )}
          </ul>
        </nav>
      </aside>
    </>
  )
}
