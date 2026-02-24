import React from 'react'
import ReactDOM from 'react-dom/client'
import axios from 'axios'
import App from './App.tsx'
import { API_BASE, isCapacitorApp } from './config'
import { setupAxiosAuth } from './utils/setupAxiosAuth'
import './index.css'

// Capacitor 앱 등에서 원격 API 사용 시 axios 기본 baseURL 설정 (AuthContext, useChat 등)
if (API_BASE) {
  axios.defaults.baseURL = API_BASE
}
setupAxiosAuth()

// 앱이 OAuth 딥링크(uniroad://oauth-callback?code=xxx)로 열렸을 때 /chat?code=xxx 로 이동해 콜백 처리
if (isCapacitorApp()) {
  import('@capacitor/app').then(({ App }) => {
    App.addListener('appUrlOpen', (event) => {
      const url = event.url
      if (!url || !url.includes('oauth-callback')) return
      try {
        const u = new URL(url)
        const code = u.searchParams.get('code')
        if (code) {
          const origin = window.location.origin
          window.location.href = `${origin}/chat?code=${encodeURIComponent(code)}`
        }
      } catch (_) {}
    })
  }).catch(() => {})
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

