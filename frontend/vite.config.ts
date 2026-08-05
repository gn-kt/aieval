import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/register': 'http://127.0.0.1:8000',
      '/login': 'http://127.0.0.1:8000',
      '/me': 'http://127.0.0.1:8000',
      '/ask': 'http://127.0.0.1:8000',
      '/result': 'http://127.0.0.1:8000',
      '/tasks': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/stats': 'http://127.0.0.1:8000',
      '/metrics': 'http://127.0.0.1:8000',
      '/sessions': 'http://127.0.0.1:8000',
      '/evaluator': 'http://127.0.0.1:8000',
      '/advisor': 'http://127.0.0.1:8000',
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})
