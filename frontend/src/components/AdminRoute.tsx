import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import LoadingSkeleton from './LoadingSkeleton'

interface Props {
  children: React.ReactNode
}

export default function AdminRoute({ children }: Props) {
  const { user, loading } = useAuth()

  if (loading) return <LoadingSkeleton lines={4} />
  if (!user || user.role !== 'admin') {
    return <Navigate to="/" replace />
  }
  return <>{children}</>
}
