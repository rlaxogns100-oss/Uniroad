import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
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
    return <Navigate to="/auth" replace />
  }
  
  if (user?.name !== '김도균') {
    return <Navigate to="/chat" replace />
  }
  
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route path="/" element={<LandingPage />} />
          {/* /chat/admin 먼저 정의 (더 구체적 경로) */}
          <Route
            path="/chat/admin"
            element={
              <AdminRoute>
                <AdminPage />
              </AdminRoute>
            }
          />
          <Route path="/chat" element={<ChatPage />} />
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App

