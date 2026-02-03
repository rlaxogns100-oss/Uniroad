import { useState, useEffect, useCallback, Fragment } from 'react'
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
  min_delay_seconds: number
  comments_per_hour_min: number
  comments_per_hour_max: number
  rest_minutes: number
}

interface CommentRecord {
  timestamp: string
  post_url: string
  post_title: string
  comment: string
  success: boolean
  post_content?: string
  query?: string
  function_result?: string
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
  const [authenticated, setAuthenticated] = useState(false)
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [status, setStatus] = useState<BotStatus | null>(null)
  const [comments, setComments] = useState<CommentRecord[]>([])
  const [totalComments, setTotalComments] = useState(0)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // 설정 상태
  const [minDelay, setMinDelay] = useState(50)
  const [commentsPerHourMin, setCommentsPerHourMin] = useState(5)
  const [commentsPerHourMax, setCommentsPerHourMax] = useState(10)
  const [restMinutes, setRestMinutes] = useState(3)
  const [configChanged, setConfigChanged] = useState(false)
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  // 프롬프트 편집
  const [answerPrompt, setAnswerPrompt] = useState('')
  const [promptLoading, setPromptLoading] = useState(false)
  const [promptSaving, setPromptSaving] = useState(false)
  const [promptError, setPromptError] = useState<string | null>(null)

