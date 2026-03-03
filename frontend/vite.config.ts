import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  // Capacitor 앱 빌드 시 상대 경로 사용 (WebView에서 asset 로딩 안정)
  base: mode === 'capacitor' ? './' : '/',
  plugins: [react()],
  server: {
    host: '0.0.0.0', // 모바일 접속 허용
    port: 8150,
    allowedHosts: true, // 같은 와이파이에서 로컬 IP(192.168.x.x 등)로 접속 허용
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path,
        timeout: 0,  // SSE를 위해 타임아웃 제거
      }
    }
  }
}))
