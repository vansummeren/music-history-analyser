import { Outlet, Route, Routes } from 'react-router-dom'
import AppShell from './components/AppShell'
import ProtectedRoute from './components/ProtectedRoute'
import { AuthProvider } from './hooks/useAuth'
import { ToastProvider } from './hooks/useToast'
import AIConfigPage from './pages/AIConfigPage'
import AnalysisPage from './pages/AnalysisPage'
import AuthCallbackPage from './pages/AuthCallbackPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'
import RunResultPage from './pages/RunResultPage'
import SchedulesPage from './pages/SchedulesPage'
import SpotifyAccountsPage from './pages/SpotifyAccountsPage'

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AppShell>
                  <Outlet />
                </AppShell>
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="spotify" element={<SpotifyAccountsPage />} />
            <Route path="ai-configs" element={<AIConfigPage />} />
            <Route path="analyses" element={<AnalysisPage />} />
            <Route
              path="analyses/:analysisId/runs/:runId"
              element={<RunResultPage />}
            />
            <Route path="schedules" element={<SchedulesPage />} />
          </Route>
        </Routes>
      </ToastProvider>
    </AuthProvider>
  )
}
