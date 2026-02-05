import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 8147,
    allowedHosts: [
      'uni2road.com',
      'www.uni2road.com',
      '3.107.178.26',
      'localhost'
    ],
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path,
        timeout: 0,  // SSE를 위해 타임아웃 제거
      }
    }
  }
})
