import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  sendMessageStream,
  sendMessageStreamWithImage,
  ChatResponse,
  ScoreReviewRequiredEvent,
  ScoreSetSuggestItem,
  approveScoreReview,
  suggestScoreSets,
  getScoreSetByName,
  skipScoreReviewSession,
  resetSession,
  migrateMessages,
  listScoreSets,
} from '../api/client'
import ChatMessage from '../components/ChatMessage'
import ThinkingProcess from '../components/ThinkingProcess'
import AgentPanel from '../components/AgentPanel'
import AuthModal from '../components/AuthModal'
import PreregisterModal from '../components/PreregisterModal'
import RollingPlaceholder from '../components/RollingPlaceholder'
import ProfileForm from '../components/ProfileForm'
import ScoreSetManagerModal from '../components/ScoreSetManagerModal'
import SchoolRecordToolStartModal from '../components/SchoolRecordToolStartModal'
import SchoolGradeInputModal from '../components/SchoolGradeInputModal'
import SchoolRecordResearchProgress from '../components/SchoolRecordResearchProgress'
import SchoolRecordDeepAnalysisPage from './SchoolRecordDeepAnalysisPage'
import { redirectToGumroadCheckout } from '../utils/gumroad'
import { useAuth } from '../contexts/AuthContext'
import { useChat } from '../hooks/useChat'
import { getSessionId, trackUserAction } from '../utils/tracking'
import { FrontendTimingLogger } from '../utils/timingLogger'
import { API_BASE, isCapacitorApp, isGalaxyAppSession } from '../config'
import { addLog } from '../utils/adminLogger'
import { QUICK_EXAMPLE_RESPONSES } from '../data/quickExampleResponses'

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
  scoreMentions?: string[]
  scoreReview?: {
    pendingId: string
    titleAuto: string
    scores: Record<string, any>
  }
  sources?: string[]
  source_urls?: string[]
  used_chunks?: UsedChunk[]
  isStreaming?: boolean  // 스트리밍 중인지 여부
  imageUrl?: string  // 이미지 첨부 시 미리보기 URL
  isMasked?: boolean  // 마스킹 여부 (비로그인 3회째 질문)
  // Agent 디버그 데이터 (관리자용)
  agentData?: {
    routerOutput: any
    functionResults: any
    mainAgentOutput: string | null
    rawAnswer?: string | null
    logs: string[]
  } | null
}

interface AgentData {
  routerOutput: any           // Router Agent 출력 (function_calls, raw_response)
  functionResults: any        // Functions 실행 결과 (chunks, documents)
  mainAgentOutput: string | null  // Main Agent 최종 답변
  rawAnswer?: string | null   // 원본 답변 (섹션 마커 포함)
  logs: string[]
}

