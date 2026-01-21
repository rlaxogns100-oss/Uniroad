import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { sendMessageStream, ChatResponse } from '../api/client'
import ChatMessage from '../components/ChatMessage'
import ThinkingProcess from '../components/ThinkingProcess'
import { useAuth } from '../contexts/AuthContext'
import { useChat } from '../hooks/useChat'

interface Message {
  id: string
  text: string
  isUser: boolean
  sources?: string[]
  source_urls?: string[]
}

interface AgentData {
  orchestrationResult: any
  subAgentResults: any
  finalAnswer: string | null
  rawAnswer?: string | null  // ✅ 원본 답변 추가
  logs: string[]
}

// 로그 메시지를 사용자 친화적으로 변환
const formatLogMessage = (log: string): string => {
  const logLower = log.toLowerCase()
  
  // 오케스트레이션 관련
  if (logLower.includes('orchestration') && logLower.includes('start')) {
    return '🔍 질문을 분석하는 중...'
  }
  if (logLower.includes('execution plan')) {
    return '📋 답변 계획을 수립하는 중...'
  }
  
  // 문서 검색 관련
  if (logLower.includes('retriev') || logLower.includes('search') || logLower.includes('document')) {
    return '📚 관련 문서를 찾고 있습니다...'
  }
  if (logLower.includes('found') && logLower.includes('document')) {
    return '✅ 관련 자료를 찾았습니다!'
  }
  
  // 에이전트 실행 관련
  if (logLower.includes('agent') && (logLower.includes('start') || logLower.includes('running'))) {
    return '⚙️ 전문 분석을 진행하는 중...'
  }
  if (logLower.includes('sub-agent') || logLower.includes('subagent')) {
    return '🔬 세부 정보를 분석하는 중...'
  }
  
  // 답변 생성 관련
  if (logLower.includes('generat') || logLower.includes('final') || logLower.includes('compos')) {
    return '✍️ 답변을 작성하고 있습니다...'
  }
  if (logLower.includes('complet') || logLower.includes('finish')) {
    return '✨ 답변 준비 완료!'
  }
  
  // RAG 관련
  if (logLower.includes('rag') && logLower.includes('mode')) {
    return '📖 문서 기반 답변을 준비하는 중...'
  }
  
  // 기본값: 원본 로그 반환 (짧게 요약)
  if (log.length > 50) {
    return log.substring(0, 47) + '...'
  }
  return log
}

