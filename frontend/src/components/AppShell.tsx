import { useEffect, useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import Header from './Header'
import Sidebar from './Sidebar'
import Toast from './Toast'
import { useAuth } from '../hooks/useAuth'

interface Props {
  children: ReactNode
}

export default function AppShell({ children }: Props) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem('dark-mode')
      return stored !== null ? stored === 'true' : true
    } catch {
      return true // default dark if localStorage unavailable
    }
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
    try {
      localStorage.setItem('dark-mode', String(darkMode))
    } catch {
      // localStorage may be unavailable in some environments
    }
  }, [darkMode])

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  if (!user) return null

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-brand-900">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main content area — offset by sidebar width on desktop */}
      <div className="flex flex-1 flex-col overflow-hidden md:ml-64">
        <Header
          user={user}
          darkMode={darkMode}
          onToggleDark={() => setDarkMode((d) => !d)}
          onMenuToggle={() => setSidebarOpen((o) => !o)}
          onLogout={handleLogout}
        />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>

      <Toast />
    </div>
  )
}
