import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getApiBaseUrl } from '../config'
import ChatMessage from '../components/ChatMessage'

type UserType = 'pro' | 'basic' | 'guest'

interface ReviewSession {
  session_id: string
  user_id: string | null
  user_name: string
  user_email?: string | null
  user_type: UserType
  chat_count: number
  start_time: string
  end_time: string
  recent_time: string
  bookmark?: boolean
  comment?: string
}

interface SessionMessage {
  id: string
  session_id: string
  user_id: string | null
  role: string
  content: string
  created_at: string
  sources?: string[]
  source_urls?: string[]
  router_output?: any
  function_result?: any
  timing?: {
    router?: number
    function?: number
    main_agent?: number
  } | null
  elapsed_time?: number
}

const formatTime = (value: string): string => {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleString('ko-KR')
}

const getElapsedMs = (msg: SessionMessage): number => {
  if (typeof msg.elapsed_time === 'number' && Number.isFinite(msg.elapsed_time) && msg.elapsed_time > 0) {
    return msg.elapsed_time
  }
  const r = Number(msg.timing?.router || 0)
  const f = Number(msg.timing?.function || 0)
  const m = Number(msg.timing?.main_agent || 0)
  const sum = r + f + m
  return Number.isFinite(sum) ? sum : 0
}

const formatElapsed = (ms: number): string => {
  if (!ms || ms <= 0) return '측정값 없음'
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`
  return `${Math.round(ms)}ms`
}

const elapsedBadgeClass = (ms: number): string => {
  if (!ms || ms <= 0) return 'bg-gray-100 text-gray-600'
  if (ms < 3000) return 'bg-green-100 text-green-700'
  if (ms < 8000) return 'bg-amber-100 text-amber-700'
  return 'bg-red-100 text-red-700'
}

const shortSessionId = (value: string): string => {
  const v = String(value || '')
  if (v.length <= 18) return v
  return `${v.slice(0, 8)}...${v.slice(-4)}`
}

const uuidLike = (value: string): boolean => /^[0-9a-f]{8}-[0-9a-f]{4}-/i.test(value || '')

const displayUserName = (row: ReviewSession): string => {
  const name = String(row.user_name || '').trim()
  if (name && !uuidLike(name)) return name
  const email = String(row.user_email || '').trim()
  if (email.includes('@')) return email.split('@')[0]
  return name || '-'
}

export default function AdminChatReviewPage() {
  const EXCLUDED_USERS_KEY = 'admin_chat_review_excluded_users_v1'
  const navigate = useNavigate()
  const [sessions, setSessions] = useState<ReviewSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)
  const [selectedMessages, setSelectedMessages] = useState<SessionMessage[]>([])
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [messageViewMode, setMessageViewMode] = useState<Record<string, 'answer' | 'router' | 'function'>>({})

  const [userTypeFilter, setUserTypeFilter] = useState<'all' | UserType>('all')
  const [chatCountMin, setChatCountMin] = useState('')
  const [chatCountMax, setChatCountMax] = useState('')
  const [recentFrom, setRecentFrom] = useState('')
  const [recentTo, setRecentTo] = useState('')
  const [userNameQuery, setUserNameQuery] = useState('')
  const [bookmarkOnly, setBookmarkOnly] = useState(false)
  const [excludedUsers, setExcludedUsers] = useState<string[]>([])
  const [excludeInput, setExcludeInput] = useState('')
  const [commentDraftBySession, setCommentDraftBySession] = useState<Record<string, string>>({})

  useEffect(() => {
    try {
      const raw = localStorage.getItem(EXCLUDED_USERS_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw)
      if (Array.isArray(parsed)) {
        setExcludedUsers(parsed.map((v) => String(v)).filter(Boolean))
      }
    } catch {}
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(EXCLUDED_USERS_KEY, JSON.stringify(excludedUsers))
    } catch {}
  }, [excludedUsers])

  const loadSessions = async () => {
    setLoading(true)
    setError(null)
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        throw new Error('관리자 인증 토큰이 없습니다. /chat/login 으로 다시 로그인해주세요.')
      }

      const apiBase = getApiBaseUrl()
      const response = await fetch(`${apiBase}/api/sessions/admin/review/sessions?limit=500`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '세션 조회 실패' }))
        throw new Error(err.detail || '세션 조회 실패')
      }
      const payload = await response.json()
      const nextSessions: ReviewSession[] = payload.sessions || []
      setSessions(nextSessions)
      setCommentDraftBySession(
        nextSessions.reduce<Record<string, string>>((acc, row) => {
          acc[row.session_id] = row.comment || ''
          return acc
        }, {})
      )
    } catch (e: any) {
      setError(e?.message || '세션 목록을 불러오지 못했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const loadSessionMessages = async (sessionId: string) => {
    setSelectedSessionId(sessionId)
    setLoadingMessages(true)
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        throw new Error('관리자 인증 토큰이 없습니다.')
      }
      const apiBase = getApiBaseUrl()
      const response = await fetch(`${apiBase}/api/sessions/admin/review/sessions/${sessionId}/messages`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: '메시지 조회 실패' }))
        throw new Error(err.detail || '메시지 조회 실패')
      }
      const payload = await response.json()
      setSelectedMessages(payload.messages || [])
      setMessageViewMode({})
    } catch (e) {
      console.error(e)
      setSelectedMessages([])
    } finally {
      setLoadingMessages(false)
    }
  }

  useEffect(() => {
    loadSessions()
  }, [])

  const filteredSessions = useMemo(() => {
    const q = userNameQuery.trim().toLowerCase()
    const minCount = chatCountMin ? Number(chatCountMin) : null
    const maxCount = chatCountMax ? Number(chatCountMax) : null
    const fromTs = recentFrom ? new Date(recentFrom).getTime() : null
    const toTs = recentTo ? new Date(recentTo).getTime() : null

    return sessions.filter((row) => {
      if (userTypeFilter !== 'all' && row.user_type !== userTypeFilter) return false

      if (Number.isFinite(minCount) && minCount !== null && row.chat_count < minCount) return false
      if (Number.isFinite(maxCount) && maxCount !== null && row.chat_count > maxCount) return false

      const recentTs = row.recent_time ? new Date(row.recent_time).getTime() : null
      if (fromTs && (!recentTs || recentTs < fromTs)) return false
      if (toTs && (!recentTs || recentTs > toTs)) return false

      const userName = (row.user_name || '').toLowerCase()
      const userId = (row.user_id || '').toLowerCase()
      const userEmail = (row.user_email || '').toLowerCase()
      if (q && !userName.includes(q) && !userId.includes(q) && !userEmail.includes(q)) return false

      if (bookmarkOnly && !row.bookmark) return false

      if (excludedUsers.length > 0) {
        const fields = [userId, userName, userEmail]
        const excluded = excludedUsers.some((token) => {
          const t = token.trim().toLowerCase()
          if (!t) return false
          return fields.some((f) => f && (f === t || f.includes(t)))
        })
        if (excluded) return false
      }

      return true
    })
  }, [sessions, userTypeFilter, chatCountMin, chatCountMax, recentFrom, recentTo, userNameQuery, bookmarkOnly, excludedUsers])

  const addExcludedUser = (raw: string) => {
    const value = raw.trim()
    if (!value) return
    setExcludedUsers((prev) => (prev.some((v) => v.toLowerCase() === value.toLowerCase()) ? prev : [...prev, value]))
    setExcludeInput('')
  }

  const removeExcludedUser = (value: string) => {
    setExcludedUsers((prev) => prev.filter((v) => v !== value))
  }

  const excludeMyself = () => {
    try {
      const raw = localStorage.getItem('user')
      if (!raw) return
      const user = JSON.parse(raw)
      const candidates = [user?.id, user?.email, user?.name].filter(Boolean).map((v) => String(v))
      if (candidates.length === 0) return
      setExcludedUsers((prev) => {
        const next = [...prev]
        for (const c of candidates) {
          if (!next.some((v) => v.toLowerCase() === c.toLowerCase())) next.push(c)
        }
        return next
      })
    } catch {}
  }

  const updateSessionMeta = async (sessionId: string, payload: { bookmark?: boolean; comment?: string }) => {
    const token = localStorage.getItem('access_token')
    if (!token) throw new Error('관리자 인증 토큰이 없습니다.')
    const apiBase = getApiBaseUrl()
    const response = await fetch(`${apiBase}/api/sessions/admin/review/sessions/${sessionId}/meta`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: '세션 메타 저장 실패' }))
      throw new Error(err.detail || '세션 메타 저장 실패')
    }
    const updated = await response.json()
    setSessions((prev) =>
      prev.map((row) =>
        row.session_id === sessionId
          ? { ...row, bookmark: !!updated.bookmark, comment: updated.comment || '' }
          : row
      )
    )
    setCommentDraftBySession((prev) => ({ ...prev, [sessionId]: updated.comment || '' }))
  }

  const handleBookmarkToggle = async (sessionId: string, current: boolean) => {
    try {
      await updateSessionMeta(sessionId, { bookmark: !current })
    } catch (e) {
      console.error(e)
      alert('북마크 저장에 실패했습니다.')
    }
  }

  const handleCommentBlur = async (sessionId: string, originalComment: string) => {
    const nextComment = commentDraftBySession[sessionId] ?? ''
    if (nextComment === (originalComment || '')) return
    try {
      await updateSessionMeta(sessionId, { comment: nextComment })
    } catch (e) {
      console.error(e)
      alert('코멘트 저장에 실패했습니다.')
      setCommentDraftBySession((prev) => ({ ...prev, [sessionId]: originalComment || '' }))
    }
  }

  const cycleAssistantView = (messageId: string) => {
    setMessageViewMode((prev) => {
      const current = prev[messageId] || 'answer'
      const next = current === 'answer' ? 'router' : current === 'router' ? 'function' : 'answer'
      return { ...prev, [messageId]: next }
    })
  }

  const formatJson = (value: any): string => {
    if (value === null || value === undefined) return '데이터 없음'
    if (typeof value === 'string') {
      try {
        return JSON.stringify(JSON.parse(value), null, 2)
      } catch {
        return value
      }
    }
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }

  const selectedSession = useMemo(
    () => filteredSessions.find((row) => row.session_id === selectedSessionId) || null,
    [filteredSessions, selectedSessionId]
  )

  const isSplitMode = Boolean(selectedSessionId)

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-[1600px] mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">로그리뷰</h1>
            <p className="text-sm text-gray-500 mt-1">세션 기준 대화 로그 검토 및 코멘트 관리</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={loadSessions}
              className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm"
            >
              새로고침
            </button>
            <button
              onClick={() => navigate('/chat/login/admin')}
              className="px-3 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm"
            >
              기존 관리자 페이지
            </button>
            <button
              onClick={() => navigate('/chat/login')}
              className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
            >
              채팅으로
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-[1600px] mx-auto px-6 py-6">
        <section className="bg-white rounded-xl border border-gray-200 p-4 mb-4">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-6 gap-3">
            <select
              value={userTypeFilter}
              onChange={(e) => setUserTypeFilter(e.target.value as 'all' | UserType)}
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            >
              <option value="all">유저 유형: 전체</option>
              <option value="pro">유저 유형: Pro</option>
              <option value="basic">유저 유형: Basic</option>
              <option value="guest">유저 유형: 비회원</option>
            </select>

            <input
              type="number"
              min={0}
              value={chatCountMin}
              onChange={(e) => setChatCountMin(e.target.value)}
              placeholder="채팅 수 최소"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
            <input
              type="number"
              min={0}
              value={chatCountMax}
              onChange={(e) => setChatCountMax(e.target.value)}
              placeholder="채팅 수 최대"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
            <input
              type="datetime-local"
              value={recentFrom}
              onChange={(e) => setRecentFrom(e.target.value)}
              placeholder="최근 대화 시작"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
            <input
              type="datetime-local"
              value={recentTo}
              onChange={(e) => setRecentTo(e.target.value)}
              placeholder="최근 대화 종료"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
            <input
              value={userNameQuery}
              onChange={(e) => setUserNameQuery(e.target.value)}
              placeholder="유저 이름/ID/메일 검색"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
            />
          </div>

          <div className="mt-3 flex items-center gap-4 text-sm">
            <label className="inline-flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={bookmarkOnly}
                onChange={(e) => setBookmarkOnly(e.target.checked)}
                className="w-4 h-4"
              />
              북마크 적용된 세션만 보기
            </label>
            <span className="text-gray-500">조회 결과: {filteredSessions.length}건</span>
          </div>
          <div className="mt-3 flex items-center gap-2 overflow-x-auto whitespace-nowrap">
            <input
              value={excludeInput}
              onChange={(e) => setExcludeInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addExcludedUser(excludeInput)
                }
              }}
              placeholder="제외할 유저(이름/ID/메일) 입력"
              className="px-3 py-2 border border-gray-300 rounded-lg text-sm min-w-[260px] shrink-0"
            />
            <button
              onClick={() => addExcludedUser(excludeInput)}
              className="px-3 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 text-sm shrink-0"
            >
              제외 추가
            </button>
            <button
              onClick={excludeMyself}
              className="px-3 py-2 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 text-sm shrink-0"
            >
              내 계정 제외
            </button>
            {excludedUsers.map((u) => (
              <button
                key={u}
                onClick={() => removeExcludedUser(u)}
                className="px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs hover:bg-red-200 shrink-0"
                title="클릭해서 제외 해제"
              >
                제외: {u} ×
              </button>
            ))}
          </div>
        </section>

        <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {loading ? (
            <div className="p-10 text-center text-gray-500">세션 목록 불러오는 중...</div>
          ) : error ? (
            <div className="p-10 text-center text-red-600">{error}</div>
          ) : filteredSessions.length === 0 ? (
            <div className="p-10 text-center text-gray-500">조건에 맞는 세션이 없습니다.</div>
          ) : (
            <div className="flex h-[72vh] min-h-[620px]">
              {/* 좌측: 세션 목록 사이드바 */}
              <div className={`${isSplitMode ? 'w-[40%]' : 'w-full'} border-r border-gray-200 transition-all duration-200 select-none`}>
                <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 text-sm text-gray-600">
                  세션 목록 ({filteredSessions.length}건)
                </div>
                <div className="h-[calc(72vh-48px)] min-h-[572px] overflow-y-auto overscroll-contain">
                  {filteredSessions.map((row) => {
                    const selected = selectedSessionId === row.session_id
                    return (
                      <div
                        key={row.session_id}
                        onClick={() => loadSessionMessages(row.session_id)}
                        className={`p-4 border-b border-gray-100 cursor-pointer transition-colors ${
                          selected ? 'bg-blue-50' : 'bg-white hover:bg-gray-50'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2 mb-2">
                          <p
                            className="min-w-0 flex-1 text-[11px] font-medium text-gray-900 truncate whitespace-nowrap"
                            title={`유저:${displayUserName(row)} 메일:${row.user_email || '-'} 세션:${row.session_id} 유형:${row.user_type === 'pro' ? 'Pro' : row.user_type === 'basic' ? 'Basic' : '비회원'} 채팅수:${row.chat_count} 최근:${formatTime(row.end_time)}`}
                          >
                            유저:{displayUserName(row)} · 메일:{row.user_email || '-'} · 세션:{shortSessionId(row.session_id)} · 유형:{row.user_type === 'pro' ? 'Pro' : row.user_type === 'basic' ? 'Basic' : '비회원'} · 채팅:{row.chat_count} · 최근:{formatTime(row.end_time)}
                          </p>
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              void handleBookmarkToggle(row.session_id, !!row.bookmark)
                            }}
                            className={`text-xl leading-none transition-transform hover:scale-110 ${
                              row.bookmark ? 'text-yellow-500' : 'text-gray-300'
                            }`}
                            title={row.bookmark ? '북마크 해제' : '북마크 적용'}
                          >
                            ★
                          </button>
                        </div>

                        <div onClick={(e) => e.stopPropagation()}>
                          <textarea
                            value={commentDraftBySession[row.session_id] ?? row.comment ?? ''}
                            onChange={(e) =>
                              setCommentDraftBySession((prev) => ({ ...prev, [row.session_id]: e.target.value }))
                            }
                            onBlur={() => void handleCommentBlur(row.session_id, row.comment || '')}
                            placeholder="코멘트를 입력하세요"
                            rows={1}
                            onInput={(e) => {
                              const el = e.currentTarget
                              el.style.height = 'auto'
                              el.style.height = `${Math.max(el.scrollHeight, 36)}px`
                            }}
                            className="w-full h-9 resize-none overflow-hidden border border-gray-300 rounded-lg px-3 py-2 text-sm leading-5 select-text"
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>

              {/* 우측: 채팅창 */}
              {isSplitMode && (
                <div className="w-[60%] flex flex-col">
                  <div className="px-4 py-3 border-b border-gray-200 bg-gray-50 flex items-center justify-between">
                    <div className="min-w-0 flex-1 pr-2">
                      <p className="text-sm font-semibold text-gray-900 truncate whitespace-nowrap">
                        {selectedSession
                          ? `유저:${selectedSession.user_name || '-'} · 메일:${selectedSession.user_email || '-'} · 세션:${shortSessionId(selectedSessionId || '')}`
                          : '세션 대화 로그'}
                      </p>
                    </div>
                    <button
                      onClick={() => {
                        setSelectedSessionId(null)
                        setSelectedMessages([])
                      }}
                      className="px-3 py-1.5 text-xs bg-white border border-gray-300 rounded-lg hover:bg-gray-100"
                    >
                      닫기
                    </button>
                  </div>

                  <div className="flex-1 overflow-y-auto overscroll-contain bg-[#f8fafc] p-4">
                    {loadingMessages ? (
                      <div className="py-10 text-center text-gray-500">대화 로그 불러오는 중...</div>
                    ) : selectedMessages.length === 0 ? (
                      <div className="py-10 text-center text-gray-400">메시지가 없습니다.</div>
                    ) : (
                      <div className="space-y-1">
                        {selectedMessages.map((msg) => (
                          <div key={msg.id}>
                            <div className="mb-2 px-1">
                              <div className="text-[11px] text-gray-500 flex items-center gap-2">
                                <span>{msg.role === 'user' ? '사용자' : 'AI'}</span>
                                <span>생성 시각: {formatTime(msg.created_at)}</span>
                                {msg.role === 'assistant' && (
                                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-200 text-slate-700">
                                    {messageViewMode[msg.id] === 'router'
                                      ? 'routerOutput'
                                      : messageViewMode[msg.id] === 'function'
                                        ? 'functionResult'
                                        : '답변'}
                                  </span>
                                )}
                              </div>
                              {msg.role === 'assistant' && (
                                <div className="mt-1 flex items-center gap-2 flex-wrap">
                                  <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-sm font-semibold ${elapsedBadgeClass(getElapsedMs(msg))}`}>
                                    걸린 시간: {formatElapsed(getElapsedMs(msg))}
                                  </span>
                                  <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-100 text-blue-700">
                                    R: {formatElapsed(Number(msg.timing?.router || 0))}
                                  </span>
                                  <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-emerald-100 text-emerald-700">
                                    F: {formatElapsed(Number(msg.timing?.function || 0))}
                                  </span>
                                  <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-purple-100 text-purple-700">
                                    M: {formatElapsed(Number(msg.timing?.main_agent || 0))}
                                  </span>
                                </div>
                              )}
                            </div>
                            {msg.role === 'assistant' && messageViewMode[msg.id] && messageViewMode[msg.id] !== 'answer' ? (
                              <div
                                onClick={() => cycleAssistantView(msg.id)}
                                className="cursor-pointer rounded-xl border border-gray-200 bg-white p-3"
                                title="클릭해서 보기 모드 전환"
                              >
                                <pre className="whitespace-pre-wrap break-words text-xs text-gray-800 font-mono">
                                  {messageViewMode[msg.id] === 'router'
                                    ? formatJson(msg.router_output)
                                    : formatJson(msg.function_result)}
                                </pre>
                              </div>
                            ) : (
                              <div
                                onClick={() => {
                                  if (msg.role === 'assistant') cycleAssistantView(msg.id)
                                }}
                                className={msg.role === 'assistant' ? 'cursor-pointer' : ''}
                                title={msg.role === 'assistant' ? '클릭해서 routerOutput/functionResult/답변 전환' : undefined}
                              >
                                <ChatMessage
                                  message={msg.content || ''}
                                  isUser={msg.role === 'user'}
                                  sources={msg.sources}
                                  source_urls={msg.source_urls}
                                  isStreaming={false}
                                />
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
