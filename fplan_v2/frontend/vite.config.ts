import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3034,
    proxy: {
      '/api': {
        target: 'http://localhost:8034',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8034',
        changeOrigin: true,
      },
    },
  },
})
