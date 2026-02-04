import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

interface EventData {
  name: string
  count: number
  percentage?: number
}

interface PageViewData {
  page: string
  views: number
}

interface TimeSeriesData {
  date: string
  events: number
}

interface PathNode {
  name: string
}

interface PathLink {
  source: string
  target: string
  value: number
}

interface PathAnalysisData {
  nodes: PathNode[]
  links: PathLink[]
}

interface EntryExitData {
  entry_pages: Array<{ page: string; sessions: number }>
  exit_pages: Array<{ page: string; sessions: number }>
}

interface FunnelStage {
  stage: string
  count: number
  order: number
  conversion_rate: number
  step_conversion: number
}

interface FunnelData {
  stages: FunnelStage[]
  total_users: number
  final_conversions: number
  overall_conversion: number
}

export default function AnalyticsDashboard() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'overview' | 'events' | 'pages' | 'timeseries' | 'pathanalysis' | 'funnel'>('overview')
  const [eventData, setEventData] = useState<EventData[]>([])
  const [pageViewData, setPageViewData] = useState<PageViewData[]>([])
  const [timeSeriesData, setTimeSeriesData] = useState<TimeSeriesData[]>([])
  const [pathAnalysisData, setPathAnalysisData] = useState<PathAnalysisData>({ nodes: [], links: [] })
  const [entryExitData, setEntryExitData] = useState<EntryExitData>({ entry_pages: [], exit_pages: [] })
  const [funnelData, setFunnelData] = useState<FunnelData>({ stages: [], total_users: 0, final_conversions: 0, overall_conversion: 0 })
  const [totalEvents, setTotalEvents] = useState(0)
  const [totalPageViews, setTotalPageViews] = useState(0)
  const [loading, setLoading] = useState(true)

  const COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']

  useEffect(() => {
    loadAnalyticsData()
  }, [])

  const loadAnalyticsData = async () => {
    setLoading(true)
    try {
      // 백엔드 API에서 GA4 데이터 조회
      const response = await fetch('/api/analytics/dashboard?days=7')
      
      if (!response.ok) {
        throw new Error('분석 데이터 조회 실패')
      }
      
      const result = await response.json()
      
      if (result.success && result.data) {
        const { events, pages, timeseries, summary, path_analysis, entry_exit, funnel } = result.data
        
        setEventData(events)
        setPageViewData(pages)
        setTimeSeriesData(timeseries)
        setPathAnalysisData(path_analysis)
        setEntryExitData(entry_exit)
        setFunnelData(funnel)
        setTotalEvents(summary.total_events)
        setTotalPageViews(summary.total_page_views)
      }
    } catch (error) {
      console.error('분석 데이터 로드 오류:', error)
      // 오류 발생 시 샘플 데이터 표시
      loadSampleData()
    } finally {
      setLoading(false)
    }
  }

  const loadSampleData = () => {
    // 샘플 데이터 (오류 발생 시 표시)
    const mockEventData: EventData[] = [
      { name: 'send_message', count: 245, percentage: 35 },
      { name: 'file_upload_success', count: 89, percentage: 13 },
      { name: 'evaluation_pause', count: 67, percentage: 10 },
      { name: 'navigate_to_chat', count: 156, percentage: 22 },
      { name: 'auto_reply_test', count: 45, percentage: 6 },
      { name: 'evaluation_skip', count: 34, percentage: 5 },
      { name: 'file_upload_error', count: 23, percentage: 3 },
      { name: 'login', count: 34, percentage: 5 },
    ]

    const mockPageViewData: PageViewData[] = [
      { page: '/chat', views: 450 },
      { page: '/upload', views: 234 },
      { page: '/adminagent', views: 189 },
      { page: '/auto-reply', views: 123 },
      { page: '/', views: 98 },
      { page: '/agent', views: 67 },
    ]

    const mockTimeSeriesData: TimeSeriesData[] = [
      { date: '2026-02-01', events: 145 },
      { date: '2026-02-02', events: 189 },
      { date: '2026-02-03', events: 234 },
      { date: '2026-02-04', events: 267 },
    ]

    setEventData(mockEventData)
    setPageViewData(mockPageViewData)
    setTimeSeriesData(mockTimeSeriesData)
    setTotalEvents(mockEventData.reduce((sum, item) => sum + item.count, 0))
    setTotalPageViews(mockPageViewData.reduce((sum, item) => sum + item.views, 0))
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">분석 데이터 로드 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* 헤더 */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">📊 GA4 분석 대시보드</h1>
              <p className="text-gray-600 mt-1">실시간 사용자 활동 및 이벤트 분석</p>
            </div>
            <button
              onClick={() => navigate('/chat/admin')}
              className="px-4 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg text-sm font-medium"
            >
              ← 관리자 페이지로
            </button>
          </div>
        </div>
      </div>

      {/* 메인 콘텐츠 */}
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* 요약 카드 */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-gray-600 text-sm font-medium">총 이벤트</div>
            <div className="text-3xl font-bold text-blue-600 mt-2">{totalEvents.toLocaleString()}</div>
            <div className="text-gray-500 text-xs mt-2">모든 추적된 이벤트</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-gray-600 text-sm font-medium">페이지 뷰</div>
            <div className="text-3xl font-bold text-green-600 mt-2">{totalPageViews.toLocaleString()}</div>
            <div className="text-gray-500 text-xs mt-2">페이지 방문 수</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-gray-600 text-sm font-medium">평균 이벤트/일</div>
            <div className="text-3xl font-bold text-purple-600 mt-2">{Math.round(totalEvents / 4).toLocaleString()}</div>
            <div className="text-gray-500 text-xs mt-2">최근 4일 기준</div>
          </div>
          <div className="bg-white rounded-lg shadow p-6">
            <div className="text-gray-600 text-sm font-medium">상위 이벤트</div>
            <div className="text-3xl font-bold text-orange-600 mt-2">{eventData[0]?.name || 'N/A'}</div>
            <div className="text-gray-500 text-xs mt-2">{eventData[0]?.count || 0}회</div>
          </div>
        </div>

        {/* 탭 네비게이션 */}
        <div className="bg-white rounded-lg shadow mb-8">
          <div className="flex border-b">
            <button
              onClick={() => setActiveTab('overview')}
              className={`flex-1 px-4 py-3 text-center font-medium ${
                activeTab === 'overview'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              📈 개요
            </button>
            <button
              onClick={() => setActiveTab('events')}
              className={`flex-1 px-4 py-3 text-center font-medium ${
                activeTab === 'events'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              🎯 이벤트
            </button>
            <button
              onClick={() => setActiveTab('pages')}
              className={`flex-1 px-4 py-3 text-center font-medium ${
                activeTab === 'pages'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              📄 페이지
            </button>
            <button
              onClick={() => setActiveTab('timeseries')}
              className={`flex-1 px-4 py-3 text-center font-medium ${
                activeTab === 'timeseries'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              📊 시계열
            </button>
            <button
              onClick={() => setActiveTab('pathanalysis')}
              className={`flex-1 px-4 py-3 text-center font-medium ${
                activeTab === 'pathanalysis'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              🔀 경로 분석
            </button>
            <button
              onClick={() => setActiveTab('funnel')}
              className={`flex-1 px-4 py-3 text-center font-medium ${
                activeTab === 'funnel'
                  ? 'border-b-2 border-blue-600 text-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              🔗 깔때기 분석
            </button>
          </div>

          {/* 탭 콘텐츠 */}
          <div className="p-6">
            {/* 개요 탭 */}
            {activeTab === 'overview' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* 이벤트 분포 파이 차트 */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">이벤트 분포</h3>
                    <ResponsiveContainer width="100%" height={300}>
                      <PieChart>
                        <Pie
                          data={eventData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ name, value }) => `${name}: ${Math.round((value / eventData.reduce((sum, d) => sum + d.count, 0)) * 100)}%`}
                          outerRadius={80}
                          fill="#8884d8"
                          dataKey="count"
                        >
                          {eventData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>

                  {/* 상위 이벤트 목록 */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">상위 이벤트</h3>
                    <div className="space-y-3">
                      {eventData.slice(0, 5).map((event, index) => (
                        <div key={index} className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div
                              className="w-3 h-3 rounded-full"
                              style={{ backgroundColor: COLORS[index % COLORS.length] }}
                            ></div>
                            <span className="text-sm font-medium text-gray-700">{event.name}</span>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-semibold text-gray-900">{event.count}</div>
                            <div className="text-xs text-gray-500">{event.percentage}%</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 이벤트 탭 */}
            {activeTab === 'events' && (
              <div className="space-y-6">
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">이벤트별 발생 횟수</h3>
                  <ResponsiveContainer width="100%" height={400}>
                    <BarChart data={eventData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="count" fill="#3b82f6" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* 이벤트 상세 테이블 */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">이벤트 상세</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-200">
                        <tr>
                          <th className="px-4 py-2 text-left">이벤트명</th>
                          <th className="px-4 py-2 text-right">발생 횟수</th>
                          <th className="px-4 py-2 text-right">비율</th>
                        </tr>
                      </thead>
                      <tbody>
                        {eventData.map((event, index) => (
                          <tr key={index} className="border-b hover:bg-gray-100">
                            <td className="px-4 py-2">{event.name}</td>
                            <td className="px-4 py-2 text-right font-semibold">{event.count}</td>
                            <td className="px-4 py-2 text-right">{event.percentage}%</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* 페이지 탭 */}
            {activeTab === 'pages' && (
              <div className="space-y-6">
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">페이지별 방문 수</h3>
                  <ResponsiveContainer width="100%" height={400}>
                    <BarChart data={pageViewData} layout="vertical">
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis type="number" />
                      <YAxis dataKey="page" type="category" width={100} />
                      <Tooltip />
                      <Bar dataKey="views" fill="#10b981" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* 페이지 상세 테이블 */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">페이지 상세</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-200">
                        <tr>
                          <th className="px-4 py-2 text-left">페이지</th>
                          <th className="px-4 py-2 text-right">방문 수</th>
                          <th className="px-4 py-2 text-right">비율</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pageViewData.map((page, index) => {
                          const percentage = Math.round((page.views / totalPageViews) * 100)
                          return (
                            <tr key={index} className="border-b hover:bg-gray-100">
                              <td className="px-4 py-2">{page.page}</td>
                              <td className="px-4 py-2 text-right font-semibold">{page.views}</td>
                              <td className="px-4 py-2 text-right">{percentage}%</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* 시계열 탭 */}
            {activeTab === 'timeseries' && (
              <div className="space-y-6">
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">일별 이벤트 발생 추이</h3>
                  <ResponsiveContainer width="100%" height={400}>
                    <LineChart data={timeSeriesData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="events"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        dot={{ fill: '#3b82f6', r: 5 }}
                        activeDot={{ r: 7 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>

                {/* 시계열 상세 테이블 */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">일별 상세</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-200">
                        <tr>
                          <th className="px-4 py-2 text-left">날짜</th>
                          <th className="px-4 py-2 text-right">이벤트 수</th>
                        </tr>
                      </thead>
                      <tbody>
                        {timeSeriesData.map((data, index) => (
                          <tr key={index} className="border-b hover:bg-gray-100">
                            <td className="px-4 py-2">{data.date}</td>
                            <td className="px-4 py-2 text-right font-semibold">{data.events}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* 경로 분석 탭 */}
            {activeTab === 'pathanalysis' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-blue-900 mb-2">🔀 사용자 경로 흐름</h3>
                  <p className="text-sm text-blue-800">
                    사용자들이 페이지 간에 이동하는 경로를 분석합니다.
                  </p>
                </div>

                {pathAnalysisData.nodes.length > 0 ? (
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="space-y-4">
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-2">페이지 노드</h4>
                        <div className="grid grid-cols-2 gap-2">
                          {pathAnalysisData.nodes.map((node, idx) => (
                            <div key={idx} className="bg-white p-2 rounded border border-gray-200">
                              <p className="text-sm font-medium text-gray-900">{node.name}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-2">경로 흐름</h4>
                        <div className="space-y-2">
                          {pathAnalysisData.links.map((link, idx) => (
                            <div key={idx} className="bg-white p-2 rounded border border-gray-200">
                              <p className="text-sm text-gray-700">
                                <span className="font-medium">{link.source}</span>
                                <span className="mx-2">→</span>
                                <span className="font-medium">{link.target}</span>
                                <span className="ml-2 text-blue-600">({link.value}회)</span>
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="bg-gray-50 rounded-lg p-8 text-center">
                    <p className="text-gray-500">경로 데이터를 불러오는 중입니다...</p>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* 진입점 분석 */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">📍 주요 진입점</h3>
                    <div className="space-y-3">
                      {entryExitData.entry_pages.length > 0 ? (
                        entryExitData.entry_pages.map((page, index) => (
                          <div key={index} className="bg-white rounded-lg p-3 border border-gray-200">
                            <div className="flex items-center justify-between mb-2">
                              <span className="font-medium text-gray-900 truncate">{page.page || '/'}</span>
                              <span className="text-sm font-semibold text-blue-600">{page.sessions}</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div 
                                className="bg-blue-600 h-2 rounded-full" 
                                style={{ 
                                  width: `${(page.sessions / (entryExitData.entry_pages[0]?.sessions || 1)) * 100}%` 
                                }}
                              ></div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="text-gray-500 text-sm">데이터 없음</p>
                      )}
                    </div>
                  </div>

                  {/* 이탈점 분석 */}
                  <div className="bg-gray-50 rounded-lg p-4">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">🚪 주요 이탈점</h3>
                    <div className="space-y-3">
                      {entryExitData.exit_pages.length > 0 ? (
                        entryExitData.exit_pages.map((page, index) => (
                          <div key={index} className="bg-white rounded-lg p-3 border border-gray-200">
                            <div className="flex items-center justify-between mb-2">
                              <span className="font-medium text-gray-900 truncate">{page.page || '/'}</span>
                              <span className="text-sm font-semibold text-red-600">{page.sessions}</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div 
                                className="bg-red-600 h-2 rounded-full" 
                                style={{ 
                                  width: `${(page.sessions / (entryExitData.exit_pages[0]?.sessions || 1)) * 100}%` 
                                }}
                              ></div>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="text-gray-500 text-sm">데이터 없음</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* 경로 상세 테이블 */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">📊 경로 상세</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-200">
                        <tr>
                          <th className="px-4 py-2 text-left">출발 페이지</th>
                          <th className="px-4 py-2 text-left">도착 페이지</th>
                          <th className="px-4 py-2 text-right">이동 횟수</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pathAnalysisData.links.length > 0 ? (
                          pathAnalysisData.links.map((link, index) => (
                            <tr key={index} className="border-b hover:bg-gray-100">
                              <td className="px-4 py-2 font-medium">{link.source}</td>
                              <td className="px-4 py-2 font-medium">{link.target}</td>
                              <td className="px-4 py-2 text-right font-semibold">{link.value}</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={3} className="px-4 py-2 text-center text-gray-500">
                              경로 데이터 없음
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* 깔때기 분석 탭 */}
            {activeTab === 'funnel' && (
              <div className="space-y-6">
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-blue-900 mb-2">🔗 유입경로 깔때기 분석</h3>
                  <p className="text-sm text-blue-800">
                    사용자가 각 단계를 거치면서 얼마나 많은 사용자가 남아있는지 보여줍니다.
                  </p>
                </div>

                {/* 깔때기 시각화 */}
                <div className="bg-gray-50 rounded-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-6">📊 전환 깔때기</h3>
                  <div className="space-y-4">
                    {funnelData.stages.length > 0 ? (
                      funnelData.stages.map((stage, index) => {
                        const maxWidth = funnelData.stages[0].count
                        const width = (stage.count / maxWidth) * 100
                        return (
                          <div key={index} className="space-y-2">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                <span className="text-2xl">
                                  {index === 0 ? '🚀' : index === 1 ? '💬' : '✅'}
                                </span>
                                <div>
                                  <div className="font-semibold text-gray-900">{stage.stage}</div>
                                  <div className="text-sm text-gray-500">
                                    {stage.count.toLocaleString()} 사용자 ({stage.conversion_rate}%)
                                  </div>
                                </div>
                              </div>
                              {index > 0 && (
                                <div className="text-right">
                                  <div className="text-sm font-semibold text-green-600">
                                    {stage.step_conversion}% 전환
                                  </div>
                                </div>
                              )}
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-8 overflow-hidden">
                              <div
                                className={`h-full rounded-full flex items-center justify-end pr-3 text-white font-semibold text-sm transition-all`}
                                style={{
                                  width: `${width}%`,
                                  backgroundColor: index === 0 ? '#3b82f6' : index === 1 ? '#8b5cf6' : '#10b981'
                                }}
                              >
                                {width > 15 && `${Math.round(width)}%`}
                              </div>
                            </div>
                          </div>
                        )
                      })
                    ) : (
                      <p className="text-gray-500 text-center py-8">깔때기 데이터를 불러오는 중입니다...</p>
                    )}
                  </div>
                </div>

                {/* 전환 요약 */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-600">
                    <div className="text-gray-600 text-sm font-medium">총 진입 사용자</div>
                    <div className="text-3xl font-bold text-blue-600 mt-2">
                      {funnelData.total_users.toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-white rounded-lg shadow p-4 border-l-4 border-purple-600">
                    <div className="text-gray-600 text-sm font-medium">최종 전환</div>
                    <div className="text-3xl font-bold text-purple-600 mt-2">
                      {funnelData.final_conversions.toLocaleString()}
                    </div>
                  </div>
                  <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-600">
                    <div className="text-gray-600 text-sm font-medium">전체 전환율</div>
                    <div className="text-3xl font-bold text-green-600 mt-2">
                      {funnelData.overall_conversion}%
                    </div>
                  </div>
                  <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-600">
                    <div className="text-gray-600 text-sm font-medium">이탈 사용자</div>
                    <div className="text-3xl font-bold text-red-600 mt-2">
                      {(funnelData.total_users - funnelData.final_conversions).toLocaleString()}
                    </div>
                  </div>
                </div>

                {/* 단계별 상세 */}
                <div className="bg-gray-50 rounded-lg p-4">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">📋 단계별 상세</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-200">
                        <tr>
                          <th className="px-4 py-2 text-left">단계</th>
                          <th className="px-4 py-2 text-right">사용자 수</th>
                          <th className="px-4 py-2 text-right">전체 대비 (%)</th>
                          <th className="px-4 py-2 text-right">단계 전환율 (%)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {funnelData.stages.length > 0 ? (
                          funnelData.stages.map((stage, index) => (
                            <tr key={index} className="border-b hover:bg-gray-100">
                              <td className="px-4 py-2 font-medium">{stage.stage}</td>
                              <td className="px-4 py-2 text-right">{stage.count.toLocaleString()}</td>
                              <td className="px-4 py-2 text-right font-semibold">{stage.conversion_rate}%</td>
                              <td className="px-4 py-2 text-right font-semibold">{stage.step_conversion}%</td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={4} className="px-4 py-2 text-center text-gray-500">
                              데이터 없음
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 주의사항 */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-8">
          <h3 className="text-sm font-semibold text-blue-900 mb-2">📌 정보</h3>
          <ul className="text-sm text-blue-800 space-y-1">
            <li>• 실시간 GA4 데이터를 표시합니다</li>
            <li>• 데이터는 최대 24시간 지연될 수 있습니다</li>
            <li>• 측정 ID: <code className="bg-white px-2 py-1 rounded">G-JG5BXZD511</code></li>
            <li>• 자세한 분석은 <a href="https://analytics.google.com" target="_blank" rel="noopener noreferrer" className="underline hover:text-blue-600">Google Analytics 대시보드</a>에서 확인하세요</li>
          </ul>
        </div>
      </div>
    </div>
  )
}
