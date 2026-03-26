import { getLoginUrl } from '../services/authApi'

export default function LoginPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-br from-brand-900 to-brand-700 text-white">
      <h1 className="text-4xl font-bold tracking-tight">Music History Analyser</h1>
      <p className="mt-4 text-brand-200">Sign in to continue</p>
      <a
        href={getLoginUrl()}
        className="mt-8 rounded-lg bg-white px-6 py-3 font-semibold text-brand-900 shadow transition hover:bg-brand-100"
      >
        Sign in
      </a>
    </main>
  )
}
