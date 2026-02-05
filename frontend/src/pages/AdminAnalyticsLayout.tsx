import { useNavigate, NavLink, Outlet } from 'react-router-dom'

export default function AdminAnalyticsLayout() {
  const navigate = useNavigate()

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">📊 관리자 분석</h1>
            <p className="text-sm text-gray-600">KPI·사용자 행동 분석</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/chat/login/admin')}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
            >
              ← 관리자 홈
            </button>
          </div>
        </div>
      </header>

      <nav className="bg-white border-b border-gray-200 px-6">
        <div className="max-w-6xl mx-auto flex gap-1">
          <NavLink
            to="/admin-analytics/kpi"
            end
            className={({ isActive }) =>
              `px-4 py-3 text-sm font-medium rounded-t-lg transition-colors ${
                isActive
                  ? 'bg-indigo-100 text-indigo-800 border-b-2 border-indigo-600 -mb-px'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`
            }
          >
            KPI 확인
          </NavLink>
          <NavLink
            to="/admin-analytics/behavior"
            className={({ isActive }) =>
              `px-4 py-3 text-sm font-medium rounded-t-lg transition-colors ${
                isActive
                  ? 'bg-indigo-100 text-indigo-800 border-b-2 border-indigo-600 -mb-px'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`
            }
          >
            사용자 행동 분석
          </NavLink>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
