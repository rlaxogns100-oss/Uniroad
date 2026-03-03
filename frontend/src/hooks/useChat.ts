import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import { getSessionId, getUTMParams } from '../utils/tracking'

export interface ChatSession {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
  message_count?: number
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  source_urls?: string[]
  created_at: string
}

export function useChat() {
  const { user, isAuthenticated } = useAuth()
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)

  // 세션 목록 불러오기
  const loadSessions = useCallback(async () => {
    if (!isAuthenticated || !user?.id) return

    try {
      setLoading(true)
      
      const token = localStorage.getItem('access_token')
      if (!token) return

      const response = await axios.get('/api/sessions/', {
        headers: { Authorization: `Bearer ${token}` }
      })

      setSessions(response.data || [])
    } catch (error) {
      console.error('세션 목록 불러오기 실패:', error)
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated, user?.id])

  // 메시지 불러오기
  const loadMessages = useCallback(async (sessionId: string) => {
    if (!isAuthenticated) return

    try {
      setLoading(true)
      // 이전 메시지 초기화 (잘못된 메시지가 표시되는 것을 방지)
      setMessages([])
      
      const token = localStorage.getItem('access_token')
      if (!token) return

      console.log('📥 [useChat] 메시지 로드 시작:', sessionId)
      const response = await axios.get(`/api/sessions/${sessionId}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      })

      console.log('✅ [useChat] 메시지 로드 완료:', response.data?.length, '개', response.data)
      setMessages(response.data || [])
    } catch (error) {
      console.error('❌ [useChat] 메시지 불러오기 실패:', error)
      setMessages([])
    } finally {
      setLoading(false)
    }
  }, [isAuthenticated])

  // 새 세션 생성
  const createSession = useCallback(async (title: string): Promise<string | null> => {
    if (!isAuthenticated || !user?.id) return null

    try {
      const token = localStorage.getItem('access_token')
      if (!token) return null

      // UTM 정보와 브라우저 세션 ID 가져오기
      const browserSessionId = getSessionId()
      const utm = getUTMParams()

      const response = await axios.post('/api/sessions/', 
        { 
          title: title.substring(0, 100),
          browser_session_id: browserSessionId,
          utm_source: utm.utm_source,
          utm_medium: utm.utm_medium,
          utm_campaign: utm.utm_campaign,
          utm_content: utm.utm_content,
          utm_term: utm.utm_term,
          referrer: document.referrer
        },
        { headers: { Authorization: `Bearer ${token}` } }
      )

      // 세션 목록 새로고침
      await loadSessions()
      
      return response.data.id
    } catch (error) {
      console.error('세션 생성 실패:', error)
      return null
    }
  }, [isAuthenticated, user?.id, loadSessions])

  // 메시지 저장 (채팅 API에서 자동으로 저장되므로 이 함수는 deprecated)
  // 하위 호환성을 위해 유지하지만 실제로는 아무것도 하지 않음
  const saveMessage = useCallback(async (
    sessionId: string,
    role: 'user' | 'assistant',
    content: string
  ) => {
    // 채팅 API(/api/chat/stream)에서 자동으로 메시지를 저장하므로
    // 이 함수는 더 이상 필요하지 않습니다.
    console.log('saveMessage는 deprecated되었습니다. 채팅 API에서 자동 저장됩니다.')
  }, [])

  // 세션 선택
  const selectSession = useCallback(async (
    sessionId: string | null,
    options?: { skipLoad?: boolean }
  ) => {
    setCurrentSessionId(sessionId)
    if (sessionId && !options?.skipLoad) {
      await loadMessages(sessionId)
    } else {
      setMessages([])
    }
  }, [loadMessages])

  // 새 채팅 시작
  const startNewChat = useCallback(() => {
    setCurrentSessionId(null)
    setMessages([])
  }, [])

  // 세션 제목 업데이트
  const updateSessionTitle = useCallback(async (sessionId: string, title: string) => {
    if (!isAuthenticated) return

    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      await axios.patch(`/api/sessions/${sessionId}`,
        { title: title.substring(0, 100) },
        { headers: { Authorization: `Bearer ${token}` } }
      )

      await loadSessions()
    } catch (error) {
      console.error('세션 제목 업데이트 실패:', error)
    }
  }, [isAuthenticated, loadSessions])

  // 세션 삭제
  const deleteSession = useCallback(async (sessionId: string) => {
    if (!isAuthenticated) return

    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      await axios.delete(`/api/sessions/${sessionId}`,
        { headers: { Authorization: `Bearer ${token}` } }
      )

      // 삭제된 세션이 현재 선택된 세션이면 초기화
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null)
        setMessages([])
      }

      // 세션 목록 새로고침
      await loadSessions()
    } catch (error) {
      console.error('세션 삭제 실패:', error)
      throw error
    }
  }, [isAuthenticated, currentSessionId, loadSessions])

  // 초기 로드
  useEffect(() => {
    if (isAuthenticated && user?.id) {
      loadSessions()
    }
  }, [isAuthenticated, user?.id, loadSessions])

  return {
    sessions,
    currentSessionId,
    messages,
    loading,
    loadSessions,
    loadMessages,
    createSession,
    saveMessage,
    selectSession,
    startNewChat,
    updateSessionTitle,
    deleteSession,
  }
}

