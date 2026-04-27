import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'

const packageJson = JSON.parse(
  readFileSync(new URL('./package.json', import.meta.url), 'utf-8'),
) as { version: string }

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(packageJson.version),
  },

  // Prevent Vite from obscuring Rust/Tauri error messages.
  clearScreen: false,

  server: {
    port: 5173,
    strictPort: true,
    host: '127.0.0.1',
    // Forward API requests to the Python backend in dev mode.
    // Tauri spawns the backend on a dynamic port, so we keep the
    // existing VITE_API_URL env-var approach.
  },

  // Use relative base so the Tauri production bundle resolves assets correctly.
  base: './',
})
