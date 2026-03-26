import { Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import AIConfigPage from './pages/AIConfigPage'
import AnalysisPage from './pages/AnalysisPage'
import AuthCallbackPage from './pages/AuthCallbackPage'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import SpotifyAccountsPage from './pages/SpotifyAccountsPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/spotify"
        element={
          <ProtectedRoute>
            <SpotifyAccountsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ai-configs"
        element={
          <ProtectedRoute>
            <AIConfigPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/analyses"
        element={
          <ProtectedRoute>
            <AnalysisPage />
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}
