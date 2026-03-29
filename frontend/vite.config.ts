import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const pkg = JSON.parse(
  readFileSync(resolve(__dirname, 'package.json'), 'utf-8'),
) as { version: string }

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
    __BUILD_NUMBER__: JSON.stringify(process.env['BUILD_NUMBER'] ?? 'dev'),
    __BUILD_DATE__: JSON.stringify(
      process.env['BUILD_DATE'] ?? 'unknown',
    ),
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        // In Docker Compose the backend is reachable via its service name.
        // Outside Docker (plain `npm run dev`) the backend is on localhost:8000.
        target: process.env['VITE_BACKEND_URL'] ?? 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
})
