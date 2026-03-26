import { Route, Routes } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
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
    </Routes>
  )
}
