import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
  Legend,
} from 'recharts'

type SignupSource = { source: string; count: number }
type CategoryClick = { category: string; count: number }
type LoginModalSource = { source: string; count: number }

// 소스 이름을 한글로 변환
const sourceNameMap: Record<string, string> = {
  sidebar_login_button: '사이드바 로그인 버튼',
  header_login_button: '상단 로그인 버튼',
  premium_card_click: '환산 점수 카드 클릭',
  rate_limit_prompt: '3회 채팅 후 로그인 유도',
  thinking_mode_button: 'Thinking 모드 버튼',
  score_input_button: '성적표 입력하기 버튼',
  mock_exam_button: '모의고사 성적 입력 버튼',
  unknown: '알 수 없음',
}

const COLORS = ['#4f46e5', '#059669', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#65a30d', '#be185d']

export default function AdminAnalyticsFunnel() {
  const { accessToken } = useAuth()
  const [days, setDays] = useState(30)
  
  // 회원가입 경로 통계
  const [signupSources, setSignupSources] = useState<SignupSource[]>([])
  const [signupTotal, setSignupTotal] = useState(0)
  const [signupLoading, setSignupLoading] = useState(false)
  const [signupError, setSignupError] = useState<string | null>(null)
  
  // 카테고리 클릭 통계
  const [categoryClicks, setCategoryClicks] = useState<CategoryClick[]>([])
  const [categoryTotal, setCategoryTotal] = useState(0)
  const [categoryLoading, setCategoryLoading] = useState(false)
  const [categoryError, setCategoryError] = useState<string | null>(null)
  
  // 로그인 모달 열림 경로 통계
  const [loginModalSources, setLoginModalSources] = useState<LoginModalSource[]>([])
  const [loginModalTotal, setLoginModalTotal] = useState(0)
  const [loginModalLoading, setLoginModalLoading] = useState(false)
  const [loginModalError, setLoginModalError] = useState<string | null>(null)

  const fetchSignupSources = useCallback(async () => {
    if (!accessToken) return
    setSignupLoading(true)
    setSignupError(null)
    try {
      const res = await axios.get<{ total_signups: number; sources: SignupSource[] }>(
        `/api/tracking/signup-sources?days=${days}`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      )
      setSignupSources(res.data.sources || [])
      setSignupTotal(res.data.total_signups || 0)
    } catch (err: any) {
      setSignupError(err.response?.data?.detail || '조회 실패')
    } finally {
      setSignupLoading(false)
    }
  }, [accessToken, days])

  const fetchCategoryClicks = useCallback(async () => {
    if (!accessToken) return
    setCategoryLoading(true)
    setCategoryError(null)
    try {
      const res = await axios.get<{ total_clicks: number; categories: CategoryClick[] }>(
        `/api/tracking/category-clicks?days=${days}`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      )
      setCategoryClicks(res.data.categories || [])
      setCategoryTotal(res.data.total_clicks || 0)
    } catch (err: any) {
      setCategoryError(err.response?.data?.detail || '조회 실패')
    } finally {
      setCategoryLoading(false)
    }
  }, [accessToken, days])

  const fetchLoginModalSources = useCallback(async () => {
    if (!accessToken) return
    setLoginModalLoading(true)
    setLoginModalError(null)
    try {
      const res = await axios.get<{ total_opens: number; sources: LoginModalSource[] }>(
        `/api/tracking/login-modal-sources?days=${days}`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      )
      setLoginModalSources(res.data.sources || [])
      setLoginModalTotal(res.data.total_opens || 0)
    } catch (err: any) {
      setLoginModalError(err.response?.data?.detail || '조회 실패')
    } finally {
      setLoginModalLoading(false)
    }
  }, [accessToken, days])

  useEffect(() => {
    fetchSignupSources()
    fetchCategoryClicks()
    fetchLoginModalSources()
  }, [fetchSignupSources, fetchCategoryClicks, fetchLoginModalSources])

  const handleRefresh = () => {
    fetchSignupSources()
    fetchCategoryClicks()
    fetchLoginModalSources()
  }

  // 파이 차트용 데이터 변환
  const signupPieData = signupSources.map((s, i) => ({
    name: sourceNameMap[s.source] || s.source,
    value: s.count,
    fill: COLORS[i % COLORS.length],
  }))

  const loginModalPieData = loginModalSources.map((s, i) => ({
    name: sourceNameMap[s.source] || s.source,
    value: s.count,
    fill: COLORS[i % COLORS.length],
  }))

  return (
    <>
      {/* 기간 선택 */}
      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100 mb-8">
        <div className="flex flex-wrap items-center gap-4">
          <span className="font-medium text-gray-700">조회 기간:</span>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value={7}>최근 7일</option>
            <option value={14}>최근 14일</option>
            <option value={30}>최근 30일</option>
            <option value={60}>최근 60일</option>
            <option value={90}>최근 90일</option>
          </select>
          <button
            onClick={handleRefresh}
            disabled={signupLoading || categoryLoading || loginModalLoading}
            className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {signupLoading || categoryLoading || loginModalLoading ? '조회 중...' : '새로고침'}
          </button>
        </div>
      </div>

      {/* 요약 카드 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
          <div className="text-3xl mb-2">🚪</div>
          <h3 className="font-semibold text-gray-800 mb-1">로그인 모달 열림</h3>
          <p className="text-2xl font-bold text-indigo-600">{loginModalTotal.toLocaleString()}회</p>
          <p className="text-sm text-gray-500 mt-1">최근 {days}일</p>
        </div>
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
          <div className="text-3xl mb-2">✅</div>
          <h3 className="font-semibold text-gray-800 mb-1">회원가입 완료</h3>
          <p className="text-2xl font-bold text-green-600">{signupTotal.toLocaleString()}명</p>
          <p className="text-sm text-gray-500 mt-1">최근 {days}일</p>
        </div>
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
          <div className="text-3xl mb-2">🎯</div>
          <h3 className="font-semibold text-gray-800 mb-1">카테고리 클릭</h3>
          <p className="text-2xl font-bold text-orange-600">{categoryTotal.toLocaleString()}회</p>
          <p className="text-sm text-gray-500 mt-1">최근 {days}일</p>
        </div>
      </div>

      {/* 로그인 모달 열림 경로 */}
      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100 mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-4">🚪 로그인 모달 열림 경로</h2>
        <p className="text-sm text-gray-500 mb-4">
          사용자가 어떤 경로로 로그인 모달을 열었는지 추적합니다.
        </p>
        {loginModalError ? (
          <p className="text-red-600 text-sm">{loginModalError}</p>
        ) : loginModalLoading ? (
          <p className="text-gray-500">로딩 중...</p>
        ) : loginModalSources.length === 0 ? (
          <p className="text-gray-500">데이터가 없습니다.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 파이 차트 */}
            <div>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={loginModalPieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
                    outerRadius={100}
                    dataKey="value"
                  >
                    {loginModalPieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => [(value ?? 0).toLocaleString() + '회', '']} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            {/* 테이블 */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse border border-gray-200">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="border border-gray-200 px-3 py-2 text-left font-medium">경로</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">횟수</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">비율</th>
                  </tr>
                </thead>
                <tbody>
                  {loginModalSources.map((s, i) => (
                    <tr key={s.source} className="hover:bg-gray-50">
                      <td className="border border-gray-200 px-3 py-2">
                        <span className="inline-block w-3 h-3 rounded-full mr-2" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                        {sourceNameMap[s.source] || s.source}
                      </td>
                      <td className="border border-gray-200 px-3 py-2 text-right">{s.count.toLocaleString()}</td>
                      <td className="border border-gray-200 px-3 py-2 text-right">
                        {loginModalTotal > 0 ? ((s.count / loginModalTotal) * 100).toFixed(1) : 0}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* 회원가입 경로별 통계 */}
      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100 mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-4">✅ 회원가입 경로별 통계</h2>
        <p className="text-sm text-gray-500 mb-4">
          사용자가 어떤 경로를 통해 회원가입을 완료했는지 추적합니다.
        </p>
        {signupError ? (
          <p className="text-red-600 text-sm">{signupError}</p>
        ) : signupLoading ? (
          <p className="text-gray-500">로딩 중...</p>
        ) : signupSources.length === 0 ? (
          <p className="text-gray-500">데이터가 없습니다.</p>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* 파이 차트 */}
            <div>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={signupPieData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
                    outerRadius={100}
                    dataKey="value"
                  >
                    {signupPieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value) => [(value ?? 0).toLocaleString() + '명', '']} />
                </PieChart>
              </ResponsiveContainer>
            </div>
            {/* 테이블 */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse border border-gray-200">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="border border-gray-200 px-3 py-2 text-left font-medium">경로</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">가입자 수</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">비율</th>
                  </tr>
                </thead>
                <tbody>
                  {signupSources.map((s, i) => (
                    <tr key={s.source} className="hover:bg-gray-50">
                      <td className="border border-gray-200 px-3 py-2">
                        <span className="inline-block w-3 h-3 rounded-full mr-2" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                        {sourceNameMap[s.source] || s.source}
                      </td>
                      <td className="border border-gray-200 px-3 py-2 text-right">{s.count.toLocaleString()}</td>
                      <td className="border border-gray-200 px-3 py-2 text-right">
                        {signupTotal > 0 ? ((s.count / signupTotal) * 100).toFixed(1) : 0}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* 카테고리 버튼 클릭 통계 */}
      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100 mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-4">🎯 카테고리 버튼 클릭 통계</h2>
        <p className="text-sm text-gray-500 mb-4">
          메인 화면의 카테고리 카드(합격 예측, 환산 점수, 모집요강, 대학 정보) 클릭 횟수입니다.
        </p>
        {categoryError ? (
          <p className="text-red-600 text-sm">{categoryError}</p>
        ) : categoryLoading ? (
          <p className="text-gray-500">로딩 중...</p>
        ) : categoryClicks.length === 0 ? (
          <p className="text-gray-500">데이터가 없습니다.</p>
        ) : (
          <div>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={categoryClicks} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="category" tick={{ fontSize: 12 }} stroke="#6b7280" />
                <YAxis tick={{ fontSize: 12 }} stroke="#6b7280" />
                <Tooltip
                  formatter={(value) => [(value ?? 0).toLocaleString() + '회', '클릭 수']}
                  contentStyle={{ borderRadius: 8 }}
                />
                <Bar dataKey="count" name="클릭 수" radius={[4, 4, 0, 0]}>
                  {categoryClicks.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            {/* 테이블 */}
            <div className="mt-6 overflow-x-auto">
              <table className="w-full text-sm border-collapse border border-gray-200">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="border border-gray-200 px-3 py-2 text-left font-medium">카테고리</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">클릭 수</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">비율</th>
                  </tr>
                </thead>
                <tbody>
                  {categoryClicks.map((c, i) => (
                    <tr key={c.category} className="hover:bg-gray-50">
                      <td className="border border-gray-200 px-3 py-2">
                        <span className="inline-block w-3 h-3 rounded-full mr-2" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                        {c.category}
                      </td>
                      <td className="border border-gray-200 px-3 py-2 text-right">{c.count.toLocaleString()}</td>
                      <td className="border border-gray-200 px-3 py-2 text-right">
                        {categoryTotal > 0 ? ((c.count / categoryTotal) * 100).toFixed(1) : 0}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* 분석 요약 */}
      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
        <h2 className="text-lg font-bold text-gray-800 mb-4">📊 유입 퍼널 분석 요약</h2>
        <p className="text-gray-600">
          이 페이지에서는 사용자가 어떤 경로로 로그인 모달을 열고, 회원가입을 완료했는지 추적합니다.
          또한 메인 화면의 카테고리 카드 클릭 통계를 확인할 수 있습니다.
        </p>
        <ul className="mt-4 space-y-2 text-sm text-gray-600">
          <li>• <strong>로그인 모달 열림 경로</strong>: 사용자가 어떤 버튼/기능을 통해 로그인 모달을 열었는지</li>
          <li>• <strong>회원가입 경로</strong>: 회원가입 완료 시 마지막으로 로그인 모달을 연 경로</li>
          <li>• <strong>카테고리 클릭</strong>: 합격 예측, 환산 점수, 모집요강, 대학 정보 카드 클릭 횟수</li>
        </ul>
      </div>
    </>
  )
}