interface SavedSchoolRecordReport {
  id: string
  sessionId: string
  messageId: string
  title: string
  description: string
  question: string
  createdAt: string
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

const extractScoreMentions = (text: string): string[] => {
  const mentions = text.match(/@[가-힣a-zA-Z0-9_]{1,10}/g) || []
  return Array.from(new Set(mentions))
}

const getMentionContext = (
  value: string,
  caretPos: number
): { start: number; end: number; query: string } | null => {
  const left = value.slice(0, caretPos)
  const match = left.match(/(^|\s)@([가-힣a-zA-Z0-9_]*)$/)
  if (!match) return null
  const atIndex = left.lastIndexOf('@')
  if (atIndex < 0) return null
  return { start: atIndex, end: caretPos, query: match[2] || '' }
}

const getQuickExampleResponse = (question: string): string | undefined => {
  return QUICK_EXAMPLE_RESPONSES[question.trim()]
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
    loadSessions,
  } = useChat()
  
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  // 트래킹(events)과 동일한 user_session 사용 → 로그인/비로그인 모두 동일 세션으로 연동
  const [sessionId, setSessionId] = useState(() => getSessionId())
  const [isSideNavOpen, setIsSideNavOpen] = useState(() => {
    // 데스크톱에서는 기본적으로 열림, 모바일에서는 닫힘
    return window.innerWidth >= 640
  })
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState(false)
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false)
  const [isPreregisterModalOpen, setIsPreregisterModalOpen] = useState(false)
  const [isProModalOpen, setIsProModalOpen] = useState(false)
  const [isBankTransferModalOpen, setIsBankTransferModalOpen] = useState(false)
  const [bankTransferName, setBankTransferName] = useState('')
  const [bankTransferPhone, setBankTransferPhone] = useState('')
  const [bankTransferSubmitting, setBankTransferSubmitting] = useState(false)
  const [dailyQuestionCount, setDailyQuestionCount] = useState<number>(() => {
    // localStorage에서 오늘 질문 횟수 불러오기
    const today = new Date().toDateString()
    const stored = localStorage.getItem('uniroad_daily_questions')
    if (stored) {
      const { date, count } = JSON.parse(stored)
      if (date === today) return count
    }
    return 0
  })
  const [isQuotaExceeded, setIsQuotaExceeded] = useState(false)
  const DAILY_QUESTION_LIMIT_BASIC = 3
  const DAILY_QUESTION_LIMIT_PRO = 100
  const [isProPopupVisible, setIsProPopupVisible] = useState(true)
  const [authModalMessage, setAuthModalMessage] = useState<{ title: string; description: string } | undefined>(undefined)
  const [isFeedbackModalOpen, setIsFeedbackModalOpen] = useState(false)
  const [feedbackText, setFeedbackText] = useState('')
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false)
  const [isAnnouncementModalOpen, setIsAnnouncementModalOpen] = useState(false)
  const [isProfileFormOpen, setIsProfileFormOpen] = useState(false)
  const [showProfileGuide, setShowProfileGuide] = useState(false)
  const [isScoreSetManagerOpen, setIsScoreSetManagerOpen] = useState(false)
  const [activeScoreId, setActiveScoreId] = useState<string | undefined>(undefined)
  const [scoreSuggestItems, setScoreSuggestItems] = useState<ScoreSetSuggestItem[]>([])
  const [scoreSuggestIndex, setScoreSuggestIndex] = useState(0)
  const [isScoreSuggestOpen, setIsScoreSuggestOpen] = useState(false)
  const [inputCaretPos, setInputCaretPos] = useState(0)
  const [scorePreview, setScorePreview] = useState<{ name: string; scores: Record<string, any> } | null>(null)
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [selectedAnnouncement, setSelectedAnnouncement] = useState<Announcement | null>(null)
  const [isAdmin, setIsAdmin] = useState(false)
  const [announcementForm, setAnnouncementForm] = useState({ title: '', content: '', is_pinned: false })
  const [editingAnnouncementId, setEditingAnnouncementId] = useState<string | null>(null)
  const [agentData, setAgentData] = useState<AgentData>({
    routerOutput: null,
    functionResults: null,
    mainAgentOutput: null,
    rawAnswer: null,
    logs: []
  })
  const [selectedAgentData, setSelectedAgentData] = useState<AgentData | null>(null) // 선택된 메시지의 Agent 데이터
  const [currentLog, setCurrentLog] = useState<string>('') // 현재 진행 상태 로그
  const [searchQuery, setSearchQuery] = useState<string>('') // 채팅 검색어
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false) // 검색창 열림 상태
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null) // 카테고리 선택 상태
  
  // 관리자 전용 테스트 설정
  const [testRunCount, setTestRunCount] = useState<number>(1) // 시행 횟수
  const [testRunMode, setTestRunMode] = useState<'sequential' | 'parallel'>('sequential') // 순차/병렬
  const [isTestSettingsOpen, setIsTestSettingsOpen] = useState(false) // 설정 패널 열림 상태
  const [thinkingMode, setThinkingMode] = useState<boolean>(false) // Thinking 모드 (기본값 Auto)
  const [isThinkingModeModalOpen, setIsThinkingModeModalOpen] = useState(false) // Auto/Thinking 선택 모달
  const [thinkingModeModalAnchor, setThinkingModeModalAnchor] = useState<{ top: number; left: number; width: number } | null>(null) // 모달이 뜰 기준 위치 (Auto 버튼)
  const [sessionLockedByMasking, setSessionLockedByMasking] = useState(false)
  const [lockReason, setLockReason] = useState<'guest_masked' | 'auth_expired' | null>(null)
  const SCHOOL_RECORD_TOOL_SKIP_KEY = 'uniroad_skip_school_record_tool_confirm'
  const [schoolRecordToolEnabled, setSchoolRecordToolEnabled] = useState(false)
  const [isSchoolRecordToolModalOpen, setIsSchoolRecordToolModalOpen] = useState(false)
  const [isSchoolGradeInputModalOpen, setIsSchoolGradeInputModalOpen] = useState(false)
  /** 오른쪽 패널 전환: 채팅 | 성적입력 | 입시기록 메뉴 | 생기부 연동 (사이드 네비 유지) */
  const [rightPanelView, setRightPanelView] = useState<'chat' | 'grade_input' | 'school_record_menu' | 'school_record_link' | 'mock_exam_input'>('chat')
  const [schoolRecordLinked, setSchoolRecordLinked] = useState<boolean | null>(null)
  const [schoolRecordStatusLoading, setSchoolRecordStatusLoading] = useState(false)
  const [savedSchoolRecordReports, setSavedSchoolRecordReports] = useState<SavedSchoolRecordReport[]>([])
  const [savedSchoolRecordReportsLoading, setSavedSchoolRecordReportsLoading] = useState(false)
  const [showAllReports, setShowAllReports] = useState(false)
  const [pendingReportMessageId, setPendingReportMessageId] = useState<string | null>(null)
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(null)
  const [skipSchoolRecordToolConfirm, setSkipSchoolRecordToolConfirm] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SCHOOL_RECORD_TOOL_SKIP_KEY) === 'true'
    } catch {
      return false
    }
  })
  const SCORE_PREDICTION_SKIP_KEY = 'uniroad_skip_score_prediction_confirm'
  const [skipScorePredictionConfirm, setSkipScorePredictionConfirmState] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SCORE_PREDICTION_SKIP_KEY) === 'true'
    } catch {
      return false
    }
  })
  const [isScorePredictionStartModalOpen, setIsScorePredictionStartModalOpen] = useState(false)
  const [scorePredictionScoreSets, setScorePredictionScoreSets] = useState<Array<{ id: string; name: string }>>([])
  const [scorePredictionScoreSetsLoading, setScorePredictionScoreSetsLoading] = useState(false)
  const isGalaxySession = isGalaxyAppSession()
  const hasProAccess = !!user?.is_premium || isGalaxySession
  const isInputLocked = sessionLockedByMasking && !isAuthenticated
  const getRequestToken = (): string | undefined => {
    if (accessToken) return accessToken
    return localStorage.getItem('access_token') || undefined
  }

  const openThinkingModeModal = (e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    setThinkingModeModalAnchor({ top: rect.top, left: rect.left, width: rect.width })
    setIsThinkingModeModalOpen(true)
  }
  const closeThinkingModeModal = () => {
    setIsThinkingModeModalOpen(false)
    setThinkingModeModalAnchor(null)
  }
  const openProModal = () => {
    if (isGalaxySession) return
    setIsProModalOpen(true)
  }
  const fetchSchoolRecordLinkedStatus = async (): Promise<boolean> => {
    if (!isAuthenticated) return false
    const token = getRequestToken()
    if (!token) return false
    const baseUrl = API_BASE || import.meta.env.VITE_API_URL || 'http://localhost:8000'
    try {
      const res = await fetch(`${baseUrl}/api/school-record/status`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return false
      const data = await res.json()
      return data?.linked === true
    } catch {
      return false
    }
  }

  const setSkipSchoolRecordConfirm = (value: boolean) => {
    setSkipSchoolRecordToolConfirm(value)
    try {
      localStorage.setItem(SCHOOL_RECORD_TOOL_SKIP_KEY, value ? 'true' : 'false')
    } catch {
      // ignore storage errors
    }
  }

  const setSkipScorePredictionConfirm = (value: boolean) => {
    setSkipScorePredictionConfirmState(value)
    try {
      localStorage.setItem(SCORE_PREDICTION_SKIP_KEY, value ? 'true' : 'false')
    } catch {
      // ignore
    }
  }

  const handleConfirmScorePredictionStart = async () => {
    setIsScorePredictionStartModalOpen(false)
    await startNewChat()
  }

  useEffect(() => {
    if (!isScorePredictionStartModalOpen || !sessionId) return
    setScorePredictionScoreSetsLoading(true)
    listScoreSets(sessionId, getRequestToken())
      .then((items) => setScorePredictionScoreSets(items.map((i) => ({ id: i.id, name: i.name }))))
      .catch(() => setScorePredictionScoreSets([]))
      .finally(() => setScorePredictionScoreSetsLoading(false))
  }, [isScorePredictionStartModalOpen, sessionId])

  const handleSelectScoreSetForPrediction = (item: { id: string; name: string }) => {
    setIsScorePredictionStartModalOpen(false)
    const nameForQuery = item.name.startsWith('@') ? item.name : `@${item.name}`
    startNewChat()
    setInput(`${nameForQuery}으로 갈 수 있는 대학 알려줘`)
  }

  const activateSchoolRecordTool = async () => {
    setSchoolRecordStatusLoading(true)
    const linked = await fetchSchoolRecordLinkedStatus()
    setSchoolRecordLinked(linked)
    setSchoolRecordStatusLoading(false)

    if (!linked) {
      navigate('/school-record-deep?tab=link')
      return
    }

    await startNewChat()
    setSchoolRecordToolEnabled(true)
  }

  const handleConfirmSchoolRecordToolStart = async () => {
    setIsSchoolRecordToolModalOpen(false)
    await activateSchoolRecordTool()
  }

  const handleSchoolRecordShortcut = () => {
    if (!hasProAccess) {
      openProModal()
      if (window.innerWidth < 640) setIsSideNavOpen(false)
      return
    }

    if (!isAuthenticated) {
      setIsAuthModalOpen(true)
      if (window.innerWidth < 640) setIsSideNavOpen(false)
      return
    }

    if (skipSchoolRecordToolConfirm) {
      void activateSchoolRecordTool()
    } else {
      setSchoolRecordLinked(null)
      setIsSchoolRecordToolModalOpen(true)
      setSchoolRecordStatusLoading(true)
      void fetchSchoolRecordLinkedStatus()
        .then((linked) => setSchoolRecordLinked(linked))
        .finally(() => setSchoolRecordStatusLoading(false))
    }

    if (window.innerWidth < 640) setIsSideNavOpen(false)
  }
  const goToGumroadCheckout = () => {
    if (!isAuthenticated || !user?.id) {
      setIsProModalOpen(false)
      setIsAuthModalOpen(true)
      return
    }
    const requestToken = getRequestToken()
    // 관리자 결제 이력용 카드결제 신청 로그 (실패해도 결제는 계속 진행)
    fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/payments/card-checkout/attempt`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(requestToken && { Authorization: `Bearer ${requestToken}` }),
      },
      body: JSON.stringify({ amount: 2900, source: 'gumroad' }),
    }).catch(() => undefined)

    const ok = redirectToGumroadCheckout(user.id, user.email)
    if (!ok) {
      alert('결제 페이지 URL이 설정되지 않았습니다. 잠시 후 다시 시도해 주세요.')
      return
    }
    setIsProModalOpen(false)
  }
  const subscribeByBankTransfer = () => {
    setBankTransferName(user?.name || '')
    setBankTransferPhone('')
    setIsBankTransferModalOpen(true)
  }

  const submitBankTransfer = async () => {
    if (!isAuthenticated || !accessToken) {
      setIsBankTransferModalOpen(false)
      setIsAuthModalOpen(true)
      return
    }
    if (!bankTransferName.trim()) {
      alert('이름을 입력해 주세요.')
      return
    }
    if (!bankTransferPhone.trim()) {
      alert('전화번호를 입력해 주세요.')
      return
    }

    setBankTransferSubmitting(true)
    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/payments/bank-transfer/submit`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${accessToken}`,
          },
          body: JSON.stringify({
            name: bankTransferName.trim(),
            phone: bankTransferPhone.trim(),
          }),
        }
      )
      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err?.detail || '무통장입금 신청에 실패했습니다.')
      }
      setIsBankTransferModalOpen(false)
      setIsProModalOpen(false)
      alert('신청이 접수되어 Pro가 즉시 적용되었습니다. 관리자가 입금 여부를 확인합니다.')
      window.location.reload()
    } catch (e: any) {
      alert(e?.message || '무통장입금 신청 중 오류가 발생했습니다.')
    } finally {
      setBankTransferSubmitting(false)
    }
  }

  // 이미지 업로드 관련
  const [selectedImage, setSelectedImage] = useState<File | null>(null)
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null)
  
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const sendingRef = useRef(false) // 중복 전송 방지
  const abortControllerRef = useRef<AbortController | null>(null) // 스트리밍 취소용
  const searchContainerRef = useRef<HTMLDivElement>(null) // 검색창 외부 클릭 감지용
  const imageInputRef = useRef<HTMLInputElement>(null) // 이미지 파일 input ref
  const inputTextareaRef = useRef<HTMLTextAreaElement>(null)

  // 모바일 뒤로가기 버튼 처리
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      // 채팅 중일 때 (메시지가 있을 때) 뒤로가기 → 시작 화면으로
      if (messages.length > 0) {
        event.preventDefault()
        // 메시지 초기화하여 시작 화면으로 이동
        setMessages([])
        sessionStorage.removeItem('uniroad_chat_messages')
        // 히스토리에 현재 상태 다시 추가 (뒤로가기 한번 더 누르면 종료되도록)
        window.history.pushState({ chatStarted: false }, '')
      }
      // 시작 화면에서 뒤로가기 → 앱 종료 (기본 동작)
    }

    // 초기 히스토리 상태 설정
    if (messages.length === 0) {
      window.history.replaceState({ chatStarted: false }, '')
    } else {
      window.history.replaceState({ chatStarted: true }, '')
      window.history.pushState({ chatStarted: true }, '')
    }

    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [messages.length])

  // 메시지가 추가될 때 히스토리 상태 업데이트
  useEffect(() => {
    if (messages.length > 0) {
      // 채팅이 시작되면 히스토리에 상태 추가
      const currentState = window.history.state
      if (!currentState?.chatStarted) {
        window.history.pushState({ chatStarted: true }, '')
      }
    }
  }, [messages.length])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // 공지사항 목록 가져오기
  useEffect(() => {
    fetchAnnouncements()
    if (isAuthenticated) {
      checkAdminStatus()
      
      // OAuth 마이그레이션 후 세션 자동 선택
      const migratedSessionId = sessionStorage.getItem('uniroad_migrated_session_id')
      if (migratedSessionId) {
        console.log('🔄 OAuth 마이그레이션된 세션 자동 선택:', migratedSessionId)
        sessionStorage.removeItem('uniroad_migrated_session_id')
        // 세션 목록 로드 후 해당 세션 선택
        loadSessions().then(() => {
          selectSession(migratedSessionId)
        })
      }
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
  // API 호출용 세션은 항상 getSessionId()로 통일해 events와 session_chat_messages 연동 유지
  useEffect(() => {
    const savedChatMessages = sessionStorage.getItem('uniroad_chat_messages')

    if (savedChatMessages && messages.length === 0 && !currentSessionId) {
      try {
        const parsed = JSON.parse(savedChatMessages)
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed)
          setSessionId(getSessionId())
        }
      } catch (e) {
        console.error('채팅 메시지 복구 실패:', e)
      }
    }
  }, [])

  // savedMessages가 변경되면 로컬 messages 상태에 동기화
  useEffect(() => {
    if (savedMessages && savedMessages.length > 0) {
      const convertedMessages: Message[] = savedMessages.map(msg => ({
        id: msg.id,
        text: msg.content,
        isUser: msg.role === 'user',
        sources: msg.sources,
        source_urls: msg.source_urls,
      }))
      setMessages(convertedMessages)
    } else if (savedMessages && savedMessages.length === 0 && currentSessionId && !isStreamingRef.current) {
      setMessages([])
    }
  }, [savedMessages, currentSessionId])

  const fetchAnnouncements = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/announcements/`)
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

      const response = await fetch(`${API_BASE}/api/announcements/check-admin/me`, {
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

      const response = await fetch(`${API_BASE}/api/announcements/`, {
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

      const response = await fetch(`${API_BASE}/api/announcements/${editingAnnouncementId}`, {
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

      const response = await fetch(`${API_BASE}/api/announcements/${id}`, {
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
    setSessionLockedByMasking(false)
    setLockReason(null)
    setAgentData({
      routerOutput: null,
      functionResults: null,
      mainAgentOutput: null,
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
    const mentionCtx = getMentionContext(input, inputCaretPos)
    if (!mentionCtx) {
      setIsScoreSuggestOpen(false)
      setScoreSuggestItems([])
      return
    }

    const debounce = setTimeout(async () => {
      try {
        const token = getRequestToken()
        const items = await suggestScoreSets(mentionCtx.query, sessionId, token || undefined)
        setScoreSuggestItems(items || [])
        setScoreSuggestIndex(0)
        setIsScoreSuggestOpen((items || []).length > 0)
      } catch {
        setIsScoreSuggestOpen(false)
        setScoreSuggestItems([])
      }
    }, 120)

    return () => clearTimeout(debounce)
  }, [input, inputCaretPos, sessionId])

  const applyScoreSuggestion = (item: ScoreSetSuggestItem) => {
    const textarea = inputTextareaRef.current
    const caretPos = textarea?.selectionStart ?? inputCaretPos
    const mentionCtx = getMentionContext(input, caretPos)
    if (!mentionCtx) return

    const safeName = item.name.startsWith('@') ? item.name.slice(1) : item.name
    const replacement = `@${safeName} `
    const nextInput = `${input.slice(0, mentionCtx.start)}${replacement}${input.slice(mentionCtx.end)}`
    const nextCaret = mentionCtx.start + replacement.length

    setInput(nextInput)
    setInputCaretPos(nextCaret)
    setIsScoreSuggestOpen(false)
    setScoreSuggestItems([])
    setActiveScoreId(item.id)

    requestAnimationFrame(() => {
      if (!textarea) return
      textarea.focus()
      textarea.setSelectionRange(nextCaret, nextCaret)
    })
  }

  const handleInputChange = (value: string, caretPos: number) => {
    setInput(value)
    setInputCaretPos(caretPos)
  }

  const renderInputOverlay = (text: string) => {
    if (!text) return <>{'\u00A0'}</>
    const mentionRegex = /(@[가-힣a-zA-Z0-9_]{1,10})/g
    const parts = text.split(mentionRegex)
    if (parts.length <= 1) return <>{text}</>
    return (
      <>
        {parts.map((part, idx) => {
          if (mentionRegex.test(part)) {
            mentionRegex.lastIndex = 0
            return (
              <span key={idx} style={{ backgroundColor: '#eef2ff', color: '#4338ca', borderRadius: '9999px', boxShadow: '-4px 0 0 #eef2ff, 4px 0 0 #eef2ff, 0 0 0 1px #e0e7ff' }}>{part}</span>
            )
          }
          return <span key={idx}>{part}</span>
        })}
      </>
    )
  }

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (isScoreSuggestOpen && scoreSuggestItems.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setScoreSuggestIndex((prev) => (prev + 1) % scoreSuggestItems.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setScoreSuggestIndex((prev) => (prev - 1 + scoreSuggestItems.length) % scoreSuggestItems.length)
        return
      }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault()
        applyScoreSuggestion(scoreSuggestItems[scoreSuggestIndex])
        return
      }
      if (e.key === 'Escape') {
        setIsScoreSuggestOpen(false)
        return
      }
    }

    if (e.key === 'Backspace') {
      const ta = e.currentTarget
      const pos = ta.selectionStart
      const selEnd = ta.selectionEnd
      if (pos === selEnd && pos > 0) {
        const mentionRegex = /@[가-힣a-zA-Z0-9_]{1,10}/g
        let match: RegExpExecArray | null
        while ((match = mentionRegex.exec(input)) !== null) {
          const start = match.index
          const end = start + match[0].length
          if (pos > start && pos <= end) {
            e.preventDefault()
            const newVal = input.slice(0, start) + input.slice(end)
            setInput(newVal)
            setInputCaretPos(start)
            requestAnimationFrame(() => {
              if (inputTextareaRef.current) {
                inputTextareaRef.current.selectionStart = start
                inputTextareaRef.current.selectionEnd = start
              }
            })
            return
          }
        }
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  useEffect(() => {
    // 세션이 변경되었을 때
    if (currentSessionId !== prevSessionIdRef.current) {
      prevSessionIdRef.current = currentSessionId
      setActiveScoreId(undefined)

      if (currentSessionId && isAuthenticated) {
        // API 호출용 sessionId 업데이트
        setSessionId(currentSessionId)
        // 메시지는 loadMessages가 완료되면 savedMessages에 반영되고, 아래 useEffect에서 처리됨
      } else if (!currentSessionId) {
        // 새 채팅인 경우 — 트래킹과 동일한 user_session 유지
        setMessages([])
        setSessionId(getSessionId())
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
    const trimmedMessage = messageToSend.trim()
    const quickExampleResponse = !selectedImage ? getQuickExampleResponse(trimmedMessage) : undefined
    
    // 일일 질문 횟수 체크 (로그인한 유저만)
    const dailyLimit = hasProAccess ? DAILY_QUESTION_LIMIT_PRO : DAILY_QUESTION_LIMIT_BASIC
    if (isAuthenticated && dailyQuestionCount >= dailyLimit) {
      setIsQuotaExceeded(true)
      return
    }
    
    // 중복 전송 방지 (더블 클릭, 빠른 Enter 연타 방지)
    // 이미지가 있으면 텍스트 없이도 전송 가능
    if ((!trimmedMessage && !selectedImage) || isLoading || sendingRef.current || isInputLocked) {
      console.log('🚫 전송 차단:', { 
        hasInput: !!trimmedMessage, 
        hasImage: !!selectedImage,
        isLoading, 
        alreadySending: sendingRef.current,
        isInputLocked,
      })
      return
    }

    // 예시 질문 하드코딩 응답: API 호출 없이 빠르게 반환
    if (quickExampleResponse) {
      const userInput = trimmedMessage
      const userMessageId = Date.now().toString()
      const botMessageId = (Date.now() + 1).toString()

      sendingRef.current = true
      isStreamingRef.current = true
      setInput('')
      setIsLoading(true)
      setCurrentLog('⚡ 빠른 답변을 준비하는 중...')

      setMessages((prev) => [
        ...prev,
        { id: userMessageId, text: userInput, isUser: true, scoreMentions: extractScoreMentions(userInput) },
        { id: botMessageId, text: '', isUser: false, isStreaming: true },
      ])

      window.setTimeout(() => {
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === botMessageId
              ? { ...msg, text: quickExampleResponse, isStreaming: false }
              : msg
          )
        )
        setIsLoading(false)
        setCurrentLog('')
        sendingRef.current = false
        isStreamingRef.current = false
      }, 1000)

      return
    }

    // 일일 질문 횟수 증가 (로그인한 유저만)
    if (isAuthenticated) {
      const newCount = dailyQuestionCount + 1
      setDailyQuestionCount(newCount)
      localStorage.setItem('uniroad_daily_questions', JSON.stringify({
        date: new Date().toDateString(),
        count: newCount
      }))
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
      scoreMentions: extractScoreMentions(userInput),
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
      routerOutput: null,
      functionResults: null,
      mainAgentOutput: null,
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

          // 비로그인 체험 응답은 마스킹 처리 + 현재 세션 입력 잠금
          const shouldMask = response.require_login === true
          if (shouldMask) {
            setLockReason('guest_masked')
            setSessionLockedByMasking(true)
          } else if (!isAuthenticated) {
            setLockReason(null)
            setSessionLockedByMasking(false)
          }

          // 현재 agentData 스냅샷 저장 (메시지에 포함시키기 위해)
          const currentAgentData = {
            routerOutput: response.router_output || null,
            functionResults: response.function_results || null,
            mainAgentOutput: response.response,
            rawAnswer: response.raw_answer || null,
            logs: [...agentData.logs]  // 현재까지의 로그 복사
          }

          // 스트리밍 봇 메시지를 최종 메시지로 업데이트 (sources, used_chunks, agentData 등 추가)
          setMessages((prev) => prev.map(msg => 
            msg.id === streamingBotMessageId
              ? {
                  ...msg,
                  text: response.response || msg.text,  // 최종 응답으로 교체 (또는 스트리밍된 텍스트 유지)
                  sources: response.sources,
                  source_urls: response.source_urls,
                  used_chunks: response.used_chunks,
                  isStreaming: false,  // 스트리밍 완료
                  isMasked: shouldMask,  // 마스킹 여부
                  agentData: currentAgentData,  // Agent 디버그 데이터 저장
                }
              : msg
          ))
          console.log('✅ 스트리밍 완료:', response.response?.substring(0, 50) || '(스트리밍 텍스트)', shouldMask ? '(마스킹됨)' : '')

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
            routerOutput: response.router_output || null,
            functionResults: response.function_results || null,
            mainAgentOutput: response.response,
            rawAnswer: response.raw_answer || null
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
            conversationHistory: messages.map(m => `${m.isUser ? 'User' : 'Bot'}: ${m.text}`),
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

          // 인증 토큰 만료/검증 실패 - 로그인 모달 즉시 표시
          if (error === '__AUTH_REQUIRED__') {
            setMessages((prev) => prev.filter(msg => msg.id !== userMessage.id && msg.id !== streamingBotMessageId))
            setLockReason('auth_expired')
            setSessionLockedByMasking(false)
            setAuthModalMessage({
              title: '다시 로그인이 필요해요',
              description: '세션이 만료되어 인증이 해제되었습니다. 다시 로그인하면 이어서 사용할 수 있어요.',
            })
            setIsAuthModalOpen(true)
            setIsLoading(false)
            setCurrentLog('')
            return
          }
          
          // 비로그인 사용자 Rate Limit 초과 - 로그인 유도
          if (error === '__RATE_LIMIT_GUEST__') {
            setMessages((prev) => prev.filter(msg => msg.id !== streamingBotMessageId))
            setLockReason('guest_masked')
            setSessionLockedByMasking(true)
            setAuthModalMessage({
              title: '로그인이 필요해요',
              description: '비로그인 체험이 완료되었습니다. 로그인하면 계속 이어서 사용할 수 있어요.',
            })
            setIsAuthModalOpen(true)
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
      
      const onScoreReviewRequiredCallback = (payload: ScoreReviewRequiredEvent) => {
          if (abortController.signal.aborted) return

          console.log('🟢 score_review_required 수신:', payload)

          setMessages((prev) => prev.map(msg =>
            msg.id === streamingBotMessageId
              ? {
                  ...msg,
                  text: '',
                  isStreaming: false,
                  scoreReview: {
                    pendingId: payload.pending_id,
                    titleAuto: payload.title_auto,
                    scores: payload.scores || {},
                  },
                }
              : msg
          ))

          setCurrentLog('')
          setIsLoading(false)
        }

      const hasScoreMention = /@[가-힣a-zA-Z0-9_]{1,10}/.test(userInput)
      const scoreIdForRequest = hasScoreMention ? activeScoreId : undefined

      // 이미지가 있으면 이미지와 함께 전송, 없으면 일반 전송
      const requestToken = getRequestToken()
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
          requestToken,  // 인증 토큰 전달
          onScoreReviewRequiredCallback,
          scoreIdForRequest,
          schoolRecordToolEnabled
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
          requestToken,  // 인증 토큰 전달
          thinkingMode,  // Thinking 모드 전달
          onScoreReviewRequiredCallback,
          scoreIdForRequest,
          schoolRecordToolEnabled
        )
      }
    } catch (error: any) {
      // AbortError는 무시 (사용자가 새 채팅을 시작한 경우)
      if (error?.name === 'AbortError') {
        console.log('요청이 취소되었습니다.')
        return
      }
      
      console.error('채팅 오류:', error)
      const isNetworkError = !error?.response && (error?.message?.includes('Failed') || error?.code === 'ERR_NETWORK' || error?.message?.includes('network'))
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: isNetworkError
          ? '서버에 연결할 수 없습니다. 인터넷 연결을 확인하고, 앱이라면 uni2road.com 서버가 켜져 있는지 확인해 주세요.'
          : '죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해주세요.',
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

  const isSchoolRecordReportMessage = (content: string): boolean => {
    const text = String(content || '')
    return (
      text.includes('# 0. 평가기준 설명') ||
      text.includes('# 0. 학교별 평가기준 설명') ||
      text.includes('# 1. 기준별 적용 평가') ||
      text.includes('# 1. 대학별 기준 적용 평가') ||
      text.includes('부록 A. 학년별 과목 세특 확장 평가') ||
      text.includes('## 답변 후 꼬리 질문')
    )
  }

  const cleanReportText = (content: string): string => {
    return String(content || '')
      .replace(/<cite[^>]*>([\s\S]*?)<\/cite>/g, '$1')
      .replace(/[#*`>|[\]]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
  }

  const buildSavedReportTitle = (question: string, reportContent: string): string => {
    const q = String(question || '').trim()
    if (q) return q.length > 36 ? `${q.slice(0, 36)}...` : q
    const cleaned = cleanReportText(reportContent)
    if (!cleaned) return '생활기록부 심층 분석 리포트'
    return cleaned.length > 36 ? `${cleaned.slice(0, 36)}...` : cleaned
  }

  const buildSavedReportDescription = (reportContent: string): string => {
    const cleaned = cleanReportText(reportContent)
    if (!cleaned) return '생기부 기반 분석 리포트입니다.'
    return cleaned.length > 120 ? `${cleaned.slice(0, 120)}...` : cleaned
  }

  const openSavedSchoolRecordReport = async (report: SavedSchoolRecordReport) => {
    setSelectedCategory(null)
    setPendingReportMessageId(String(report.messageId || ''))
    await selectSession(report.sessionId)
  }

  useEffect(() => {
    if (!pendingReportMessageId || messages.length === 0) return
    const target = document.getElementById(`chat-message-${pendingReportMessageId}`)
    if (!target) return

    target.scrollIntoView({ behavior: 'smooth', block: 'center' })
    setHighlightedMessageId(pendingReportMessageId)
    setPendingReportMessageId(null)

    const timer = window.setTimeout(() => {
      setHighlightedMessageId((prev) => (prev === pendingReportMessageId ? null : prev))
    }, 1800)
    return () => window.clearTimeout(timer)
  }, [pendingReportMessageId, messages])

  useEffect(() => {
    if (!isAuthenticated || !schoolRecordToolEnabled) {
      setSavedSchoolRecordReports([])
      setSavedSchoolRecordReportsLoading(false)
      return
    }
    if (messages.length > 0) {
      setSavedSchoolRecordReportsLoading(false)
      return
    }

    let cancelled = false
    const baseUrl = API_BASE || import.meta.env.VITE_API_URL || 'http://localhost:8000'
    const token = getRequestToken()

    const loadSavedReports = async () => {
      try {
        setSavedSchoolRecordReportsLoading(true)
        if (!token) {
          if (!cancelled) setSavedSchoolRecordReports([])
          return
        }

        const targetSessions = (sessions || []).slice(0, 12)
        if (targetSessions.length === 0) {
          if (!cancelled) setSavedSchoolRecordReports([])
          return
        }

        const perSessionReports = await Promise.all(
          targetSessions.map(async (session) => {
            try {
              const res = await fetch(`${baseUrl}/api/sessions/${session.id}/messages`, {
                headers: { Authorization: `Bearer ${token}` },
              })
              if (!res.ok) return [] as SavedSchoolRecordReport[]
              const rows = await res.json()
              const list = Array.isArray(rows) ? rows : []
              const reports: SavedSchoolRecordReport[] = []

              list.forEach((row: any, idx: number) => {
                if (String(row?.role || '') !== 'assistant') return
                const content = String(row?.content || '')
                if (!isSchoolRecordReportMessage(content)) return

                let question = ''
                for (let i = idx - 1; i >= 0; i -= 1) {
                  if (String(list[i]?.role || '') === 'user') {
                    question = String(list[i]?.content || '').trim()
                    break
                  }
                }

                reports.push({
                  id: `${session.id}:${String(row?.message_id || row?.id || idx)}`,
                  sessionId: session.id,
                  messageId: String(row?.id || row?.message_id || idx),
                  title: buildSavedReportTitle(question, content),
                  description: buildSavedReportDescription(content),
                  question,
                  createdAt: String(row?.created_at || session.updated_at || ''),
                })
              })

              return reports
            } catch {
              return [] as SavedSchoolRecordReport[]
            }
          })
        )

        const merged = perSessionReports
          .flat()
          .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
          .slice(0, 9)

        if (!cancelled) setSavedSchoolRecordReports(merged)
      } finally {
        if (!cancelled) setSavedSchoolRecordReportsLoading(false)
      }
    }

    void loadSavedReports()
    return () => {
      cancelled = true
    }
  }, [isAuthenticated, schoolRecordToolEnabled, sessions, messages.length])

  const schoolRecordResearchSuggestions = [
    '내 생기부 기준으로 학생부종합전형 유리한 대학/학과 10개를 근거와 함께 정리해줘',
    '교과/비교과를 함께 보고 내 강점과 약점을 평가해줘',
    '면접에서 물어볼 가능성이 높은 질문 15개를 만들어줘',
    '지원 전략을 상향·적정·안정 3단계로 나눠서 제안해줘',
  ]

  const schoolRecordResearchReports = [
    {
      title: '학생부종합 지원 전략 리포트',
      description: '교과·비교과·세특을 통합 분석해 지원 가능 대학군과 위험 요소를 정리합니다.',
      question: '내 생기부를 바탕으로 학생부종합 지원 전략 리포트를 작성해줘. 대학군을 상향/적정/안정으로 나눠줘.',
    },
    {
      title: '세특 기반 면접 대비 리포트',
      description: '활동 맥락과 전공 연계성을 기준으로 예상 질문과 답변 프레임을 구성합니다.',
      question: '내 생기부 세특을 기반으로 면접 예상 질문 20개와 답변 포인트를 만들어줘.',
    },
    {
      title: '학년별 성장 스토리 리포트',
      description: '1~3학년 흐름을 분석해 자기소개서/면접에서 활용 가능한 스토리 라인을 정리합니다.',
      question: '1학년부터 3학년까지의 성장 흐름을 스토리로 정리하고, 자기소개에 활용할 핵심 문장을 만들어줘.',
    },
  ]

  const startSchoolRecordResearch = (question: string) => {
    setSelectedCategory(null)
    void handleSend(question)
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
        routerOutput={selectedAgentData?.routerOutput || agentData.routerOutput}
        functionResults={selectedAgentData?.functionResults || agentData.functionResults}
        mainAgentOutput={selectedAgentData?.mainAgentOutput || agentData.mainAgentOutput}
        rawAnswer={selectedAgentData?.rawAnswer || agentData.rawAnswer}
        logs={selectedAgentData?.logs || agentData.logs}
        isOpen={isAgentPanelOpen}
        onClose={() => {
          setIsAgentPanelOpen(false)
          setSelectedAgentData(null)
        }}
      />

      <div className={`flex h-screen bg-white relative transition-all duration-300 ${
        isAgentPanelOpen ? 'w-1/2' : 'w-full'
      }`}>
        {/* 사이드 네비게이션 */}
        <div
          className={`fixed top-0 left-0 h-full w-56 z-50 transform transition-transform duration-300 ease-in-out ${
            isSideNavOpen ? 'translate-x-0' : '-translate-x-full'
          } sm:fixed sm:z-40 bg-gray-50`}
        >
        <div className="h-full flex flex-col">
          {/* 상단: 닫기(왼쪽) + 채팅 기록 검색(오른쪽) */}
          <div className="flex items-center justify-between px-4 py-4 border-b border-gray-200 bg-gray-50">
            <button
              onClick={() => setIsSideNavOpen(false)}
              className="p-2 -ml-1 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              title="사이드바 닫기"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <button
              onClick={() => setIsSearchOpen(!isSearchOpen)}
              className="p-2 -mr-1 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
              title="채팅 기록 검색"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </button>
          </div>

          {/* 메뉴: 새 채팅, 내 입시 기록 연동하기 (깔끔한 리스트 스타일) */}
          <nav className="px-4 pt-5 pb-4">
            <button
              onClick={() => {
                handleNewChat()
                if (window.innerWidth < 640) setIsSideNavOpen(false)
              }}
              className="w-full flex items-center gap-3 px-2 py-3 rounded-lg transition-colors text-left text-gray-800 hover:bg-gray-100/80"
            >
              <span className="flex items-center justify-center w-5 h-5 text-gray-600">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </span>
              <span className="text-xs font-medium text-gray-800">새 채팅</span>
            </button>
            <button
              onClick={() => {
                if (!isAuthenticated) {
                  alert('로그인이 필요합니다.')
                  trackUserAction('login_modal_open', 'school_record_link')
                  sessionStorage.setItem('uniroad_login_modal_source', 'school_record_link')
                  setIsAuthModalOpen(true)
                  return
                }
                setRightPanelView('school_record_menu')
              }}
              className="w-full flex items-center gap-3 px-2 py-3 rounded-lg transition-colors text-left text-gray-800 hover:bg-gray-100/80"
            >
              <span className="flex items-center justify-center w-5 h-5 shrink-0">
                <img src="/folder-icon.png" alt="" className="w-5 h-5 object-contain" />
              </span>
              <span className="text-xs font-medium text-gray-800">내 입시 기록 연동하기</span>
            </button>
          </nav>

          {/* 분석 */}
          <div className="px-4 sm:px-6 pt-2 pb-2">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-bold text-gray-900">분석</h2>
            </div>
            <button
              onClick={() => handleSchoolRecordShortcut()}
              className="w-full flex items-center justify-start gap-3 pl-0 pr-2 py-3 rounded-lg transition-colors text-left text-gray-800 hover:bg-gray-100/80"
            >
              <span className="flex items-center justify-center w-6 h-6 shrink-0">
                <img src="/pen-icon.png" alt="" className="w-6 h-6 object-contain" />
              </span>
              <span className="text-xs font-medium text-gray-800">내 생활기록부 분석하기</span>
            </button>
            <button
              onClick={() => {
                if (!isAuthenticated) {
                  alert('로그인이 필요합니다.')
                  trackUserAction('login_modal_open', 'school_grade_input')
                  sessionStorage.setItem('uniroad_login_modal_source', 'school_grade_input')
                  setIsAuthModalOpen(true)
                  return
                }
                if (skipScorePredictionConfirm) {
                  setRightPanelView('grade_input')
                } else {
                  setIsScorePredictionStartModalOpen(true)
                }
              }}
              className="w-full flex items-center justify-start gap-3 pl-0 pr-2 py-3 rounded-lg transition-colors text-left text-gray-800 hover:bg-gray-100/80"
            >
              <span className="flex items-center justify-center w-6 h-6 shrink-0 -ml-0.5">
                <img src="/calculator-icon.png" alt="" className="w-6 h-6 object-contain object-left" />
              </span>
              <span className="text-xs font-medium text-gray-800">내 점수로 어디 갈 수 있을까?</span>
            </button>
          </div>

          {/* 기록 (로그인한 경우에만 표시) */}
          {isAuthenticated && (
            <div className="flex-1 px-4 sm:px-6 pb-4 overflow-y-auto custom-scrollbar">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-xs font-bold text-gray-900">기록</h2>
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
                    className="w-full px-3 py-2 pl-9 text-xs bg-gray-50 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
                          if (confirm('이 기록을 삭제하시겠습니까?')) {
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
                {/* 요금제 표시 */}
                <div className="flex items-center justify-center gap-2 mb-3 px-3 py-2 bg-gray-100 rounded-lg">
                  {isGalaxySession ? (
                    <span className="text-xs font-semibold text-gray-900">앱</span>
                  ) : user?.is_premium ? (
                    <span className="text-xs font-semibold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">PRO</span>
                  ) : (
                    <span className="text-xs font-semibold text-gray-900">Basic</span>
                  )}
                </div>
                <div className="flex justify-center gap-3">
                  <a 
                    href="/policy" 
                    className="text-[10px] sm:text-xs text-gray-500 hover:text-blue-500 hover:underline transition-colors"
                  >
                    개인정보처리방침
                  </a>
                  <span className="text-gray-300">|</span>
                  <a 
                    href="/delete.html" 
                    className="text-[10px] sm:text-xs text-gray-500 hover:text-blue-500 hover:underline transition-colors"
                  >
                    회원 탈퇴
                  </a>
                </div>
                <p className="mt-2 text-center text-[10px] sm:text-xs text-gray-500">
                  문의: <a href="mailto:ceo@uni2road.com" className="hover:text-blue-500 hover:underline">ceo@uni2road.com</a>
                </p>
              </div>
            ) : (
              <div>
                <div className="flex justify-center gap-3 mb-3 sm:mb-4">
                  <a 
                    href="/policy" 
                    className="text-[10px] sm:text-xs text-gray-500 hover:text-blue-500 hover:underline transition-colors"
                  >
                    개인정보처리방침
                  </a>
                  <span className="text-gray-300">|</span>
                  <a 
                    href="/delete.html" 
                    className="text-[10px] sm:text-xs text-gray-500 hover:text-blue-500 hover:underline transition-colors"
                  >
                    회원 탈퇴
                  </a>
                </div>
                <p className="mb-3 sm:mb-4 text-center text-[10px] sm:text-xs text-gray-500">
                  문의: <a href="mailto:ceo@uni2road.com" className="hover:text-blue-500 hover:underline">ceo@uni2road.com</a>
                </p>
                <button
                  onClick={() => {
                    trackUserAction('login_modal_open', 'sidebar_login_button')
                    sessionStorage.setItem('uniroad_login_modal_source', 'sidebar_login_button')
                    setIsAuthModalOpen(true)
                  }}
                  className="w-full px-3 sm:px-4 py-2.5 sm:py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 active:bg-blue-700 transition-colors font-medium text-xs"
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
        isSideNavOpen ? 'sm:ml-56' : 'sm:ml-0'
      }`}>
        {rightPanelView === 'chat' ? (
          <>
        {/* 헤더 - 모바일과 데스크톱 분리 */}
        <header className="bg-white safe-area-top sticky top-0 z-10">
          {/* 모바일 헤더 */}
          <div className="sm:hidden pl-0 pr-4 py-3 flex justify-between items-center">
            <div className="flex items-center gap-2 -ml-1">
            {!isSideNavOpen && (
            <button
                onClick={() => setIsSideNavOpen(true)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5 text-gray-700" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            )}
              <img
                src="/로고.png"
                alt="유니로드"
                className="h-5 cursor-pointer"
                onClick={handleNewChat}
              />
            </div>
            
            <div className="flex items-center gap-2">
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
                  onClick={() => {
                    trackUserAction('login_modal_open', 'header_login_button')
                    sessionStorage.setItem('uniroad_login_modal_source', 'header_login_button')
                    setIsAuthModalOpen(true)
                  }}
                  className="px-3 py-1.5 text-sm text-blue-600 hover:text-blue-700 active:text-blue-700 transition-colors font-medium"
                >
                  로그인
                </button>
              )}
            </div>
          </div>
          
          {/* 데스크톱 헤더 */}
          <div className="hidden sm:flex pl-2 pr-6 py-4 justify-between items-center">
            <div className="flex items-center gap-2 -ml-1">
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
                alt="유니로드"
                className="h-6 cursor-pointer"
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
                  onClick={() => {
                    trackUserAction('login_modal_open', 'header_login_button')
                    sessionStorage.setItem('uniroad_login_modal_source', 'header_login_button')
                    setIsAuthModalOpen(true)
                  }}
                  className="px-4 py-2 text-sm text-blue-600 hover:text-blue-700 transition-colors font-medium"
                >
                  로그인
            </button>
              )}
            </div>
          </div>
        </header>

        {/* 채팅 영역 */}
        <div className={`flex-1 py-4 ${messages.length === 0 ? 'overflow-hidden flex flex-col justify-start px-2 sm:px-4' : 'overflow-y-auto px-[17px] sm:px-6'}`}>
          <div className={`mx-auto w-full ${messages.length === 0 ? 'max-w-[600px]' : 'max-w-[600px]'}`}>
            {messages.length === 0 ? (
              <>
              <div className="flex flex-col items-center w-full pt-5 pb-4 mx-auto px-1 sm:px-2">
                {/* 레이아웃: 제목 → 큰 입력 카드 → 하단 4개 버튼 */}
                <h2 className="text-xl sm:text-2xl font-semibold text-gray-900 text-center mb-1">
                  입시에 대한 궁금한 점을 물어보세요
                </h2>
                <p className="text-xs sm:text-sm text-gray-500 text-center mb-6">
                  출처 기반의 정확한 입시 정보를 전달해드립니다
                </p>
                {/* 빈 화면: 실제 채팅 입력창 */}
                <div className="w-full mx-auto px-1 sm:px-2 mt-6 mb-6">
                  <div className="bg-white rounded-2xl shadow-[0_2px_12px_rgba(0,0,0,0.08)] focus-within:shadow-[0_4px_20px_rgba(0,0,0,0.12)] px-4 py-2 transition-shadow duration-200">
                    <textarea
                      ref={inputTextareaRef}
                      value={input}
                      onChange={(e) => handleInputChange(e.target.value, e.target.selectionStart)}
                      onKeyDown={handleInputKeyDown}
                      placeholder="입시에 대한 궁금한 점을 물어보세요"
                      disabled={isLoading || isInputLocked}
                      rows={1}
                      className="w-full text-base bg-transparent focus:outline-none disabled:bg-gray-100 min-h-[28px] max-h-[200px] resize-none overflow-y-auto placeholder:text-gray-400"
                      style={{ height: 'auto' }}
                      onInput={(e) => {
                        const target = e.target as HTMLTextAreaElement
                        target.style.height = 'auto'
                        target.style.height = Math.min(target.scrollHeight, 200) + 'px'
                      }}
                    />
                    {isScoreSuggestOpen && scoreSuggestItems.length > 0 && (
                      <div className="mt-2 bg-white border border-gray-200 rounded-xl shadow-lg py-1 max-h-48 overflow-y-auto w-48">
                        {scoreSuggestItems.map((item, idx) => (
                          <button
                            key={`${item.id}-${item.name}`}
                            type="button"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => applyScoreSuggestion(item)}
                            className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                              idx === scoreSuggestIndex ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50 text-gray-700'
                            }`}
                          >
                            {item.name.startsWith('@') ? item.name : `@${item.name}`}
                          </button>
                        ))}
                      </div>
                    )}
                    <div className="flex items-center justify-between mt-2">
                      <div className="flex items-center gap-2">
                        {schoolRecordToolEnabled && (
                          <div className="inline-flex items-center gap-1.5 bg-amber-100 text-amber-800 rounded-full px-3 py-1 text-sm font-medium">
                            <span>생기부 분석</span>
                            <button
                              onClick={() => setSchoolRecordToolEnabled(false)}
                              className="hover:bg-amber-200 rounded-full transition-colors"
                              title="도구 끄기"
                            >
                              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={(e) => openThinkingModeModal(e)}
                          disabled={isLoading || isInputLocked}
                          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all flex items-center gap-2 ${
                            'bg-white text-gray-600 border border-transparent hover:bg-gray-100 hover:text-gray-700'
                          } disabled:opacity-50`}
                          title={thinkingMode ? 'Thinking 모드' : 'Auto 모드'}
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                          </svg>
                          <span className="text-sm">{thinkingMode ? 'Thinking' : 'Auto'}</span>
                          <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleSend()}
                          disabled={isLoading || isInputLocked || (!input.trim() && !selectedImage)}
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
                {/* 하단 4개 액션 버튼 */}
                <div className="w-full mb-6 sm:mb-10">
                  <RollingPlaceholder
                      onQuestionClick={(question) => {
                        setSelectedCategory(null) // 질문 클릭 시 카테고리 초기화
                        handleSend(question)
                      }}
                      selectedCategory={selectedCategory}
                      onCategorySelect={setSelectedCategory}
                      onCategoryExpand={(firstQuestion) => setInput(firstQuestion)}
                      isAuthenticated={isAuthenticated}
                      onLoginRequired={(message) => {
                        setAuthModalMessage(message)
                        setIsAuthModalOpen(true)
                      }}
                      onProfileRequired={() => {
                        setShowProfileGuide(true)
                        setIsProfileFormOpen(true)
                      }}
                      onSchoolRecordClick={handleSchoolRecordShortcut}
                    />
                  </div>

                  {schoolRecordToolEnabled && (
                    <div className="w-full mb-6 sm:mb-10 max-w-3xl mx-auto px-2 sm:px-4">
                      <div className="rounded-2xl border border-blue-100 bg-blue-50/50 p-4 sm:p-5">
                        <div className="flex items-center gap-2 mb-3">
                          <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-blue-100 text-blue-700">📘</span>
                          <h3 className="text-sm sm:text-base font-semibold text-gray-900">생기부 심층 분석 빠른 시작</h3>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                          {schoolRecordResearchSuggestions.map((item) => (
                            <button
                              key={item}
                              type="button"
                              onClick={() => startSchoolRecordResearch(item)}
                              className="text-left rounded-xl border border-white bg-white px-3 py-2 text-sm text-gray-700 hover:border-blue-200 hover:bg-blue-50 transition-colors"
                            >
                              {item}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="mt-4 rounded-2xl border border-gray-200 bg-white p-4 sm:p-5">
                        <div className="flex items-center justify-between mb-3">
                          <h3 className="text-sm sm:text-base font-semibold text-gray-900">최근 생기부 분석 리포트</h3>
                          {savedSchoolRecordReports.length > 3 && (
                            <button
                              type="button"
                              onClick={() => setShowAllReports((v) => !v)}
                              className="text-xs text-blue-600 hover:text-blue-700"
                            >
                              {showAllReports ? '접기' : '모두 보기'}
                            </button>
                          )}
                        </div>

                        {savedSchoolRecordReportsLoading ? (
                          <p className="text-sm text-gray-500">생성된 리포트를 불러오는 중...</p>
                        ) : savedSchoolRecordReports.length > 0 ? (
                          <div className="space-y-2">
                            {(showAllReports ? savedSchoolRecordReports : savedSchoolRecordReports.slice(0, 3)).map((report) => (
                              <button
                                key={report.id}
                                type="button"
                                onClick={() => void openSavedSchoolRecordReport(report)}
                                className="w-full text-left rounded-xl border border-gray-100 px-3 py-2 hover:bg-gray-50 transition-colors"
                              >
                                <p className="text-sm font-medium text-gray-900">{report.title}</p>
                                <p className="text-xs text-gray-500 mt-1 line-clamp-2">{report.description}</p>
                                <div className="mt-2 flex items-center justify-between">
                                  <p className="text-[11px] text-gray-400">
                                    {report.createdAt ? new Date(report.createdAt).toLocaleDateString('ko-KR') : ''}
                                  </p>
                                  <p className="text-[11px] font-medium text-blue-600">리포트 열기</p>
                                </div>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <div>
                            <div className="space-y-2">
                              {(showAllReports ? schoolRecordResearchReports : schoolRecordResearchReports.slice(0, 3)).map((report) => (
                                <button
                                  key={report.title}
                                  type="button"
                                  onClick={() => startSchoolRecordResearch(report.question)}
                                  className="w-full text-left rounded-xl border border-gray-100 px-3 py-2 hover:bg-gray-50 transition-colors"
                                >
                                  <p className="text-sm font-medium text-gray-900">{report.title}</p>
                                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">{report.description}</p>
                                  <p className="mt-2 text-[11px] font-medium text-blue-600">지금 바로 작성하기</p>
                                </button>
                              ))}
                            </div>
                            {schoolRecordResearchReports.length > 3 && (
                              <div className="mt-2 flex justify-end">
                                <button
                                  type="button"
                                  onClick={() => setShowAllReports((v) => !v)}
                                  className="text-xs text-blue-600 hover:text-blue-700"
                                >
                                  {showAllReports ? '접기' : '모두 보기'}
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  )}

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
                </div>
              </>
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
                <div
                  key={msg.id}
                  id={`chat-message-${msg.id}`}
                  className={`transition-colors duration-700 rounded-xl ${
                    highlightedMessageId === msg.id ? 'bg-blue-50/70' : ''
                  }`}
                >
                <ChatMessage
                  message={msg.text}
                  isUser={msg.isUser}
                  scoreMentions={msg.scoreMentions}
                  scoreReview={msg.scoreReview}
                  sources={msg.sources}
                  source_urls={msg.source_urls}
                  usedChunks={msg.used_chunks}
                  userQuery={userQuery}
                  isStreaming={msg.isStreaming}
                  imageUrl={msg.imageUrl}
                  onRegenerate={!msg.isUser && userQuery && index === messages.length - 1 ? () => handleRegenerate(msg.id, userQuery) : undefined}
                  onLoginClick={() => {
                    trackUserAction('login_modal_open', 'rate_limit_prompt')
                    sessionStorage.setItem('uniroad_login_modal_source', 'rate_limit_prompt')
                    setIsAuthModalOpen(true)
                  }}
                  isMasked={msg.isMasked}
                  agentData={msg.agentData}
                  isAdmin={isAdmin}
                  onAgentClick={() => {
                    if (msg.agentData) {
                      setSelectedAgentData(msg.agentData)
                      setIsAgentPanelOpen(true)
                    }
                  }}
                  onFollowUpClick={(question) => handleSend(question)}
                  onScoreReviewApprove={async (pendingId, title, scores) => {
                    try {
                      const requestToken = getRequestToken()
                      const approved = await approveScoreReview(
                        pendingId,
                        sessionId,
                        title,
                        scores,
                        requestToken
                      )
                      const approvedScoreId = approved.score_id

                      let originalQuestion = ''
                      for (let i = index - 1; i >= 0; i--) {
                        if (messages[i].isUser) {
                          originalQuestion = messages[i].text
                          break
                        }
                      }

                      setActiveScoreId(approvedScoreId)
                      setMessages((prev) => prev.map((m) =>
                        m.id === msg.id
                          ? { ...m, text: '', scoreReview: undefined, isStreaming: true }
                          : m
                      ))
                      setIsLoading(true)

                      if (originalQuestion) {
                        const abortController = new AbortController()
                        abortControllerRef.current = abortController
                        const botMsgId = msg.id

                        await sendMessageStream(
                          originalQuestion,
                          sessionId,
                          (log) => setCurrentLog(log),
                          (response) => {
                            const finalText = response.response || ''
                            setMessages((prev) => prev.map((m) =>
                              m.id === botMsgId
                                ? {
                                    ...m,
                                    text: finalText,
                                    isStreaming: false,
                                    sources: response.sources,
                                    source_urls: response.source_urls,
                                    agentData: {
                                      routerOutput: response.router_output || null,
                                      functionResults: response.function_results || null,
                                      mainAgentOutput: finalText,
                                      rawAnswer: response.raw_answer || null,
                                      logs: [],
                                    },
                                  }
                                : m
                            ))
                            setIsLoading(false)
                            setCurrentLog('')
                          },
                          (error) => {
                            setMessages((prev) => prev.map((m) =>
                              m.id === botMsgId
                                ? { ...m, text: error, isStreaming: false }
                                : m
                            ))
                            setIsLoading(false)
                            setCurrentLog('')
                          },
                          abortController.signal,
                          (chunk) => {
                            setMessages((prev) => prev.map((m) =>
                              m.id === botMsgId
                                ? { ...m, text: m.text + chunk }
                                : m
                            ))
                            scrollToBottom()
                          },
                          requestToken,
                          thinkingMode,
                          undefined,
                          approvedScoreId,
                        )
                      }
                    } catch (e) {
                      console.error('성적 검토 승인 실패:', e)
                      setMessages((prev) => prev.map((m) =>
                        m.id === msg.id
                          ? {
                              ...m,
                              text: '성적 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
                              scoreReview: undefined,
                              isStreaming: false,
                            }
                          : m
                      ))
                      setIsLoading(false)
                    }
                  }}
                  onScoreReviewSkipSession={async (pendingId) => {
                    try {
                      const requestToken = getRequestToken()
                      await skipScoreReviewSession(sessionId, pendingId, requestToken)
                      setMessages((prev) => prev.map((m) =>
                        m.id === msg.id
                          ? {
                              ...m,
                              text: '이번 세션에서는 성적 확인을 다시 묻지 않아요. 질문을 계속해 주세요.',
                              scoreReview: undefined,
                            }
                          : m
                      ))
                    } catch (e) {
                      console.error('성적 검토 스킵 실패:', e)
                    }
                  }}
                  onScoreTagClick={async (name) => {
                    try {
                      const requestToken = getRequestToken()
                      const data = await getScoreSetByName(name, sessionId, requestToken)
                      setActiveScoreId(data.id)
                      const normalizedName = data.name.startsWith('@') ? data.name : `@${data.name}`
                      setScorePreview({
                        name: normalizedName,
                        scores: data.scores || {},
                      })
                    } catch (e) {
                      console.error('성적표 조회 실패:', e)
                      alert('성적표를 불러오지 못했습니다.')
                    }
                  }}
                />
                </div>
              )
            })}

            {isLoading && (
              <div className="flex justify-start mb-4">
                {schoolRecordToolEnabled ? (
                  <SchoolRecordResearchProgress logs={agentData.logs} />
                ) : (
                  <ThinkingProcess logs={agentData.logs} />
                )}
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
                <div className="max-w-[600px] mx-auto">
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
              <div className="max-w-[600px] mx-auto">
                <div className="bg-gray-50 rounded-3xl focus-within:ring-2 focus-within:ring-blue-500 px-3 sm:px-4 py-2 sm:py-3">
                  {isInputLocked && lockReason === 'guest_masked' && (
                    <div className="mb-2 rounded-lg bg-amber-50 px-3 py-2 text-xs sm:text-sm text-amber-700">
                      로그인하면 계속 이어서 사용할 수 있어요.
                    </div>
                  )}
                  {/* 텍스트 입력 영역 */}
                  <textarea
                    ref={inputTextareaRef}
                    value={input}
                    onChange={(e) => handleInputChange(e.target.value, e.target.selectionStart)}
                    onKeyDown={handleInputKeyDown}
                    placeholder="입시에 대한 궁금한 점을 물어보세요"
                    disabled={isLoading || isInputLocked}
                    rows={1}
                    className="w-full text-base bg-transparent focus:outline-none disabled:bg-gray-100 min-h-[28px] sm:min-h-[32px] max-h-[200px] resize-none overflow-y-auto placeholder:text-gray-400"
                    style={{ height: 'auto' }}
                    onInput={(e) => {
                      const target = e.target as HTMLTextAreaElement
                      target.style.height = 'auto'
                      target.style.height = Math.min(target.scrollHeight, 200) + 'px'
                    }}
                  />
                  {isScoreSuggestOpen && scoreSuggestItems.length > 0 && (
                    <div className="mt-2 bg-white border border-gray-200 rounded-xl shadow-lg py-1 max-h-48 overflow-y-auto w-48">
                      {scoreSuggestItems.map((item, idx) => (
                        <button
                          key={`${item.id}-${item.name}`}
                          type="button"
                          onMouseDown={(e) => e.preventDefault()}
                          onClick={() => applyScoreSuggestion(item)}
                          className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                            idx === scoreSuggestIndex ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50 text-gray-700'
                          }`}
                        >
                          {item.name.startsWith('@') ? item.name : `@${item.name}`}
                        </button>
                      ))}
                    </div>
                  )}
                  
                  {/* 하단 영역: 버튼들 + 전송 버튼 */}
                  <div className="flex items-center justify-between mt-2">
                    <div className="flex items-center gap-2">
                    </div>
                    
                    {/* 응답 모드 선택(Auto/Thinking) + 전송 버튼 */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => openThinkingModeModal(e)}
                        disabled={isLoading || isInputLocked}
                        className={`px-2.5 py-1.5 rounded-full text-xs font-medium transition-all flex items-center gap-1 ${
                          'bg-white text-gray-600 border border-transparent hover:bg-gray-100 hover:text-gray-700'
                        } disabled:opacity-50`}
                        title={thinkingMode ? 'Thinking 모드' : 'Auto 모드'}
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <span className="text-sm">{thinkingMode ? 'Thinking' : 'Auto'}</span>
                        <svg className="w-3.5 h-3.5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                        </svg>
                      </button>
                      <button
                        onClick={() => handleSend()}
                        disabled={isLoading || isInputLocked || (!input.trim() && !selectedImage)}
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
          </div>
        )}
          </>
        ) : (
          <>
            <div className="bg-white safe-area-top sticky top-0 z-10 border-b border-gray-200 px-4 py-3 flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                if (rightPanelView === 'school_record_link' || rightPanelView === 'mock_exam_input') setRightPanelView('school_record_menu')
                else setRightPanelView('chat')
              }}
                className="p-2 -ml-1 rounded-lg hover:bg-gray-100 transition-colors flex items-center gap-2 text-gray-700"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
                <span className="text-sm font-medium">
                  {rightPanelView === 'school_record_link' || rightPanelView === 'mock_exam_input' ? '입시 기록 메뉴로' : '채팅으로 돌아가기'}
                </span>
              </button>
            </div>
            <div className="flex-1 overflow-auto min-h-0">
              {rightPanelView === 'grade_input' && (
                <SchoolGradeInputModal
                  embedded
                  isOpen
                  onClose={() => setRightPanelView('chat')}
                  onRequireSchoolRecordLink={() => setRightPanelView('school_record_menu')}
                  onOpenMockExamInput={() => setRightPanelView('mock_exam_input')}
                />
              )}
              {rightPanelView === 'mock_exam_input' && (
                <ScoreSetManagerModal
                  embedded
                  isOpen
                  onClose={() => setRightPanelView('school_record_menu')}
                  sessionId={sessionId}
                  token={getRequestToken()}
                  onUseScoreSet={(scoreSetId, scoreSetName) => {
                    setActiveScoreId(scoreSetId)
                    setInput((prev) => (prev.trim() ? `${prev} ${scoreSetName} ` : `${scoreSetName} `))
                    setRightPanelView('chat')
                  }}
                />
              )}
              {rightPanelView === 'school_record_menu' && (
                <div className="p-6 max-w-2xl mx-auto">
                  <h1 className="text-xl font-bold text-gray-900 mb-6">입시 기록 연동</h1>
                  <div className="rounded-2xl bg-blue-50/80 border border-blue-100 p-5 sm:p-6 mb-8">
                    <p className="font-semibold text-gray-900 mb-1">신뢰할 수 있는 자료를 한 곳에 모아, 더 깊이 있는 답변을 받아보세요.</p>
                    <p className="text-sm text-gray-600">생활기록부, 내신 성적, 모의고사 성적을 연동할 수 있어요.</p>
                    <div className="mt-4 flex flex-wrap gap-2 justify-end opacity-70">
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-700 text-xs font-medium">W</span>
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded bg-blue-200 text-blue-700 text-xs font-medium">X</span>
                      <span className="inline-flex items-center justify-center w-8 h-8 rounded bg-blue-100 text-blue-700 text-xs font-medium">PDF</span>
                      <svg className="w-8 h-8 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="relative group">
                      <button
                        type="button"
                        onClick={() => setRightPanelView('school_record_link')}
                        className="w-full flex items-center gap-3 p-4 rounded-xl border-2 border-dashed border-blue-200 bg-white hover:border-blue-300 hover:bg-blue-50/50 transition-colors text-left"
                      >
                        <span className="flex items-center justify-center w-10 h-10 rounded-full bg-blue-100 text-blue-600">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                        </span>
                        <span className="font-medium text-gray-900">생활기록부 연동하기</span>
                      </button>
                      <div className="absolute top-full left-0 right-0 mt-2 px-4 py-3 rounded-xl border border-blue-200 bg-white shadow-md text-sm opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-opacity z-10 pointer-events-none">
                        <p className="font-medium text-gray-900">생활기록부를 연동하고 더 많은 기능을 즐겨보세요</p>
                        <p className="text-xs text-gray-600 mt-1">연동하는 법을 할 줄 몰라도 좋아요 차근차근 알려줄게요</p>
                      </div>
                    </div>
                    <div className="relative group">
                      <button
                        type="button"
                        onClick={() => setRightPanelView('grade_input')}
                        className="w-full flex items-center gap-3 p-4 rounded-xl border-2 border-dashed border-blue-200 bg-white hover:border-blue-300 hover:bg-blue-50/50 transition-colors text-left"
                      >
                        <span className="flex items-center justify-center w-10 h-10 rounded-full bg-blue-100 text-blue-600">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                        </span>
                        <span className="font-medium text-gray-900">내신 성적 입력하기</span>
                      </button>
                      <div className="absolute top-full left-0 right-0 mt-2 px-4 py-3 rounded-xl border border-blue-200 bg-white shadow-md text-sm opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-opacity z-10 pointer-events-none">
                        <p className="font-medium text-gray-900">고등학교 내신을 입력하고 더 많은 기능을 즐겨보세요</p>
                        <p className="text-xs text-gray-600 mt-1">생활기록부를 연동하면 자동으로 입력돼요</p>
                      </div>
                    </div>
                    <div className="relative group">
                      <button
                        type="button"
                        onClick={() => setRightPanelView('mock_exam_input')}
                        className="w-full flex items-center gap-3 p-4 rounded-xl border-2 border-dashed border-blue-200 bg-white hover:border-blue-300 hover:bg-blue-50/50 transition-colors text-left"
                      >
                        <span className="flex items-center justify-center w-10 h-10 rounded-full bg-blue-100 text-blue-600">
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                        </span>
                        <span className="font-medium text-gray-900">모의고사 성적 입력하기</span>
                      </button>
                      <div className="absolute top-full left-0 right-0 mt-2 px-4 py-3 rounded-xl border border-blue-200 bg-white shadow-md text-sm opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-opacity z-10 pointer-events-none">
                        <p className="font-medium text-gray-900">모의고사 성적을 입력하고 더 많은 기능을 즐겨보세요</p>
                        <p className="text-xs text-gray-600 mt-1">모의고사 성적을 몇개만 알려주어도, AI가 자동으로 채워서 분석해드려요</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {rightPanelView === 'school_record_link' && <SchoolRecordDeepAnalysisPage />}
            </div>
          </>
        )}
      </div>

      {/* Auto / Thinking 모드 선택 모달 - Auto 버튼 바로 위에 표시 */}
      {isThinkingModeModalOpen && thinkingModeModalAnchor && (
        <div
          className="fixed inset-0 z-[60]"
          onClick={closeThinkingModeModal}
          aria-hidden
        >
          <div
            className="absolute bg-white rounded-2xl shadow-2xl w-[min(300px,calc(100vw-24px))] overflow-hidden"
            style={{
              bottom: `${window.innerHeight - thinkingModeModalAnchor.top + 8}px`,
              left: `${Math.min(thinkingModeModalAnchor.left, window.innerWidth - 308)}px`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-4 pt-4 pb-4">
              <button
                onClick={() => {
                  setThinkingMode(false)
                  closeThinkingModeModal()
                }}
                className="w-full flex items-center justify-between gap-3 px-3 py-3 hover:bg-gray-50 rounded-lg transition-colors text-left"
              >
                <div>
                  <p className="font-semibold text-gray-900">Auto</p>
                  <p className="text-sm text-gray-500 mt-0.5">난이도에 따라 생각하는 시간 조정</p>
                </div>
                {!thinkingMode && (
                  <svg className="w-5 h-5 text-gray-900 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </button>
              <button
                onClick={() => {
                  if (hasProAccess) {
                    setThinkingMode(true)
                    closeThinkingModeModal()
                  } else {
                    closeThinkingModeModal()
                    openProModal()
                  }
                }}
                className="w-full flex items-center justify-between gap-3 px-3 py-3 hover:bg-gray-50 rounded-lg transition-colors text-left"
              >
                <div>
                  <p className="font-semibold text-gray-900">Thinking</p>
                  <p className="text-sm text-gray-500 mt-0.5">더 많은 자료 참고하여 더 깊이 생각</p>
                </div>
                {thinkingMode && (
                  <svg className="w-5 h-5 text-gray-900 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 로그인 모달 */}
      <AuthModal 
        isOpen={isAuthModalOpen} 
        onClose={() => {
          setIsAuthModalOpen(false)
          setAuthModalMessage(undefined)
        }}
        customMessage={authModalMessage}
        onOAuthStart={() => {
          // OAuth 리다이렉트 전에 현재 메시지를 sessionStorage에 저장
          if (messages.length > 0) {
            console.log('🔄 OAuth 시작 - 메시지 저장:', messages.length, '개')
            sessionStorage.setItem('uniroad_pending_migration', JSON.stringify({
              messages: messages.map(m => ({
                role: m.isUser ? 'user' : 'assistant',
                content: m.text,
                sources: m.sources,
                source_urls: m.source_urls
              })),
              sessionId: sessionId
            }))
          }
        }}
        onLoginSuccess={async () => {
          // 비로그인 상태에서 채팅한 내역이 있으면 마이그레이션
          // accessToken은 상태 업데이트가 비동기라 아직 null일 수 있으므로 localStorage에서 직접 가져옴
          const token = localStorage.getItem('access_token')
          if (messages.length > 0 && token) {
            try {
              console.log('🔄 채팅 내역 마이그레이션 시작:', messages.length, '개 메시지')
              const result = await migrateMessages(
                token,
                messages.map(m => ({
                  role: m.isUser ? 'user' as const : 'assistant' as const,
                  content: m.text,
                  sources: m.sources,
                  source_urls: m.source_urls
                })),
                sessionId
              )
              console.log('✅ 채팅 내역 마이그레이션 완료:', result.session_id)
              
              // 세션 ID 업데이트 (현재 메시지는 유지)
              setSessionId(result.session_id)
              
              // 세션 목록 새로고침 (백그라운드)
              loadSessions()
            } catch (error) {
              console.error('❌ 채팅 마이그레이션 실패:', error)
            }
          }
          
          // 마스킹/잠금 해제
          setMessages(prev => prev.map(msg => 
            msg.isMasked
              ? { ...msg, isMasked: false }
              : msg
          ))
          setSessionLockedByMasking(false)
          setLockReason(null)
        }}
      />

      {/* 사전신청 모달 */}
      <PreregisterModal
        isOpen={isPreregisterModalOpen}
        onClose={() => setIsPreregisterModalOpen(false)}
        userId={user?.id}
        userName={user?.name}
      />

      {/* 일일 질문 초과 모달 */}
      {isQuotaExceeded && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl max-w-sm w-full overflow-hidden animate-scaleIn">
            <div className="p-6 text-center">
              <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-8 h-8 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-xl font-bold text-gray-900 mb-2">오늘의 질문량 끝!</h3>
              <p className="text-gray-600 mb-1">일일 질문 {hasProAccess ? DAILY_QUESTION_LIMIT_PRO : DAILY_QUESTION_LIMIT_BASIC}회를 모두 사용했어요.</p>
              <p className="text-sm text-gray-500 mb-6">내일 자정에 초기화됩니다.</p>
              
              <div className="space-y-3">
                {!isGalaxySession && (
                  <button
                    onClick={() => {
                      setIsQuotaExceeded(false)
                      openProModal()
                    }}
                    className="w-full py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl font-semibold hover:from-blue-700 hover:to-purple-700 transition-all"
                  >
                    PRO 구독해서 더 많이 쓰기
                  </button>
                )}
                <button
                  onClick={() => setIsQuotaExceeded(false)}
                  className="w-full py-2 text-gray-500 hover:text-gray-700 transition-colors text-sm"
                >
                  닫기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* PRO 구독 모달 (Fake Door Test) */}
      {!isGalaxySession && isProModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full overflow-hidden animate-scaleIn border border-gray-200">
            {/* 헤더 */}
            <div className="p-6 sm:p-7 border-b border-gray-100 relative">
              <button
                onClick={() => setIsProModalOpen(false)}
                className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <h2 className="text-2xl font-bold text-gray-900 mb-1">플랜 업그레이드</h2>
              <p className="text-sm text-gray-600">유니로드 Pro, 최고의 AI 컨설턴트와 함께하세요.</p>
            </div>

            {/* 요금제 비교 카드 */}
            <div className="p-6 sm:p-7 grid grid-cols-1 md:grid-cols-2 gap-4 border-b border-gray-100">
              <div className="rounded-2xl border border-gray-200 bg-white p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-xl font-semibold text-gray-900">Basic</h3>
                  <span className="text-lg font-bold text-emerald-600">무료</span>
                </div>
                <ul className="space-y-2 text-sm text-gray-700">
                  <li className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-gray-400" />일일 {DAILY_QUESTION_LIMIT_BASIC}회 AI 상담</li>
                  <li className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-gray-400" />최신 모집 요강</li>
                  <li className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-gray-400" />성적 분석 및 대학 추천</li>
                </ul>
              </div>

              <div className="rounded-2xl border-2 border-indigo-200 bg-indigo-50/60 p-5">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <h3 className="text-xl font-semibold text-gray-900">Pro</h3>
                    <span className="text-[11px] font-semibold bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">새학기 특가 할인!</span>
                  </div>
                  <div className="flex items-end gap-2">
                    <span className="text-sm text-gray-400 line-through">25,900원</span>
                    <span className="text-lg font-bold text-gray-900">2,900원/월</span>
                  </div>
                </div>
                <ul className="space-y-2 text-sm text-gray-700">
                  <li className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />일일 {DAILY_QUESTION_LIMIT_PRO}회 AI 상담</li>
                  <li className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />심층 분석을 위한 Thinking 모드</li>
                  <li className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />학교생활기록부 완벽 분석</li>
                  <li className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />최신 기능 우선 적용</li>
                </ul>
              </div>
            </div>

            {/* 결제 버튼 */}
            <div className="px-6 sm:px-7 pb-6">
              <button
                onClick={goToGumroadCheckout}
                className="w-full py-3.5 bg-gray-900 text-white rounded-xl font-semibold hover:bg-black transition-colors"
              >
                Pro 요금제 시작하기 (카드결제)
              </button>
              <button
                onClick={subscribeByBankTransfer}
                className="w-full mt-3 py-3.5 border border-gray-200 text-gray-800 rounded-xl font-semibold hover:bg-gray-50 transition-colors"
              >
                무통장입금으로 구독하기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 무통장입금 신청 모달 */}
      {!isGalaxySession && isBankTransferModalOpen && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/55 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full border border-gray-200">
            <div className="p-5 border-b border-gray-100 flex items-start justify-between gap-4">
              <div>
                <h3 className="text-xl font-bold text-gray-900">무통장입금 신청</h3>
                <p className="text-sm text-gray-600 mt-1">입금 후 결제했습니다 버튼을 눌러주세요.</p>
              </div>
              <button
                onClick={() => setIsBankTransferModalOpen(false)}
                className="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-5 space-y-4">
              <div className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-sm">
                <p className="text-gray-600">가격</p>
                <p className="text-sm text-gray-400 line-through">25,900원</p>
                <p className="text-lg font-bold text-gray-900">2,900원</p>
                <p className="text-gray-600 mt-3">입금계좌</p>
                <p className="font-semibold text-gray-900">3333354523620</p>
                <p className="text-gray-700">카카오뱅크 (김태훈)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">이름</label>
                <input
                  value={bankTransferName}
                  onChange={(e) => setBankTransferName(e.target.value)}
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="입금자명"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">전화번호</label>
                <input
                  value={bankTransferPhone}
                  onChange={(e) => setBankTransferPhone(e.target.value)}
                  className="w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="01012345678"
                />
              </div>

              <button
                onClick={submitBankTransfer}
                disabled={bankTransferSubmitting}
                className="w-full py-3 bg-gray-900 text-white rounded-xl font-semibold hover:bg-black transition-colors disabled:opacity-60"
              >
                {bankTransferSubmitting ? '처리 중...' : '결제했습니다'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 의견 보내기 모달 */}
      {isFeedbackModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full animate-slideUp">
            {/* 헤더 */}
            <div className="relative px-6 pt-6 pb-4 border-b border-gray-100">
              <button
                onClick={() => {
                  setIsFeedbackModalOpen(false)
                  setFeedbackText('')
                }}
                className="absolute top-4 right-4 p-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
              <div className="text-center">
                <img src="/로고.png" alt="UniRoad Logo" className="h-12 mx-auto mb-3" />
                <h2 className="text-xl font-bold text-gray-900">의견 보내기</h2>
                <p className="text-sm text-gray-600 mt-2">
                  유니로드에 대한 의견을 자유롭게 남겨주세요
                </p>
              </div>
            </div>

            {/* 본문 */}
            <div className="px-6 py-6">
              <textarea
                value={feedbackText}
                onChange={(e) => setFeedbackText(e.target.value)}
                placeholder="개선 아이디어, 버그 제보, 질문 등 어떤 의견이든 환영합니다."
                className="w-full h-40 px-4 py-3 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                disabled={feedbackSubmitting}
              />
              
              {/* 버튼 */}
              <div className="mt-4 flex gap-3">
                <button
                  onClick={() => {
                    setIsFeedbackModalOpen(false)
                    setFeedbackText('')
                  }}
                  className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors font-medium"
                  disabled={feedbackSubmitting}
                >
                  취소
                </button>
                <button
                  onClick={async () => {
                    if (!feedbackText.trim()) {
                      alert('의견을 입력해주세요.')
                      return
                    }
                    
                    setFeedbackSubmitting(true)
                    try {
                      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/feedback`, {
                        method: 'POST',
                        headers: {
                          'Content-Type': 'application/json',
                          ...(accessToken && { 'Authorization': `Bearer ${accessToken}` })
                        },
                        body: JSON.stringify({
                          content: feedbackText,
                          user_id: user?.id || null
                        })
                      })
                      
                      if (response.ok) {
                        alert('소중한 의견 감사합니다!')
                        setIsFeedbackModalOpen(false)
                        setFeedbackText('')
                      } else {
                        alert('전송에 실패했습니다. 다시 시도해주세요.')
                      }
                    } catch (error) {
                      console.error('피드백 전송 오류:', error)
                      alert('전송에 실패했습니다. 다시 시도해주세요.')
                    } finally {
                      setFeedbackSubmitting(false)
                    }
                  }}
                  className="flex-1 px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-xl hover:from-blue-600 hover:to-blue-700 transition-all font-medium disabled:opacity-50"
                  disabled={feedbackSubmitting || !feedbackText.trim()}
                >
                  {feedbackSubmitting ? '전송 중...' : '보내기'}
                </button>
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

      <SchoolRecordToolStartModal
        isOpen={isSchoolRecordToolModalOpen}
        linked={schoolRecordLinked}
        loading={schoolRecordStatusLoading}
        dontAskAgain={skipSchoolRecordToolConfirm}
        confirmLabel={schoolRecordLinked === true ? '새 채팅' : '생기부 연동하기'}
        onToggleDontAskAgain={setSkipSchoolRecordConfirm}
        onClose={() => setIsSchoolRecordToolModalOpen(false)}
        onConfirm={() => { void handleConfirmSchoolRecordToolStart() }}
      />

      <SchoolRecordToolStartModal
        isOpen={isScorePredictionStartModalOpen}
        linked={true}
        loading={scorePredictionScoreSetsLoading}
        dontAskAgain={skipScorePredictionConfirm}
        confirmLabel="새 채팅"
        title="합격 예측을 시작하시겠습니까?"
        description="연동된 성적을 읽어 더 정확하게 답합니다."
        statusText={
          scorePredictionScoreSetsLoading
            ? '성적 목록을 불러오는 중...'
            : scorePredictionScoreSets.length === 0
              ? '저장된 모의고사 성적이 없습니다. 성적을 먼저 입력해 주세요.'
              : '연동된 성적을 읽어 더 정확하게 답합니다.'
        }
        scoreSets={scorePredictionScoreSets.length > 0 ? scorePredictionScoreSets : undefined}
        onSelectScoreSet={handleSelectScoreSetForPrediction}
        onToggleDontAskAgain={setSkipScorePredictionConfirm}
        onClose={() => setIsScorePredictionStartModalOpen(false)}
        onConfirm={() => { void handleConfirmScorePredictionStart() }}
      />

      <SchoolGradeInputModal
        isOpen={isSchoolGradeInputModalOpen}
        onClose={() => setIsSchoolGradeInputModalOpen(false)}
        onRequireSchoolRecordLink={() => {
          setIsSchoolGradeInputModalOpen(false)
          navigate('/school-record-deep?tab=link')
        }}
        onOpenMockExamInput={() => {
          setIsSchoolGradeInputModalOpen(false)
          // 성적 입력 모달이 닫힌 뒤 모의고사 성적 관리 모달(해당 모달) 오픈
          requestAnimationFrame(() => {
            setIsScoreSetManagerOpen(true)
          })
        }}
      />

      {/* 프로필 폼 모달 */}
      <ProfileForm 
        isOpen={isProfileFormOpen} 
        onClose={() => {
          setIsProfileFormOpen(false)
          setShowProfileGuide(false)
        }}
        showGuide={showProfileGuide}
      />

      <ScoreSetManagerModal
        isOpen={isScoreSetManagerOpen}
        onClose={() => setIsScoreSetManagerOpen(false)}
        sessionId={sessionId}
        token={getRequestToken()}
        onUseScoreSet={(scoreSetId, scoreSetName) => {
          setActiveScoreId(scoreSetId)
          setInput((prev) => (prev.trim() ? `${prev} ${scoreSetName} ` : `${scoreSetName} `))
          setIsScoreSetManagerOpen(false)
        }}
      />

      {scorePreview && (
        <div className="fixed inset-0 z-[70] bg-black/40 flex items-center justify-center p-4" onClick={() => setScorePreview(null)}>
          <div className="bg-white w-full max-w-3xl rounded-xl shadow-xl max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b px-4 py-3 flex items-center justify-between">
              <h3 className="text-lg font-bold text-gray-900">{scorePreview.name} 성적표</h3>
              <button className="text-gray-500 hover:text-gray-700 text-2xl" onClick={() => setScorePreview(null)}>
                ×
              </button>
            </div>
            <div className="p-4">
              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="text-left">
                      <th className="py-2 border-b">과목</th>
                      <th className="py-2 border-b">선택과목</th>
                      <th className="py-2 border-b">표준점수</th>
                      <th className="py-2 border-b">백분위</th>
                      <th className="py-2 border-b">등급</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(scorePreview.scores || {}).map(([subject, row]) => {
                      const scoreRow = row as Record<string, any>
                      return (
                        <tr key={subject} className="border-b border-gray-100">
                          <td className="py-2">{subject}</td>
                          <td className="py-2">{scoreRow['선택과목'] ?? scoreRow['과목명'] ?? '-'}</td>
                          <td className="py-2">{scoreRow['표준점수'] ?? '-'}</td>
                          <td className="py-2">{scoreRow['백분위'] ?? '-'}</td>
                          <td className="py-2">{scoreRow['등급'] ?? '-'}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-gray-500">읽기 전용 보기입니다.</p>
            </div>
          </div>
        </div>
      )}

      {/* PRO 업그레이드 팝업 - 웹 + 로그인한 Basic 유저에게만 표시 (PRO 유저는 숨김) */}
      {isProPopupVisible && !isGalaxySession && !isCapacitorApp() && isAuthenticated && user?.id && !user?.is_premium && (
        <div className="fixed bottom-4 right-4 z-40 group">
          <div 
            className="relative bg-[#1a1a2e] text-white rounded-2xl p-4 shadow-2xl min-w-[260px] cursor-pointer overflow-hidden border border-gray-700/50"
            onClick={(e) => {
              const target = e.target as HTMLElement
              if (target.closest('button')) return
              openProModal()
            }}
          >
            {/* 배경 별 효과 */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
              <div className="absolute w-1 h-1 bg-white rounded-full top-4 right-8 animate-pulse"></div>
              <div className="absolute w-0.5 h-0.5 bg-white/80 rounded-full top-8 right-16 animate-pulse" style={{ animationDelay: '0.5s' }}></div>
              <div className="absolute w-1 h-1 bg-white/90 rounded-full bottom-6 right-12 animate-pulse" style={{ animationDelay: '1s' }}></div>
              <div className="absolute w-0.5 h-0.5 bg-white rounded-full top-12 right-20 animate-pulse" style={{ animationDelay: '0.3s' }}></div>
              <div className="absolute w-0.5 h-0.5 bg-white/70 rounded-full bottom-10 right-6 animate-pulse" style={{ animationDelay: '0.7s' }}></div>
            </div>
            
            {/* X 버튼 - 항상 크게 표시하고 터치 영역 확대 */}
            <button
              onClick={(e) => {
                e.stopPropagation()
                setIsProPopupVisible(false)
              }}
              aria-label="업그레이드 팝업 닫기"
              className="absolute top-1.5 right-1.5 z-20 w-10 h-10 flex items-center justify-center text-gray-200 hover:text-white active:text-white transition-colors rounded-full bg-white/5 hover:bg-white/15 active:bg-white/20"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.4} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
            
            <div className="relative z-10 flex items-center gap-4">
              {/* 왼쪽: 텍스트 */}
              <div className="flex-1">
                <h3 className="text-base font-bold">유니로드 PRO</h3>
                <p className="text-sm text-gray-400">새학기 기념 90% 할인!</p>
              </div>
              
              {/* 오른쪽: 업그레이드 버튼 */}
              <div className="px-4 py-2 bg-white text-gray-900 rounded-full font-semibold text-sm whitespace-nowrap">
                업그레이드
              </div>
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  )
}
