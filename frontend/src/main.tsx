import React from 'react'
import ReactDOM from 'react-dom/client'
import axios from 'axios'
import App from './App.tsx'
import { API_BASE } from './config'
import './index.css'

// Capacitor 앱 등에서 원격 API 사용 시 axios 기본 baseURL 설정 (AuthContext, useChat 등)
if (API_BASE) {
  axios.defaults.baseURL = API_BASE
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

