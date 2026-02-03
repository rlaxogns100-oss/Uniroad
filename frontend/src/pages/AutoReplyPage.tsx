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
  min_delay_seconds: number
  comments_per_hour_min: number
  comments_per_hour_max: number
  rest_minutes: number
  keywords?: string[]
}

interface CommentRecord {
  timestamp: string
  post_url: string
  post_title: string
  comment: string
  success: boolean
  dry_run?: boolean  // 가실행 여부
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

// ExpandableCell 컴포넌트 (AdminAgentPage와 동일)
function ExpandableCell({ content, maxLength = 30, isExpanded = false }: { content: any, maxLength?: number, isExpanded?: boolean }) {
  let processedContent = content
  
  // 문자열인 경우 JSON 파싱 시도
  if (typeof processedContent === 'string') {
    try {
      const parsed = JSON.parse(processedContent)
      processedContent = parsed
    } catch {
      // 파싱 실패하면 원본 문자열 사용
    }
  }
  
  const stringContent = typeof processedContent === 'object' 
    ? JSON.stringify(processedContent, null, 2) 
    : String(processedContent || '-')
  
  const needsExpansion = stringContent.length > maxLength
  const displayContent = needsExpansion && !isExpanded 
    ? stringContent.substring(0, maxLength) + '...'
    : stringContent
  
  return (
    <div className="relative">
      {isExpanded ? (
        <pre className="text-xs whitespace-pre-wrap font-mono max-h-[400px] overflow-y-auto bg-gray-50 p-2 rounded">
          {stringContent}
        </pre>
      ) : (
        <span className="text-xs text-gray-700">{displayContent}</span>
      )}
    </div>
  )
}

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
  
  // 드롭다운 상태
  const [realCommentsOpen, setRealCommentsOpen] = useState(true)
  const [dryRunCommentsOpen, setDryRunCommentsOpen] = useState(true)
  
  // 설정 상태
  const [minDelay, setMinDelay] = useState(50)
  const [commentsPerHourMin, setCommentsPerHourMin] = useState(5)
  const [commentsPerHourMax, setCommentsPerHourMax] = useState(10)
  const [restMinutes, setRestMinutes] = useState(3)
  const [keywords, setKeywords] = useState<string[]>([])
  const [keywordsText, setKeywordsText] = useState('')  // 텍스트 입력용
  const [keywordsExpanded, setKeywordsExpanded] = useState(false)
  const [configChanged, setConfigChanged] = useState(false)
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  // 프롬프트 편집 (Query + Answer 2개)
  const [queryPrompt, setQueryPrompt] = useState('')
  const [answerPrompt, setAnswerPrompt] = useState('')
  const [promptLoading, setPromptLoading] = useState(false)
  const [promptSaving, setPromptSaving] = useState(false)
  const [promptError, setPromptError] = useState<string | null>(null)
  const [promptsExpanded, setPromptsExpanded] = useState(false)
  
