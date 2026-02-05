import { useState, useEffect, useMemo } from 'react'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  LabelList,
} from 'recharts'

type SamePersonPoint = {
  is_same_person: string
  latest_ts: string
  total_questions: number
  distinct_hour_appearances: number
  label: string
}

type LatestLog = {
  id: string
  timestamp: string
  userQuestion: string
  finalAnswer: string
  conversationHistory: string[]
}

/** 같은 (total_questions, distinct_hour_appearances)끼리 묶은 한 점 */
type GroupedPoint = {
  total_questions: number
  distinct_hour_appearances: number
  count: number
  coordinateLabel: string
  persons: SamePersonPoint[]
}

/** 클릭한 좌표의 사용자별 로그 */
type GroupDetailItem = {
  person: SamePersonPoint
  log: LatestLog | null
  error?: string
}

const COLORS = ['#4f46e5', '#059669', '#d97706', '#dc2626', '#7c3aed', '#0891b2', '#65a30d', '#ca8a04']

export default function AdminAnalyticsBehavior() {
  const { accessToken } = useAuth()
  const [items, setItems] = useState<SamePersonPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [summary, setSummary] = useState<{ count_is_same_person_null: number; count_no_user_id_same_person: number } | null>(null)
  const [nullRows, setNullRows] = useState<{ id: string; timestamp: string; userQuestionSnippet: string }[]>([])
  const [nullRowsLoading, setNullRowsLoading] = useState(false)
  const [modalLog, setModalLog] = useState<LatestLog | null>(null)
  const [modalLoading, setModalLoading] = useState(false)
  const [modalError, setModalError] = useState<string | null>(null)
  const [groupDetail, setGroupDetail] = useState<{ point: GroupedPoint; items: GroupDetailItem[] } | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState<string | null>(null)

  const groupedData = useMemo(() => {
    const key = (p: SamePersonPoint) => `${p.total_questions},${p.distinct_hour_appearances}`
    const map = new Map<string, SamePersonPoint[]>()
    for (const p of items) {
      const k = key(p)
      if (!map.has(k)) map.set(k, [])
      map.get(k)!.push(p)
    }
    return Array.from(map.entries()).map(([k, persons]) => {
      const [x, y] = k.split(',').map(Number)
      const count = persons.length
      return {
        total_questions: x,
        distinct_hour_appearances: y,
        count,
        coordinateLabel: count > 1 ? `(${x}, ${y}) ${count}명` : `(${x}, ${y})`,
        persons,
      } as GroupedPoint
    })
  }, [items])

  const fetchGroupDetails = (point: GroupedPoint) => {
    if (!accessToken || point.persons.length === 0) return
    setDetailLoading(true)
    setDetailError(null)
    setGroupDetail(null)
    const requests = point.persons.map((person) =>
      axios
        .get<{ log: LatestLog | null }>('/api/admin/stats/behavior/latest-conversation', {
          params: { is_same_person: person.is_same_person },
          headers: { Authorization: `Bearer ${accessToken}` },
        })
        .then((res): GroupDetailItem => ({ person, log: res.data.log ?? null }))
        .catch((err): GroupDetailItem => ({
          person,
          log: null,
          error: err.response?.data?.detail ?? '조회 실패',
        }))
    )
    Promise.all(requests).then((items) => {
      setGroupDetail({ point, items })
      setDetailLoading(false)
    })
  }

  const closeDetail = () => {
    setGroupDetail(null)
    setDetailError(null)
  }

  useEffect(() => {
    if (!accessToken) return
    let cancelled = false
    setLoading(true)
    setError(null)
    axios
      .get<{
        items: SamePersonPoint[]
        count_is_same_person_null: number
        count_no_user_id_same_person: number
      }>('/api/admin/stats/behavior/same-person-activity', {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      .then((res) => {
        if (cancelled) return
        const list = (res.data.items || []).map((r) => ({
          ...r,
          label: (r.is_same_person || '').slice(0, 8),
        }))
        setItems(list)
        setSummary({
          count_is_same_person_null: res.data.count_is_same_person_null ?? 0,
          count_no_user_id_same_person: res.data.count_no_user_id_same_person ?? 0,
        })
      })
      .catch((err) => {
        if (!cancelled) setError(err.response?.data?.detail ?? '조회 실패')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [accessToken])

  useEffect(() => {
    if (!accessToken || summary == null) return
    let cancelled = false
    setNullRowsLoading(true)
    axios
      .get<{ rows: { id: string; timestamp: string; userQuestionSnippet: string }[] }>(
        '/api/admin/stats/behavior/null-same-person-rows',
        { headers: { Authorization: `Bearer ${accessToken}` } }
      )
      .then((res) => { if (!cancelled) setNullRows(res.data.rows || []) })
      .catch(() => { if (!cancelled) setNullRows([]) })
      .finally(() => { if (!cancelled) setNullRowsLoading(false) })
    return () => { cancelled = true }
  }, [accessToken, summary])

  const openModalByLogId = (logId: string) => {
    if (!accessToken) return
    setModalLog(null)
    setModalError(null)
    setModalLoading(true)
    axios
      .get<{ log: LatestLog | null }>('/api/admin/stats/behavior/log-by-id', {
        params: { log_id: logId },
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      .then((res) => setModalLog(res.data.log ?? null))
      .catch((err) => setModalError(err.response?.data?.detail ?? '조회 실패'))
      .finally(() => setModalLoading(false))
  }

  const closeModal = () => {
    setModalLog(null)
    setModalError(null)
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
        <h2 className="text-lg font-bold text-gray-800 mb-2">👤 사용자 행동 분석 (admin_logs)</h2>
        <p className="text-gray-600 text-sm mb-4">
          로그인 한 유저의 로그 분석
        </p>
      </div>

      <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
        <h3 className="font-semibold text-gray-800 mb-4">
          로그인 한 유저중 총 질문 횟수 vs 처음 질문 - 마지막 질문 시간
        </h3>
        {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
        {loading ? (
          <p className="text-gray-500 py-8">로딩 중...</p>
        ) : items.length === 0 ? (
          <p className="text-gray-500 py-8">user_id가 있는 is_same_person 데이터가 없습니다.</p>
        ) : (
          <ResponsiveContainer width="100%" height={420}>
            <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
              <XAxis
                type="number"
                dataKey="total_questions"
                name="총 질문 횟수"
                label={{ value: '총 질문 횟수', position: 'bottom', offset: 0 }}
                tick={{ fontSize: 12 }}
              />
              <YAxis
                type="number"
                dataKey="distinct_hour_appearances"
                name="처음 질문 - 마지막 질문 시간(시간)"
                label={{ value: '처음 질문 - 마지막 질문 시간(시간)', angle: -90, position: 'insideLeft', offset: 0 }}
                tick={{ fontSize: 12 }}
              />
              <ZAxis type="number" range={[120, 400]} name="인원" />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null
                  const p = payload[0].payload as GroupedPoint
                  return (
                    <div className="bg-white border border-gray-200 rounded-lg shadow-lg px-3 py-2 text-sm max-w-[280px]">
                      <div className="font-medium text-gray-800">
                        좌표 ({p.total_questions}, {p.distinct_hour_appearances}) · {p.count}명
                      </div>
                      <div className="mt-1 text-gray-600 text-xs max-h-24 overflow-y-auto">
                        {p.persons.map((u, i) => (
                          <div key={i} className="truncate font-mono" title={u.is_same_person}>
                            {u.is_same_person}
                          </div>
                        ))}
                      </div>
                      <div className="text-gray-500 text-xs mt-1">클릭 시 아래에 로그 전체 표시</div>
                    </div>
                  )
                }}
              />
              <Legend />
              <Scatter
                name=""
                data={groupedData}
                onClick={(e: { payload?: GroupedPoint }) => {
                  const point = e.payload
                  if (point?.persons?.length) fetchGroupDetails(point)
                }}
                cursor="pointer"
                shape={(props: { cx?: number; cy?: number; index?: number }, index?: number) => {
                  const cx = props.cx ?? 0
                  const cy = props.cy ?? 0
                  const i = typeof index === 'number' ? index : props.index ?? 0
                  const fill = COLORS[i % COLORS.length]
                  return (
                    <g>
                      <circle cx={cx} cy={cy} r={14} fill={fill} stroke="#fff" strokeWidth={2} />
                    </g>
                  )
                }}
              >
                <LabelList dataKey="coordinateLabel" position="top" fontSize={10} pointerEvents="none" />
                {groupedData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        )}
        <p className="text-gray-500 text-xs mt-2">같은 좌표는 한 점으로 묶어 표시됩니다. 점을 클릭하면 해당 좌표의 모든 사용자 로그가 아래에 표시됩니다.</p>
      </div>

      {summary != null && (
        <>
          <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
            <h3 className="font-semibold text-gray-800 mb-2">
              로그인하지 않고 질문한 사람들 ({summary.count_is_same_person_null.toLocaleString()}건)
            </h3>
            <p className="text-gray-600 text-sm mb-4">행을 클릭하면 해당 로그의 질문·답변·history를 모달로 볼 수 있습니다.</p>
            {nullRowsLoading ? (
              <p className="text-gray-500 py-6">로딩 중...</p>
            ) : nullRows.length === 0 ? (
              <p className="text-gray-500 py-6">데이터가 없습니다.</p>
            ) : (
              <div className="overflow-x-auto max-h-64 overflow-y-auto border border-gray-200 rounded-lg">
                <table className="w-full text-sm border-collapse">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="border-b border-gray-200 px-3 py-2 text-left font-medium">ID</th>
                      <th className="border-b border-gray-200 px-3 py-2 text-left font-medium">timestamp</th>
                      <th className="border-b border-gray-200 px-3 py-2 text-left font-medium">질문 (일부)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {nullRows.map((row) => (
                      <tr
                        key={row.id}
                        className="hover:bg-indigo-50 cursor-pointer border-b border-gray-100"
                        onClick={() => openModalByLogId(row.id)}
                      >
                        <td className="px-3 py-2 font-mono text-gray-600">{row.id}</td>
                        <td className="px-3 py-2 text-gray-600">
                          {row.timestamp ? new Date(row.timestamp).toLocaleString('ko-KR') : '-'}
                        </td>
                        <td className="px-3 py-2 text-gray-800 max-w-md truncate" title={row.userQuestionSnippet}>
                          {row.userQuestionSnippet || '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {(modalLog != null || modalLoading || modalError) && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={(e) => e.target === e.currentTarget && closeModal()}
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200">
              <h3 className="font-semibold text-gray-800">로그 상세</h3>
              <button
                type="button"
                onClick={closeModal}
                className="text-gray-500 hover:text-gray-700 text-sm font-medium"
              >
                닫기
              </button>
            </div>
            <div className="px-6 py-4 overflow-y-auto flex-1">
              {modalLoading && <p className="text-gray-500 py-4">로딩 중...</p>}
              {modalError && <p className="text-red-600 text-sm py-2">{modalError}</p>}
              {!modalLoading && !modalError && modalLog && (
                <div className="space-y-3 text-sm">
                  <div className="text-gray-500">
                    로그 ID: <span className="font-mono">{modalLog.id}</span>
                    {' · '}
                    {modalLog.timestamp ? new Date(modalLog.timestamp).toLocaleString('ko-KR') : '-'}
                  </div>
                  <div>
                    <span className="text-gray-600 font-medium">질문:</span>
                    <p className="mt-1 p-2 bg-gray-50 rounded border border-gray-200 whitespace-pre-wrap text-gray-800">
                      {modalLog.userQuestion || '(없음)'}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-600 font-medium">최종 답변:</span>
                    <p className="mt-1 p-2 bg-gray-50 rounded border border-gray-200 whitespace-pre-wrap text-gray-800">
                      {modalLog.finalAnswer || '(없음)'}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-600 font-medium">conversation_history ({modalLog.conversationHistory?.length ?? 0}개):</span>
                    <ul className="mt-1 space-y-1 max-h-64 overflow-y-auto p-2 bg-gray-50 rounded border border-gray-200">
                      {(modalLog.conversationHistory ?? []).length === 0 ? (
                        <li className="text-gray-500">(비어 있음)</li>
                      ) : (
                        (modalLog.conversationHistory ?? []).map((msg, i) => (
                          <li key={i} className="text-gray-700 whitespace-pre-wrap border-b border-gray-100 last:border-0 pb-1 text-xs">
                            {typeof msg === 'string' ? msg : JSON.stringify(msg)}
                          </li>
                        ))
                      )}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {(groupDetail != null || detailLoading || detailError) && (
        <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-800">
              {groupDetail
                ? `선택한 좌표 (${groupDetail.point.total_questions}, ${groupDetail.point.distinct_hour_appearances}) · ${groupDetail.point.count}명`
                : '선택한 좌표'}
            </h3>
            <button
              type="button"
              onClick={closeDetail}
              className="text-gray-500 hover:text-gray-700 text-sm"
            >
              닫기
            </button>
          </div>
          {detailLoading && <p className="text-gray-500 py-4">로딩 중...</p>}
          {detailError && <p className="text-red-600 text-sm py-2">{detailError}</p>}
          {!detailLoading && groupDetail && (
            <div className="space-y-6">
              {groupDetail.items.map(({ person, log, error }, idx) => (
                <div key={person.is_same_person} className="border border-gray-200 rounded-lg p-4 bg-gray-50/50">
                  <div className="font-mono text-sm text-gray-600 mb-2 break-all" title={person.is_same_person}>
                    is_same_person #{idx + 1}: {person.is_same_person}
                  </div>
                  {error && <p className="text-red-600 text-sm">{error}</p>}
                  {!error && log && (
                    <div className="space-y-2 text-sm">
                      <div className="text-gray-500">
                        로그 ID: <span className="font-mono">{log.id}</span>
                        {' · '}
                        {log.timestamp ? new Date(log.timestamp).toLocaleString('ko-KR') : '-'}
                      </div>
                      <div>
                        <span className="text-gray-600 font-medium">질문:</span>
                        <p className="mt-0.5 p-2 bg-white rounded border border-gray-200 whitespace-pre-wrap text-gray-800">
                          {log.userQuestion || '(없음)'}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-600 font-medium">최종 답변:</span>
                        <p className="mt-0.5 p-2 bg-white rounded border border-gray-200 whitespace-pre-wrap text-gray-800">
                          {log.finalAnswer || '(없음)'}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-600 font-medium">conversation_history ({log.conversationHistory?.length ?? 0}개):</span>
                        <ul className="mt-0.5 space-y-1 max-h-48 overflow-y-auto p-2 bg-white rounded border border-gray-200">
                          {(log.conversationHistory ?? []).length === 0 ? (
                            <li className="text-gray-500">(비어 있음)</li>
                          ) : (
                            (log.conversationHistory ?? []).map((msg, i) => (
                              <li key={i} className="text-gray-700 whitespace-pre-wrap border-b border-gray-100 last:border-0 pb-1 last:pb-0 text-xs">
                                {typeof msg === 'string' ? msg : JSON.stringify(msg)}
                              </li>
                            ))
                          )}
                        </ul>
                      </div>
                    </div>
                  )}
                  {!error && !log && <p className="text-gray-500">로그 없음</p>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
