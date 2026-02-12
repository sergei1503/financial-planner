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
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'ui-vendor': ['lucide-react', 'sonner', 'date-fns'],
          'charts': ['recharts'],
          'clerk': ['@clerk/clerk-react'],
          'query': ['@tanstack/react-query'],
        },
      },
    },
    // Enable source maps for better debugging in production
    sourcemap: true,
    // Increase chunk size warning limit (default 500KB)
    chunkSizeWarningLimit: 1000,
  },
})
