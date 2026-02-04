import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import LandingPage from './pages/LandingPage'
import ChatPage from './pages/ChatPage'
import AdminPage from './pages/AdminPage'
import AdminUploadPage from './pages/AdminUploadPage'
import AgentAdminPage from './pages/AgentAdminPage'
import AdminAgentPage from './pages/AdminAgentPage'
import AuthPage from './pages/AuthPage'
import TimingDashboard from './pages/TimingDashboard'
import AutoReplyPage from './pages/AutoReplyPage'
import AnalyticsDashboard from './pages/AnalyticsDashboard'
import AdminAnalytics from './pages/AdminAnalytics'
import { useEffect } from 'react'
import { initializeTracking, trackPageView } from './utils/tracking'

// 보호된 라우트 (로그인 필요)
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, loading } = useAuth()
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">로딩 중...</p>
        </div>
      </div>
    )
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/auth" replace />
  }
  
  return <>{children}</>
}

// 관리자 전용 라우트 (김도균만 접근 가능)
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, loading } = useAuth()
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">로딩 중...</p>
        </div>
      </div>
    )
  }
  
  if (!isAuthenticated) {
    console.warn('❌ 인증되지 않음, /auth로 리다이렉트')
    return <Navigate to="/auth" replace />
  }
  
  // 관리자 확인 (이름 또는 이메일로 확인)
  const isAdmin = user?.name === '김도균' || user?.email === 'herry0515@naver.com'
  
  if (!isAdmin) {
    console.warn(`❌ 관리자 아님 (name: ${user?.name}, email: ${user?.email}), /chat/login으로 리다이렉트`)
    return <Navigate to="/chat/login" replace />
  }
  
  console.log('✅ 관리자 접근 허용:', user?.name)
  return <>{children}</>
}

// 페이지 추적 컴포넌트
function PageTracker() {
  const location = useLocation()
  
  useEffect(() => {
    trackPageView(location.pathname)
  }, [location])
  
  return null
}

function App() {
  useEffect(() => {
    // 추적 초기화
    initializeTracking()
  }, [])
  
  return (
    <BrowserRouter>
      <AuthProvider>
        <PageTracker />
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/" element={<LandingPage />} />
          
          {/* 로그인 후 채팅 페이지 */}
          <Route
            path="/chat/login/admin"
            element={
              <AdminRoute>
                <AdminPage />
              </AdminRoute>
            }
          />
          <Route
            path="/chat/login"
            element={
              <ProtectedRoute>
                <ChatPage />
              </ProtectedRoute>
            }
          />
          
          {/* 로그인 없이 접근 가능한 채팅 */}
          <Route path="/chat" element={<ChatPage />} />
          
          {/* 관리자 페이지들 */}
          <Route
            path="/upload"
            element={
              <AdminRoute>
                <AdminUploadPage />
              </AdminRoute>
            }
          />
          <Route
            path="/agent"
            element={
              <AdminRoute>
                <AgentAdminPage />
              </AdminRoute>
            }
          />
          <Route
            path="/timing-dashboard"
            element={
              <AdminRoute>
                <TimingDashboard />
              </AdminRoute>
            }
          />
          <Route
            path="/adminagent"
            element={
              <AdminRoute>
                <AdminAgentPage />
              </AdminRoute>
            }
          />
          <Route path="/auto-reply" element={<AutoReplyPage />} />
          <Route
            path="/analytics"
            element={
              <AdminRoute>
                <AnalyticsDashboard />
              </AdminRoute>
            }
          />
          <Route
            path="/admin-analytics"
            element={
              <AdminRoute>
                <AdminAnalytics />
              </AdminRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App

