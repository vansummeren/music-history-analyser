import { LogOut, Menu, Moon, Sun } from 'lucide-react'
import type { UserProfile } from '../services/authApi'

interface Props {
  user: UserProfile
  darkMode: boolean
  onToggleDark: () => void
  onMenuToggle: () => void
  onLogout: () => void
}

export default function Header({
  user,
  darkMode,
  onToggleDark,
  onMenuToggle,
  onLogout,
}: Props) {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-gray-200 bg-white/90 px-4 py-3 backdrop-blur dark:border-brand-800 dark:bg-brand-900/90">
      {/* Mobile hamburger */}
      <button
        onClick={onMenuToggle}
        className="rounded p-1.5 text-gray-500 transition hover:text-gray-700 dark:text-brand-400 dark:hover:text-white md:hidden"
        aria-label="Toggle navigation menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      {/* Spacer for desktop (sidebar occupies the left) */}
      <div className="hidden md:block" />

      {/* Right: dark mode toggle + user info + logout */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleDark}
          className="rounded p-1.5 text-gray-500 transition hover:text-gray-700 dark:text-brand-400 dark:hover:text-white"
          aria-label={darkMode ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {darkMode ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </button>

        <div className="hidden flex-col items-end sm:flex">
          <span className="text-sm font-medium text-gray-900 dark:text-white">
            {user.display_name ?? user.email ?? 'User'}
          </span>
          <span className="text-xs capitalize text-gray-500 dark:text-brand-400">
            {user.role}
          </span>
        </div>

        <button
          onClick={onLogout}
          className="flex items-center gap-1.5 rounded-lg bg-gray-100 px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-200 dark:bg-brand-800 dark:text-brand-300 dark:hover:bg-brand-700 dark:hover:text-white"
          aria-label="Log out"
        >
          <LogOut className="h-4 w-4" />
          <span className="hidden sm:inline">Log out</span>
        </button>
      </div>
    </header>
  )
}
