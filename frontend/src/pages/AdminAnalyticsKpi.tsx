import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import * as XLSX from 'xlsx'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
  BarChart,
  Bar,
  Cell,
} from 'recharts'

type CumulativePoint = { day: string; new_users: number; cumulative_users: number }
type QuestionCumulativePoint = { day: string; new_questions: number; cumulative_questions: number }

export type RetentionPoint = {
  cohort_day: string
  cohort_users: number
  day_1_users: number
  day_2_users: number
  day_3_users: number
  day_4_users: number
  day_5_users: number
  day_6_users: number
  day_7_users: number
  day_1_rate: number
  day_2_rate: number
  day_3_rate: number
  day_4_rate: number
  day_5_rate: number
  day_6_rate: number
  day_7_rate: number
}

export type PathRow = {
  step: string
  sessionSource: string
  activeUsers: number
  completionRate: number
  exits: number
  bounceRate: number
}

const STORAGE_KEY_PATH = 'admin_analytics_path_data'
const STORAGE_KEY_SOURCE = 'admin_analytics_path_source'

function parsePathExcel(file: File): Promise<PathRow[]> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const data = e.target?.result
        if (!data) return reject(new Error('파일을 읽을 수 없습니다.'))
        const wb = XLSX.read(data, { type: 'binary', cellDates: false })
        const firstSheet = wb.Sheets[wb.SheetNames[0]]
        const rows: unknown[][] = XLSX.utils.sheet_to_json(firstSheet, { header: 1 })
        const headerIdx = rows.findIndex((r) => Array.isArray(r) && r[0] === '단계')
        if (headerIdx < 0) return reject(new Error("'단계' 헤더를 찾을 수 없습니다. GA4 유입경로 탐색 분석 엑셀 형식인지 확인하세요."))
        const parsed: PathRow[] = []
        for (let i = headerIdx + 1; i < rows.length; i++) {
          const r = rows[i] as unknown[]
          if (!r || r.length < 6) continue
          const step = String(r[0] ?? '').trim()
          const sessionSource = String(r[1] ?? '').trim()
          if (!step) continue
          const activeUsers = Number(r[2])
          const completionRate = Number(r[3])
          const exits = Number(r[4])
          const bounceRate = Number(r[5])
          if (Number.isNaN(activeUsers)) continue
          parsed.push({
            step,
            sessionSource,
            activeUsers: Math.round(activeUsers),
            completionRate: Number.isNaN(completionRate) ? 0 : completionRate,
            exits: Number.isNaN(exits) ? 0 : Math.round(exits),
            bounceRate: Number.isNaN(bounceRate) ? 0 : bounceRate,
          })
        }
        resolve(parsed)
      } catch (err) {
        reject(err)
      }
    }
    reader.onerror = () => reject(new Error('파일 읽기 실패'))
    reader.readAsBinaryString(file)
  })
}

