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
      .get<{ series: QuestionCumulativePoint[] }>('/api/admin/stats/questions/cumulative-timeseries', { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((res) => { if (!cancelled) setQuestionSeries(res.data.series || []) })
      .catch((err) => { if (!cancelled) setQuestionSeriesError(err.response?.data?.detail ?? '조회 실패') })
    return () => { cancelled = true }
  }, [accessToken])

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