  // 실시간 로그
  const [logs, setLogs] = useState<string[]>([])
  const [logsExpanded, setLogsExpanded] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)

  // 테스트 댓글 기록
  const [testCommentsOpen, setTestCommentsOpen] = useState(true)
  const [testInput, setTestInput] = useState('')
  const [testLoading, setTestLoading] = useState(false)
  const [testResults, setTestResults] = useState<Array<{
    post_content: string
    query: string
    function_result: string
    answer: string
  }>>([])
  const [testExpandedRows, setTestExpandedRows] = useState<Set<number>>(new Set())

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
      const loadedKeywords = data.config.keywords ?? []
      setKeywords(loadedKeywords)
      setKeywordsText(loadedKeywords.join(', '))
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
      setQueryPrompt(data.query_prompt ?? '')
      setAnswerPrompt(data.answer_prompt ?? '')
    } catch (e: any) {
      setPromptError(e.message ?? '프롬프트를 불러올 수 없습니다.')
    } finally {
      setPromptLoading(false)
    }
  }, [])

  const handleSavePrompts = async () => {
    setPromptSaving(true)
    setPromptError(null)
    try {
      const res = await fetch(`${API_BASE}/prompts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query_prompt: queryPrompt,
          answer_prompt: answerPrompt
        })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '저장 실패')
      alert('프롬프트가 저장되었습니다.')
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

  // 실시간 로그 스트리밍
  useEffect(() => {
    if (!status?.running) {
      // 봇이 실행 중이 아니면 연결 안 함
      return
    }

    const eventSource = new EventSource(`${API_BASE}/logs/stream`)
    
    eventSource.onmessage = (event) => {
      setLogs(prev => {
        const newLogs = [...prev, event.data]
        // 최근 500줄만 유지
        return newLogs.slice(-500)
      })
    }
    
    eventSource.onerror = (error) => {
      console.error('로그 스트림 오류:', error)
      eventSource.close()
    }
    
    return () => {
      eventSource.close()
    }
  }, [status?.running])

  // 자동 스크롤
  useEffect(() => {
    if (autoScroll && logsExpanded) {
      const logContainer = document.getElementById('log-container')
      if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight
      }
    }
  }, [logs, autoScroll, logsExpanded])

  const handleStart = async (dryRun: boolean = false) => {
    setActionLoading(true)
    setError(null)
    try {
      const url = `${API_BASE}/start${dryRun ? '?dry_run=true' : ''}`
      const res = await fetch(url, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '시작 실패')
      await fetchStatus()
      if (dryRun) {
        alert('가실행 모드로 봇이 시작되었습니다. (댓글을 실제로 달지 않습니다)')
      }
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
          rest_minutes: restMinutes,
          keywords: keywords
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

  const handleKeywordsChange = (text: string) => {
    setKeywordsText(text)
    // 콤마로 분리하고 빈 값 제거
    const newKeywords = text.split(',').map(k => k.trim()).filter(k => k.length > 0)
    setKeywords(newKeywords)
    setConfigChanged(true)
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

  const handleTestRun = async () => {
    if (!testInput.trim()) {
      alert('테스트할 게시글 내용을 입력해주세요.')
      return
    }
    
    setTestLoading(true)
    try {
      const res = await fetch(`${API_BASE}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ post_content: testInput })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '테스트 실행 실패')
      
      // 결과를 테이블에 추가
      setTestResults(prev => [{
        post_content: testInput,
        query: data.query || '',
        function_result: data.function_result || '',
        answer: data.answer || ''
      }, ...prev])
      
      // 입력 초기화
      setTestInput('')
    } catch (e: any) {
      alert(`테스트 실패: ${e.message}`)
    } finally {
      setTestLoading(false)
    }
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
                <>
                  <button
                    onClick={() => handleStart(false)}
                    disabled={actionLoading || !status?.cookie_exists}
                    className="flex-1 py-2.5 px-4 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors"
                  >
                    {actionLoading ? '처리 중...' : '봇 시작'}
                  </button>
                  <button
                    onClick={() => handleStart(true)}
                    disabled={actionLoading || !status?.cookie_exists}
                    className="flex-1 py-2.5 px-4 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors"
                    title="댓글을 실제로 달지 않고 생성만 테스트합니다"
                  >
                    {actionLoading ? '처리 중...' : '가실행'}
                  </button>
                </>
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

        {/* 검색 키워드 설정 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden mb-8">
          <button
            onClick={() => setKeywordsExpanded(!keywordsExpanded)}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-gray-800">검색 키워드 설정</h2>
              <span className="text-sm text-gray-500">({keywords.length}개)</span>
            </div>
            <svg
              className={`w-5 h-5 text-gray-500 transition-transform ${keywordsExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          
          {keywordsExpanded && (
            <div className="px-6 pb-6">
              <p className="text-sm text-gray-500 mb-4">
                봇이 검색할 키워드 목록입니다. 콤마(,)로 구분하여 입력하세요. 비어있으면 기본 키워드를 사용합니다.
              </p>
              
              <input
                type="text"
                value={keywordsText}
                onChange={(e) => handleKeywordsChange(e.target.value)}
                placeholder="정시, 표점, 백분위, 서울대, 연세대, ..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
              />
              
              <div className="mt-3 flex items-center justify-between">
                <span className="text-sm text-gray-500">
                  현재 {keywords.length}개 키워드 {keywords.length === 0 && '(기본값 사용)'}
                </span>
                <button
                  onClick={handleSaveConfig}
                  disabled={!configChanged || actionLoading}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-medium rounded-lg transition-colors"
                >
                  {actionLoading ? '저장 중...' : '설정 저장'}
                </button>
              </div>
              
              {keywords.length === 0 && (
                <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-600 mb-1 font-medium">기본 키워드:</p>
                  <p className="text-xs text-gray-500">
                    정시, 표점, 표준점수, 환산점수, 백분위, 추합, 예비, 최초합, 전찬, 추가합격, 상향, 소신, 안정, 하향, 스나, 빵꾸, 인서울, 수도권, 지거국, 대학 라인, 어디가, 건동홍, 국숭세단, 광명상가, 인가경, 한서삼, 서울대, 연세대, 고려대, 성균관대, 한양대, 중앙대, 건국대, 한국외대, 중대, 경희대, 동국대, 명지대, 서강대, 광운대, 선리대, 숭실대, 이화여대
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 실시간 로그 뷰어 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden mb-8">
          <button
            onClick={() => setLogsExpanded(!logsExpanded)}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-gray-800">실시간 봇 로그</h2>
              {status?.running && (
                <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse mr-1.5"></span>
                  실행 중
                </span>
              )}
              <span className="text-sm text-gray-500">({logs.length}줄)</span>
            </div>
            <svg
              className={`w-5 h-5 text-gray-500 transition-transform ${logsExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          
          {logsExpanded && (
            <div className="px-6 pb-6">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoScroll}
                      onChange={(e) => setAutoScroll(e.target.checked)}
                      className="rounded border-gray-300"
                    />
                    자동 스크롤
                  </label>
                </div>
                <button
                  onClick={() => setLogs([])}
                  className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  로그 지우기
                </button>
              </div>
              
              <div
                id="log-container"
                className="bg-gray-900 text-gray-100 rounded-lg p-4 font-mono text-xs overflow-y-auto"
                style={{ maxHeight: '500px' }}
              >
                {logs.length === 0 ? (
                  <div className="text-gray-500">
                    {status?.running ? '로그를 불러오는 중...' : '봇을 시작하면 로그가 표시됩니다.'}
                  </div>
                ) : (
                  logs.map((log, idx) => (
                    <div key={idx} className="whitespace-pre-wrap break-words">
                      {log}
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Query/Answer Agent 프롬프트 편집 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden mb-8">
          <button
            onClick={() => setPromptsExpanded(!promptsExpanded)}
            className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 transition-colors"
          >
            <h2 className="text-lg font-semibold text-gray-800">봇 프롬프트 편집</h2>
            <svg
              className={`w-5 h-5 text-gray-500 transition-transform ${promptsExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
          
          {promptsExpanded && (
            <div className="px-6 pb-6">
              <p className="text-sm text-gray-500 mb-4">
                Query Agent와 Answer Agent의 지시문입니다. 수정 후 저장하면 다음 사이클부터 적용됩니다. 비어 있으면 봇 기본값을 사용합니다.
              </p>
              {promptError && (
                <div className="mb-3 p-2 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                  {promptError}
                </div>
              )}
              {promptLoading ? (
                <div className="text-gray-500 text-sm">불러오는 중...</div>
              ) : (
                <div className="space-y-6">
              {/* Query Agent 프롬프트 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Query Agent 프롬프트 (게시글 분석 및 함수 호출 생성)
                </label>
                <textarea
                  value={queryPrompt}
                  onChange={(e) => setQueryPrompt(e.target.value)}
                  placeholder="비어 있으면 기본 Query Agent 프롬프트를 사용합니다. 여기서 수정하면 다음 사이클부터 반영됩니다."
                  rows={16}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-xs"
                />
              </div>

              {/* Answer Agent 프롬프트 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Answer Agent 프롬프트 (댓글 생성)
                </label>
                <textarea
                  value={answerPrompt}
                  onChange={(e) => setAnswerPrompt(e.target.value)}
                  placeholder="비어 있으면 기본 Answer Agent 프롬프트를 사용합니다. 여기서 수정하면 다음 사이클부터 반영됩니다."
                  rows={12}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-xs"
                />
              </div>

              <div className="flex gap-2">
                <button
                  onClick={fetchPrompts}
                  disabled={promptLoading}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  다시 불러오기
                </button>
                <button
                  onClick={handleSavePrompts}
                  disabled={promptSaving}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50"
                >
                  {promptSaving ? '저장 중...' : '프롬프트 저장'}
                </button>
              </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 댓글 기록 - 실제 댓글과 가실행 댓글 분리 */}
        
        {/* 실제 댓글 기록 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div 
            className="px-6 py-4 border-b border-gray-100 flex items-center justify-between cursor-pointer hover:bg-gray-50"
            onClick={() => setRealCommentsOpen(!realCommentsOpen)}
          >
            <h2 className="text-lg font-semibold text-gray-800">
              실제 댓글 기록 <span className="text-gray-400 font-normal">({comments.filter(c => !c.dry_run).length}개)</span>
            </h2>
            <svg 
              className={`w-5 h-5 text-gray-500 transition-transform ${realCommentsOpen ? 'rotate-180' : ''}`}
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          
          {realCommentsOpen && (
            <>
              {comments.filter(c => !c.dry_run).length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  아직 실제 댓글 기록이 없습니다.
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
                      {comments.filter(c => !c.dry_run).map((record, idx) => {
                        const isExpanded = expandedRows.has(idx)
                        return (
                          <tr
                            key={idx}
                            onClick={() => {
                              setExpandedRows(prev => {
                                const next = new Set(prev)
                                if (next.has(idx)) next.delete(idx)
                                else next.add(idx)
                                return next
                              })
                            }}
                            className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                          >
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.post_content || '-'} maxLength={35} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.query || '-'} maxLength={40} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.function_result || '-'} maxLength={50} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.comment} maxLength={40} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <a
                                href={record.post_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={e => e.stopPropagation()}
                                className="text-xs text-blue-600 hover:underline block truncate"
                                title={record.post_title || record.post_url}
                              >
                                {record.post_title || '링크'}
                              </a>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>

        {/* 가실행 댓글 기록 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div 
            className="px-6 py-4 border-b border-gray-100 flex items-center justify-between cursor-pointer hover:bg-gray-50"
            onClick={() => setDryRunCommentsOpen(!dryRunCommentsOpen)}
          >
            <h2 className="text-lg font-semibold text-gray-800">
              가실행 댓글 기록 <span className="text-gray-400 font-normal">({comments.filter(c => c.dry_run).length}개)</span>
            </h2>
            <svg 
              className={`w-5 h-5 text-gray-500 transition-transform ${dryRunCommentsOpen ? 'rotate-180' : ''}`}
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          
          {dryRunCommentsOpen && (
            <>
              {comments.filter(c => c.dry_run).length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  아직 가실행 댓글 기록이 없습니다.
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
                      {comments.filter(c => c.dry_run).map((record, idx) => {
                        const isExpanded = expandedRows.has(idx + 10000) // 다른 인덱스 사용
                        return (
                          <tr
                            key={idx}
                            onClick={() => {
                              setExpandedRows(prev => {
                                const next = new Set(prev)
                                const rowId = idx + 10000
                                if (next.has(rowId)) next.delete(rowId)
                                else next.add(rowId)
                                return next
                              })
                            }}
                            className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                          >
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.post_content || '-'} maxLength={35} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.query || '-'} maxLength={40} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.function_result || '-'} maxLength={50} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.comment} maxLength={40} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <a
                                href={record.post_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={e => e.stopPropagation()}
                                className="text-xs text-blue-600 hover:underline block truncate"
                                title={record.post_title || record.post_url}
                              >
                                {record.post_title || '링크'}
                              </a>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>

        {/* 테스트 댓글 기록 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden mt-6">
          <div 
            className="px-6 py-4 border-b border-gray-100 flex items-center justify-between cursor-pointer hover:bg-gray-50"
            onClick={() => setTestCommentsOpen(!testCommentsOpen)}
          >
            <h2 className="text-lg font-semibold text-gray-800">
              테스트 댓글 기록 <span className="text-gray-400 font-normal">({testResults.length}개)</span>
            </h2>
            <svg 
              className={`w-5 h-5 text-gray-500 transition-transform ${testCommentsOpen ? 'rotate-180' : ''}`}
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          
          {testCommentsOpen && (
            <div className="p-6">
              <p className="text-sm text-gray-500 mb-4">
                게시글 내용을 직접 입력하여 Query Agent → RAG → Answer Agent 파이프라인을 테스트합니다. (첫 줄: 제목, 나머지: 본문)
              </p>
              
              <div className="overflow-x-auto">
                <table className="w-full bg-white border border-gray-200 table-fixed">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '22%' }}>원글 (입력)</th>
                      <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '18%' }}>쿼리</th>
                      <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '22%' }}>함수결과</th>
                      <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '22%' }}>최종답변</th>
                      <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '16%' }}>실행</th>
                    </tr>
                  </thead>
                  <tbody>
                    {/* 입력 행 */}
                    <tr className="border-b border-gray-200 bg-blue-50">
                      <td className="px-2 py-2 align-top">
                        <textarea
                          value={testInput}
                          onChange={(e) => setTestInput(e.target.value)}
                          placeholder="제목&#10;본문 내용..."
                          rows={4}
                          className="w-full px-2 py-1.5 text-xs border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none"
                        />
                      </td>
                      <td className="px-2 py-2 align-top text-xs text-gray-400">-</td>
                      <td className="px-2 py-2 align-top text-xs text-gray-400">-</td>
                      <td className="px-2 py-2 align-top text-xs text-gray-400">-</td>
                      <td className="px-2 py-2 align-top">
                        <button
                          onClick={handleTestRun}
                          disabled={testLoading || !testInput.trim()}
                          className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white text-xs font-medium rounded transition-colors"
                        >
                          {testLoading ? '실행 중...' : '실행'}
                        </button>
                      </td>
                    </tr>
                    
                    {/* 결과 행들 */}
                    {testResults.map((result, idx) => {
                      const isExpanded = testExpandedRows.has(idx)
                      return (
                        <tr
                          key={idx}
                          onClick={() => {
                            setTestExpandedRows(prev => {
                              const next = new Set(prev)
                              if (next.has(idx)) next.delete(idx)
                              else next.add(idx)
                              return next
                            })
                          }}
                          className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                        >
                          <td className="px-2 py-1.5 align-top">
                            <ExpandableCell content={result.post_content || '-'} maxLength={35} isExpanded={isExpanded} />
                          </td>
                          <td className="px-2 py-1.5 align-top">
                            <ExpandableCell content={result.query || '-'} maxLength={40} isExpanded={isExpanded} />
                          </td>
                          <td className="px-2 py-1.5 align-top">
                            <ExpandableCell content={result.function_result || '-'} maxLength={50} isExpanded={isExpanded} />
                          </td>
                          <td className="px-2 py-1.5 align-top">
                            <ExpandableCell content={result.answer || '-'} maxLength={40} isExpanded={isExpanded} />
                          </td>
                          <td className="px-2 py-1.5 align-top text-xs text-gray-400">완료</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              
              {testResults.length > 0 && (
                <div className="mt-3 flex justify-end">
                  <button
                    onClick={() => setTestResults([])}
                    className="px-3 py-1.5 text-sm bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                  >
                    결과 지우기
                  </button>
                </div>
              )}
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
