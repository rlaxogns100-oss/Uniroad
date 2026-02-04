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
  id?: string
  timestamp: string
  post_url: string
  post_title: string
  comment: string
  success: boolean
  dry_run?: boolean  // 가실행 여부
  post_content?: string
  query?: string
  function_result?: string
  status?: 'pending' | 'approved' | 'cancelled' | 'posted' | 'failed'  // 반자동 시스템 상태
  action_history?: Array<{action: string, timestamp: string, old_comment?: string}>
  posted_at?: string | null
}

interface PosterStatus {
  running: boolean
  pid: number | null
  approved_count: number
  timestamp: string
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
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())  // ID 기반으로 변경
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

  // 스킵 링크 관리
  const [skipLinksOpen, setSkipLinksOpen] = useState(false)
  const [skipLinks, setSkipLinks] = useState<Array<{url: string, article_id: string, added_at: string}>>([])
  const [skipLinkInput, setSkipLinkInput] = useState('')
  const [skipLinkLoading, setSkipLinkLoading] = useState(false)

  // 게시 워커 상태
  const [posterStatus, setPosterStatus] = useState<PosterStatus | null>(null)
  const [posterLoading, setPosterLoading] = useState(false)
  
  // 게시 로그
  const [posterLogs, setPosterLogs] = useState<string[]>([])
  const [posterLogsExpanded, setPosterLogsExpanded] = useState(false)
  
  // 댓글 필터 탭
  const [commentFilter, setCommentFilter] = useState<'all' | 'pending' | 'approved' | 'cancelled' | 'posted'>('all')
  
  // 댓글 수정 모달
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editingComment, setEditingComment] = useState<CommentRecord | null>(null)
  const [editCommentText, setEditCommentText] = useState('')
  const [actionLoading2, setActionLoading2] = useState<Set<string>>(new Set())  // 여러 개 병렬 처리 가능

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
      const res = await fetch(`${API_BASE}/comments?limit=500`)
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

  const fetchSkipLinks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/skip-links`)
      if (!res.ok) throw new Error('스킵 링크 조회 실패')
      const data = await res.json()
      setSkipLinks(data.links || [])
    } catch (e) {
      console.error('스킵 링크 조회 에러:', e)
    }
  }, [])

  const fetchPosterStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/poster/status`)
      if (!res.ok) throw new Error('게시 워커 상태 조회 실패')
      const data: PosterStatus = await res.json()
      setPosterStatus(data)
    } catch (e) {
      console.error('게시 워커 상태 조회 에러:', e)
    }
  }, [])

  const fetchPosterLogs = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/poster/logs?lines=50`)
      if (!res.ok) throw new Error('게시 로그 조회 실패')
      const data = await res.json()
      setPosterLogs(data.logs || [])
    } catch (e) {
      console.error('게시 로그 조회 에러:', e)
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
      await Promise.all([fetchStatus(), fetchComments(), fetchPrompts(), fetchSkipLinks(), fetchPosterStatus(), fetchPosterLogs()])
      setLoading(false)
    }
    load()

    // 10초마다 상태 업데이트
    const interval = setInterval(() => {
      fetchStatus()
      fetchComments()
      fetchPosterStatus()
      fetchPosterLogs()
    }, 10000)

    return () => clearInterval(interval)
  }, [fetchStatus, fetchComments, fetchPrompts, fetchSkipLinks, fetchPosterStatus, fetchPosterLogs])

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

  // 게시 워커 시작/중지
  const handleStartPoster = async () => {
    setPosterLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/poster/start`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '게시 워커 시작 실패')
      await fetchPosterStatus()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setPosterLoading(false)
    }
  }

  const handleStopPoster = async () => {
    setPosterLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/poster/stop`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '게시 워커 중지 실패')
      await fetchPosterStatus()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setPosterLoading(false)
    }
  }

  // 댓글 액션 핸들러들
  const handleApprove = async (commentId: string) => {
    setActionLoading2(prev => new Set(prev).add(commentId))
    try {
      const res = await fetch(`${API_BASE}/comments/${commentId}/approve`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '승인 실패')
      await fetchComments()
      await fetchPosterStatus()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading2(prev => {
        const next = new Set(prev)
        next.delete(commentId)
        return next
      })
    }
  }

  const handleCancel = async (commentId: string) => {
    setActionLoading2(prev => new Set(prev).add(commentId))
    try {
      const res = await fetch(`${API_BASE}/comments/${commentId}/cancel`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '취소 실패')
      
      // 즉시 로컬 상태 업데이트 (Optimistic Update)
      setComments(prev => prev.map(c => 
        c.id === commentId ? { ...c, status: 'cancelled' as const } : c
      ))
      
      // 백그라운드에서 전체 새로고침 (await 제거)
      fetchComments()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading2(prev => {
        const next = new Set(prev)
        next.delete(commentId)
        return next
      })
    }
  }

  const openEditModal = (record: CommentRecord) => {
    setEditingComment(record)
    setEditCommentText(record.comment)
    setEditModalOpen(true)
  }

  const handleEditSave = async () => {
    if (!editingComment?.id) return
    setActionLoading2(prev => new Set(prev).add(editingComment.id!))
    try {
      const res = await fetch(`${API_BASE}/comments/${editingComment.id}/edit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_comment: editCommentText })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '수정 실패')
      setEditModalOpen(false)
      setEditingComment(null)
      await fetchComments()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading2(prev => {
        const next = new Set(prev)
        next.delete(editingComment.id!)
        return next
      })
    }
  }

  const handleRegenerate = async (commentId: string) => {
    setActionLoading2(prev => new Set(prev).add(commentId))
    try {
      const res = await fetch(`${API_BASE}/comments/${commentId}/regenerate`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '재생성 실패')
      await fetchComments()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading2(prev => {
        const next = new Set(prev)
        next.delete(commentId)
        return next
      })
    }
  }

  const handleRevertToPending = async (commentId: string) => {
    setActionLoading2(prev => new Set(prev).add(commentId))
    try {
      const res = await fetch(`${API_BASE}/comments/${commentId}/revert`, { method: 'POST' })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '되돌리기 실패')
      await fetchComments()
      await fetchPosterStatus()
    } catch (e: any) {
      alert(e.message)
    } finally {
      setActionLoading2(prev => {
        const next = new Set(prev)
        next.delete(commentId)
        return next
      })
    }
  }

  // 상태 뱃지 렌더링
  const renderStatusBadge = (status?: string) => {
    switch (status) {
      case 'pending':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">대기중</span>
      case 'approved':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">승인됨</span>
      case 'posted':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">게시완료</span>
      case 'cancelled':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">취소됨</span>
      case 'failed':
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">실패</span>
      default:
        return <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">-</span>
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

  // 스킵 링크 관련 함수들
  const handleAddSkipLink = async () => {
    if (!skipLinkInput.trim()) {
      alert('URL을 입력해주세요.')
      return
    }
    
    setSkipLinkLoading(true)
    try {
      const res = await fetch(`${API_BASE}/skip-links`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: skipLinkInput })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '추가 실패')
      
      setSkipLinkInput('')
      await fetchSkipLinks()
      alert(data.message)
    } catch (e: any) {
      alert(`추가 실패: ${e.message}`)
    } finally {
      setSkipLinkLoading(false)
    }
  }

  const handleRemoveSkipLink = async (url: string) => {
    if (!confirm('이 링크를 삭제하시겠습니까?')) return
    
    try {
      const res = await fetch(`${API_BASE}/skip-links`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '삭제 실패')
      
      await fetchSkipLinks()
    } catch (e: any) {
      alert(`삭제 실패: ${e.message}`)
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
        <div className="max-w-[1600px] mx-auto px-4 py-4 flex items-center justify-between">
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

      <main className="max-w-[1600px] mx-auto px-4 py-8">
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

        {/* 게시 로그 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div 
            className="px-6 py-4 border-b border-gray-100 flex items-center justify-between cursor-pointer hover:bg-gray-50"
            onClick={() => setPosterLogsExpanded(!posterLogsExpanded)}
          >
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-gray-800">게시 로그</h2>
              {posterStatus?.running && (
                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                  <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse mr-1"></span>
                  실행중
                </span>
              )}
            </div>
            <svg 
              className={`w-5 h-5 text-gray-500 transition-transform ${posterLogsExpanded ? 'rotate-180' : ''}`}
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          {posterLogsExpanded && (
            <div className="p-4">
              <div className="bg-gray-900 rounded-lg p-4 h-64 overflow-y-auto font-mono text-xs">
                {posterLogs.length === 0 ? (
                  <div className="text-gray-500">게시 로그가 없습니다.</div>
                ) : (
                  posterLogs.map((log, idx) => (
                    <div key={idx} className={`${log.includes('[에러]') || log.includes('Error') ? 'text-red-400' : log.includes('[게시 완료]') ? 'text-green-400' : 'text-gray-300'}`}>
                      {log}
                    </div>
                  ))
                )}
              </div>
              <button
                onClick={fetchPosterLogs}
                className="mt-2 px-3 py-1 text-xs bg-gray-100 hover:bg-gray-200 rounded"
              >
                새로고침
              </button>
            </div>
          )}
        </div>

        {/* 댓글 기록 - 실제 댓글과 가실행 댓글 분리 */}
        
        {/* 실제 댓글 기록 (반자동 시스템) */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
          <div 
            className="px-6 py-4 border-b border-gray-100 flex items-center justify-between cursor-pointer hover:bg-gray-50"
            onClick={() => setRealCommentsOpen(!realCommentsOpen)}
          >
            <div className="flex items-center gap-4">
              <h2 className="text-lg font-semibold text-gray-800">
                실제 댓글 기록 <span className="text-gray-400 font-normal">({comments.filter(c => !c.dry_run).length}개)</span>
              </h2>
              {/* 게시 워커 상태 및 컨트롤 */}
              <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                {posterStatus?.running ? (
                  <>
                    <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse mr-1.5"></span>
                      게시 워커 실행중
                    </span>
                    <button
                      onClick={handleStopPoster}
                      disabled={posterLoading}
                      className="px-3 py-1 text-xs bg-red-500 hover:bg-red-600 text-white rounded-lg disabled:opacity-50"
                    >
                      {posterLoading ? '...' : '게시 중지'}
                    </button>
                  </>
                ) : (
                  <>
                    <span className="text-xs text-gray-500">
                      승인 대기: {posterStatus?.approved_count || 0}개
                    </span>
                    <button
                      onClick={handleStartPoster}
                      disabled={posterLoading || (posterStatus?.approved_count || 0) === 0}
                      className="px-3 py-1 text-xs bg-green-500 hover:bg-green-600 text-white rounded-lg disabled:opacity-50"
                    >
                      {posterLoading ? '...' : '게시 시작'}
                    </button>
                  </>
                )}
              </div>
            </div>
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
              {/* 필터 탭 */}
              <div className="px-4 py-2 border-b border-gray-100 flex gap-2 flex-wrap">
                {[
                  { key: 'all', label: '전체', count: comments.filter(c => !c.dry_run).length },
                  { key: 'pending', label: '대기중', count: comments.filter(c => !c.dry_run && c.status === 'pending').length },
                  { key: 'approved', label: '승인됨', count: comments.filter(c => !c.dry_run && c.status === 'approved').length },
                  { key: 'cancelled', label: '취소됨', count: comments.filter(c => !c.dry_run && c.status === 'cancelled').length },
                  { key: 'posted', label: '게시완료', count: comments.filter(c => !c.dry_run && c.status === 'posted').length },
                ].map(tab => (
                  <button
                    key={tab.key}
                    onClick={(e) => { e.stopPropagation(); setCommentFilter(tab.key as any); }}
                    className={`px-3 py-1 text-xs rounded-full transition-colors ${
                      commentFilter === tab.key 
                        ? 'bg-blue-500 text-white' 
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {tab.label} ({tab.count})
                  </button>
                ))}
              </div>
              {comments.filter(c => !c.dry_run).length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  아직 실제 댓글 기록이 없습니다.
                </div>
              ) : (
                <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                  <table className="w-full bg-white border border-gray-200 table-fixed">
                    <thead className="sticky top-0 bg-gray-50 z-10">
                      <tr className="bg-gray-50 border-b border-gray-200">
                        <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '5%' }}>상태</th>
                        <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '15%' }}>원글</th>
                        <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '15%' }}>쿼리</th>
                        <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '18%' }}>함수결과</th>
                        <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '18%' }}>최종답변</th>
                        <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '12%' }}>링크</th>
                        <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{ width: '17%' }}>액션</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comments
                        .filter(c => !c.dry_run)
                        .filter(c => commentFilter === 'all' || c.status === commentFilter)
                        .map((record, idx) => {
                        const rowId = record.id || `idx-${idx}`
                        const isExpanded = expandedRows.has(rowId)
                        const isLoading = record.id ? actionLoading2.has(record.id) : false
                        return (
                          <tr
                            key={rowId}
                            onClick={() => {
                              setExpandedRows(prev => {
                                const next = new Set(prev)
                                if (next.has(rowId)) next.delete(rowId)
                                else next.add(rowId)
                                return next
                              })
                            }}
                            className="border-b border-gray-100 hover:bg-gray-50 cursor-pointer"
                          >
                            <td className="px-2 py-1.5 align-top">
                              {renderStatusBadge(record.status)}
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.post_content || '-'} maxLength={30} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.query || '-'} maxLength={30} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.function_result || '-'} maxLength={40} isExpanded={isExpanded} />
                            </td>
                            <td className="px-2 py-1.5 align-top">
                              <ExpandableCell content={record.comment} maxLength={35} isExpanded={isExpanded} />
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
                                {record.post_title?.substring(0, 15) || '링크'}
                              </a>
                            </td>
                            <td className="px-2 py-1.5 align-top" onClick={e => e.stopPropagation()}>
                              {(record.status === 'pending' || record.status === 'approved') && record.id && (
                                <div className="flex flex-wrap gap-1">
                                  {record.status === 'pending' && (
                                    <button
                                      onClick={() => handleApprove(record.id!)}
                                      disabled={isLoading}
                                      className="px-2 py-0.5 text-xs bg-blue-500 hover:bg-blue-600 text-white rounded disabled:opacity-50"
                                    >
                                      {isLoading ? '...' : '확인'}
                                    </button>
                                  )}
                                  {record.status === 'approved' && (
                                    <button
                                      onClick={() => handleRevertToPending(record.id!)}
                                      disabled={isLoading}
                                      className="px-2 py-0.5 text-xs bg-orange-500 hover:bg-orange-600 text-white rounded disabled:opacity-50"
                                    >
                                      {isLoading ? '...' : '승인취소'}
                                    </button>
                                  )}
                                  <button
                                    onClick={() => handleCancel(record.id!)}
                                    disabled={isLoading}
                                    className="px-2 py-0.5 text-xs bg-gray-400 hover:bg-gray-500 text-white rounded disabled:opacity-50"
                                  >
                                    {isLoading ? '...' : '취소'}
                                  </button>
                                  <button
                                    onClick={() => openEditModal(record)}
                                    disabled={isLoading}
                                    className="px-2 py-0.5 text-xs bg-yellow-500 hover:bg-yellow-600 text-white rounded disabled:opacity-50"
                                  >
                                    수정
                                  </button>
                                  <button
                                    onClick={() => handleRegenerate(record.id!)}
                                    disabled={isLoading}
                                    className="px-2 py-0.5 text-xs bg-purple-500 hover:bg-purple-600 text-white rounded disabled:opacity-50"
                                  >
                                    {isLoading ? '...' : '재생성'}
                                  </button>
                                </div>
                              )}
                              {record.status === 'posted' && (
                                <span className="text-xs text-green-600">게시완료</span>
                              )}
                              {(record.status === 'cancelled' || record.status === 'failed') && record.id && (
                                <div className="flex flex-wrap gap-1 items-center">
                                  <span className="text-xs text-gray-500">{record.status === 'cancelled' ? '취소됨' : '실패'}</span>
                                  <button
                                    onClick={() => handleRevertToPending(record.id!)}
                                    disabled={isLoading}
                                    className="px-2 py-0.5 text-xs bg-blue-500 hover:bg-blue-600 text-white rounded disabled:opacity-50"
                                  >
                                    {isLoading ? '...' : '되돌리기'}
                                  </button>
                                </div>
                              )}
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
                        const rowId = record.id || `dry-${idx}`
                        const isExpanded = expandedRows.has(rowId)
                        return (
                          <tr
                            key={rowId}
                            onClick={() => {
                              setExpandedRows(prev => {
                                const next = new Set(prev)
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

        {/* 스킵 링크 관리 */}
        <div className="bg-white rounded-xl shadow-sm overflow-hidden mt-6">
          <div 
            className="px-6 py-4 border-b border-gray-100 flex items-center justify-between cursor-pointer hover:bg-gray-50"
            onClick={() => setSkipLinksOpen(!skipLinksOpen)}
          >
            <h2 className="text-lg font-semibold text-gray-800">
              수동 스킵 링크 <span className="text-gray-400 font-normal">({skipLinks.length}개)</span>
            </h2>
            <svg 
              className={`w-5 h-5 text-gray-500 transition-transform ${skipLinksOpen ? 'rotate-180' : ''}`}
              fill="none" 
              stroke="currentColor" 
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </div>
          
          {skipLinksOpen && (
            <div className="p-6">
              <p className="text-sm text-gray-500 mb-4">
                수동으로 댓글을 단 글의 URL을 추가하면 봇이 해당 글을 건너뜁니다. 브라우저 주소창의 URL을 그대로 복사해서 붙여넣으세요.
              </p>
              
              <div className="flex gap-2 mb-4">
                <input
                  type="text"
                  value={skipLinkInput}
                  onChange={(e) => setSkipLinkInput(e.target.value)}
                  placeholder="https://cafe.naver.com/suhui/29429119"
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                  onKeyDown={(e) => e.key === 'Enter' && handleAddSkipLink()}
                />
                <button
                  onClick={handleAddSkipLink}
                  disabled={skipLinkLoading || !skipLinkInput.trim()}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-medium rounded-lg transition-colors text-sm"
                >
                  {skipLinkLoading ? '추가 중...' : '추가'}
                </button>
              </div>
              
              {skipLinks.length === 0 ? (
                <div className="text-center text-gray-500 py-4">
                  등록된 스킵 링크가 없습니다.
                </div>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {skipLinks.map((link, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
                      <div className="flex-1 min-w-0">
                        <a
                          href={link.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-sm text-blue-600 hover:underline truncate block"
                        >
                          {link.url}
                        </a>
                        <span className="text-xs text-gray-400">
                          Article ID: {link.article_id} | {new Date(link.added_at).toLocaleString('ko-KR')}
                        </span>
                      </div>
                      <button
                        onClick={() => handleRemoveSkipLink(link.url)}
                        className="ml-2 px-2 py-1 text-xs text-red-600 hover:bg-red-50 rounded transition-colors"
                      >
                        삭제
                      </button>
                    </div>
                  ))}
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
            <li>3. 이 페이지에서 '봇 시작' 버튼 클릭 → 댓글이 자동 생성되어 대기열에 추가됨</li>
            <li>4. 생성된 댓글을 검토하고 '확인' 버튼으로 승인</li>
            <li>5. '게시 시작' 버튼 클릭 → 승인된 댓글이 딜레이를 적용하여 자동 게시됨</li>
          </ul>
        </div>
      </main>

      {/* 댓글 수정 모달 */}
      {editModalOpen && editingComment && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-800">댓글 수정</h3>
            </div>
            <div className="p-6">
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">원글</label>
                <div className="p-3 bg-gray-50 rounded-lg text-sm text-gray-600 max-h-32 overflow-y-auto">
                  {editingComment.post_content || editingComment.post_title || '-'}
                </div>
              </div>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">댓글 내용</label>
                <textarea
                  value={editCommentText}
                  onChange={(e) => setEditCommentText(e.target.value)}
                  rows={6}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div className="flex justify-end gap-3">
                <button
                  onClick={() => {
                    setEditModalOpen(false)
                    setEditingComment(null)
                  }}
                  className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg transition-colors"
                >
                  취소
                </button>
                <button
                  onClick={handleEditSave}
                  disabled={editingComment?.id ? actionLoading2.has(editingComment.id) : false}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
                >
                  {editingComment?.id && actionLoading2.has(editingComment.id) ? '저장 중...' : '저장'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
