import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

interface LoginStats {
  success: boolean
  today: string
  total_logins_today: number
  hourly_stats: Array<{ time: string; count: number }>
  recent_logins: Array<{
    id: string
    email: string
    display_name: string
    last_sign_in: string
    created_at: string | null
  }>
  timestamp: string
}

interface UserSummary {
  success: boolean
  total_users: number
  today_new_users: number
  today_logins: number
  timestamp: string
}

export default function AnalyticsDashboard() {
  const navigate = useNavigate()
  const [loginStats, setLoginStats] = useState<LoginStats | null>(null)
  const [userSummary, setUserSummary] = useState<UserSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  // 데이터 로드
  const loadData = async () => {
    try {
      setError(null)
      const [statsRes, summaryRes] = await Promise.all([
        fetch('/api/analytics/login-stats'),
        fetch('/api/analytics/user-summary')
      ])

      if (!statsRes.ok || !summaryRes.ok) {
        throw new Error('데이터 로드 실패')
      }

      const stats = await statsRes.json()
      const summary = await summaryRes.json()

      setLoginStats(stats)
      setUserSummary(summary)
    } catch (err: any) {
      console.error('❌ 데이터 로드 오류:', err)
      setError(err.message || '데이터를 불러올 수 없습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  // 초기 로드
  useEffect(() => {
    loadData()
  }, [])

  // 자동 새로고침 (30초마다)
  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(() => {
      loadData()
    }, 30000)

    return () => clearInterval(interval)
  }, [autoRefresh])

  // 시간대별 최대값 구하기 (차트 스케일링용)
  const maxHourlyCount = loginStats
    ? Math.max(...loginStats.hourly_stats.map((s) => s.count), 1)
    : 1

  // 로딩 상태
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600 text-lg font-medium">분석 데이터를 불러오는 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-indigo-50">
      {/* 헤더 */}
      <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">📊 실시간 분석 대시보드</h1>
            <p className="text-sm text-gray-600">사용자 로그인 통계</p>
          </div>
          <div className="flex gap-3 items-center">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="w-4 h-4 rounded"
              />
              <span className="text-sm text-gray-700">자동 새로고침 (30초)</span>
            </label>
            <button
              onClick={loadData}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              🔄 새로고침
            </button>
            <button
              onClick={() => navigate('/chat/login/admin')}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
            >
              ← 돌아가기
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {/* 에러 표시 */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            ⚠️ {error}
          </div>
        )}

        {/* 요약 카드 */}
        {userSummary && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            {/* 전체 사용자 */}
            <div className="bg-white rounded-2xl shadow-lg p-6 border-l-4 border-blue-500">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm font-medium">전체 사용자</p>
                  <p className="text-4xl font-bold text-blue-600 mt-2">
                    {userSummary.total_users}
                  </p>
                </div>
                <div className="text-5xl opacity-20">👥</div>
              </div>
            </div>

            {/* 오늘 신규 가입 */}
            <div className="bg-white rounded-2xl shadow-lg p-6 border-l-4 border-green-500">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm font-medium">오늘 신규 가입</p>
                  <p className="text-4xl font-bold text-green-600 mt-2">
                    {userSummary.today_new_users}
                  </p>
                </div>
                <div className="text-5xl opacity-20">✨</div>
              </div>
            </div>

            {/* 오늘 로그인 */}
            <div className="bg-white rounded-2xl shadow-lg p-6 border-l-4 border-purple-500">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm font-medium">오늘 로그인</p>
                  <p className="text-4xl font-bold text-purple-600 mt-2">
                    {userSummary.today_logins}
                  </p>
                </div>
                <div className="text-5xl opacity-20">🔐</div>
              </div>
            </div>
          </div>
        )}

        {/* 시간대별 로그인 차트 */}
        {loginStats && (
          <div className="bg-white rounded-2xl shadow-lg p-6 mb-8 border border-gray-100">
            <h2 className="text-lg font-bold text-gray-800 mb-6">⏰ 시간대별 로그인 수</h2>
            <div className="space-y-2">
              {loginStats.hourly_stats.map((stat) => (
                <div key={stat.time} className="flex items-center gap-4">
                  <div className="w-12 text-sm font-medium text-gray-600">{stat.time}</div>
                  <div className="flex-1 bg-gray-100 rounded-full h-8 overflow-hidden">
                    <div
                      className="bg-gradient-to-r from-blue-400 to-blue-600 h-full flex items-center justify-end pr-3 transition-all duration-300"
                      style={{
                        width: `${(stat.count / maxHourlyCount) * 100}%`
                      }}
                    >
                      {stat.count > 0 && (
                        <span className="text-white text-xs font-bold">{stat.count}</span>
                      )}
                    </div>
                  </div>
                  <div className="w-8 text-right text-sm font-medium text-gray-600">
                    {stat.count}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 최근 로그인 사용자 */}
        {loginStats && (
          <div className="bg-white rounded-2xl shadow-lg p-6 border border-gray-100">
            <h2 className="text-lg font-bold text-gray-800 mb-6">
              👤 최근 로그인 사용자 ({loginStats.recent_logins.length}명)
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                      이름
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                      이메일
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                      마지막 로그인
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-semibold text-gray-700">
                      가입일
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {loginStats.recent_logins.map((user, idx) => {
                    const lastSignIn = new Date(user.last_sign_in)
                    const createdAt = user.created_at ? new Date(user.created_at) : null
                    const timeAgo = getTimeAgo(lastSignIn)

                    return (
                      <tr
                        key={user.id}
                        className={`border-b border-gray-100 hover:bg-gray-50 transition-colors ${
                          idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'
                        }`}
                      >
                        <td className="py-3 px-4 text-sm font-medium text-gray-900">
                          {user.display_name}
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-600">{user.email}</td>
                        <td className="py-3 px-4 text-sm text-gray-600">
                          <span className="inline-block px-2 py-1 bg-blue-100 text-blue-800 rounded">
                            {timeAgo}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-600">
                          {createdAt ? createdAt.toLocaleDateString('ko-KR') : '-'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* 마지막 업데이트 시간 */}
        {loginStats && (
          <div className="mt-6 text-center text-sm text-gray-500">
            마지막 업데이트: {new Date(loginStats.timestamp).toLocaleTimeString('ko-KR')}
          </div>
        )}
      </div>
    </div>
  )
}

// 시간 차이를 읽기 쉬운 형식으로 변환
function getTimeAgo(date: Date): string {
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return '방금 전'
  if (diffMins < 60) return `${diffMins}분 전`
  if (diffHours < 24) return `${diffHours}시간 전`
  if (diffDays < 7) return `${diffDays}일 전`
  return date.toLocaleDateString('ko-KR')
}
