import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from 'axios'
import {
  ChartBarIcon,
  UserGroupIcon,
  QuestionMarkCircleIcon,
  DevicePhoneMobileIcon,
  ArrowTrendingUpIcon,
  ArrowLeftIcon,
  ArrowPathIcon,
  FunnelIcon,
  ChatBubbleLeftRightIcon,
  GlobeAltIcon,
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

interface DeviceStats {
  name: string
  count: number
  percentage: number
}

interface PatternStats {
  pattern: string
  count: number
  percentage: number
  sample_questions: string[]
}

interface UTMQuestion {
  utm_source: string
  utm_medium: string
  utm_campaign: string | null
  total_questions: number
  pattern_percentages: Record<string, number>
  top_patterns: [string, number][]
  sample_questions: string[]
}

export default function AdminAnalytics() {
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'funnel' | 'questions' | 'devices' | 'utm'>('funnel')
  const [timeRange, setTimeRange] = useState(7)
  
  // 데이터 상태
  const [funnelData, setFunnelData] = useState<any>(null)
  const [deviceData, setDeviceData] = useState<any>(null)
  const [questionData, setQuestionData] = useState<any>(null)
  const [utmQuestions, setUtmQuestions] = useState<any>(null)
  const [loginStats, setLoginStats] = useState<any>(null)
  const [userSummary, setUserSummary] = useState<any>(null)

  // 데이터 로드
  const loadData = async () => {
    setLoading(true)
    try {
      console.log('데이터 로드 시작...')
      const [funnel, devices, questions, utm, login, summary] = await Promise.all([
        axios.get(`/api/analytics/funnel?days=${timeRange}`),
        axios.get(`/api/analytics/device-stats?days=${timeRange}`),
        axios.get(`/api/analytics/popular-questions?days=${timeRange}`),
        axios.get(`/api/analytics/utm-questions?days=${timeRange}`),
        axios.get('/api/analytics/login-stats'),
        axios.get('/api/analytics/user-summary')
      ])
      
      console.log('API 응답:', {
        funnel: funnel.data,
        devices: devices.data,
        questions: questions.data,
        utm: utm.data,
        login: login.data,
        summary: summary.data
      })
      
      setFunnelData(funnel.data)
      setDeviceData(devices.data)
      setQuestionData(questions.data)
      setUtmQuestions(utm.data)
      setLoginStats(login.data)
      setUserSummary(summary.data)
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

  // 질문 분석 렌더링
  const renderQuestions = () => {
    if (!questionData) return null
    
    return (
      <div className="space-y-6">
        {/* 질문 패턴 분석 */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <ChatBubbleLeftRightIcon className="w-5 h-5" />
            질문 패턴 분석
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {questionData.pattern_stats.slice(0, 6).map((pattern: PatternStats) => (
              <div key={pattern.pattern} className="border rounded-lg p-4">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-medium">{pattern.pattern}</h4>
                  <span className="text-sm text-gray-500">{pattern.count}개 ({pattern.percentage}%)</span>
                </div>
                <div className="space-y-1">
                  {pattern.sample_questions.slice(0, 2).map((q: string, idx: number) => (
                    <p key={idx} className="text-sm text-gray-600 truncate">
                      • {q}
                    </p>
                  ))}
                </div>
              </div>
            ))}
          </div>
          
          {/* 인기 키워드 */}
          <div>
            <h4 className="font-medium mb-2">자주 사용된 키워드</h4>
            <div className="flex flex-wrap gap-2">
              {questionData.top_keywords.slice(0, 15).map((kw: any) => (
                <span
                  key={kw.keyword}
                  className="px-3 py-1 bg-gray-100 text-gray-700 rounded-full text-sm"
                >
                  {kw.keyword} ({kw.count})
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    )
  }

  // UTM별 질문 분석
  const renderUTMQuestions = () => {
    if (!utmQuestions) return null
    
    return (
      <div className="space-y-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <GlobeAltIcon className="w-5 h-5" />
            매체별 질문 특성
          </h3>
          
          <div className="space-y-6">
            {utmQuestions.utm_analysis.slice(0, 5).map((utm: UTMQuestion, idx: number) => (
              <div key={idx} className="border rounded-lg p-4">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h4 className="font-medium">
                      {utm.utm_source || 'direct'} / {utm.utm_medium || 'none'}
                    </h4>
                    {utm.utm_campaign && (
                      <p className="text-sm text-gray-500">{utm.utm_campaign}</p>
                    )}
                  </div>
                  <span className="text-sm font-medium text-gray-600">
                    {utm.total_questions}개 질문
                  </span>
                </div>
                
                {/* 주요 패턴 */}
                <div className="mb-3">
                  <p className="text-sm text-gray-600 mb-1">주요 관심사:</p>
                  <div className="flex gap-2">
                    {utm.top_patterns.map(([pattern, percentage]) => (
                      <span
                        key={pattern}
                        className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-sm"
                      >
                        {pattern} ({percentage}%)
                      </span>
                    ))}
                  </div>
                </div>
                
                {/* 샘플 질문 */}
                <div>
                  <p className="text-sm text-gray-600 mb-1">대표 질문:</p>
                  <ul className="space-y-1">
                    {utm.sample_questions.slice(0, 2).map((q: string, qIdx: number) => (
                      <li key={qIdx} className="text-sm text-gray-700">
                        • {q}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    )
  }

  // 디바이스 통계
  const renderDevices = () => {
    if (!deviceData) return null
    
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* 디바이스 타입 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <DevicePhoneMobileIcon className="w-5 h-5" />
              디바이스 타입
            </h3>
            <div className="space-y-3">
              {deviceData.device_stats.map((device: DeviceStats) => (
                <div key={device.name} className="flex justify-between items-center">
                  <span className="font-medium capitalize">{device.name}</span>
                  <div className="text-right">
                    <span className="text-sm text-gray-600">{device.count}명</span>
                    <span className="ml-2 font-medium">{device.percentage}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* 브라우저 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">브라우저</h3>
            <div className="space-y-3">
              {deviceData.browser_stats.map((browser: DeviceStats) => (
                <div key={browser.name} className="flex justify-between items-center">
                  <span className="font-medium">{browser.name}</span>
                  <div className="text-right">
                    <span className="text-sm text-gray-600">{browser.count}명</span>
                    <span className="ml-2 font-medium">{browser.percentage}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
          
          {/* 운영체제 */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-semibold mb-4">운영체제</h3>
            <div className="space-y-3">
              {deviceData.os_stats.map((os: DeviceStats) => (
                <div key={os.name} className="flex justify-between items-center">
                  <span className="font-medium">{os.name}</span>
                  <div className="text-right">
                    <span className="text-sm text-gray-600">{os.count}명</span>
                    <span className="ml-2 font-medium">{os.percentage}%</span>
                  </div>
                </div>
              ))}
            </div>
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
                <option value={7}>최근 7일</option>
                <option value={30}>최근 30일</option>
                <option value={90}>최근 90일</option>
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
                <p className="text-sm text-gray-600">오늘 로그인</p>
                <p className="text-2xl font-bold">{loginStats?.today_count || 0}</p>
              </div>
              <ClockIcon className="w-8 h-8 text-purple-500" />
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600">총 질문 수</p>
                <p className="text-2xl font-bold">{questionData?.total_questions || 0}</p>
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
                onClick={() => setActiveTab('utm')}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'utm'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                매체별 질문
              </button>
              <button
                onClick={() => setActiveTab('questions')}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'questions'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                질문 분석
              </button>
              <button
                onClick={() => setActiveTab('devices')}
                className={`px-6 py-3 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === 'devices'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                디바이스
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
              {activeTab === 'utm' && renderUTMQuestions()}
              {activeTab === 'questions' && renderQuestions()}
              {activeTab === 'devices' && renderDevices()}
            </>
          )}
        </div>
      </div>
    </div>
  )
}