  const handlePasswordSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (password === '123456') {
      setAuthenticated(true)
      setAuthError('')
    } else {
      setAuthError('비밀번호가 올바르지 않습니다.')
    }
  }

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/status`)
      if (!res.ok) throw new Error('상태 조회 실패')
      const data: BotStatus = await res.json()
      setStatus(data)
      setMinDelay(data.config.min_delay_seconds ?? 50)
      setCommentsPerHourMin(data.config.comments_per_hour_min ?? 5)
      setCommentsPerHourMax(data.config.comments_per_hour_max ?? 10)
      setRestMinutes(data.config.rest_minutes ?? 3)
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

  const fetchPrompts = useCallback(async () => {
    setPromptLoading(true)
    setPromptError(null)
    try {
      const res = await fetch(`${API_BASE}/prompts`)
      if (!res.ok) throw new Error('프롬프트 조회 실패')
      const data = await res.json()
      setAnswerPrompt(data.answer_prompt ?? '')
    } catch (e: any) {
      setPromptError(e.message ?? '프롬프트를 불러올 수 없습니다.')
    } finally {
      setPromptLoading(false)
    }
  }, [])

  const handleSavePrompt = async () => {
    setPromptSaving(true)
    setPromptError(null)
    try {
      const res = await fetch(`${API_BASE}/prompts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answer_prompt: answerPrompt })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '저장 실패')
    } catch (e: any) {
      setPromptError(e.message ?? '저장 실패')
    } finally {
      setPromptSaving(false)
    }
  }

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      await Promise.all([fetchStatus(), fetchComments(), fetchPrompts()])
      setLoading(false)
    }
    load()

    // 10초마다 상태 업데이트
    const interval = setInterval(() => {
      fetchStatus()
      fetchComments()
    }, 10000)

    return () => clearInterval(interval)
  }, [fetchStatus, fetchComments, fetchPrompts])

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
          comments_per_hour_min: commentsPerHourMin,
          comments_per_hour_max: commentsPerHourMax,
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

  if (!authenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full">
          <h2 className="text-2xl font-bold text-gray-800 mb-6 text-center">봇 관리자 인증</h2>
          <form onSubmit={handlePasswordSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                비밀번호
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="비밀번호를 입력하세요"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                autoFocus
              />
            </div>
            {authError && (
              <div className="text-red-600 text-sm">{authError}</div>
            )}
            <button
              type="submit"
              className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
            >
              접속
            </button>
          </form>
        </div>
      </div>
    )
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
              
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    시간당 댓글 수 (최소)
                  </label>
                  <input
                    type="number"
                    value={commentsPerHourMin}
                    onChange={(e) => {
                      setCommentsPerHourMin(Number(e.target.value))
                      setConfigChanged(true)
                    }}
                    min={1}
                    max={60}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    시간당 댓글 수 (최대)
                  </label>
                  <input
                    type="number"
                    value={commentsPerHourMax}
                    onChange={(e) => {
                      setCommentsPerHourMax(Number(e.target.value))
                      setConfigChanged(true)
                    }}
                    min={1}
                    max={60}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              </div>
              <p className="text-xs text-gray-500 -mt-1">
                예: 5~10이면 시간당 약 5~10개, 댓글 사이에 랜덤 딜레이 적용
              </p>
              
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
                최소 딜레이 이상으로, 시간당 댓글 수 범위에 맞춰 댓글과 댓글 사이에 랜덤 딜레이가 적용됩니다.
              </p>
            </div>
          </div>
        </div>

        {/* Answer Agent 프롬프트 편집 */}
        <div className="bg-white rounded-xl shadow-sm p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Answer Agent 프롬프트</h2>
          <p className="text-sm text-gray-500 mb-3">
            댓글 생성에 사용되는 지시문입니다. 수정 후 저장하면 다음 사이클부터 적용됩니다. 비어 있으면 봇 기본값을 사용합니다.
          </p>
          {promptError && (
            <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
              {promptError}
            </div>
          )}
          {promptLoading ? (
            <div className="text-gray-500 text-sm">불러오는 중...</div>
          ) : (
            <>
              <textarea
                value={answerPrompt}
                onChange={(e) => setAnswerPrompt(e.target.value)}
                placeholder="저장된 프롬프트가 없으면 여기 비워두고 저장 시 기본값이 사용됩니다. 수정 후 저장하면 여기 내용이 적용됩니다."
                rows={14}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
              />
              <div className="mt-3 flex gap-2">
                <button
                  onClick={fetchPrompts}
                  disabled={promptLoading}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  다시 불러오기
                </button>
                <button
                  onClick={handleSavePrompt}
                  disabled={promptSaving}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  {promptSaving ? '저장 중...' : '프롬프트 저장'}
                </button>
              </div>
            </>
          )}
        </div>

        {/* 댓글 기록 - 5열 (원글/쿼리/함수결과/최종답변/링크) + 행 클릭 펼치기 */}
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
              <table className="w-full bg-white border border-gray-200 table-fixed">
                <thead>
                  <tr className="bg-gray-50 border-b border-gray-200">
                    <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '18%' }}>원글</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '18%' }}>쿼리</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '22%' }}>함수결과</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '22%' }}>최종답변</th>
                    <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '20%' }}>링크</th>
                  </tr>
                </thead>
                <tbody>
                  {comments.map((record, idx) => {
                    const isExpanded = expandedRows.has(idx)
                    const raw = (s: string | undefined) => (s ?? '-').trim() || '-'
                    const clip = (s: string, len: number) => s.length <= len ? s : s.slice(0, len) + '...'
                    return (
                      <Fragment key={idx}>
                        <tr
                          onClick={() => {
                            setExpandedRows(prev => {
                              const next = new Set(prev)
                              if (next.has(idx)) next.delete(idx)
                              else next.add(idx)
                              return next
                            })
                          }
                          }
                          className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                        >
                          <td className="px-2 py-1.5 align-top">
                            <span className="text-xs text-gray-700">{isExpanded ? raw(record.post_content) : clip(raw(record.post_content), 35)}</span>
                          </td>
                          <td className="px-2 py-1.5 align-top">
                            <span className="text-xs font-mono text-gray-700 break-all">{isExpanded ? raw(record.query) : clip(raw(record.query), 40)}</span>
                          </td>
                          <td className="px-2 py-1.5 align-top">
                            <span className="text-xs text-gray-700">{isExpanded ? raw(record.function_result) : clip(raw(record.function_result), 50)}</span>
                          </td>
                          <td className="px-2 py-1.5 align-top">
                            <span className="text-xs text-gray-700">{isExpanded ? record.comment : clip(record.comment, 40)}</span>
                          </td>
                          <td className="px-2 py-1.5 align-top">
                            <a
                              href={record.post_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={e => e.stopPropagation()}
                              className="text-xs text-blue-600 hover:underline truncate block"
                            >
                              {record.post_title || record.post_url || '(링크)'}
                            </a>
                          </td>
                        </tr>
                        {isExpanded && (
                          <tr className="bg-gray-50 border-b border-gray-100">
                            <td colSpan={5} className="px-4 py-3">
                              <div className="grid grid-cols-1 gap-4 text-xs">
                                <div>
                                  <div className="font-semibold text-gray-600 mb-1">원글</div>
                                  <pre className="whitespace-pre-wrap font-mono bg-white p-2 rounded max-h-40 overflow-y-auto">{raw(record.post_content)}</pre>
                                </div>
                                <div>
                                  <div className="font-semibold text-gray-600 mb-1">쿼리</div>
                                  <pre className="whitespace-pre-wrap font-mono bg-white p-2 rounded max-h-32 overflow-y-auto">{raw(record.query)}</pre>
                                </div>
                                <div>
                                  <div className="font-semibold text-gray-600 mb-1">함수결과</div>
                                  <pre className="whitespace-pre-wrap font-mono bg-white p-2 rounded max-h-40 overflow-y-auto">{raw(record.function_result)}</pre>
                                </div>
                                <div>
                                  <div className="font-semibold text-gray-600 mb-1">최종답변</div>
                                  <pre className="whitespace-pre-wrap font-mono bg-white p-2 rounded max-h-32 overflow-y-auto">{record.comment}</pre>
                                </div>
                                <div>
                                  <a href={record.post_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline break-all">{record.post_url}</a>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    )
                  })}
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
