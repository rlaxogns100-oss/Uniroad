import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'

type G2uPctr = {
  g2u_converted_count: number
  g2u_guest_only_count: number
  g2u_rate: number
  pctr_avg: number
  pctr_groups_count: number
}

export default function AdminAnalyticsConversion() {
  const { accessToken } = useAuth()
  const [data, setData] = useState<G2uPctr | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!accessToken) return
    let cancelled = false
    axios
      .get<G2uPctr>('/api/admin/stats/conversion/g2u-pctr', {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      .then((res) => { if (!cancelled) setData(res.data) })
      .catch((err) => { if (!cancelled) setError(err.response?.data?.detail ?? '조회 실패') })
    return () => { cancelled = true }
  }, [accessToken])

  const totalGuest = data
    ? data.g2u_converted_count + data.g2u_guest_only_count
    : 0

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-bold text-gray-800 mb-1">질문 → 유저 전환 분석</h2>
        <p className="text-sm text-gray-500">
          익명(게스트)으로 챗봇을 써보다가 로그인한 비율과, 가입 전 평균 질문 수를 봅니다.
        </p>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}
      {!error && !data && <p className="text-gray-500">로딩 중...</p>}
      {!error && data && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
              <div className="text-2xl mb-2">🔄</div>
              <h3 className="font-semibold text-gray-800 mb-1">G2U 전환율 (게스트 → 유저)</h3>
              <p className="text-2xl font-bold text-indigo-600 mb-2">
                {data.g2u_rate.toFixed(1)}%
              </p>
              <p className="text-sm text-gray-500 mb-3">
                익명으로 맛보기만 하던 사람 중, 로그인(가입)까지 한 비율입니다.
              </p>
              <p className="text-xs text-gray-500">
                전환 {data.g2u_converted_count}명 / 게스트 경험 {totalGuest}명
                {totalGuest > 0 && ` (비전환 ${data.g2u_guest_only_count}명)`}
              </p>
            </div>

            <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
              <div className="text-2xl mb-2">💬</div>
              <h3 className="font-semibold text-gray-800 mb-1">PCTR (전환 전 평균 질문 수)</h3>
              <p className="text-2xl font-bold text-emerald-600 mb-2">
                {data.pctr_avg.toFixed(1)}개
              </p>
              <p className="text-sm text-gray-500 mb-3">
                가입 버튼을 누르기 전까지, 평균 몇 번 질문했는지입니다.
              </p>
              <p className="text-xs text-gray-500">
                전환한 그룹 {data.pctr_groups_count}명 기준
              </p>
            </div>
          </div>

          <div className="bg-white rounded-2xl shadow-xl p-6 border border-gray-100">
            <h3 className="font-semibold text-gray-800 mb-3">활용 참고</h3>
            <ul className="text-sm text-gray-600 space-y-2 list-disc list-inside">
              <li>G2U가 낮으면: 가입 절차가 부담스럽거나, 가입 혜택이 매력적이지 않다는 신호일 수 있습니다.</li>
              <li>PCTR이 1~2에 가깝다면: 이미 기대하고 들어온 유저가 많다는 뜻일 수 있습니다.</li>
              <li>PCTR이 5~10이라면: 답변을 꽤 확인한 뒤 신뢰하고 가입한 유저 비율이 높을 수 있습니다. 무료 질문 한도 설계 시 참고할 수 있습니다.</li>
            </ul>
          </div>
        </>
      )}
    </div>
  )
}
