import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import {
  UserGroupIcon,
  QuestionMarkCircleIcon,
  ArrowTrendingUpIcon,
  ArrowLeftIcon,
  ArrowPathIcon,
  FunnelIcon,
  ChatBubbleLeftRightIcon,
  ClockIcon
} from '@heroicons/react/24/outline'

interface FunnelStats {
  landing_visits: number
  chat_visits: number
  logged_in: number
  sent_message: number
}

interface UTMConversion {
  utm_source: string
  utm_medium: string
  stats: FunnelStats
  conversions: {
    landing_to_chat: number
    chat_to_login: number
    login_to_message: number
  }
}

interface UserLogEntry {
  id: string
  timestamp: string
  userQuestion: string
  finalAnswer: string
}

interface UserWithLogs {
  userId: string | null
  label: string
  logs: UserLogEntry[]
  count: number
}

export default function AdminAnalytics() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'funnel' | 'users'>('funnel')
  const [timeRange, setTimeRange] = useState(7)
  
  // 데이터 상태
  const [funnelData, setFunnelData] = useState<any>(null)
  const [loginStats, setLoginStats] = useState<any>(null)
  const [userSummary, setUserSummary] = useState<any>(null)
  const [logsByUser, setLogsByUser] = useState<{ users: UserWithLogs[]; totalLogs: number } | null>(null)
  const [expandedUserId, setExpandedUserId] = useState<string | null>(null)

  // 데이터 로드
  const loadData = async () => {
    setLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      const headers = token ? { Authorization: `Bearer ${token}` } : {}
      const [funnel, login, summary, byUser] = await Promise.all([
        axios.get(`/api/analytics/funnel?days=${timeRange}`),
        axios.get('/api/analytics/login-stats'),
        axios.get('/api/analytics/user-summary'),
        axios.get('/api/admin/logs/by-user?limit=2000', { headers })
      ])
      setFunnelData(funnel.data)
      setLoginStats(login.data)
      setUserSummary(summary.data)
      setLogsByUser(byUser.data)
    } catch (error) {
      console.error('데이터 로드 실패:', error)
      alert('데이터를 불러오는데 실패했습니다. 콘솔을 확인해주세요.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [timeRange])

  // 전환율 색상 결정
  const getConversionColor = (rate: number) => {
    if (rate >= 70) return 'text-green-600'
    if (rate >= 40) return 'text-yellow-600'
    return 'text-red-600'
  }

  // 깔때기 시각화
  const renderFunnel = () => {
    console.log('renderFunnel 호출됨, funnelData:', funnelData)
    if (!funnelData) {
      return <div className="text-center py-8 text-gray-500">깔때기 데이터가 없습니다.</div>
    }
    
    const { total_stats, total_conversions } = funnelData
    
    return (
      <div className="space-y-6">
        {/* 전체 깔때기 */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <FunnelIcon className="w-5 h-5" />
            전체 전환 깔때기
          </h3>
          
          <div className="space-y-4">
            {/* 랜딩 페이지 */}
            <div className="relative">
              <div className="bg-blue-100 rounded-lg p-4">
                <div className="flex justify-between items-center">
                  <span className="font-medium">랜딩 페이지</span>
                  <span className="text-2xl font-bold">{total_stats.landing_visits}</span>
                </div>
              </div>
              {total_conversions.landing_to_chat > 0 && (
                <div className="text-center py-2">
                  <span className={`text-sm font-medium ${getConversionColor(total_conversions.landing_to_chat)}`}>
                    ↓ {total_conversions.landing_to_chat}%
                  </span>
                </div>
              )}
            </div>
            
            {/* 채팅 페이지 */}
            <div className="relative">
              <div className="bg-indigo-100 rounded-lg p-4 w-5/6 mx-auto">
                <div className="flex justify-between items-center">
                  <span className="font-medium">채팅 페이지</span>
                  <span className="text-2xl font-bold">{total_stats.chat_visits}</span>
                </div>
              </div>
              {total_conversions.chat_to_login > 0 && (
                <div className="text-center py-2">
                  <span className={`text-sm font-medium ${getConversionColor(total_conversions.chat_to_login)}`}>
                    ↓ {total_conversions.chat_to_login}%
                  </span>
                </div>
              )}
            </div>
            
            {/* 로그인 */}
            <div className="relative">
              <div className="bg-purple-100 rounded-lg p-4 w-4/6 mx-auto">
                <div className="flex justify-between items-center">
                  <span className="font-medium">로그인</span>
                  <span className="text-2xl font-bold">{total_stats.logged_in}</span>
                </div>
              </div>
              {total_conversions.login_to_message > 0 && (
                <div className="text-center py-2">
                  <span className={`text-sm font-medium ${getConversionColor(total_conversions.login_to_message)}`}>
                    ↓ {total_conversions.login_to_message}%
                  </span>
                </div>
              )}
            </div>
            
            {/* 메시지 전송 */}
            <div className="relative">
              <div className="bg-green-100 rounded-lg p-4 w-3/6 mx-auto">
                <div className="flex justify-between items-center">
                  <span className="font-medium">메시지 전송</span>
                  <span className="text-2xl font-bold">{total_stats.sent_message}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* UTM별 전환율 */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">매체별 전환율</h3>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">매체</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">방문자</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">랜딩→채팅</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">채팅→로그인</th>
                  <th className="px-4 py-2 text-center text-xs font-medium text-gray-500 uppercase">로그인→메시지</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {funnelData.utm_conversions.map((utm: UTMConversion, idx: number) => (
                  <tr key={idx}>
                    <td className="px-4 py-2">
                      <div>
                        <div className="font-medium">{utm.utm_source || 'direct'}</div>
                        <div className="text-sm text-gray-500">{utm.utm_medium || 'none'}</div>
                      </div>
                    </td>
                    <td className="px-4 py-2 text-center font-medium">
                      {utm.stats.landing_visits}
                    </td>
                    <td className={`px-4 py-2 text-center font-medium ${getConversionColor(utm.conversions.landing_to_chat)}`}>
                      {utm.conversions.landing_to_chat}%
                    </td>
                    <td className={`px-4 py-2 text-center font-medium ${getConversionColor(utm.conversions.chat_to_login)}`}>
                      {utm.conversions.chat_to_login}%
                    </td>
                    <td className={`px-4 py-2 text-center font-medium ${getConversionColor(utm.conversions.login_to_message)}`}>
                      {utm.conversions.login_to_message}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  // 유저별 질문·답변 (admin_logs)
  const renderUsersLogs = () => {
    if (!logsByUser?.users?.length) {
      return (
        <div className="bg-white rounded-lg shadow p-6">
          <p className="text-gray-500">유저별 로그가 없습니다. (admin_logs 테이블 기준)</p>
        </div>
      )
    }
    return (
      <div className="space-y-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <ChatBubbleLeftRightIcon className="w-5 h-5" />
            유저별 질문·답변 내역 (admin_logs)
          </h3>
          <p className="text-sm text-gray-500 mb-4">
            총 {logsByUser.totalLogs}건 · 유저 {logsByUser.users.length}명
          </p>
          <div className="space-y-2">
            {logsByUser.users.map((u) => (
              <div key={u.userId ?? '__guest__'} className="border rounded-lg overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpandedUserId(expandedUserId === (u.userId ?? '__guest__') ? null : (u.userId ?? '__guest__'))}
                  className="w-full px-4 py-3 flex items-center justify-between bg-gray-50 hover:bg-gray-100 text-left"
                >
                  <span className="font-medium">{u.label}</span>
                  <span className="text-sm text-gray-500">{u.count}건</span>
                </button>
                {expandedUserId === (u.userId ?? '__guest__') && (
                  <div className="p-4 space-y-4 max-h-96 overflow-y-auto">
                    {u.logs.map((log) => (
                      <div key={log.id} className="border-l-4 border-blue-200 pl-3 py-2 space-y-1">
                        <p className="text-xs text-gray-500">
                          {log.timestamp ? new Date(log.timestamp).toLocaleString('ko-KR') : '-'}
                        </p>
                        <p className="font-medium text-gray-800">Q: {log.userQuestion}</p>
                        <p className="text-sm text-gray-600 whitespace-pre-wrap">A: {log.finalAnswer || '(답변 없음)'}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <ArrowPathIcon className="w-8 h-8 animate-spin mx-auto mb-4 text-blue-600" />
          <p className="text-gray-600">데이터를 불러오는 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/chat/login/admin')}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </button>
              <h1 className="text-xl font-semibold">관리자 분석</h1>
            </div>
            
            <div className="flex items-center gap-4">
              {/* 기간 선택 */}
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(Number(e.target.value))}
                className="px-3 py-1.5 border rounded-lg text-sm"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((d) => (
                  <option key={d} value={d}>
                    {d === 1 ? '최근 1일' : `최근 ${d}일`}
                  </option>
                ))}
              </select>
              
              {/* 새로고침 */}
              <button
                onClick={loadData}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <ArrowPathIcon className="w-5 h-5" />
              </button>
            </div>
          </div>
        </div>
      </div>
      
      {/* 요약 카드 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">전체 사용자</p>
                <p className="text-2xl font-bold">{userSummary?.total_users || 0}</p>
              </div>
              <UserGroupIcon className="w-8 h-8 text-blue-500" />
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">오늘 신규</p>
                <p className="text-2xl font-bold">{userSummary?.today_new_users || 0}</p>
              </div>
              <ArrowTrendingUpIcon className="w-8 h-8 text-green-500" />
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">기간 내 로그인</p>
                <p className="text-2xl font-bold">{funnelData?.total_stats?.logged_in ?? 0}</p>
              </div>
              <ClockIcon className="w-8 h-8 text-purple-500" />
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">로그 질문 수</p>
                <p className="text-2xl font-bold">{logsByUser?.totalLogs ?? 0}</p>
              </div>
              <QuestionMarkCircleIcon className="w-8 h-8 text-orange-500" />
            </div>
          </div>
        </div>
        
        {/* 탭 네비게이션 */}
        <div className="bg-white rounded-lg shadow mb-6">
          <div className="border-b">
            <nav className="flex -mb-px">
              <button
                onClick={() => setActiveTab('funnel')}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'funnel'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                전환 깔때기
              </button>
              <button
                onClick={() => setActiveTab('users')}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'users'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                유저별 질문·답변
              </button>
            </nav>
          </div>
        </div>
        
        {/* 탭 컨텐츠 */}
        <div>
          {loading ? (
            <div className="text-center py-8">
              <p className="text-gray-600">데이터 로딩 중...</p>
            </div>
          ) : (
            <>
              {activeTab === 'funnel' && renderFunnel()}
              {activeTab === 'users' && renderUsersLogs()}
            </>
          )}
        </div>
      </div>
    </div>
  )
}