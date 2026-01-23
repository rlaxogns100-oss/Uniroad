import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { sendMessageStream, ChatResponse } from '../api/client'
import ChatMessage from '../components/ChatMessage'
import ThinkingProcess from '../components/ThinkingProcess'
import AgentPanel from '../components/AgentPanel'
import AuthModal from '../components/AuthModal'
import { useAuth } from '../contexts/AuthContext'
import { useChat } from '../hooks/useChat'

interface UsedChunk {
  id: string
  content: string
  title: string
  source: string
  file_url: string
  metadata?: Record<string, any>
}

interface Message {
  id: string
  text: string
  isUser: boolean
  sources?: string[]
  source_urls?: string[]
  used_chunks?: UsedChunk[]
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
  // Supabase 세션 ID만 사용 (로컬 세션 ID 생성 제거)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isSideNavOpen, setIsSideNavOpen] = useState(() => {
    // 데스크톱에서는 기본적으로 열림, 모바일에서는 닫힘
    return window.innerWidth >= 640
  })
  const [isRecordDropdownOpen, setIsRecordDropdownOpen] = useState(false)
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState(false)
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false)
  const [isOpenChatModalOpen, setIsOpenChatModalOpen] = useState(false)
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
  const isAbortedRef = useRef(false) // 사용자가 중단했는지 추적

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // 화면 크기 변경 시 사이드바 상태 조정
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 640) {
        setIsSideNavOpen(true)
      } else {
        setIsSideNavOpen(false)
      }
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  // 새 채팅 시작 핸들러
  const handleNewChat = () => {
    // 진행 중인 요청 취소
    if (abortControllerRef.current) {
      isAbortedRef.current = true
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
  const prevSessionIdRef = useRef<string | null>(null)
  useEffect(() => {
    // 세션이 변경되었을 때
    if (currentSessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = currentSessionId
      
      if (currentSessionId && isAuthenticated) {
        // API 호출용 sessionId 업데이트 (Supabase 세션 ID 사용)
        setSessionId(currentSessionId)
        // 메시지는 loadMessages가 완료되면 savedMessages에 반영되고, 아래 useEffect에서 처리됨
      } else if (!currentSessionId) {
        // 새 채팅인 경우 - 세션 ID는 null로 유지 (새 세션 생성 시 설정됨)
        setMessages([])
        setSessionId(null)
      }
    }
  }, [currentSessionId, isAuthenticated])
  
  // savedMessages가 업데이트되면 현재 세션의 메시지로 변환
  useEffect(() => {
    if (currentSessionId && savedMessages.length >= 0) {
      // savedMessages가 현재 세션의 메시지인지 확인 (loadMessages가 올바른 세션 ID로 호출되었으므로)
      const convertedMessages: Message[] = savedMessages.map((msg) => ({
        id: msg.id,
        text: msg.content,
        isUser: msg.role === 'user',
      }))
      setMessages(convertedMessages)
    }
  }, [savedMessages, currentSessionId])

  useEffect(() => {
    scrollToBottom()
  }, [messages, currentLog]) // currentLog 변경시에도 스크롤

  const toggleAgentPanel = () => {
    setIsAgentPanelOpen(!isAgentPanelOpen)
  }

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

    // 세션 처리: 새 채팅인 경우 Supabase 세션 생성
    let currentSessionIdToUse = currentSessionId
    if (!currentSessionIdToUse && isAuthenticated) {
      // 새 세션 생성 (제목은 사용자 메시지 앞부분)
      const title = userInput.substring(0, 50)
      const newSessionId = await createSession(title)
      if (newSessionId) {
        currentSessionIdToUse = newSessionId
        setSessionId(newSessionId)  // Supabase 세션 ID 사용
        await selectSession(newSessionId)
      } else {
        // 세션 생성 실패 시 요청 중단
        setIsLoading(false)
        sendingRef.current = false
        return
      }
    }
    
    // 세션 ID가 없으면 요청 중단 (인증된 사용자는 반드시 세션이 있어야 함)
    if (isAuthenticated && !currentSessionIdToUse) {
      console.error('세션 ID가 없습니다')
      setIsLoading(false)
      sendingRef.current = false
      return
    }
    
    // 인증되지 않은 사용자도 기본 세션 ID 사용 (하지만 Supabase에 저장 안 됨)
    if (!isAuthenticated) {
      currentSessionIdToUse = currentSessionIdToUse || 'default'
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      text: userInput,
      isUser: true,
    }

    // 사용자 메시지를 먼저 UI에 추가
    setMessages((prev) => {
      // 중복 방지: 같은 내용의 메시지가 이미 있으면 추가하지 않음
      const isDuplicate = prev.some(
        (msg) => msg.isUser && msg.text === userInput && 
        Date.now() - parseInt(msg.id) < 1000 // 1초 이내에 같은 메시지가 있으면 중복으로 간주
      )
      if (isDuplicate) {
        console.log('🚫 중복 메시지 차단:', userInput)
        return prev
      }
      return [...prev, userMessage]
    })

    // 사용자 메시지 저장 (로그인한 경우) - UI 업데이트 후
    if (isAuthenticated && currentSessionIdToUse) {
      await saveMessage(currentSessionIdToUse, 'user', userInput)
    }

    // 중단 상태 초기화
    isAbortedRef.current = false
    
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
        async (response: ChatResponse & { is_streaming?: boolean }) => {
          // 취소된 경우 콜백 실행 안 함
          if (abortController.signal.aborted) return
          
          // 스트리밍 답변 청크인 경우 기존 메시지에 누적
          if (response.is_streaming) {
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1]
              // 마지막 메시지가 사용자 메시지가 아니고, 아직 완성되지 않은 답변인 경우
              if (lastMessage && !lastMessage.isUser && lastMessage.id.startsWith('streaming-')) {
                // 기존 메시지에 청크 추가
                return prev.map((msg, idx) => 
                  idx === prev.length - 1 
                    ? { ...msg, text: msg.text + response.response }
                    : msg
                )
              } else {
                // 새로운 스트리밍 메시지 생성
                const streamingMessage: Message = {
                  id: `streaming-${Date.now()}`,
                  text: response.response,
                  isUser: false,
                  sources: [],
                  source_urls: [],
                  used_chunks: [],
                }
                return [...prev, streamingMessage]
              }
            })
            return  // 스트리밍 청크는 여기서 종료
          }
          
          // 완성된 답변인 경우
          const botMessage: Message = {
            id: (Date.now() + 1).toString(),
            text: response.response,
            isUser: false,
            sources: response.sources || [],
            source_urls: response.source_urls || [],
            used_chunks: response.used_chunks || [],
          }

          // 스트리밍 메시지가 있으면 완성된 메시지로 교체
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1]
            if (lastMessage && !lastMessage.isUser && lastMessage.id.startsWith('streaming-')) {
              // 스트리밍 메시지를 완성된 메시지로 교체 (소스 정보 포함)
              return prev.map((msg, idx) => 
                idx === prev.length - 1 
                  ? { 
                      ...botMessage, 
                      id: msg.id.replace('streaming-', ''),  // streaming- 제거
                      text: response.response  // 최종 답변으로 교체
                    }
                  : msg
              )
            }
            
            // 중복 방지: 같은 내용의 메시지가 이미 있으면 추가하지 않음
            const isDuplicate = prev.some(
              (msg) => !msg.isUser && msg.text === response.response && 
              Date.now() - parseInt(msg.id) < 2000 // 2초 이내에 같은 메시지가 있으면 중복으로 간주
            )
            if (isDuplicate) {
              console.log('🚫 중복 답변 차단:', response.response.substring(0, 50))
              return prev
            }
            return [...prev, botMessage]
          })

          // 어시스턴트 메시지 저장 (로그인한 경우)
          if (isAuthenticated && currentSessionIdToUse) {
            await saveMessage(currentSessionIdToUse, 'assistant', response.response)
            
            // 첫 메시지인 경우 세션 제목 업데이트
            setMessages((prev) => {
              if (prev.filter(m => m.isUser).length === 1 && userInput) {
                const title = userInput.substring(0, 50)
                updateSessionTitle(currentSessionIdToUse, title)
              }
              return prev
            })
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
      // 중단된 경우 메시지에 중단 표시 추가 (버튼 클릭 시 이미 추가되었을 수 있으므로 중복 방지)
      if (isAbortedRef.current) {
        setMessages((prev) => {
          const lastMsg = prev[prev.length - 1]
          // 이미 중단 메시지가 추가되었는지 확인
          if (lastMsg && lastMsg.text.includes('중지되었습니다')) {
            return prev // 이미 추가됨
          }
          // 스트리밍 메시지가 있으면 업데이트
          if (lastMsg && !lastMsg.isUser && lastMsg.id.startsWith('streaming-')) {
            return prev.map((msg, idx) =>
              idx === prev.length - 1
                ? { ...msg, text: msg.text + '\n\n✨ 대답이 중지되었습니다.' }
                : msg
            )
          }
          return prev
        })
      }
      
      setIsLoading(false)
      setCurrentLog('')
      sendingRef.current = false
      abortControllerRef.current = null
      isAbortedRef.current = false // 초기화
      console.log('✅ 메시지 전송 완료')
    }
  }



  return (
    <div className="flex h-screen">
      {/* Agent 디버그 패널 (좌측) */}
      <AgentPanel
        orchestrationResult={agentData.orchestrationResult}
        subAgentResults={agentData.subAgentResults}
        finalAnswer={agentData.finalAnswer}
        rawAnswer={agentData.rawAnswer}
        logs={agentData.logs}
        isOpen={isAgentPanelOpen}
        onClose={() => setIsAgentPanelOpen(false)}
      />

      <div className={`flex h-screen bg-gray-50 relative transition-all duration-300 ${
        isAgentPanelOpen ? 'w-1/2' : 'w-full'
      }`}>
        {/* 사이드 네비게이션 */}
        <div
          className={`fixed top-0 left-0 h-full w-80 bg-white shadow-xl z-50 transform transition-transform duration-300 ease-in-out ${
            isSideNavOpen ? 'translate-x-0' : '-translate-x-full'
          } sm:fixed sm:z-40`}
        >
        <div className="h-full flex flex-col">
          {/* 우측 상단 닫기 버튼 */}
          <div className="absolute top-4 right-4 z-10">
            <button
              onClick={() => setIsSideNavOpen(false)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          </div>

          {/* 1. 공지사항 */}
          <div className="px-4 sm:px-6 pt-16 pb-2">
            <button className="w-full flex items-center gap-3 px-4 py-3 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors text-left">
              <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                </svg>
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-900">공지사항</p>
              </div>
            </button>
          </div>

          {/* 2. 오픈채팅방 */}
          <div className="px-4 sm:px-6 pb-2">
            <button 
              onClick={() => setIsOpenChatModalOpen(true)}
              className="w-full flex items-center gap-3 px-4 py-3 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors text-left"
            >
              <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
                </svg>
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-900 mb-0.5">오픈채팅방</p>
                <p className="text-[10px] text-gray-600 leading-snug">
                  사용 후기를 들려주세요.<br />
                  서울대 개발자의 무료 입시상담!
                </p>
              </div>
            </button>
          </div>

          {/* 3. 내 입시 기록 관리 (드롭다운) */}
          <div className="px-4 sm:px-6 pb-2">
            <button 
              onClick={() => setIsRecordDropdownOpen(!isRecordDropdownOpen)}
              className="w-full flex items-center gap-3 px-4 py-3 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors text-left"
            >
              <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center flex-shrink-0">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-900">내 입시 기록 관리</p>
              </div>
              <svg 
                className={`w-5 h-5 text-gray-600 transition-transform ${isRecordDropdownOpen ? 'rotate-180' : ''}`}
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            
            {/* 드롭다운 메뉴 */}
            {isRecordDropdownOpen && (
              <div className="mt-2 ml-4 space-y-1 border-l-2 border-blue-200 pl-4">
                {/* 내 생활기록부 관리 */}
                <button className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-gray-50 rounded-lg transition-colors text-left group">
                  <div className="w-5 h-5 rounded-full border-2 border-gray-300 flex items-center justify-center flex-shrink-0 group-hover:border-blue-500 transition-colors">
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-900">내 생활기록부 관리</p>
                    <p className="text-[10px] text-gray-500">10초만에 연동하기</p>
                  </div>
                </button>

                {/* 3월 6월 9월 모의고사 성적 입력 */}
                <button className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-gray-50 rounded-lg transition-colors text-left group">
                  <div className="w-5 h-5 rounded-full border-2 border-gray-300 flex items-center justify-center flex-shrink-0 group-hover:border-blue-500 transition-colors">
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-900">3월 6월 9월 모의고사 성적 입력</p>
                    <p className="text-[10px] text-gray-500">모의고사 성적을 입력해주세요</p>
                  </div>
                </button>

                {/* 내신 성적 입력 */}
                <button className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-gray-50 rounded-lg transition-colors text-left group">
                  <div className="w-5 h-5 rounded-full border-2 border-gray-300 flex items-center justify-center flex-shrink-0 group-hover:border-blue-500 transition-colors">
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-900">내신 성적 입력</p>
                    <p className="text-[10px] text-gray-500">내신 성적을 입력해주세요</p>
                  </div>
                </button>
              </div>
            )}
          </div>

          {/* 4. 채팅 검색 (로그인한 경우에만 표시) */}
          {isAuthenticated && (
            <div className="px-4 sm:px-6 pb-3 border-t border-gray-100 pt-4">
              <div className="relative">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="채팅 검색"
                  className="w-full px-3 py-2.5 pl-10 text-sm bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <svg
                  className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400"
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
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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

          {/* 5. 채팅 내역 (로그인한 경우에만 표시) */}
          {isAuthenticated && (
            <div className="flex-1 px-4 sm:px-6 pb-4 overflow-y-auto custom-scrollbar">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-bold text-gray-900">채팅 내역</h2>
                <button
                  onClick={handleNewChat}
                  className="text-xs text-blue-600 hover:text-blue-700 font-medium"
                >
                  새 채팅
                </button>
              </div>
              
              <div className="space-y-1">
                {(() => {
                  // 검색어로 필터링
                  const filteredSessions = searchQuery
                    ? sessions.filter((session) =>
                        session.title.toLowerCase().includes(searchQuery.toLowerCase())
                      )
                    : sessions

                  if (filteredSessions.length === 0) {
                    return (
                      <p className="text-xs text-gray-500 text-center py-4">
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
                      className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                        currentSessionId === session.id
                          ? 'bg-blue-50 text-blue-900'
                          : 'hover:bg-gray-50 text-gray-900'
                      }`}
                    >
                      <p className="text-xs font-medium truncate">{session.title}</p>
                      <p className="text-[10px] text-gray-500 mt-0.5">
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
                  onClick={() => setIsAuthModalOpen(true)}
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
      <div className={`flex flex-col flex-1 min-w-0 transition-all duration-300 ${
        isSideNavOpen ? 'sm:ml-80' : 'sm:ml-0'
      }`}>
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
                onClick={() => setIsAuthModalOpen(true)}
                className="px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 active:text-blue-700 transition-colors font-medium"
              >
                로그인
            </button>
            )}
          </div>
          
          {/* 데스크톱 헤더 */}
          <div className="hidden sm:flex px-6 py-4 justify-between items-center">
            <div className="flex items-center gap-4">
              {/* 사이드바 토글 버튼 - 사이드바가 닫혔을 때만 표시 */}
              {!isSideNavOpen && (
                <button
                  onClick={() => setIsSideNavOpen(true)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  title="사이드바 열기"
                >
                  <svg className="w-6 h-6 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              )}
              <img src="/로고.png" alt="UniZ Logo" className="h-10" />
            </div>
            
            <div className="flex items-center gap-3">
              {user?.name === '김도균' && (
                <>
                  <button
                    onClick={toggleAgentPanel}
                    className={`px-4 py-2 rounded-lg transition-colors flex items-center gap-2 text-sm font-medium ${
                      isAgentPanelOpen
                        ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                        : 'bg-slate-700 text-white hover:bg-slate-600'
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                    </svg>
                    Agent
                  </button>
                  <button
                    onClick={() => navigate('/admin')}
                    className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm font-medium"
                  >
                    관리자
                  </button>
                </>
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
                  onClick={() => setIsAuthModalOpen(true)}
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
                used_chunks={msg.used_chunks}
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
              
              {/* 전송/정지 버튼 */}
            <button
              onClick={() => {
                if (isLoading) {
                  // 응답 중단
                  if (abortControllerRef.current) {
                    isAbortedRef.current = true
                    abortControllerRef.current.abort()
                    
                    // 즉시 중단 메시지 표시
                    setMessages((prev) => {
                      const lastMsg = prev[prev.length - 1]
                      if (lastMsg && !lastMsg.isUser) {
                        // 스트리밍 메시지가 있으면 업데이트
                        if (lastMsg.id.startsWith('streaming-')) {
                          return prev.map((msg, idx) =>
                            idx === prev.length - 1
                              ? { ...msg, text: msg.text + '\n\n✨ 대답이 중지되었습니다.' }
                              : msg
                          )
                        } else {
                          // 완료된 메시지면 새 메시지 추가
                          const abortMessage: Message = {
                            id: Date.now().toString(),
                            text: '✨ 대답이 중지되었습니다.',
                            isUser: false,
                          }
                          return [...prev, abortMessage]
                        }
                      } else {
                        // 마지막 메시지가 사용자 메시지이거나 없으면 새 메시지 추가
                        const abortMessage: Message = {
                          id: Date.now().toString(),
                          text: '✨ 대답이 중지되었습니다.',
                          isUser: false,
                        }
                        return [...prev, abortMessage]
                      }
                    })
                    
                    setIsLoading(false)
                    setCurrentLog('')
                    abortControllerRef.current = null
                  }
                } else {
                  // 메시지 전송
                  handleSend()
                }
              }}
              disabled={!isLoading && !input.trim()}
                className="flex-shrink-0 w-11 h-11 sm:w-12 sm:h-12 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
                {isLoading ? (
                  // 정지 아이콘
                  <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="currentColor" viewBox="0 0 24 24">
                    <rect x="7" y="7" width="10" height="10" rx="1" />
                  </svg>
                ) : (
                  // 전송 아이콘
                  <svg className="w-5 h-5 sm:w-6 sm:h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                )}
            </button>
            </div>
          </div>
        </div>
      </div>

      {/* 로그인 모달 */}
      <AuthModal 
        isOpen={isAuthModalOpen} 
        onClose={() => setIsAuthModalOpen(false)} 
      />

      {/* 오픈채팅방 모달 */}
      {isOpenChatModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full animate-slideUp">
            {/* 헤더 */}
            <div className="relative px-6 pt-6 pb-4 border-b border-gray-100">
              <button
                onClick={() => setIsOpenChatModalOpen(false)}
                className="absolute top-4 right-4 p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <div className="text-center">
                <img src="/로고.png" alt="UniZ Logo" className="h-12 mx-auto mb-3" />
                <h2 className="text-xl font-bold text-gray-900">유니로드와 소통하기</h2>
              </div>
            </div>

            {/* 본문 */}
            <div className="px-6 py-6">
              <div className="mb-6 text-center">
                <p className="text-base font-semibold text-gray-900 mb-2">
                  서울대 21학번 선배가 직접 만드는 입시 AI
                </p>
                <p className="text-sm text-gray-600 leading-relaxed">
                  입시의 어려움을 누구보다 잘 알기에, 수험생 여러분께 진짜 도움이 되는 AI를 직접 만들고 있습니다.
                  <br /><br />
                  편하게 사용해 보시고 솔직한 후기를 들려주세요. 서비스 이용 관련 문의는 물론, 막막한 입시 고민 상담도 언제든 환영합니다.
                </p>
              </div>

              {/* 버튼 */}
              <div className="space-y-3">
                <a
                  href="https://open.kakao.com/o/sTxWEbbi"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl hover:from-blue-600 hover:to-blue-700 active:from-blue-700 active:to-blue-800 transition-all shadow-md hover:shadow-lg font-medium text-center"
                >
                  <span className="mr-2">👨‍💻</span>
                  개발자와 1:1 대화하기
                </a>
                <a
                  href="https://open.kakao.com/o/ggA6GPci"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full px-4 py-3 bg-gradient-to-r from-green-500 to-green-600 text-white rounded-xl hover:from-green-600 hover:to-green-700 active:from-green-700 active:to-green-800 transition-all shadow-md hover:shadow-lg font-medium text-center"
                >
                  <span className="mr-2">💬</span>
                  유니로드 공식 소통방 참여
                </a>
              </div>

              <p className="mt-4 text-xs text-center text-gray-500">
                여러분의 소중한 의견으로 유니로드는 더 똑똑해집니다 ✨
              </p>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}
