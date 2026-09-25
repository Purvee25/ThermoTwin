import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const API_TARGET = process.env.THERMOTWIN_API ?? 'http://localhost:8010'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: API_TARGET, rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
})
