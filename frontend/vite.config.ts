import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // 모든 네트워크 인터페이스에서 접근 가능
    port: 5173,
    allowedHosts: [
      'uni2road.com',
      'www.uni2road.com',
      '3.107.178.26',
      'localhost'
    ],
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path,
        timeout: 0,  // SSE를 위해 타임아웃 제거
      }
    }
  }
})
