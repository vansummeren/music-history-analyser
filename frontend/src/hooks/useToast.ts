import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from 'react'

export type ToastType = 'success' | 'error' | 'info'

export interface ToastMessage {
  id: string
  message: string
  type: ToastType
}

interface ToastContextValue {
  toasts: ToastMessage[]
  showToast: (message: string, type?: ToastType) => void
  dismissToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  // Track timeout IDs so they can be cancelled on manual dismiss
  const timeoutsRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const dismissToast = useCallback((id: string) => {
    const existing = timeoutsRef.current.get(id)
    if (existing !== undefined) {
      clearTimeout(existing)
      timeoutsRef.current.delete(id)
    }
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback(
    (message: string, type: ToastType = 'info') => {
      const id = crypto.randomUUID()
      setToasts((prev) => [...prev, { id, message, type }])
      const timer = setTimeout(() => {
        timeoutsRef.current.delete(id)
        setToasts((prev) => prev.filter((t) => t.id !== id))
      }, 4000)
      timeoutsRef.current.set(id, timer)
    },
    [],
  )

  return createElement(
    ToastContext.Provider,
    { value: { toasts, showToast, dismissToast } },
    children,
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used within ToastProvider')
  return ctx
}
