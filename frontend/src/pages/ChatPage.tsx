import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { sendMessageStream, sendMessageStreamWithImage, ChatResponse, resetSession } from '../api/client'
import ChatMessage from '../components/ChatMessage'
import ThinkingProcess from '../components/ThinkingProcess'
import AgentPanel from '../components/AgentPanel'
import AuthModal from '../components/AuthModal'
import RollingPlaceholder from '../components/RollingPlaceholder'
import ProfileForm from '../components/ProfileForm'
import { useAuth } from '../contexts/AuthContext'
import { useChat } from '../hooks/useChat'
import { FrontendTimingLogger } from '../utils/timingLogger'
import { addLog } from '../utils/adminLogger'

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
  isStreaming?: boolean  // 스트리밍 중인지 여부
  imageUrl?: string  // 이미지 첨부 시 미리보기 URL
  showLoginPrompt?: boolean  // 로그인 유도 메시지 표시 여부
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

// 공지사항 인터페이스
interface Announcement {
  id: string
  title: string
  content: string
  author_email: string
  is_pinned: boolean
  created_at: string
  updated_at: string
}

export default function ChatPage() {
  const navigate = useNavigate()
  const { user, signOut, isAuthenticated, accessToken } = useAuth()
  const {
    sessions,
    currentSessionId,
    messages: savedMessages,
    createSession,
    selectSession,
    startNewChat,
    updateSessionTitle,
    deleteSession,
  } = useChat()
  
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState(() => `session-${Date.now()}`)
  const [isSideNavOpen, setIsSideNavOpen] = useState(() => {
    // 데스크톱에서는 기본적으로 열림, 모바일에서는 닫힘
    return window.innerWidth >= 640
  })
  const [isRecordDropdownOpen, setIsRecordDropdownOpen] = useState(false)
  const [isAnnouncementDropdownOpen, setIsAnnouncementDropdownOpen] = useState(false)
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState(false)
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false)
  const [authModalMessage, setAuthModalMessage] = useState<{ title: string; description: string } | undefined>(undefined)
  const [isOpenChatModalOpen, setIsOpenChatModalOpen] = useState(false)
  const [isAnnouncementModalOpen, setIsAnnouncementModalOpen] = useState(false)
  const [isProfileFormOpen, setIsProfileFormOpen] = useState(false)
  const [showProfileGuide, setShowProfileGuide] = useState(false)
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [selectedAnnouncement, setSelectedAnnouncement] = useState<Announcement | null>(null)
  const [isAdmin, setIsAdmin] = useState(false)
  const [announcementForm, setAnnouncementForm] = useState({ title: '', content: '', is_pinned: false })
  const [editingAnnouncementId, setEditingAnnouncementId] = useState<string | null>(null)
  const [agentData, setAgentData] = useState<AgentData>({
    orchestrationResult: null,
    subAgentResults: null,
    finalAnswer: null,
    rawAnswer: null,
    logs: []
  })
  const [currentLog, setCurrentLog] = useState<string>('') // 현재 진행 상태 로그
  const [searchQuery, setSearchQuery] = useState<string>('') // 채팅 검색어
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false) // 검색창 열림 상태
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null) // 카테고리 선택 상태
  
  // 관리자 전용 테스트 설정
  const [testRunCount, setTestRunCount] = useState<number>(1) // 시행 횟수
  const [testRunMode, setTestRunMode] = useState<'sequential' | 'parallel'>('sequential') // 순차/병렬
  const [isTestSettingsOpen, setIsTestSettingsOpen] = useState(false) // 설정 패널 열림 상태
  
  // 이미지 업로드 관련
  const [selectedImage, setSelectedImage] = useState<File | null>(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null)
  const [isUploadMenuOpen, setIsUploadMenuOpen] = useState(false) // 업로드 메뉴 열림 상태
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const sendingRef = useRef(false) // 중복 전송 방지
  const abortControllerRef = useRef<AbortController | null>(null) // 스트리밍 취소용
  const searchContainerRef = useRef<HTMLDivElement>(null) // 검색창 외부 클릭 감지용
  const imageInputRef = useRef<HTMLInputElement>(null) // 이미지 파일 input ref
  const uploadMenuRef = useRef<HTMLDivElement>(null) // 업로드 메뉴 ref

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // 공지사항 목록 가져오기
  useEffect(() => {
    fetchAnnouncements()
    if (isAuthenticated) {
      checkAdminStatus()
    }
  }, [isAuthenticated])

  // 모바일 화면 복귀 시 채팅 상태 유지 (sessionStorage 활용)
  useEffect(() => {
    // 메시지가 있으면 sessionStorage에 저장
    if (messages.length > 0) {
      sessionStorage.setItem('uniroad_chat_messages', JSON.stringify(messages))
      sessionStorage.setItem('uniroad_chat_session_id', sessionId)
    }
  }, [messages, sessionId])

  // 초기 로드 시 sessionStorage에서 메시지 복구 (비로그인 또는 새로고침 시)
  useEffect(() => {
    const savedChatMessages = sessionStorage.getItem('uniroad_chat_messages')
    const savedSessionId = sessionStorage.getItem('uniroad_chat_session_id')

    if (savedChatMessages && messages.length === 0 && !currentSessionId) {
      try {
        const parsed = JSON.parse(savedChatMessages)
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed)
          if (savedSessionId) {
            setSessionId(savedSessionId)
          }
        }
      } catch (e) {
        console.error('채팅 메시지 복구 실패:', e)
      }
    }
  }, [])

  // savedMessages가 변경되면 로컬 messages 상태에 동기화
  useEffect(() => {
    console.log('🔄 [ChatPage] savedMessages 변경 감지:', {
      savedMessagesLength: savedMessages?.length,
      currentSessionId,
      savedMessages
    })
    
    if (savedMessages && savedMessages.length > 0) {
      // 메시지가 있을 때만 변환
      const convertedMessages: Message[] = savedMessages.map(msg => ({
        id: msg.id,
        text: msg.content,
        isUser: msg.role === 'user',
        sources: msg.sources,
        source_urls: msg.source_urls,
      }))
      console.log('✅ [ChatPage] 메시지 변환 완료:', convertedMessages.length, '개')
      setMessages(convertedMessages)
    } else if (savedMessages && savedMessages.length === 0 && currentSessionId && !isStreamingRef.current) {
      // 세션이 선택되었지만 메시지가 없는 경우 (새 세션)
      // 단, 스트리밍 중이 아닐 때만 (메시지 전송 중에는 로컬 메시지 유지)
      console.log('🆕 [ChatPage] 빈 세션으로 설정')
      setMessages([])
    } else {
      console.log('⚠️ [ChatPage] 조건 불일치:', { 
        hasSavedMessages: !!savedMessages, 
        length: savedMessages?.length, 
        hasSessionId: !!currentSessionId,
        isStreaming: isStreamingRef.current
      })
    }
  }, [savedMessages, currentSessionId])

  const fetchAnnouncements = async () => {
    try {
      const response = await fetch('/api/announcements/')
      if (response.ok) {
        const data = await response.json()
        setAnnouncements(data)
      }
    } catch (error) {
      console.error('공지사항 로드 실패:', error)
    }
  }

  const checkAdminStatus = async () => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      const response = await fetch('/api/announcements/check-admin/me', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (response.ok) {
        const data = await response.json()
        setIsAdmin(data.is_admin)
      }
    } catch (error) {
      console.error('관리자 권한 확인 실패:', error)
    }
  }

  const handleCreateAnnouncement = async () => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      const response = await fetch('/api/announcements/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(announcementForm)
      })

      if (response.ok) {
        await fetchAnnouncements()
        setIsAnnouncementModalOpen(false)
        setAnnouncementForm({ title: '', content: '', is_pinned: false })
        alert('공지사항이 등록되었습니다.')
      }
    } catch (error) {
      console.error('공지사항 생성 실패:', error)
      alert('공지사항 생성에 실패했습니다.')
    }
  }

  const handleUpdateAnnouncement = async () => {
    if (!editingAnnouncementId) return

    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      const response = await fetch(`/api/announcements/${editingAnnouncementId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(announcementForm)
      })

      if (response.ok) {
        await fetchAnnouncements()
        setIsAnnouncementModalOpen(false)
        setAnnouncementForm({ title: '', content: '', is_pinned: false })
        setEditingAnnouncementId(null)
        alert('공지사항이 수정되었습니다.')
      }
    } catch (error) {
      console.error('공지사항 수정 실패:', error)
      alert('공지사항 수정에 실패했습니다.')
    }
  }

  const handleDeleteAnnouncement = async (id: string) => {
    if (!confirm('정말 삭제하시겠습니까?')) return

    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      const response = await fetch(`/api/announcements/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      })

      if (response.ok) {
        await fetchAnnouncements()
        alert('공지사항이 삭제되었습니다.')
      }
    } catch (error) {
      console.error('공지사항 삭제 실패:', error)
      alert('공지사항 삭제에 실패했습니다.')
    }
  }

  const openEditModal = (announcement: Announcement) => {
    setEditingAnnouncementId(announcement.id)
    setAnnouncementForm({
      title: announcement.title,
      content: announcement.content,
      is_pinned: announcement.is_pinned
    })
    setIsAnnouncementModalOpen(true)
  }

  const openCreateModal = () => {
    setEditingAnnouncementId(null)
    setAnnouncementForm({ title: '', content: '', is_pinned: false })
    setIsAnnouncementModalOpen(true)
  }

  // 초기 화면 크기에 따라 사이드바 상태 설정 (한 번만)
  useEffect(() => {
    if (window.innerWidth >= 640) {
      setIsSideNavOpen(true)
    }
  }, [])

  // 검색창 외부 클릭 감지
  useEffect(() => {
    if (!isSearchOpen) return

    const handleClickOutside = (event: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target as Node)) {
        setIsSearchOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isSearchOpen])

  // 업로드 메뉴 외부 클릭 감지
  useEffect(() => {
    if (!isUploadMenuOpen) return

    const handleClickOutside = (event: MouseEvent) => {
      if (uploadMenuRef.current && !uploadMenuRef.current.contains(event.target as Node)) {
        setIsUploadMenuOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isUploadMenuOpen])

  // 새 채팅 시작 핸들러
  const handleNewChat = async () => {
    // 진행 중인 요청 취소
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    
    // 백엔드 메모리 히스토리 초기화
    if (currentSessionId) {
      try {
        await resetSession(currentSessionId)
      } catch (e) {
        console.log('세션 리셋 실패 (무시):', e)
      }
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
    
    // 이미지 상태 초기화
    setSelectedImage(null)
    setImagePreviewUrl(null)
  }

  // 이미지 선택 핸들러
  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    // 파일 타입 검증
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
    if (!allowedTypes.includes(file.type)) {
      alert('지원하지 않는 이미지 형식입니다. (JPEG, PNG, GIF, WebP만 가능)')
      return
    }
    
    // 파일 크기 검증 (10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('이미지 크기는 10MB를 초과할 수 없습니다.')
      return
    }
    
    // 이미지 미리보기 URL 생성
    const previewUrl = URL.createObjectURL(file)
    setSelectedImage(file)
    setImagePreviewUrl(previewUrl)
    
    // input 초기화 (같은 파일 다시 선택 가능하도록)
    e.target.value = ''
  }
  
  // 이미지 선택 취소
  const handleImageRemove = () => {
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl)
    }
    setSelectedImage(null)
    setImagePreviewUrl(null)
  }

  // 세션 선택 시 메시지 불러오기
  const prevSessionIdRef = useRef<string | null>(null)
  const isStreamingRef = useRef(false) // 스트리밍 중인지 추적
  
  useEffect(() => {
    // 세션이 변경되었을 때
    if (currentSessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = currentSessionId
      
      if (currentSessionId && isAuthenticated) {
        // API 호출용 sessionId 업데이트
        setSessionId(currentSessionId)
        // 메시지는 loadMessages가 완료되면 savedMessages에 반영되고, 아래 useEffect에서 처리됨
      } else if (!currentSessionId) {
        // 새 채팅인 경우
        setMessages([])
        setSessionId(`session-${Date.now()}`)
      }
    }
  }, [currentSessionId, isAuthenticated])
  
  // savedMessages가 업데이트되면 현재 세션의 메시지로 변환
  // 단, 스트리밍 중이 아닐 때만 (로컬 메시지를 보호)
  useEffect(() => {
    if (currentSessionId && savedMessages.length >= 0 && !isStreamingRef.current) {
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

  // 재생성 함수: 이전 질문/답변 제거 후 다시 질문
  const handleRegenerate = (aiMessageId: string, userQuery: string) => {
    // messages에서 해당 AI 메시지의 index 찾기
    const aiIndex = messages.findIndex(m => m.id === aiMessageId)
    if (aiIndex === -1) return
    
    // 직전 사용자 메시지 찾기
    let userIndex = -1
    for (let i = aiIndex - 1; i >= 0; i--) {
      if (messages[i].isUser) {
        userIndex = i
        break
      }
    }
    
    // 메시지 제거 (사용자 질문 + AI 답변)
    const newMessages = messages.filter((_, idx) => {
      if (userIndex !== -1 && idx === userIndex) return false
      if (idx === aiIndex) return false
      return true
    })
    
    setMessages(newMessages)
    
    // 약간의 딜레이 후 다시 질문
    setTimeout(() => {
      handleSend(userQuery)
    }, 100)
  }

  const handleSend = async (directMessage?: string) => {
    const messageToSend = directMessage || input
    
    // 중복 전송 방지 (더블 클릭, 빠른 Enter 연타 방지)
    // 이미지가 있으면 텍스트 없이도 전송 가능
    if ((!messageToSend.trim() && !selectedImage) || isLoading || sendingRef.current) {
      console.log('🚫 전송 차단:', { 
        hasInput: !!messageToSend.trim(), 
        hasImage: !!selectedImage,
        isLoading, 
        alreadySending: sendingRef.current 
      })
      return
    }

    console.log('📤 메시지 전송 시작:', messageToSend)
    sendingRef.current = true
    isStreamingRef.current = true // 스트리밍 시작
    
    // 타이밍 측정 시작
    const timingLogger = new FrontendTimingLogger(currentSessionId || 'new', messageToSend)
    
    const userInput = messageToSend
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
        // currentSessionId 업데이트 (중복 세션 생성 방지)
        selectSession(newSessionId)
      }
    }

    // 이미지 처리: 현재 선택된 이미지와 미리보기 URL 저장
    const currentImage = selectedImage
    const currentImagePreviewUrl = imagePreviewUrl
    
    // 이미지 상태 초기화 (전송 시작)
    setSelectedImage(null)
    setImagePreviewUrl(null)
    
    const userMessage: Message = {
      id: Date.now().toString(),
      text: currentImage ? `[이미지 첨부] ${userInput}` : userInput,
      isUser: true,
      imageUrl: currentImagePreviewUrl || undefined,
    }

    // 스트리밍 봇 메시지 ID (실시간 업데이트용)
    const streamingBotMessageId = (Date.now() + 1).toString()

    // 사용자 메시지를 먼저 UI에 추가 + 빈 봇 메시지도 함께 추가 (스트리밍용)
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
      // 사용자 메시지 + 빈 봇 메시지 (스트리밍 시작)
      const streamingBotMessage: Message = {
        id: streamingBotMessageId,
        text: '',  // 빈 상태로 시작, 청크가 도착하면 업데이트
        isUser: false,
        isStreaming: true,  // 스트리밍 중
      }
      return [...prev, userMessage, streamingBotMessage]
    })

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

    // 타이밍: 세션 준비 완료
    timingLogger.mark('session_ready')
    timingLogger.mark('ui_updated')
    timingLogger.mark('request_start')

    try {
      let firstLogReceived = false
      let firstChunkReceived = false
      
      // 공통 콜백 함수들 정의
      const onLogCallback = (log: string) => {
          // 취소된 경우 콜백 실행 안 함
          if (abortController.signal.aborted) return
          
          // 타이밍: 첫 로그 수신
          if (!firstLogReceived) {
            timingLogger.mark('first_log_received')
            firstLogReceived = true
          }
          
          // 백엔드 단계 감지
          timingLogger.markFromLog(log)
          
          setAgentData((prev) => ({
            ...prev,
            logs: [...prev.logs, log]
          }))
          // 메인 채팅 영역에도 현재 로그 표시 (사용자 친화적으로 변환)
          const formattedLog = formatLogMessage(log)
          setCurrentLog(formattedLog)
        }
      
      const onResultCallback = async (response: ChatResponse) => {
          // 취소된 경우 콜백 실행 안 함
          if (abortController.signal.aborted) return
          
          // 타이밍: 결과 수신
          timingLogger.mark('result_received')

          // 타이밍: 파싱 완료
          timingLogger.mark('parse_complete')

          // 스트리밍 봇 메시지를 최종 메시지로 업데이트 (sources, used_chunks 등 추가)
          setMessages((prev) => prev.map(msg => 
            msg.id === streamingBotMessageId
              ? {
                  ...msg,
                  text: response.response || msg.text,  // 최종 응답으로 교체 (또는 스트리밍된 텍스트 유지)
                  sources: response.sources,
                  source_urls: response.source_urls,
                  used_chunks: response.used_chunks,
                  isStreaming: false,  // 스트리밍 완료
                }
              : msg
          ))
          console.log('✅ 스트리밍 완료:', response.response?.substring(0, 50) || '(스트리밍 텍스트)')

          // 타이밍: 렌더링 완료
          timingLogger.mark('render_complete')

          // 스트리밍 종료 표시 (메시지 추가 직후)
          isStreamingRef.current = false

          // 첫 메시지인 경우 세션 제목 업데이트 (로그인한 경우)
          if (isAuthenticated && currentSessionIdToUse) {
            const userMessageCount = messages.filter(m => m.isUser).length + 1 // +1은 방금 추가한 메시지
            if (userMessageCount === 1 && userInput) {
              const title = userInput.substring(0, 50)
              updateSessionTitle(currentSessionIdToUse, title)
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
          
          // 백엔드 타이밍 정보 저장
          if (response.metadata?.timing) {
            timingLogger.setBackendTiming(response.metadata.timing)
          }
          
          // 타이밍: 저장 완료 & 전체 완료
          timingLogger.mark('save_complete')
          timingLogger.mark('total_complete')
          
          // 타이밍 로그 저장 및 출력
          timingLogger.printSummary()
          timingLogger.logToLocalStorage()
          
          // 실행 로그 저장 (모든 사용자)
          const elapsedMs = response.metadata?.timing?.total_time 
            ? response.metadata.timing.total_time * 1000 
            : Date.now() - parseInt(userMessage.id)
          
          void addLog({
            conversationHistory: messages.map(m => `${m.isUser ? 'User' : 'Bot'}: ${m.text.substring(0, 100)}`),
            userQuestion: userInput,
            routerOutput: response.router_output || null,
            functionResult: response.function_results || null,
            finalAnswer: response.response,
            elapsedTime: elapsedMs,
            timing: response.metadata?.timing || undefined,
          })
        }
      
      const onErrorCallback = (error: string) => {
          // 취소된 경우 에러 메시지 표시 안 함
          if (abortController.signal.aborted) return
          
          // 비로그인 사용자 Rate Limit 초과 - 로그인 유도
          if (error === '__RATE_LIMIT_GUEST__') {
            setMessages((prev) => prev.map(msg => 
              msg.id === streamingBotMessageId
                ? { ...msg, text: '로그인을 통해 더 많은 입시 정보와 개인별로 갈 수 있는 대학을 확인해보세요!!', showLoginPrompt: true }
                : msg
            ))
            setIsLoading(false)
            setCurrentLog('')
            return
          }
          
          // 스트리밍 봇 메시지를 에러 메시지로 교체
          setMessages((prev) => prev.map(msg => 
            msg.id === streamingBotMessageId
              ? { ...msg, text: error }
              : msg
          ))
        }
      
      // onChunk 콜백 - 실시간 텍스트 스트리밍
      const onChunkCallback = (chunk: string) => {
          // 취소된 경우 콜백 실행 안 함
          if (abortController.signal.aborted) return
          
          // 첫 청크가 오면 생각하는 과정 즉시 숨김
          if (!firstChunkReceived) {
            firstChunkReceived = true
            setCurrentLog('')
            setIsLoading(false)
          }
          
          // 스트리밍 봇 메시지에 청크 추가
          setMessages((prev) => prev.map(msg => 
            msg.id === streamingBotMessageId
              ? { ...msg, text: msg.text + chunk }
              : msg
          ))
          
          // 자동 스크롤
          scrollToBottom()
        }
      
      // 이미지가 있으면 이미지와 함께 전송, 없으면 일반 전송
      if (currentImage) {
        await sendMessageStreamWithImage(
          userInput,
          currentSessionIdToUse || sessionId,
          currentImage,
          onLogCallback,
          onResultCallback,
          onErrorCallback,
          abortController.signal,
          onChunkCallback,
          accessToken || undefined  // 인증 토큰 전달
        )
      } else {
        await sendMessageStream(
          userInput,
          currentSessionIdToUse || sessionId,
          onLogCallback,
          onResultCallback,
          onErrorCallback,
          abortController.signal,
          onChunkCallback,
          accessToken || undefined  // 인증 토큰 전달
        )
      }
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
      isStreamingRef.current = false // 스트리밍 종료
      abortControllerRef.current = null
      console.log('✅ 메시지 전송 완료')
      
      // 관리자 추가 실행 (시행 횟수 > 1인 경우)
      if (user?.name === '김도균' && testRunCount > 1) {
        runAdditionalTests(userInput, testRunCount - 1, testRunMode)
      }
    }
  }
  
  // 관리자 전용: 추가 테스트 실행 (백그라운드)
  const runAdditionalTests = async (question: string, count: number, mode: 'sequential' | 'parallel') => {
    console.log(`🔬 추가 테스트 실행: ${count}회 (${mode})`)
    
    const runSingleTest = async (runIndex: number): Promise<void> => {
      const startTime = Date.now()
      
      try {
        await sendMessageStream(
          question,
          `test-${Date.now()}-${runIndex}`,
          // 로그 콜백 (무시)
          () => {},
          // 결과 콜백
          (response: ChatResponse) => {
            const elapsedMs = Date.now() - startTime
            
            void addLog({
              conversationHistory: [],
              userQuestion: `[추가실행 ${runIndex + 2}] ${question}`,
              routerOutput: response.router_output || null,
              functionResult: response.function_results || null,
              finalAnswer: response.response,
              elapsedTime: elapsedMs,
              timing: response.metadata?.timing || undefined,
            })
            
            console.log(`✅ 추가 테스트 ${runIndex + 2} 완료: ${elapsedMs}ms`)
          },
          // 에러 콜백
          (error: string) => {
            void addLog({
              conversationHistory: [],
              userQuestion: `[추가실행 ${runIndex + 2}] ${question}`,
              routerOutput: { error },
              functionResult: null,
              finalAnswer: `오류: ${error}`,
              elapsedTime: Date.now() - startTime,
            })
          }
        )
      } catch (error: any) {
        console.error(`추가 테스트 ${runIndex + 2} 오류:`, error)
      }
    }
    
    if (mode === 'parallel') {
      // 병렬 실행
      const promises = Array.from({ length: count }, (_, i) => runSingleTest(i))
      await Promise.all(promises)
    } else {
      // 순차 실행
      for (let i = 0; i < count; i++) {
        await runSingleTest(i)
      }
    }
    
    console.log('🔬 추가 테스트 모두 완료')
  }



  return (
    <div className="flex h-screen">
      {/* 전역 이미지 파일 input (숨김) */}
      <input
        ref={imageInputRef}
        type="file"
        accept="image/jpeg,image/png,image/gif,image/webp"
        onChange={handleImageSelect}
        className="hidden"
      />
      
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

      <div className={`flex h-screen bg-white relative transition-all duration-300 ${
        isAgentPanelOpen ? 'w-1/2' : 'w-full'
      }`}>
        {/* 사이드 네비게이션 */}
        <div
          className={`fixed top-0 left-0 h-full w-80 z-50 transform transition-transform duration-300 ease-in-out ${
            isSideNavOpen ? 'translate-x-0' : '-translate-x-full'
          } sm:fixed sm:z-40`}
          style={{ backgroundColor: '#F1F5FB' }}
        >
        <div className="h-full flex flex-col">
          {/* 사이드바 토글 버튼 (왼쪽 상단) */}
          <div className="absolute top-4 left-4 z-10">
            <button
              onClick={() => setIsSideNavOpen(false)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title="사이드바 닫기"
            >
              <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>

          {/* 1. 새 채팅 버튼 (로그인/비로그인 모두 표시) */}
          <div className="px-4 sm:px-6 pt-16 pb-2">
            <button
              onClick={() => {
                handleNewChat()
                // 모바일에서는 사이드바 자동 닫기
                if (window.innerWidth < 640) {
                  setIsSideNavOpen(false)
                }
              }}
              className="w-full flex items-center justify-start gap-3 px-3 py-2.5 text-gray-700 hover:bg-[#DEE2E6] rounded-lg transition-colors text-left"
            >
              <svg className="w-5 h-5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
              <span className="text-sm font-medium text-left">새 채팅</span>
            </button>
          </div>

          {/* 2. 공지사항 (드롭다운) */}
          <div className="px-4 sm:px-6 pb-2">
            <button 
              onClick={() => setIsAnnouncementDropdownOpen(!isAnnouncementDropdownOpen)}
              className="w-full flex items-center justify-start gap-3 px-3 py-2.5 text-gray-700 hover:bg-[#DEE2E6] rounded-lg transition-colors text-left"
            >
              <svg className="w-5 h-5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
              </svg>
              <span className="text-sm font-medium flex-1 text-left">공지사항</span>
              <svg 
                className={`w-5 h-5 text-gray-500 flex-shrink-0 transition-transform ${isAnnouncementDropdownOpen ? 'rotate-180' : ''}`}
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            
            {/* 드롭다운 메뉴 */}
            {isAnnouncementDropdownOpen && (
              <div className="mt-2 ml-4 space-y-1 border-l-2 border-gray-200 pl-4 max-h-96 overflow-y-auto">
                {announcements.length === 0 ? (
                  <p className="text-xs text-gray-500 py-2">등록된 공지사항이 없습니다.</p>
                ) : (
                  announcements.map((announcement) => {
                    // 5일 이내인지 확인
                    const createdDate = new Date(announcement.created_at)
                    const now = new Date()
                    const diffTime = now.getTime() - createdDate.getTime()
                    const diffDays = diffTime / (1000 * 60 * 60 * 24)
                    const isNew = diffDays <= 5

                    return (
                    <div key={announcement.id} className={`group ${isNew ? 'animate-shake-new' : ''}`}>
                      <button 
                        onClick={() => {
                          setSelectedAnnouncement(announcement)
                          setIsAnnouncementModalOpen(false)
                          setTimeout(() => setIsAnnouncementModalOpen(true), 0)
                        }}
                        className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-[#DEE2E6] rounded-lg transition-colors text-left"
                      >
                        <div className={`w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 ${
                          announcement.is_pinned ? 'bg-red-500' : 'border-2 border-gray-300'
                        } group-hover:border-blue-500 transition-colors`}>
                          {announcement.is_pinned && (
                            <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                              <path d="M10 2a6 6 0 00-6 6v3.586l-.707.707A1 1 0 004 14h12a1 1 0 00.707-1.707L16 11.586V8a6 6 0 00-6-6zM10 18a3 3 0 01-3-3h6a3 3 0 01-3 3z" />
                            </svg>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="text-xs font-medium text-gray-900 truncate">{announcement.title}</p>
                            {isNew && (
                              <span className="new-badge flex-shrink-0">NEW</span>
                            )}
                          </div>
                          <p className="text-[10px] text-gray-500">
                            {new Date(announcement.created_at).toLocaleDateString('ko-KR')}
                          </p>
                        </div>
                        {isAuthenticated && isAdmin && (
                          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                openEditModal(announcement)
                              }}
                              className="p-1 hover:bg-blue-100 rounded text-blue-600"
                              title="수정"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                              </svg>
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                handleDeleteAnnouncement(announcement.id)
                              }}
                              className="p-1 hover:bg-red-100 rounded text-red-600"
                              title="삭제"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        )}
                      </button>
                    </div>
                    )
                  })
                )}
                
                {/* 관리자 추가 버튼 */}
                {isAuthenticated && isAdmin && (
                  <button
                    onClick={openCreateModal}
                    className="w-full flex items-center gap-2 px-3 py-2.5 mt-2 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors text-left group border-2 border-dashed border-blue-300"
                  >
                    <div className="w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center flex-shrink-0">
                      <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-blue-700">새 공지사항 추가</p>
                    </div>
                  </button>
                )}
              </div>
            )}
          </div>

          {/* 3. 오픈채팅방 */}
          <div className="px-4 sm:px-6 pb-2">
            <button 
              onClick={() => setIsOpenChatModalOpen(true)}
              className="w-full flex items-center justify-start gap-3 px-3 py-2.5 text-gray-700 hover:bg-[#DEE2E6] rounded-lg transition-colors text-left"
            >
              <svg className="w-5 h-5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 8h2a2 2 0 012 2v6a2 2 0 01-2 2h-2v4l-4-4H9a1.994 1.994 0 01-1.414-.586m0 0L11 14h4a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2v4l.586-.586z" />
              </svg>
              <span className="text-sm font-medium text-left">오픈채팅방</span>
            </button>
          </div>

          {/* 4. 내 입시 기록 관리 (드롭다운) */}
          <div className="px-4 sm:px-6 pb-2">
            <button 
              onClick={() => setIsRecordDropdownOpen(!isRecordDropdownOpen)}
              className="w-full flex items-center justify-start gap-3 px-3 py-2.5 text-gray-700 hover:bg-[#DEE2E6] rounded-lg transition-colors text-left"
            >
              <svg className="w-5 h-5 text-gray-500 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <span className="text-sm font-medium flex-1 text-left">내 입시 기록 관리</span>
              <svg 
                className={`w-5 h-5 text-gray-500 flex-shrink-0 transition-transform ${isRecordDropdownOpen ? 'rotate-180' : ''}`}
                fill="none" 
                stroke="currentColor" 
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            
            {/* 드롭다운 메뉴 */}
            {isRecordDropdownOpen && (
              <div className="mt-2 ml-4 space-y-1 border-l-2 border-gray-200 pl-4">
                {/* 내 생활기록부 관리 */}
                <button className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-[#DEE2E6] rounded-lg transition-colors text-left group">
                  <div className="w-5 h-5 rounded-full border-2 border-gray-300 flex items-center justify-center flex-shrink-0 group-hover:border-blue-500 transition-colors">
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-900">내 생활기록부 관리</p>
                    <p className="text-[10px] text-gray-500">10초만에 연동하기</p>
                  </div>
                </button>

                {/* 3월 6월 9월 모의고사 성적 입력 */}
                <button 
                  onClick={() => {
                    if (!isAuthenticated) {
                      alert('로그인이 필요합니다.')
                      setIsAuthModalOpen(true)
                      return
                    }
                    setIsProfileFormOpen(true)
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-[#DEE2E6] rounded-lg transition-colors text-left group"
                >
                  <div className="w-5 h-5 rounded-full border-2 border-blue-500 flex items-center justify-center flex-shrink-0 group-hover:border-blue-600 transition-colors">
                    <svg className="w-3 h-3 text-blue-500 group-hover:text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium text-gray-900">모의고사 성적 입력</p>
                    <p className="text-[10px] text-gray-500">AI 상담에 활용됩니다</p>
                  </div>
                </button>

                {/* 내신 성적 입력 */}
                <button className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-[#DEE2E6] rounded-lg transition-colors text-left group">
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

          {/* 5. 채팅 내역 (로그인한 경우에만 표시) */}
          {isAuthenticated && (
            <div className="flex-1 px-4 sm:px-6 pb-4 overflow-y-auto custom-scrollbar">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-bold text-gray-900">채팅 내역</h2>
                <button
                  onClick={() => setIsSearchOpen(!isSearchOpen)}
                  className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                  title="채팅 검색"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </button>
              </div>
              
              {/* 검색창 (토글) */}
              {isSearchOpen && (
                <div ref={searchContainerRef} className="relative mb-3">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="채팅 검색..."
                    autoFocus
                    className="w-full px-3 py-2 pl-9 text-sm bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <svg className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  {searchQuery && (
                    <button
                      onClick={() => setSearchQuery('')}
                      className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  )}
                </div>
              )}
              
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
                    <div
                      key={session.id}
                      className={`w-full px-3 py-2 rounded-lg transition-colors flex items-center justify-between group ${
                        currentSessionId === session.id
                          ? 'text-gray-900'
                          : 'hover:bg-[#DEE2E6] text-gray-900'
                      }`}
                      style={currentSessionId === session.id ? { backgroundColor: '#DBE4F6' } : undefined}
                    >
                      <button
                        onClick={() => {
                          selectSession(session.id)
                          // 모바일에서는 사이드바 자동 닫기
                          if (window.innerWidth < 640) {
                            setIsSideNavOpen(false)
                          }
                        }}
                        className="flex-1 text-left min-w-0"
                      >
                        <p className="text-xs font-medium truncate">{session.title}</p>
                        <p className="text-[10px] text-gray-500 mt-0.5">
                          {new Date(session.updated_at).toLocaleDateString('ko-KR', {
                            month: 'short',
                            day: 'numeric',
                          })}
                        </p>
                      </button>
                      <button
                        onClick={async (e) => {
                          e.stopPropagation()
                          if (confirm('이 채팅 내역을 삭제하시겠습니까?')) {
                            try {
                              await deleteSession(session.id)
                            } catch (error) {
                              alert('삭제에 실패했습니다.')
                            }
                          }
                        }}
                        className="opacity-0 group-hover:opacity-100 text-red-500 hover:text-red-700 p-1 transition-opacity"
                        title="삭제"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
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
                  className="w-full px-3 sm:px-4 py-2.5 sm:py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 active:bg-blue-700 transition-colors font-medium text-xs sm:text-sm"
                >
                  회원가입 또는 로그인
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 모바일 오버레이 - 사이드바 바깥 클릭 시 닫기 */}
      {isSideNavOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 sm:hidden"
          onClick={() => setIsSideNavOpen(false)}
        />
      )}

      {/* 메인 채팅 영역 */}
      <div className={`flex flex-col flex-1 min-w-0 transition-all duration-300 ${
        isSideNavOpen ? 'sm:ml-80' : 'sm:ml-0'
      }`}>
        {/* 헤더 - 모바일과 데스크톱 분리 */}
        <header className="bg-white safe-area-top sticky top-0 z-10">
          {/* 모바일 헤더 */}
          <div className="sm:hidden px-4 py-3 flex justify-between items-center">
            <div className="flex items-center gap-3">
            {!isSideNavOpen && (
            <button
                onClick={() => setIsSideNavOpen(true)}
                className="p-2 -ml-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            )}
              <img
                src="/로고.png"
                alt="UniZ Logo"
                className="h-8 cursor-pointer"
                onClick={handleNewChat}
              />
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
              {/* 사이드바 토글 버튼 - 사이드바 닫혔을 때만 표시 */}
              {!isSideNavOpen && (
                <button
                  onClick={() => setIsSideNavOpen(true)}
                  className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
                  title="사이드바 열기"
                >
                  <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              )}
              <img
                src="/로고.png"
                alt="UniZ Logo"
                className="h-10 cursor-pointer"
                onClick={handleNewChat}
              />
            </div>
            
            <div className="flex items-center gap-3">
              {user?.name === '김도균' && (
                <>
                  {/* 테스트 설정 */}
                  <div className="relative">
                    <button
                      onClick={() => setIsTestSettingsOpen(!isTestSettingsOpen)}
                      className={`px-3 py-2 rounded-lg transition-colors flex items-center gap-2 text-sm font-medium ${
                        testRunCount > 1
                          ? 'bg-orange-500 text-white hover:bg-orange-600'
                          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                      }`}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                      </svg>
                      {testRunCount}x
                    </button>
                    
                    {/* 드롭다운 패널 */}
                    {isTestSettingsOpen && (
                      <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-lg shadow-xl border border-gray-200 p-4 z-50">
                        <h3 className="text-sm font-bold text-gray-900 mb-3">테스트 설정</h3>
                        
                        {/* 시행 횟수 */}
                        <div className="mb-3">
                          <label className="text-xs font-medium text-gray-600 block mb-1">시행 횟수</label>
                          <div className="flex items-center gap-2">
                            <input
                              type="range"
                              min="1"
                              max="20"
                              value={testRunCount}
                              onChange={(e) => setTestRunCount(parseInt(e.target.value))}
                              className="flex-1"
                            />
                            <span className="text-sm font-bold text-gray-900 w-8 text-center">{testRunCount}</span>
                          </div>
                        </div>
                        
                        {/* 실행 모드 */}
                        <div className="mb-3">
                          <label className="text-xs font-medium text-gray-600 block mb-1">실행 모드</label>
                          <div className="flex gap-2">
                            <button
                              onClick={() => setTestRunMode('sequential')}
                              className={`flex-1 px-3 py-1.5 text-xs rounded-lg transition-colors ${
                                testRunMode === 'sequential'
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                              }`}
                            >
                              순차
                            </button>
                            <button
                              onClick={() => setTestRunMode('parallel')}
                              className={`flex-1 px-3 py-1.5 text-xs rounded-lg transition-colors ${
                                testRunMode === 'parallel'
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                              }`}
                            >
                              병렬
                            </button>
                          </div>
                        </div>
                        
                        <p className="text-[10px] text-gray-500">
                          첫 번째 결과만 채팅에 표시, 나머지는 Admin 페이지에서 확인
                        </p>
                      </div>
                    )}
                  </div>
                  
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
                    onClick={() => navigate('/chat/admin')}
                    className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm font-medium"
                  >
                    Admin
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
        <div className="flex-1 overflow-y-auto px-[17px] sm:px-6 py-4 pb-16">
          <div className="max-w-[800px] mx-auto">
            {messages.length === 0 ? (
              <div className="min-h-[calc(100vh-150px)] flex flex-col items-center justify-between sm:justify-center px-4 sm:px-8 pt-8 sm:pt-12 pb-6">
                {/* 상단 영역: 인사말 + 카드 + 채팅창 */}
                <div className="w-full flex flex-col justify-center sm:flex-none">
                  {/* 인사말 */}
                  <div className="text-center mb-8 sm:mb-10">
                    <h1 className="text-xl sm:text-2xl md:text-3xl font-bold text-gray-900 mb-3 sm:mb-4 whitespace-nowrap">
                      {isAuthenticated && user?.name ? (
                        <>안녕하세요 {user.name}님 👋 여러분과 입시 여정을 함께하는 유니로드입니다!</>
                      ) : (
                        <>안녕하세요 👋 여러분과 입시 여정을 함께하는 유니로드입니다!</>
                      )}
                    </h1>
                    <p className="text-base sm:text-lg text-gray-600">
                      무엇을 도와드릴까요? 🎓
                    </p>
                  </div>

                  {/* 롤링 플레이스홀더 - 채팅창 위에 배치 */}
                  <div className="w-full mb-8 sm:mb-10">
                    <RollingPlaceholder
                      onQuestionClick={(question) => {
                        setSelectedCategory(null) // 질문 클릭 시 카테고리 초기화
                        handleSend(question)
                      }}
                      selectedCategory={selectedCategory}
                      onCategorySelect={setSelectedCategory}
                      isAuthenticated={isAuthenticated}
                      onLoginRequired={(message) => {
                        setAuthModalMessage(message)
                        setIsAuthModalOpen(true)
                      }}
                      onProfileRequired={() => {
                        setShowProfileGuide(true)
                        setIsProfileFormOpen(true)
                      }}
                    />
                  </div>

                  {/* 데스크톱: 이미지 미리보기 */}
                  {imagePreviewUrl && (
                    <div className="hidden sm:block w-full mb-2">
                      <div className="inline-flex items-center gap-2 bg-gray-100 rounded-lg p-2">
                        <img 
                          src={imagePreviewUrl} 
                          alt="첨부 이미지" 
                          className="h-16 w-16 object-cover rounded-lg"
                        />
                        <button
                          onClick={handleImageRemove}
                          className="p-1 hover:bg-gray-200 rounded-full transition-colors"
                          title="이미지 제거"
                        >
                          <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  )}
                  
                  {/* 데스크톱: 채팅창 (모바일에서 숨김) */}
                  <div className="hidden sm:block w-full max-w-3xl mx-auto px-4">
                    <div className="bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.08)] focus-within:shadow-[0_4px_20px_rgba(0,0,0,0.12)] px-4 py-3 transition-shadow duration-200">
                      {/* 텍스트 입력 영역 */}
                      <textarea
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
                        rows={1}
                        className="w-full text-base bg-transparent focus:outline-none disabled:bg-gray-100 min-h-[32px] max-h-[200px] resize-none overflow-y-auto placeholder:text-gray-400"
                        style={{ height: 'auto' }}
                        onInput={(e) => {
                          const target = e.target as HTMLTextAreaElement
                          target.style.height = 'auto'
                          target.style.height = Math.min(target.scrollHeight, 200) + 'px'
                        }}
                      />
                      
                      {/* 하단 영역: 버튼들 + 태그 + 전송 버튼 */}
                      <div className="flex items-center justify-between mt-2">
                        <div className="flex items-center gap-2">
                          {/* 성적 입력 메뉴 버튼 */}
                          <div className="relative" ref={uploadMenuRef}>
                            <button
                              onClick={() => setIsUploadMenuOpen(!isUploadMenuOpen)}
                              disabled={isLoading}
                              className="w-8 h-8 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-full flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                              title="성적 입력"
                            >
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                              </svg>
                            </button>
                            
                            {/* 드롭업 메뉴 */}
                            {isUploadMenuOpen && (
                              <div className="absolute bottom-10 left-0 bg-white rounded-xl shadow-lg border border-gray-200 py-2 min-w-[200px] z-50">
                                <button
                                  onClick={() => {
                                    imageInputRef.current?.click()
                                    setIsUploadMenuOpen(false)
                                  }}
                                  className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center gap-3 transition-colors"
                                >
                                  <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                  </svg>
                                  <span className="text-sm font-medium text-gray-700">성적표 이미지 입력하기</span>
                                </button>
                                <button
                                  onClick={() => {
                                    if (!isAuthenticated) {
                                      alert('로그인이 필요합니다.')
                                      setIsAuthModalOpen(true)
                                    } else {
                                      setIsProfileFormOpen(true)
                                    }
                                    setIsUploadMenuOpen(false)
                                  }}
                                  className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center gap-3 transition-colors"
                                >
                                  <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                  </svg>
                                  <span className="text-sm font-medium text-gray-700">성적표 입력하기</span>
                                </button>
                              </div>
                            )}
                          </div>
                          
                          {/* 선택된 카테고리 태그 */}
                          {selectedCategory && (
                            <div className="inline-flex items-center gap-1.5 bg-blue-100 text-blue-700 rounded-full px-3 py-1 text-sm font-medium">
                              <span>{selectedCategory}</span>
                              <button
                                onClick={() => setSelectedCategory(null)}
                                className="hover:bg-blue-200 rounded-full transition-colors"
                                title="태그 제거"
                              >
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                          )}
                        </div>
                        
                        {/* 전송 버튼 */}
                        <button
                          onClick={() => handleSend()}
                          disabled={isLoading || (!input.trim() && !selectedImage)}
                          className="w-10 h-10 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>

                </div>

                {/* 모바일 하단: 채팅창 (데스크톱에서 숨김) */}
                <div className="sm:hidden w-full mt-auto pb-2">
                  {/* 모바일: 이미지 미리보기 */}
                  {imagePreviewUrl && (
                    <div className="mb-2">
                      <div className="inline-flex items-center gap-2 bg-gray-100 rounded-lg p-2">
                        <img 
                          src={imagePreviewUrl} 
                          alt="첨부 이미지" 
                          className="h-12 w-12 object-cover rounded-lg"
                        />
                        <button
                          onClick={handleImageRemove}
                          className="p-1 hover:bg-gray-200 rounded-full transition-colors"
                          title="이미지 제거"
                        >
                          <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  )}
                  
                  <div className="w-full">
                    <div className="bg-gray-50 rounded-3xl focus-within:ring-2 focus-within:ring-blue-500 px-3 py-2">
                      {/* 텍스트 입력 영역 */}
                      <textarea
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
                        rows={1}
                        className="w-full text-base bg-transparent focus:outline-none disabled:bg-gray-100 min-h-[28px] max-h-[200px] resize-none overflow-y-auto placeholder:text-gray-400"
                        style={{ height: 'auto' }}
                        onInput={(e) => {
                          const target = e.target as HTMLTextAreaElement
                          target.style.height = 'auto'
                          target.style.height = Math.min(target.scrollHeight, 200) + 'px'
                        }}
                      />
                      
                      {/* 하단 영역: 버튼들 + 태그 + 전송 버튼 */}
                      <div className="flex items-center justify-between mt-2">
                        <div className="flex items-center gap-2">
                          {/* 성적 입력 메뉴 버튼 (모바일) */}
                          <div className="relative">
                            <button
                              onClick={() => setIsUploadMenuOpen(!isUploadMenuOpen)}
                              disabled={isLoading}
                              className="w-8 h-8 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-full flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                              title="성적 입력"
                            >
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                              </svg>
                            </button>
                            
                            {/* 드롭업 메뉴 (모바일) */}
                            {isUploadMenuOpen && (
                              <div className="absolute bottom-10 left-0 bg-white rounded-xl shadow-lg border border-gray-200 py-2 min-w-[200px] z-50">
                                <button
                                  onClick={() => {
                                    imageInputRef.current?.click()
                                    setIsUploadMenuOpen(false)
                                  }}
                                  className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center gap-3 transition-colors"
                                >
                                  <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                                  </svg>
                                  <span className="text-sm font-medium text-gray-700">성적표 이미지 입력하기</span>
                                </button>
                                <button
                                  onClick={() => {
                                    if (!isAuthenticated) {
                                      alert('로그인이 필요합니다.')
                                      setIsAuthModalOpen(true)
                                    } else {
                                      setIsProfileFormOpen(true)
                                    }
                                    setIsUploadMenuOpen(false)
                                  }}
                                  className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center gap-3 transition-colors"
                                >
                                  <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                                  </svg>
                                  <span className="text-sm font-medium text-gray-700">성적표 입력하기</span>
                                </button>
                              </div>
                            )}
                          </div>
                          
                          {/* 선택된 카테고리 태그 */}
                          {selectedCategory && (
                            <div className="inline-flex items-center gap-1 bg-blue-100 text-blue-700 rounded-full px-2.5 py-0.5 text-xs font-medium">
                              <span>{selectedCategory}</span>
                              <button
                                onClick={() => setSelectedCategory(null)}
                                className="hover:bg-blue-200 rounded-full transition-colors"
                                title="태그 제거"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                          )}
                        </div>
                        
                        {/* 전송 버튼 */}
                        <button
                          onClick={() => handleSend()}
                          disabled={isLoading || (!input.trim() && !selectedImage)}
                          className="w-9 h-9 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}

            {messages.map((msg, index) => {
              // AI 답변일 경우 직전 사용자 질문 찾기
              let userQuery: string | undefined
              if (!msg.isUser) {
                for (let i = index - 1; i >= 0; i--) {
                  if (messages[i].isUser) {
                    userQuery = messages[i].text
                    break
                  }
                }
              }
              
              return (
                <ChatMessage
                  key={msg.id}
                  message={msg.text}
                  isUser={msg.isUser}
                  sources={msg.sources}
                  source_urls={msg.source_urls}
                  userQuery={userQuery}
                  isStreaming={msg.isStreaming}
                  imageUrl={msg.imageUrl}
                  onRegenerate={!msg.isUser && userQuery && index === messages.length - 1 ? () => handleRegenerate(msg.id, userQuery) : undefined}
                  showLoginPrompt={msg.showLoginPrompt}
                  onLoginClick={() => setIsAuthModalOpen(true)}
                />
              )
            })}

            {isLoading && (
              <div className="flex justify-start mb-4">
                <ThinkingProcess logs={agentData.logs} />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* 입력 영역 - 고정 (메시지가 있을 때만 표시) */}
        {messages.length > 0 && (
          <div className="bg-white sticky bottom-0 sm:bottom-[40px]">
            {/* 이미지 미리보기 */}
            {imagePreviewUrl && (
              <div className="px-4 sm:px-6 pb-2">
                <div className="max-w-[800px] mx-auto">
                  <div className="inline-flex items-center gap-2 bg-gray-100 rounded-lg p-2">
                    <img 
                      src={imagePreviewUrl} 
                      alt="첨부 이미지" 
                      className="h-16 w-16 object-cover rounded-lg"
                    />
                    <button
                      onClick={handleImageRemove}
                      className="p-1 hover:bg-gray-200 rounded-full transition-colors"
                      title="이미지 제거"
                    >
                      <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            )}
            
            <div className="px-4 sm:px-6 py-2">
              <div className="max-w-[800px] mx-auto">
                <div className="bg-gray-50 rounded-3xl focus-within:ring-2 focus-within:ring-blue-500 px-3 sm:px-4 py-2 sm:py-3">
                  {/* 텍스트 입력 영역 */}
                  <textarea
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
                    rows={1}
                    className="w-full text-base bg-transparent focus:outline-none disabled:bg-gray-100 min-h-[28px] sm:min-h-[32px] max-h-[200px] resize-none overflow-y-auto placeholder:text-gray-400"
                    style={{ height: 'auto' }}
                    onInput={(e) => {
                      const target = e.target as HTMLTextAreaElement
                      target.style.height = 'auto'
                      target.style.height = Math.min(target.scrollHeight, 200) + 'px'
                    }}
                  />
                  
                  {/* 하단 영역: 버튼들 + 태그 + 전송 버튼 */}
                  <div className="flex items-center justify-between mt-2">
                    <div className="flex items-center gap-2">
                      {/* 성적 입력 메뉴 버튼 */}
                      <div className="relative">
                        <button
                          onClick={() => setIsUploadMenuOpen(!isUploadMenuOpen)}
                          disabled={isLoading}
                          className="w-8 h-8 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-full flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                          title="성적 입력"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                          </svg>
                        </button>
                        
                        {/* 드롭업 메뉴 */}
                        {isUploadMenuOpen && (
                          <div className="absolute bottom-10 left-0 bg-white rounded-xl shadow-lg border border-gray-200 py-2 min-w-[200px] z-50">
                            <button
                              onClick={() => {
                                imageInputRef.current?.click()
                                setIsUploadMenuOpen(false)
                              }}
                              className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center gap-3 transition-colors"
                            >
                              <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                              </svg>
                              <span className="text-sm font-medium text-gray-700">성적표 이미지 입력하기</span>
                            </button>
                            <button
                              onClick={() => {
                                if (!isAuthenticated) {
                                  alert('로그인이 필요합니다.')
                                  setIsAuthModalOpen(true)
                                } else {
                                  setIsProfileFormOpen(true)
                                }
                                setIsUploadMenuOpen(false)
                              }}
                              className="w-full px-4 py-3 text-left hover:bg-gray-50 flex items-center gap-3 transition-colors"
                            >
                              <svg className="w-5 h-5 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                              </svg>
                              <span className="text-sm font-medium text-gray-700">성적표 입력하기</span>
                            </button>
                          </div>
                        )}
                      </div>
                      
                      {/* 선택된 카테고리 태그 */}
                      {selectedCategory && (
                        <div className="inline-flex items-center gap-1 sm:gap-1.5 bg-blue-100 text-blue-700 rounded-full px-2.5 sm:px-3 py-0.5 sm:py-1 text-xs sm:text-sm font-medium">
                          <span>{selectedCategory}</span>
                          <button
                            onClick={() => setSelectedCategory(null)}
                            className="hover:bg-blue-200 rounded-full transition-colors"
                            title="태그 제거"
                          >
                            <svg className="w-3.5 h-3.5 sm:w-4 sm:h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                          </button>
                        </div>
                      )}
                    </div>
                    
                    {/* 전송 버튼 */}
                    <button
                      onClick={() => handleSend()}
                      disabled={isLoading || (!input.trim() && !selectedImage)}
                      className="w-9 h-9 sm:w-10 sm:h-10 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                    >
                      <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 로그인 모달 */}
      <AuthModal 
        isOpen={isAuthModalOpen} 
        onClose={() => {
          setIsAuthModalOpen(false)
          setAuthModalMessage(undefined)
        }}
        customMessage={authModalMessage}
        onLoginSuccess={() => {
          // 로그인 성공 시 처음 화면으로 돌아가기
          setMessages([])
          setSelectedCategory(null)
        }}
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

      {/* 공지사항 모달 */}
      {isAnnouncementModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto animate-slideUp">
            {/* 헤더 */}
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
              <h2 className="text-xl font-bold text-gray-900">
                {selectedAnnouncement ? '공지사항' : editingAnnouncementId ? '공지사항 수정' : '새 공지사항'}
              </h2>
              <button
                onClick={() => {
                  setIsAnnouncementModalOpen(false)
                  setSelectedAnnouncement(null)
                  setEditingAnnouncementId(null)
                }}
                className="p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* 본문 */}
            <div className="px-6 py-6">
              {selectedAnnouncement ? (
                // 공지사항 보기
                <div>
                  <div className="mb-4">
                    <div className="flex items-center gap-2 mb-2">
                      {selectedAnnouncement.is_pinned && (
                        <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-medium rounded">고정</span>
                      )}
                      <span className="text-sm text-gray-500">
                        {new Date(selectedAnnouncement.created_at).toLocaleDateString('ko-KR', {
                          year: 'numeric',
                          month: 'long',
                          day: 'numeric'
                        })}
                      </span>
                    </div>
                    <h3 className="text-2xl font-bold text-gray-900 mb-4">{selectedAnnouncement.title}</h3>
                  </div>
                  <div className="prose max-w-none">
                    <p className="text-gray-700 whitespace-pre-wrap">{selectedAnnouncement.content}</p>
                  </div>
                  
                  {isAuthenticated && isAdmin && (
                    <div className="mt-6 pt-6 border-t flex gap-2">
                      <button
                        onClick={() => {
                          openEditModal(selectedAnnouncement)
                          setSelectedAnnouncement(null)
                        }}
                        className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                      >
                        수정
                      </button>
                      <button
                        onClick={() => {
                          handleDeleteAnnouncement(selectedAnnouncement.id)
                          setIsAnnouncementModalOpen(false)
                          setSelectedAnnouncement(null)
                        }}
                        className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                      >
                        삭제
                      </button>
                    </div>
                  )}
                </div>
              ) : (
                // 공지사항 작성/수정 폼
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      제목 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={announcementForm.title}
                      onChange={(e) => setAnnouncementForm({ ...announcementForm, title: e.target.value })}
                      placeholder="공지사항 제목을 입력하세요"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      내용 <span className="text-red-500">*</span>
                    </label>
                    <textarea
                      value={announcementForm.content}
                      onChange={(e) => setAnnouncementForm({ ...announcementForm, content: e.target.value })}
                      placeholder="공지사항 내용을 입력하세요"
                      rows={10}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                    />
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_pinned"
                      checked={announcementForm.is_pinned}
                      onChange={(e) => setAnnouncementForm({ ...announcementForm, is_pinned: e.target.checked })}
                      className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500"
                    />
                    <label htmlFor="is_pinned" className="text-sm text-gray-700">
                      상단 고정
                    </label>
                  </div>

                  <div className="flex gap-2 pt-4">
                    <button
                      onClick={() => {
                        setIsAnnouncementModalOpen(false)
                        setEditingAnnouncementId(null)
                      }}
                      className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-[#DEE2E6] transition-colors"
                    >
                      취소
                    </button>
                    <button
                      onClick={editingAnnouncementId ? handleUpdateAnnouncement : handleCreateAnnouncement}
                      disabled={!announcementForm.title.trim() || !announcementForm.content.trim()}
                      className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                    >
                      {editingAnnouncementId ? '수정' : '등록'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 프로필 폼 모달 */}
      <ProfileForm 
        isOpen={isProfileFormOpen} 
        onClose={() => {
          setIsProfileFormOpen(false)
          setShowProfileGuide(false)
        }}
        showGuide={showProfileGuide}
      />
      </div>
    </div>
  )
}