export default function AdminAnalyticsKpi() {
  const { accessToken } = useAuth()
  const [totalUsers, setTotalUsers] = useState<number | null>(null)
  const [usersError, setUsersError] = useState<string | null>(null)
  const [cumulativeSeries, setCumulativeSeries] = useState<CumulativePoint[]>([])
  const [seriesError, setSeriesError] = useState<string | null>(null)
  const [questionSeries, setQuestionSeries] = useState<QuestionCumulativePoint[]>([])
  const [questionSeriesError, setQuestionSeriesError] = useState<string | null>(null)
  const [pathData, setPathData] = useState<PathRow[]>([])
  const [pathUploadError, setPathUploadError] = useState<string | null>(null)
  const [selectedPathSource, setSelectedPathSource] = useState<string>('')
  const [activeRollingSeries, setActiveRollingSeries] = useState<{ days: number; active_users: number }[]>([])
  const [activeRollingError, setActiveRollingError] = useState<string | null>(null)
  const [retentionSeries, setRetentionSeries] = useState<RetentionPoint[]>([])
  const [retentionError, setRetentionError] = useState<string | null>(null)
  const [retentionFrom, setRetentionFrom] = useState<string>('')
  const [retentionTo, setRetentionTo] = useState<string>('')
  const [selectedRetentionDays, setSelectedRetentionDays] = useState<number[]>([1, 2, 3, 4, 5, 6, 7])
  const [retentionLoading, setRetentionLoading] = useState(false)
  const [cohortUserCohortDay, setCohortUserCohortDay] = useState<string>('')
  const [cohortUserDayN, setCohortUserDayN] = useState<number | ''>('')
  type CohortUserRow = {
    user_id: string | null
    email: string
    latestLog?: {
      id: string | null
      timestamp: string | null
      userQuestion: string
      finalAnswer: string
      conversationHistory: string[]
    } | null
  }
  const [cohortUserList, setCohortUserList] = useState<CohortUserRow[]>([])
  const [cohortUserLoading, setCohortUserLoading] = useState(false)
  const [cohortUserError, setCohortUserError] = useState<string | null>(null)
  const [cohortUserModalLog, setCohortUserModalLog] = useState<{ email: string; log: CohortUserRow['latestLog'] } | null>(null)
  // 서버에 저장 (한 번 넣어두면 다른 관리자도 동일하게 봄)
  const savePathExcel = useCallback(
    (data: PathRow[], source: string) => {
      if (!accessToken) return
      axios
        .put(
          '/api/admin/stats/path-excel',
          { pathData: data, selectedPathSource: source },
          { headers: { Authorization: `Bearer ${accessToken}` } }
        )
        .catch(() => { /* 저장 실패 시 무시(로컬에는 반영됨) */ })
    },
    [accessToken]
  )

  // 페이지 로드 시 서버에서 공용 엑셀 데이터 조회
  useEffect(() => {
    if (!accessToken) return
    let cancelled = false
    axios
      .get<{ pathData: PathRow[]; selectedPathSource: string }>('/api/admin/stats/path-excel', {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      .then((res) => {
        if (cancelled) return
        const data = res.data?.pathData || []
        const source = res.data?.selectedPathSource ?? ''
        if (data.length > 0) {
          setPathData(data)
          setSelectedPathSource(source)
        } else {
          // 서버에 없으면 로컬 저장값으로 초기화 (이전 브라우저 데이터)
          try {
            const raw = localStorage.getItem(STORAGE_KEY_PATH)
            if (raw) {
              const local = JSON.parse(raw) as PathRow[]
              if (local.length > 0) {
                setPathData(local)
                setSelectedPathSource(localStorage.getItem(STORAGE_KEY_SOURCE) ?? '')
              }
            }
          } catch {}
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [accessToken])

  // 로컬에도 동기화 (오프라인/캐시용)
  useEffect(() => {
    if (pathData.length > 0) localStorage.setItem(STORAGE_KEY_PATH, JSON.stringify(pathData))
  }, [pathData])
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY_SOURCE, selectedPathSource)
  }, [selectedPathSource])

  const handlePathFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0]
      e.target.value = ''
      setPathUploadError(null)
      if (!file) return
      if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
        setPathUploadError('엑셀 파일(.xlsx, .xls)만 업로드 가능합니다.')
        return
      }
      parsePathExcel(file)
        .then((parsed) => {
          setPathData(parsed)
          setSelectedPathSource('')
          savePathExcel(parsed, '')
        })
        .catch((err) => setPathUploadError(err?.message ?? '파싱 실패'))
    },
    [savePathExcel]
  )

  const pathSessionSources = (() => {
    const set = new Set(pathData.map((r) => r.sessionSource))
    const list = Array.from(set)
    const totalLike = list.find((s) => /총계|total|전체/i.test(s))
    const rest = list.filter((s) => s !== totalLike).sort((a, b) => a.localeCompare(b, 'ko'))
    return totalLike ? [totalLike, ...rest] : rest
  })()

  const pathChartData = (() => {
    if (selectedPathSource) {
      return pathData
        .filter((r) => r.sessionSource === selectedPathSource)
        .sort((a, b) => a.step.localeCompare(b.step, 'ko'))
    }
    const byStep = new Map<string, PathRow>()
    for (const r of pathData) {
      const cur = byStep.get(r.step)
      if (!cur || r.activeUsers > cur.activeUsers) byStep.set(r.step, r)
    }
    return Array.from(byStep.values()).sort((a, b) => a.step.localeCompare(b.step, 'ko'))
  })()

  const pathTableRows = selectedPathSource
    ? pathData.filter((r) => r.sessionSource === selectedPathSource)
    : pathData

  useEffect(() => {
    if (!accessToken) return
    let cancelled = false
    axios
      .get<{ total_users: number }>('/api/admin/stats/users/count', { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((res) => { if (!cancelled) setTotalUsers(res.data.total_users) })
      .catch((err) => { if (!cancelled) setUsersError(err.response?.data?.detail ?? '조회 실패') })
    return () => { cancelled = true }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken) return
    let cancelled = false
    axios
      .get<{ series: CumulativePoint[] }>('/api/admin/stats/users/cumulative-timeseries', { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((res) => { if (!cancelled) setCumulativeSeries(res.data.series || []) })
      .catch((err) => { if (!cancelled) setSeriesError(err.response?.data?.detail ?? '조회 실패') })
    return () => { cancelled = true }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken) return
    let cancelled = false
    axios
      .get<{ series: { days: number; active_users: number }[] }>('/api/admin/stats/active-users/rolling', { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((res) => { if (!cancelled) setActiveRollingSeries(res.data.series || []) })
      .catch((err) => { if (!cancelled) setActiveRollingError(err.response?.data?.detail ?? '조회 실패') })
    return () => { cancelled = true }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken) return
    let cancelled = false
    axios
      .get<{ series: QuestionCumulativePoint[] }>('/api/admin/stats/questions/cumulative-timeseries', { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((res) => { if (!cancelled) setQuestionSeries(res.data.series || []) })
      .catch((err) => { if (!cancelled) setQuestionSeriesError(err.response?.data?.detail ?? '조회 실패') })
    return () => { cancelled = true }
  }, [accessToken])

  const fetchRetention = useCallback(() => {
    if (!accessToken) return
    setRetentionLoading(true)
    setRetentionError(null)
    const params = new URLSearchParams()
    if (retentionFrom) params.set('from_date', retentionFrom)
    if (retentionTo) params.set('to_date', retentionTo)
    const url = `/api/admin/stats/retention/day-series${params.toString() ? `?${params.toString()}` : ''}`
    axios
      .get<{ series: RetentionPoint[] }>(url, { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((res) => {
        setRetentionSeries(res.data.series || [])
      })
      .catch((err) => {
        setRetentionError(err.response?.data?.detail ?? '리텐션 조회 실패')
      })
      .finally(() => setRetentionLoading(false))
  }, [accessToken, retentionFrom, retentionTo])

  useEffect(() => {
    if (!accessToken) return
    fetchRetention()
  }, [accessToken])

  const fetchCohortUsers = useCallback(() => {
    if (!accessToken || !cohortUserCohortDay) return
    setCohortUserLoading(true)
    setCohortUserError(null)
    const params = new URLSearchParams({ cohort_day: cohortUserCohortDay })
    if (cohortUserDayN !== '') params.set('day_n', String(cohortUserDayN))
    axios
      .get<{ users: { user_id: string | null; email: string }[] }>(
        `/api/admin/stats/retention/cohort-users?${params.toString()}`,
        { headers: { Authorization: `Bearer ${accessToken}` } }
      )
      .then((res) => setCohortUserList(res.data.users || []))
      .catch((err) => setCohortUserError(err.response?.data?.detail ?? '유저 목록 조회 실패'))
      .finally(() => setCohortUserLoading(false))
  }, [accessToken, cohortUserCohortDay, cohortUserDayN])

  const formatDay = (dayStr: string) => {
    if (!dayStr) return ''
    const [y, m, d] = dayStr.split('-')
    return `${Number(m)}/${Number(d)}`
  }
  const chartData = cumulativeSeries.map((p) => ({ ...p, dayLabel: formatDay(p.day) }))
  const questionChartData = questionSeries.map((p) => ({ ...p, dayLabel: formatDay(p.day) }))
  const totalQuestions = questionSeries.length > 0 ? questionSeries[questionSeries.length - 1].cumulative_questions : null

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
          <div className="text-3xl mb-2">👥</div>
          <h3 className="font-semibold text-gray-800 mb-1">누적 가입자 수</h3>
          {usersError ? (
            <p className="text-red-600 text-sm">{usersError}</p>
          ) : totalUsers !== null ? (
            <p className="text-2xl font-bold text-indigo-600">{totalUsers.toLocaleString()}명</p>
          ) : (
            <p className="text-indigo-600">로딩 중...</p>
          )}
          <p className="text-sm text-gray-500 mt-1">Supabase Auth 사용자 수</p>
        </div>
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
          <div className="text-3xl mb-2">💬</div>
          <h3 className="font-semibold text-gray-800 mb-1">누적 질문 수</h3>
          {questionSeriesError ? (
            <p className="text-red-600 text-sm">{questionSeriesError}</p>
          ) : totalQuestions !== null ? (
            <p className="text-2xl font-bold text-indigo-600">{totalQuestions.toLocaleString()}건</p>
          ) : (
            <p className="text-indigo-600">로딩 중...</p>
          )}
          <p className="text-sm text-gray-500 mt-1">admin_logs 기준</p>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100 mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-4">📊 활성 사용자 (오늘 기준 롤링, admin_logs)</h2>
        <p className="text-sm text-gray-500 mb-4">활성 사용자 = 로그인 유저 중 질문한 유저. 오늘만, 어제+오늘, …, 1주(7일), 2주(14일) 구간별 수</p>
        {activeRollingError ? (
          <p className="text-red-600 text-sm">{activeRollingError}</p>
        ) : activeRollingSeries.length === 0 ? (
          <p className="text-gray-500">로딩 중...</p>
        ) : (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 lg:grid-cols-7 gap-3 mb-6">
              {activeRollingSeries.map((p) => (
                <div key={p.days} className="rounded-xl border border-gray-200 bg-gray-50/50 p-3 text-center">
                  <div className="text-xs font-medium text-gray-500 mb-0.5">
                    {p.days === 1 ? '오늘' : p.days === 7 ? '1주' : p.days === 14 ? '2주' : `${p.days}일`}
                  </div>
                  <div className="text-lg font-bold text-indigo-600">{p.active_users.toLocaleString()}명</div>
                </div>
              ))}
            </div>
            <div className="border-t border-gray-200 pt-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">추이 그래프</h3>
              <ResponsiveContainer width="100%" height={280}>
                <LineChart
                  data={activeRollingSeries.map((p) => ({
                    days: p.days,
                    label: p.days === 1 ? '오늘' : p.days === 7 ? '1주' : p.days === 14 ? '2주' : `${p.days}일`,
                    active_users: p.active_users,
                  }))}
                  margin={{ top: 8, right: 16, left: 0, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="#6b7280" />
                  <YAxis tick={{ fontSize: 12 }} stroke="#6b7280" allowDecimals={false} />
                  <Tooltip
                    formatter={(value: number | undefined) => [value != null ? value.toLocaleString() + '명' : '-', '활성 사용자']}
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.days ? `최근 ${payload[0].payload.days}일` : ''}
                    contentStyle={{ borderRadius: 8 }}
                  />
                  <Line type="monotone" dataKey="active_users" name="활성 사용자" stroke="#4f46e5" strokeWidth={2} dot={{ r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </>
        )}
      </div>

      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100 mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-4">📈 누적 가입자 추이 (Created at 기준)</h2>
        {seriesError ? (
          <p className="text-red-600 text-sm">{seriesError}</p>
        ) : chartData.length === 0 ? (
          <p className="text-gray-500">데이터 로딩 중이거나 가입 이력이 없습니다.</p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="dayLabel" tick={{ fontSize: 12 }} stroke="#6b7280" />
              <YAxis tick={{ fontSize: 12 }} stroke="#6b7280" />
              <Tooltip
                formatter={(value: number | undefined) => [(value ?? 0).toLocaleString() + '명', '']}
                labelFormatter={(_, payload) => (payload?.[0]?.payload?.day ?? '') + ' (한국 날짜)'}
                contentStyle={{ borderRadius: 8 }}
              />
              <Legend />
              <Area type="monotone" dataKey="cumulative_users" name="누적 가입자 수" stroke="#4f46e5" fill="#818cf8" fillOpacity={0.3} strokeWidth={2} />
              <Line type="monotone" dataKey="new_users" name="일별 신규 가입" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100 mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-4">📈 누적 질문 수 (일자별, admin_logs.created_at 기준)</h2>
        {questionSeriesError ? (
          <p className="text-red-600 text-sm">{questionSeriesError}</p>
        ) : questionChartData.length === 0 ? (
          <p className="text-gray-500">데이터 로딩 중이거나 질문 이력이 없습니다.</p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={questionChartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="dayLabel" tick={{ fontSize: 12 }} stroke="#6b7280" />
              <YAxis tick={{ fontSize: 12 }} stroke="#6b7280" />
              <Tooltip
                formatter={(value: number | undefined) => [(value ?? 0).toLocaleString() + '건', '']}
                labelFormatter={(_, payload) => (payload?.[0]?.payload?.day ?? '') + ' (한국 날짜)'}
                contentStyle={{ borderRadius: 8 }}
              />
              <Legend />
              <Area type="monotone" dataKey="cumulative_questions" name="누적 질문 수" stroke="#059669" fill="#34d399" fillOpacity={0.3} strokeWidth={2} />
              <Line type="monotone" dataKey="new_questions" name="일별 신규 질문" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100 mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-4">📊 Day-1 ~ Day-7 리텐션 추이 (admin_logs 태생일 기준)</h2>
        <p className="text-sm text-gray-500 mb-4">
          가입일(최초 방문일)이 같은 코호트별로, 다음 날·2일 후·…·7일 후 재방문 비율(%).
        </p>
        <div className="flex flex-wrap items-center gap-4 mb-4">
          <label className="flex items-center gap-2 text-sm">
            <span className="text-gray-600">시작일</span>
            <input
              type="date"
              value={retentionFrom}
              onChange={(e) => setRetentionFrom(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-gray-600">종료일</span>
            <input
              type="date"
              value={retentionTo}
              onChange={(e) => setRetentionTo(e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2 text-sm"
            />
          </label>
          <button
            type="button"
            onClick={fetchRetention}
            disabled={retentionLoading}
            className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            {retentionLoading ? '조회 중…' : '조회'}
          </button>
          <span className="text-sm text-gray-500">표시할 Day:</span>
          <div className="flex flex-wrap gap-2">
            {[1, 2, 3, 4, 5, 6, 7].map((d) => (
              <label key={d} className="inline-flex items-center gap-1 text-sm cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedRetentionDays.includes(d)}
                  onChange={() => {
                    setSelectedRetentionDays((prev) =>
                      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d].sort((a, b) => a - b))
                  }}
                />
                Day-{d}
              </label>
            ))}
          </div>
        </div>
        {retentionError ? (
          <p className="text-red-600 text-sm">{retentionError}</p>
        ) : retentionSeries.length === 0 && !retentionLoading ? (
          <p className="text-gray-500">데이터가 없거나 기간을 선택 후 조회해 주세요.</p>
        ) : (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart
              data={retentionSeries.map((p) => ({
                ...p,
                cohortLabel: formatDay(p.cohort_day),
              }))}
              margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="cohortLabel" tick={{ fontSize: 12 }} stroke="#6b7280" />
              <YAxis tick={{ fontSize: 12 }} stroke="#6b7280" unit="%" domain={[0, 'auto']} />
              <Tooltip
                formatter={(value: number | undefined) => [(value != null ? value : 0).toFixed(1) + '%', '']}
                labelFormatter={(_, payload) => (payload?.[0]?.payload?.cohort_day ?? '') + ' (가입일)'}
                contentStyle={{ borderRadius: 8 }}
              />
              <Legend />
              {[1, 2, 3, 4, 5, 6, 7].map((d) =>
                selectedRetentionDays.includes(d) ? (
                  <Line
                    key={d}
                    type="monotone"
                    dataKey={`day_${d}_rate`}
                    name={`Day-${d}`}
                    stroke={['#4f46e5', '#059669', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#65a30d'][d - 1]}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                ) : null
              )}
            </LineChart>
          </ResponsiveContainer>
        )}
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">👤 해당 코호트 유저 보기</h3>
          <p className="text-xs text-gray-500 mb-3">가입일(코호트)을 선택하고, 전체 유저 또는 Day-N 달성 유저만 조회할 수 있습니다.</p>
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <label className="flex items-center gap-2 text-sm">
              <span className="text-gray-600">가입일(코호트)</span>
              <select
                value={cohortUserCohortDay}
                onChange={(e) => setCohortUserCohortDay(e.target.value)}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm min-w-[140px]"
              >
                <option value="">선택</option>
                {retentionSeries.map((p) => (
                  <option key={p.cohort_day} value={p.cohort_day}>
                    {p.cohort_day} (유저 {p.cohort_users}명)
                  </option>
                ))}
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm">
              <span className="text-gray-600">대상</span>
              <select
                value={cohortUserDayN === '' ? '' : cohortUserDayN}
                onChange={(e) => setCohortUserDayN(e.target.value === '' ? '' : Number(e.target.value))}
                className="rounded-lg border border-gray-300 px-3 py-2 text-sm min-w-[120px]"
              >
                <option value="">전체 유저</option>
                {[1, 2, 3, 4, 5, 6, 7].map((d) => (
                  <option key={d} value={d}>Day-{d} 달성 유저</option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={fetchCohortUsers}
              disabled={cohortUserLoading || !cohortUserCohortDay}
              className="px-4 py-2 bg-gray-700 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50"
            >
              {cohortUserLoading ? '조회 중…' : '유저 목록 조회'}
            </button>
          </div>
          {cohortUserError && <p className="text-red-600 text-sm mb-2">{cohortUserError}</p>}
          {cohortUserList.length > 0 && (
            <div className="overflow-x-auto max-h-60 overflow-y-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm border-collapse">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="border-b border-gray-200 px-3 py-2 text-left font-medium text-gray-700">이메일</th>
                    <th className="border-b border-gray-200 px-3 py-2 text-left font-medium text-gray-700">user_id</th>
                    <th className="border-b border-gray-200 px-3 py-2 text-left font-medium text-gray-700 w-24">최신 대화</th>
                  </tr>
                </thead>
                <tbody>
                  {cohortUserList.map((u, i) => (
                    <tr key={u.user_id ?? i} className="hover:bg-gray-50">
                      <td className="border-b border-gray-100 px-3 py-2">{u.email || '-'}</td>
                      <td className="border-b border-gray-100 px-3 py-2 font-mono text-xs text-gray-500">{u.user_id ?? '-'}</td>
                      <td className="border-b border-gray-100 px-3 py-2">
                        {u.latestLog ? (
                          <button
                            type="button"
                            onClick={() => setCohortUserModalLog({ email: u.email || '', log: u.latestLog ?? undefined })}
                            className="text-indigo-600 hover:text-indigo-800 text-xs font-medium"
                          >
                            보기
                          </button>
                        ) : (
                          <span className="text-gray-400 text-xs">없음</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-gray-500 px-3 py-2 bg-gray-50 border-t border-gray-200">총 {cohortUserList.length}명</p>
            </div>
          )}
        {cohortUserModalLog && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={() => setCohortUserModalLog(null)}>
            <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
                <h3 className="font-semibold text-gray-800">최신 대화 · {cohortUserModalLog.email}</h3>
                <button type="button" onClick={() => setCohortUserModalLog(null)} className="text-gray-500 hover:text-gray-700 text-sm">닫기</button>
              </div>
              <div className="p-4 overflow-y-auto space-y-4">
                {cohortUserModalLog.log?.timestamp && (
                  <p className="text-xs text-gray-500">로그 ID: {cohortUserModalLog.log.id ?? '-'} · {new Date(cohortUserModalLog.log.timestamp).toLocaleString('ko-KR')}</p>
                )}
                <div>
                  <span className="text-gray-600 font-medium text-sm">질문</span>
                  <p className="mt-1 p-2 bg-gray-50 rounded border border-gray-200 whitespace-pre-wrap text-gray-800 text-sm">{cohortUserModalLog.log?.userQuestion || '(없음)'}</p>
                </div>
                <div>
                  <span className="text-gray-600 font-medium text-sm">최종 답변</span>
                  <p className="mt-1 p-2 bg-gray-50 rounded border border-gray-200 whitespace-pre-wrap text-gray-800 text-sm">{cohortUserModalLog.log?.finalAnswer || '(없음)'}</p>
                </div>
                <div>
                  <span className="text-gray-600 font-medium text-sm">conversation_history ({(cohortUserModalLog.log?.conversationHistory ?? []).length}개)</span>
                  <ul className="mt-1 space-y-1 max-h-64 overflow-y-auto p-2 bg-gray-50 rounded border border-gray-200">
                    {(cohortUserModalLog.log?.conversationHistory ?? []).length === 0 ? (
                      <li className="text-gray-500 text-xs">(비어 있음)</li>
                    ) : (
                      (cohortUserModalLog.log?.conversationHistory ?? []).map((msg, i) => (
                        <li key={i} className="text-gray-700 whitespace-pre-wrap border-b border-gray-100 last:border-0 pb-1 text-xs">
                          {typeof msg === 'string' ? msg : JSON.stringify(msg)}
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        )}
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100 mb-8">
        <h2 className="text-lg font-bold text-gray-800 mb-4">🔀 유입경로 엑셀 시각화</h2>
        <p className="text-sm text-gray-500 mb-4">
          GA4 유입경로 탐색 분석에서 내보낸 엑셀(단계, 세션 소스, 활성 사용자, 완료율, 이탈수, 이탈률)을 넣으면 자동으로 시각화합니다.
        </p>
        <label className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-100 text-indigo-800 rounded-lg cursor-pointer hover:bg-indigo-200 transition-colors font-medium">
          <span>📁 엑셀 선택</span>
          <input type="file" accept=".xlsx,.xls" className="hidden" onChange={handlePathFile} />
        </label>
        {pathUploadError && <p className="mt-2 text-red-600 text-sm">{pathUploadError}</p>}
        {pathData.length > 0 && (
          <>
            <div className="mt-6 flex flex-wrap items-center gap-4">
              <span className="font-medium text-gray-700">세션 소스:</span>
              <select
                value={selectedPathSource}
                onChange={(e) => {
                  const v = e.target.value
                  setSelectedPathSource(v)
                  savePathExcel(pathData, v)
                }}
                className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 min-w-[180px]"
              >
                <option value="">전체 (단계별 최대)</option>
                {pathSessionSources.map((src) => (
                  <option key={src} value={src}>{src}</option>
                ))}
              </select>
              <span className="text-sm text-gray-500">
                {selectedPathSource ? `"${selectedPathSource}" 기준` : '단계별 최대 활성 사용자'}
              </span>
            </div>
            <div className="mt-6">
              <h3 className="font-semibold text-gray-700 mb-3">단계별 활성 사용자 {selectedPathSource ? `· ${selectedPathSource}` : ''}</h3>
              {pathChartData.length === 0 ? (
                <p className="text-gray-500 py-4">선택한 세션 소스에 해당하는 단계 데이터가 없습니다.</p>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={pathChartData} layout="vertical" margin={{ left: 120, right: 24, top: 8, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis type="number" tick={{ fontSize: 12 }} />
                    <YAxis type="category" dataKey="step" width={110} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(value: number | undefined) => [(value ?? 0).toLocaleString() + '명', '활성 사용자']} contentStyle={{ borderRadius: 8 }} />
                    <Bar dataKey="activeUsers" name="활성 사용자" fill="#4f46e5" radius={[0, 4, 4, 0]}>
                      {pathChartData.map((_, i) => (
                        <Cell key={i} fill={['#4f46e5', '#6366f1', '#818cf8', '#a5b4fc'][i % 4]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
            <div className="mt-6 overflow-x-auto">
              <h3 className="font-semibold text-gray-700 mb-3">세션 소스별 상세 {selectedPathSource ? `· ${selectedPathSource}` : '· 전체'}</h3>
              <table className="w-full text-sm border-collapse border border-gray-200">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="border border-gray-200 px-3 py-2 text-left font-medium">단계</th>
                    <th className="border border-gray-200 px-3 py-2 text-left font-medium">세션 소스</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">활성 사용자</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">완료율</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">이탈수</th>
                    <th className="border border-gray-200 px-3 py-2 text-right font-medium">이탈률</th>
                  </tr>
                </thead>
                <tbody>
                  {pathTableRows.map((row, i) => (
                    <tr key={i} className="hover:bg-gray-50">
                      <td className="border border-gray-200 px-3 py-2">{row.step}</td>
                      <td className="border border-gray-200 px-3 py-2">{row.sessionSource}</td>
                      <td className="border border-gray-200 px-3 py-2 text-right">{row.activeUsers.toLocaleString()}</td>
                      <td className="border border-gray-200 px-3 py-2 text-right">{(row.completionRate * 100).toFixed(1)}%</td>
                      <td className="border border-gray-200 px-3 py-2 text-right">{row.exits.toLocaleString()}</td>
                      <td className="border border-gray-200 px-3 py-2 text-right">{(row.bounceRate * 100).toFixed(1)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>

      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
        <h2 className="text-lg font-bold text-gray-800 mb-4">📈 분석 요약</h2>
        <p className="text-gray-600">
          KPI 확인 페이지입니다. 누적 가입자·질문 수, 유입경로 엑셀 시각화를 제공합니다.
        </p>
      </div>
    </>
  )
}
