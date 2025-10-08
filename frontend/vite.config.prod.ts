import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  preview: {
    host: '0.0.0.0',
    port: 80,
    allowedHosts: [
      'alreasense-production.up.railway.app',
      'localhost',
      '127.0.0.1',
      '0.0.0.0'
    ],
  },
})