export default function ChatPage() {
  const navigate = useNavigate()
  const { user, signOut, isAuthenticated } = useAuth()
  const {
    sessions,
    currentSessionId,
    messages: savedMessages,
    createSession,
    saveMessage,
    selectSession,
    startNewChat,
    updateSessionTitle,
  } = useChat()
  
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState(() => `session-${Date.now()}`)
  const [isSideNavOpen, setIsSideNavOpen] = useState(false)
  const [agentData, setAgentData] = useState<AgentData>({
    orchestrationResult: null,
    subAgentResults: null,
    finalAnswer: null,
    rawAnswer: null,
    logs: []
  })
  const [currentLog, setCurrentLog] = useState<string>('') // 현재 진행 상태 로그
  const [searchQuery, setSearchQuery] = useState<string>('') // 채팅 검색어
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const sendingRef = useRef(false) // 중복 전송 방지
  const abortControllerRef = useRef<AbortController | null>(null) // 스트리밍 취소용

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // 새 채팅 시작 핸들러
  const handleNewChat = () => {
    // 진행 중인 요청 취소
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    
    // 모든 상태 초기화
    setMessages([])
    setInput('')
    setIsLoading(false)
    setCurrentLog('')
    setAgentData({
      orchestrationResult: null,
      subAgentResults: null,
      finalAnswer: null,
      rawAnswer: null,
      logs: []
    })
    sendingRef.current = false
    
    // 새 채팅 시작
    startNewChat()
  }

  // 세션 선택 시 메시지 불러오기
  useEffect(() => {
    if (currentSessionId && isAuthenticated) {
      // Supabase에서 불러온 메시지를 Message 형식으로 변환
      const convertedMessages: Message[] = savedMessages.map((msg) => ({
        id: msg.id,
        text: msg.content,
        isUser: msg.role === 'user',
      }))
      setMessages(convertedMessages)
      setSessionId(currentSessionId) // API 호출용 sessionId도 업데이트
    } else if (!currentSessionId) {
      // 새 채팅인 경우
      setMessages([])
      setSessionId(`session-${Date.now()}`)
    }
  }, [currentSessionId, savedMessages, isAuthenticated])

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentLog]) // currentLog 변경시에도 스크롤


  const handleSend = async () => {
    // 중복 전송 방지 (더블 클릭, 빠른 Enter 연타 방지)
    if (!input.trim() || isLoading || sendingRef.current) {
      console.log('🚫 전송 차단:', { 
        hasInput: !!input.trim(), 
        isLoading, 
        alreadySending: sendingRef.current 
      })
      return
    }

    console.log('📤 메시지 전송 시작:', input)
    sendingRef.current = true
    
    const userInput = input
    setInput('')
    setIsLoading(true)

    // 세션 처리: 새 채팅인 경우 세션 생성
    let currentSessionIdToUse = currentSessionId
    if (!currentSessionIdToUse && isAuthenticated) {
      // 새 세션 생성 (제목은 사용자 메시지 앞부분)
      const title = userInput.substring(0, 50)
      const newSessionId = await createSession(title)
      if (newSessionId) {
        currentSessionIdToUse = newSessionId
        setSessionId(newSessionId)
        await selectSession(newSessionId)
      }
    }

    // 사용자 메시지 저장 (로그인한 경우)
    if (isAuthenticated && currentSessionIdToUse) {
      await saveMessage(currentSessionIdToUse, 'user', userInput)
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      text: userInput,
      isUser: true,
    }

    setMessages((prev) => [...prev, userMessage])

    // 로그 초기화
    setAgentData({
      orchestrationResult: null,
      subAgentResults: null,
      finalAnswer: null,
      rawAnswer: null,
      logs: []
    })
    setCurrentLog('🔍 질문을 분석하는 중...')

    // AbortController 생성
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    try {
      await sendMessageStream(
        userInput,
        currentSessionIdToUse || sessionId,
        // 로그 콜백
        (log: string) => {
          // 취소된 경우 콜백 실행 안 함
          if (abortController.signal.aborted) return
          
          setAgentData((prev) => ({
            ...prev,
            logs: [...prev.logs, log]
          }))
          // 메인 채팅 영역에도 현재 로그 표시 (사용자 친화적으로 변환)
          const formattedLog = formatLogMessage(log)
          setCurrentLog(formattedLog)
        },
        // 결과 콜백
        async (response: ChatResponse) => {
          // 취소된 경우 콜백 실행 안 함
          if (abortController.signal.aborted) return
          
          const botMessage: Message = {
            id: (Date.now() + 1).toString(),
            text: response.response,
            isUser: false,
            sources: response.sources,
            source_urls: response.source_urls,
          }

          setMessages((prev) => [...prev, botMessage])

          // 어시스턴트 메시지 저장 (로그인한 경우)
          if (isAuthenticated && currentSessionIdToUse) {
            await saveMessage(currentSessionIdToUse, 'assistant', response.response)
            
            // 첫 메시지인 경우 세션 제목 업데이트
            if (messages.length === 0 && userInput) {
              const title = userInput.substring(0, 50)
              await updateSessionTitle(currentSessionIdToUse, title)
            }
          }

          // Agent 디버그 데이터 업데이트
          setAgentData((prev) => ({
            ...prev,
            orchestrationResult: response.orchestration_result || null,
            subAgentResults: response.sub_agent_results || null,
            finalAnswer: response.response,
            rawAnswer: response.raw_answer || null  // ✅ 원본 답변 추가
          }))
        },
        // 에러 콜백
        (error: string) => {
          // 취소된 경우 에러 메시지 표시 안 함
          if (abortController.signal.aborted) return
          
          const errorMessage: Message = {
            id: (Date.now() + 1).toString(),
            text: error,
            isUser: false,
          }
          setMessages((prev) => [...prev, errorMessage])
        },
        abortController.signal
      )
    } catch (error: any) {
      // AbortError는 무시 (사용자가 새 채팅을 시작한 경우)
      if (error?.name === 'AbortError') {
        console.log('요청이 취소되었습니다.')
        return
      }
      
      console.error('채팅 오류:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: '죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해주세요.',
        isUser: false,
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      // 취소되지 않은 경우에만 상태 초기화
      if (!abortControllerRef.current?.signal.aborted) {
        setIsLoading(false)
        setCurrentLog('')
      }
      sendingRef.current = false
      abortControllerRef.current = null
      console.log('✅ 메시지 전송 완료')
    }
  }



  return (
    <div className="flex h-screen bg-gray-50 relative">
      {/* 사이드 네비게이션 오버레이 */}
      {isSideNavOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 sm:hidden"
          onClick={() => setIsSideNavOpen(false)}
        />
      )}

      {/* 사이드 네비게이션 */}
      <div
        className={`fixed top-0 left-0 h-full w-80 bg-white shadow-xl z-50 transform transition-transform duration-300 ease-in-out ${
          isSideNavOpen ? 'translate-x-0' : '-translate-x-full'
        } sm:translate-x-0 sm:static sm:w-80`}
      >
        <div className="h-full flex flex-col overflow-y-auto">
          {/* 검색 바 (로그인한 경우에만 상단에 표시) */}
          {isAuthenticated && (
            <div className="p-4 sm:p-6 pb-3 sm:pb-4">
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="채팅 검색"
                  className="w-full px-2.5 sm:px-3 py-2 sm:py-2.5 pl-8 sm:pl-10 text-xs sm:text-sm bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <svg
                  className="absolute left-2 sm:left-3 top-1/2 transform -translate-y-1/2 w-3.5 h-3.5 sm:w-4 sm:h-4 text-gray-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-2 sm:right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    <svg className="w-3.5 h-3.5 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
                  </button>
                )}
              </div>
            </div>
          )}

          {/* 사이드 네비 헤더 */}
          <div className="px-4 sm:px-6 pb-3 sm:pb-4">
            <div className="flex items-center justify-between mb-1.5 sm:mb-2">
              <h2 className="text-base sm:text-xl font-bold text-gray-900">내 입시 기록 관리</h2>
              <button
                onClick={() => setIsSideNavOpen(false)}
                className="sm:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <p className="text-xs sm:text-sm text-gray-500">
              입시 기록을 입력하면 더 정확한 답변을 받을 수 있어요
            </p>
          </div>

          {/* 메뉴 항목들 */}
          <div className="flex-1 px-4 sm:px-6 pb-3 sm:pb-4">
            <div className="space-y-0">
              {/* 내 생활기록부 관리 */}
              <button className="w-full flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-3 sm:py-4 hover:bg-gray-50 active:bg-gray-100 transition-colors text-left group">
                <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-full border-2 border-gray-300 flex items-center justify-center flex-shrink-0 group-hover:border-blue-500 transition-colors">
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs sm:text-sm font-medium text-gray-900">내 생활기록부 관리</p>
                  <p className="text-[10px] sm:text-xs text-gray-500 mt-0.5">10초만에 연동하기</p>
                </div>
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {/* 3월 6월 9월 모의고사 성적 입력 */}
              <button className="w-full flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-3 sm:py-4 hover:bg-gray-50 active:bg-gray-100 transition-colors text-left group">
                <div className="w-5 h-5 sm:w-6 sm:h-6 rounded-full border-2 border-gray-300 flex items-center justify-center flex-shrink-0 group-hover:border-blue-500 transition-colors">
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs sm:text-sm font-medium text-gray-900">3월 6월 9월 모의고사 성적 입력</p>
                  <p className="text-[10px] sm:text-xs text-gray-500 mt-0.5">모의고사 성적을 입력해주세요</p>
                </div>
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {/* 내신 성적 입력 */}
              <button className="w-full flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-3 sm:py-4 hover:bg-gray-50 active:bg-gray-100 transition-colors text-left group">
                <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-green-100 flex items-center justify-center flex-shrink-0">
                  <svg className="w-4 h-4 sm:w-5 sm:h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs sm:text-sm font-medium text-gray-900">내신 성적 입력</p>
                  <p className="text-[10px] sm:text-xs text-gray-500 mt-0.5">내신 성적을 입력해주세요</p>
                </div>
                <svg className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {/* 채팅 기억 (로그인한 경우에만 표시) */}
              {isAuthenticated && (
                <button className="w-full flex items-center gap-2 sm:gap-3 px-3 sm:px-4 py-3 sm:py-4 hover:bg-gray-50 active:bg-gray-100 transition-colors text-left group">
                  <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-green-100 flex items-center justify-center flex-shrink-0">
                    <svg className="w-4 h-4 sm:w-5 sm:h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs sm:text-sm font-medium text-gray-900">채팅 기억</p>
                    <p className="text-[10px] sm:text-xs text-gray-500 mt-0.5">자동 기억 사용중</p>
                  </div>
                  <svg className="w-4 h-4 sm:w-5 sm:h-5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              )}
            </div>
          </div>

          {/* 채팅 기록 섹션 (로그인한 경우에만 표시) */}
          {isAuthenticated && (
            <div className="px-4 sm:px-6 pb-4 sm:pb-6 pt-3 sm:pt-4">
              <div className="flex items-center justify-between mb-3 sm:mb-4">
                <h2 className="text-base sm:text-xl font-bold text-gray-900">채팅</h2>
                <button
                  onClick={handleNewChat}
                  className="text-[10px] sm:text-xs text-blue-600 hover:text-blue-700 font-medium"
                >
                  새 채팅
                </button>
              </div>
              
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {(() => {
                  // 검색어로 필터링
                  const filteredSessions = searchQuery
                    ? sessions.filter((session) =>
                        session.title.toLowerCase().includes(searchQuery.toLowerCase())
                      )
                    : sessions

                  if (filteredSessions.length === 0) {
                    return (
                      <p className="text-[10px] sm:text-xs text-gray-500 text-center py-3 sm:py-4">
                        {searchQuery ? '검색 결과가 없습니다' : '채팅 기록이 없습니다'}
                      </p>
                    )
                  }

                  return filteredSessions.map((session) => (
                    <button
                      key={session.id}
                      onClick={() => {
                        selectSession(session.id)
                        setIsSideNavOpen(false)
                      }}
                      className={`w-full text-left px-2.5 sm:px-3 py-1.5 sm:py-2 rounded-lg transition-colors ${
                        currentSessionId === session.id
                          ? 'bg-blue-50 text-blue-900'
                          : 'hover:bg-gray-50 text-gray-900'
                      }`}
                    >
                      <p className="text-[10px] sm:text-xs font-medium truncate">{session.title}</p>
                      <p className="text-[9px] sm:text-[10px] text-gray-500 mt-0.5">
                        {new Date(session.updated_at).toLocaleDateString('ko-KR', {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </p>
                    </button>
                  ))
                })()}
              </div>
            </div>
          )}

          {/* 하단 섹션 */}
          <div className="p-4 sm:p-6 pt-3 sm:pt-4">
            {isAuthenticated ? (
              <div>
                <p className="text-[10px] sm:text-xs text-gray-500 text-center mb-3 sm:mb-4 leading-relaxed">
                  채팅 기록 저장, 공유 및 맞춤 경험을 이용하세요
                </p>
                <button
                  onClick={() => {
                    if (confirm('로그아웃 하시겠습니까?')) {
                      signOut()
                    }
                  }}
                  className="w-full px-3 sm:px-4 py-2 text-xs sm:text-sm text-gray-600 hover:text-gray-900 transition-colors"
                >
                  로그아웃
                </button>
              </div>
            ) : (
              <div>
                <p className="text-[10px] sm:text-xs text-gray-500 text-center mb-3 sm:mb-4 leading-relaxed">
                  채팅 기록 저장, 공유 및 맞춤 경험을 이용하세요
                </p>
                <button
                  onClick={() => navigate('/auth')}
                  className="w-full px-3 sm:px-4 py-2.5 sm:py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 active:bg-blue-800 transition-colors font-medium text-xs sm:text-sm"
                >
                  회원가입 또는 로그인
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 메인 채팅 영역 */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* 헤더 - 모바일과 데스크톱 분리 */}
        <header className="bg-white safe-area-top sticky top-0 z-10">
          {/* 모바일 헤더 */}
          <div className="sm:hidden px-4 py-3 flex justify-between items-center">
            <div className="flex items-center gap-3">
            <button
                onClick={() => setIsSideNavOpen(true)}
                className="p-2 -ml-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg className="w-6 h-6 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
              <img src="/로고.png" alt="UniZ Logo" className="h-8" />
            </div>
            
            {isAuthenticated ? (
              <button
                onClick={() => {
                  if (confirm('로그아웃 하시겠습니까?')) {
                    signOut()
                  }
                }}
                className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 active:text-gray-900 transition-colors"
              >
                로그아웃
              </button>
            ) : (
            <button
                onClick={() => navigate('/auth')}
                className="px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 active:text-blue-700 transition-colors font-medium"
              >
                로그인
            </button>
            )}
          </div>
          
          {/* 데스크톱 헤더 */}
          <div className="hidden sm:flex px-6 py-4 justify-between items-center">
            <div className="flex items-center gap-4">
              <img src="/로고.png" alt="UniZ Logo" className="h-10" />
            </div>
            
            <div className="flex items-center gap-3">
              {user?.name === '김도균' && (
            <button
              onClick={() => navigate('/admin')}
                  className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm font-medium"
            >
              관리자
            </button>
              )}
            
              {isAuthenticated ? (
            <button
              onClick={() => {
                if (confirm('로그아웃 하시겠습니까?')) {
                  signOut()
                    }
                  }}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors font-medium"
                >
                  로그아웃
                </button>
              ) : (
                <button
                  onClick={() => navigate('/auth')}
                  className="px-4 py-2 text-sm text-blue-600 hover:text-blue-700 transition-colors font-medium"
                >
                  로그인
            </button>
              )}
            </div>
          </div>
        </header>

        {/* 채팅 영역 */}
        <div className="flex-1 overflow-y-auto px-4 sm:px-6 py-6 sm:py-8 pb-safe">
          <div className="max-w-3xl mx-auto">
            {messages.length === 0 && (
              <div className="text-center py-12 sm:py-16">
                <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-3 sm:mb-4">
                  {isAuthenticated && user?.name ? (
                    <>안녕하세요 {user.name}님! 👋</>
                  ) : (
                    <>안녕하세요! 👋</>
                  )}
                </h1>
                <p className="text-base sm:text-lg text-gray-600 mb-8 sm:mb-12">
                  무엇을 도와드릴까요?
                </p>
                
                {/* 퀵 액션 카드 - 모바일: 세로, 데스크톱: 그리드 */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 sm:gap-4 max-w-2xl mx-auto">
                  <button
                    onClick={() => setInput('서울대 2028 정시 변경사항 알려줘')}
                    className="bg-white rounded-2xl p-3 sm:p-6 shadow-sm hover:shadow-md active:shadow-md active:scale-[0.98] transition-all text-left group"
                  >
                    <div className="flex items-start gap-3 sm:gap-4">
                      <div className="text-2xl sm:text-4xl flex-shrink-0 group-hover:scale-110 transition-transform">📋</div>
                      <div className="flex-1">
                        <p className="text-sm sm:text-lg font-semibold text-gray-900 mb-0.5 sm:mb-1">대입 정책 조회</p>
                        <p className="text-xs sm:text-sm text-gray-500">최신 입시 정책을 빠르게 확인하세요</p>
                      </div>
                  </div>
                  </button>
                  
                  <button
                    onClick={() => setInput('내신 2.5등급인데 서울대 연세대 고려대 비교해줘')}
                    className="bg-white rounded-2xl p-3 sm:p-6 shadow-sm hover:shadow-md active:shadow-md active:scale-[0.98] transition-all text-left group"
                  >
                    <div className="flex items-start gap-3 sm:gap-4">
                      <div className="text-2xl sm:text-4xl flex-shrink-0 group-hover:scale-110 transition-transform">🎓</div>
                      <div className="flex-1">
                        <p className="text-sm sm:text-lg font-semibold text-gray-900 mb-0.5 sm:mb-1">대학별 입결 비교</p>
                        <p className="text-xs sm:text-sm text-gray-500">내 성적으로 갈 수 있는 대학을 비교 분석</p>
                      </div>
                  </div>
                  </button>
                  
                  <button
                    onClick={() => setInput('백분위 95%면 어느 대학 갈 수 있어?')}
                    className="bg-white rounded-2xl p-3 sm:p-6 shadow-sm hover:shadow-md active:shadow-md active:scale-[0.98] transition-all text-left group"
                  >
                    <div className="flex items-start gap-3 sm:gap-4">
                      <div className="text-2xl sm:text-4xl flex-shrink-0 group-hover:scale-110 transition-transform">📊</div>
                      <div className="flex-1">
                        <p className="text-sm sm:text-lg font-semibold text-gray-900 mb-0.5 sm:mb-1">합격 가능성 분석</p>
                        <p className="text-xs sm:text-sm text-gray-500">정확한 데이터 기반으로 합격 가능성 예측</p>
                      </div>
                  </div>
                  </button>
                  
                  <button
                    onClick={() => setInput('수능까지 3개월 남았는데 공부 계획 세워줘')}
                    className="bg-white rounded-2xl p-3 sm:p-6 shadow-sm hover:shadow-md active:shadow-md active:scale-[0.98] transition-all text-left group"
                  >
                    <div className="flex items-start gap-3 sm:gap-4">
                      <div className="text-2xl sm:text-4xl flex-shrink-0 group-hover:scale-110 transition-transform">📚</div>
                      <div className="flex-1">
                        <p className="text-sm sm:text-lg font-semibold text-gray-900 mb-0.5 sm:mb-1">맞춤형 공부 계획</p>
                        <p className="text-xs sm:text-sm text-gray-500">나에게 딱 맞는 효율적인 학습 전략 수립</p>
                      </div>
                  </div>
                  </button>
                </div>
              </div>
            )}

            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                message={msg.text}
                isUser={msg.isUser}
                sources={msg.sources}
                source_urls={msg.source_urls}
              />
            ))}

            {isLoading && (
              <div className="flex justify-start mb-4">
                <ThinkingProcess logs={agentData.logs} />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* 입력 영역 - 고정 */}
        <div className="bg-white pb-safe safe-area-bottom sticky bottom-0">
          <div className="px-4 sm:px-6 py-3 sm:py-4">
            <div className="max-w-3xl mx-auto flex items-end gap-2">
              {/* 입력 필드 */}
              <div className="flex-1 relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSend()
                    }
                  }}
                  placeholder="유니로드에게 무엇이든 물어보세요"
              disabled={isLoading}
                  className="w-full px-4 py-3 text-base bg-gray-50 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 min-h-[48px] placeholder:text-gray-400"
            />
              </div>
              
              {/* 전송 버튼 */}
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
                className="flex-shrink-0 w-11 h-11 sm:w-12 sm:h-12 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
                <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
            </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
