import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

interface BotStatus {
  running: boolean
  pid: number | null
  cookie_exists: boolean
  config: BotConfig
  bot_dir: string
  timestamp: string
}

interface BotConfig {
  max_comments_per_minute: number
  min_delay_seconds: number
  max_delay_seconds: number
  rest_minutes: number
}

interface CommentRecord {
  timestamp: string
  post_url: string
  post_title: string
  comment: string
  success: boolean
}

interface CommentsResponse {
  success: boolean
  comments: CommentRecord[]
  total: number
  limit: number
  offset: number
}

const API_BASE = '/api/auto-reply'

export default function AutoReplyPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<BotStatus | null>(null)
  const [comments, setComments] = useState<CommentRecord[]>([])
  const [totalComments, setTotalComments] = useState(0)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // 설정 상태
  const [minDelay, setMinDelay] = useState(50)
  const [maxDelay, setMaxDelay] = useState(80)
  const [restMinutes, setRestMinutes] = useState(3)
  const [configChanged, setConfigChanged] = useState(false)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/status`)
      if (!res.ok) throw new Error('상태 조회 실패')
      const data: BotStatus = await res.json()
      setStatus(data)
      setMinDelay(data.config.min_delay_seconds)
      setMaxDelay(data.config.max_delay_seconds)
      setRestMinutes(data.config.rest_minutes)
      setConfigChanged(false)
    } catch (e) {
      setError('봇 상태를 불러올 수 없습니다.')
    }
  }, [])

  const fetchComments = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/comments?limit=50`)
      if (!res.ok) throw new Error('댓글 조회 실패')
      const data: CommentsResponse = await res.json()
      setComments(data.comments)
      setTotalComments(data.total)
    } catch (e) {
      console.error('댓글 조회 에러:', e)
    }
  }, [])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      await Promise.all([fetchStatus(), fetchComments()])
      setLoading(false)
    }
    load()

    // 10초마다 상태 업데이트
    const interval = setInterval(() => {
      fetchStatus()
      fetchComments()
    }, 10000)

    return () => clearInterval(interval)
  }, [fetchStatus, fetchComments])

  const handleStart = async () => {
    setActionLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/start`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '시작 실패')
      await fetchStatus()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleStop = async () => {
    setActionLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/stop`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '중지 실패')
      await fetchStatus()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const handleSaveConfig = async () => {
    setActionLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          min_delay_seconds: minDelay,
          max_delay_seconds: maxDelay,
          rest_minutes: restMinutes
        })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '설정 저장 실패')
      setConfigChanged(false)
      await fetchStatus()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setActionLoading(false)
    }
  }

  const formatTime = (isoString: string) => {
    const date = new Date(isoString)
    return date.toLocaleString('ko-KR', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">로딩 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <header className="bg-white shadow-sm">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="text-gray-500 hover:text-gray-700"
            >
              ← 돌아가기
            </button>
            <h1 className="text-xl font-bold text-gray-800">자동 댓글 봇 관리</h1>
          </div>
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              status?.running 
                ? 'bg-green-100 text-green-800' 
                : 'bg-red-100 text-red-800'
            }`}>
              <span className={`w-2 h-2 rounded-full mr-2 ${
                status?.running ? 'bg-green-500 animate-pulse' : 'bg-red-500'
              }`}></span>
              {status?.running ? '실행 중' : '중지됨'}
            </span>
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-8">
        {error && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}

        {/* 상태 및 컨트롤 */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          {/* 봇 상태 */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">봇 상태</h2>
            
            <div className="space-y-3 mb-6">
              <div className="flex justify-between">
                <span className="text-gray-600">상태</span>
                <span className={`font-medium ${status?.running ? 'text-green-600' : 'text-red-600'}`}>
                  {status?.running ? '실행 중' : '중지됨'}
                </span>
              </div>
              {status?.pid && (
                <div className="flex justify-between">
                  <span className="text-gray-600">프로세스 ID</span>
                  <span className="font-mono text-gray-800">{status.pid}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-gray-600">쿠키 파일</span>
                <span className={status?.cookie_exists ? 'text-green-600' : 'text-red-600'}>
                  {status?.cookie_exists ? '있음' : '없음'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">총 댓글 수</span>
                <span className="font-medium text-gray-800">{totalComments}개</span>
              </div>
            </div>

            <div className="flex gap-3">
              {status?.running ? (
                <button
                  onClick={handleStop}
                  disabled={actionLoading}
                  className="flex-1 py-2.5 px-4 bg-red-600 hover:bg-red-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors"
                >
                  {actionLoading ? '처리 중...' : '봇 중지'}
                </button>
              ) : (
                <button
                  onClick={handleStart}
                  disabled={actionLoading || !status?.cookie_exists}
                  className="flex-1 py-2.5 px-4 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors"
                >
                  {actionLoading ? '처리 중...' : '봇 시작'}
                </button>
              )}
            </div>

            {!status?.cookie_exists && (
              <p className="mt-3 text-sm text-amber-600">
                쿠키 파일이 없습니다. 로컬에서 get_cookies.py를 실행하세요.
              </p>
            )}
          </div>

          {/* 설정 */}
          <div className="bg-white rounded-xl shadow-sm p-6">
            <h2 className="text-lg font-semibold text-gray-800 mb-4">봇 설정</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  최소 딜레이 (초)
                </label>
                <input
                  type="number"
                  value={minDelay}
                  onChange={(e) => {
                    setMinDelay(Number(e.target.value))
                    setConfigChanged(true)
                  }}
                  min={10}
                  max={300}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  최대 딜레이 (초)
                </label>
                <input
                  type="number"
                  value={maxDelay}
                  onChange={(e) => {
                    setMaxDelay(Number(e.target.value))
                    setConfigChanged(true)
                  }}
                  min={10}
                  max={300}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  휴식 시간 (분)
                </label>
                <input
                  type="number"
                  value={restMinutes}
                  onChange={(e) => {
                    setRestMinutes(Number(e.target.value))
                    setConfigChanged(true)
                  }}
                  min={1}
                  max={30}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <button
                onClick={handleSaveConfig}
                disabled={!configChanged || actionLoading}
                className="w-full py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-medium rounded-lg transition-colors"
              >
                {actionLoading ? '저장 중...' : '설정 저장'}
              </button>

              <p className="text-sm text-gray-500">
                분당 최대 댓글 수는 딜레이 설정으로 자동 조절됩니다.
                <br />
                예: 60초 딜레이 = 분당 1개
              </p>
            </div>
          </div>
        </div>

        {/* 댓글 기록 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100">
            <h2 className="text-lg font-semibold text-gray-800">
              댓글 기록 <span className="text-gray-400 font-normal">({totalComments}개)</span>
            </h2>
          </div>
          
          {comments.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              아직 댓글 기록이 없습니다.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      시간
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      게시글
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      댓글 내용
                    </th>
                    <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                      상태
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {comments.map((record, idx) => (
                    <tr key={idx} className="hover:bg-gray-50">
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-600">
                        {formatTime(record.timestamp)}
                      </td>
                      <td className="px-4 py-3">
                        <a
                          href={record.post_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 hover:underline line-clamp-1"
                        >
                          {record.post_title || '(제목 없음)'}
                        </a>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-sm text-gray-700 line-clamp-2">
                          {record.comment}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                          record.success
                            ? 'bg-green-100 text-green-800'
                            : 'bg-red-100 text-red-800'
                        }`}>
                          {record.success ? '성공' : '실패'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* 안내 */}
        <div className="mt-8 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h3 className="font-medium text-blue-800 mb-2">사용 안내</h3>
          <ul className="text-sm text-blue-700 space-y-1">
            <li>1. 로컬 PC에서 get_cookies.py 실행하여 네이버 로그인 쿠키 생성</li>
            <li>2. 생성된 naver_cookies.pkl 파일을 서버로 업로드</li>
            <li>3. 이 페이지에서 '봇 시작' 버튼 클릭</li>
            <li>4. 설정은 봇 실행 중에도 변경 가능 (다음 사이클에 적용)</li>
          </ul>
        </div>
      </main>
    </div>
  )
}
