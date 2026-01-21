import { useState, useEffect, useCallback } from 'react'
import { getSupabaseClient } from '../lib/supabase'
import { useAuth } from '../contexts/AuthContext'

export interface ChatSession {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
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
      const client = getSupabaseClient(token || undefined)

      const { data, error } = await client
        .from('chat_sessions')
        .select('*')
        .eq('user_id', user.id)
        .order('updated_at', { ascending: false })

      if (error) throw error
      setSessions(data || [])
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
      const client = getSupabaseClient(token || undefined)

      const { data, error } = await client
        .from('chat_messages')
        .select('*')
        .eq('session_id', sessionId)
        .order('created_at', { ascending: true })

      if (error) throw error
      setMessages(data || [])
    } catch (error) {
      console.error('메시지 불러오기 실패:', error)
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
      const client = getSupabaseClient(token || undefined)

      const { data, error } = await client
        .from('chat_sessions')
        .insert({
          user_id: user.id,
          title: title.substring(0, 100), // 제목 길이 제한
        })
        .select()
        .single()

      if (error) throw error
      
      // 세션 목록 새로고침
      await loadSessions()
      
      return data.id
    } catch (error) {
      console.error('세션 생성 실패:', error)
      return null
    }
  }, [isAuthenticated, user?.id, loadSessions])

  // 메시지 저장
  const saveMessage = useCallback(async (
    sessionId: string,
    role: 'user' | 'assistant',
    content: string
  ) => {
    if (!isAuthenticated) return

    try {
      const token = localStorage.getItem('access_token')
      const client = getSupabaseClient(token || undefined)

      const { error } = await client
        .from('chat_messages')
        .insert({
          session_id: sessionId,
          role,
          content,
        })

      if (error) throw error

      // 세션의 updated_at 갱신
      await client
        .from('chat_sessions')
        .update({ updated_at: new Date().toISOString() })
        .eq('id', sessionId)

      // 세션 목록 새로고침
      await loadSessions()
      
      // 메시지 목록 새로고침 (UI 업데이트를 위해)
      await loadMessages(sessionId)
    } catch (error) {
      console.error('메시지 저장 실패:', error)
    }
  }, [isAuthenticated, loadMessages, loadSessions])

  // 세션 선택
  const selectSession = useCallback(async (sessionId: string | null) => {
    setCurrentSessionId(sessionId)
    if (sessionId) {
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
      const client = getSupabaseClient(token || undefined)

      const { error } = await client
        .from('chat_sessions')
        .update({ title: title.substring(0, 100) })
        .eq('id', sessionId)

      if (error) throw error
      await loadSessions()
    } catch (error) {
      console.error('세션 제목 업데이트 실패:', error)
    }
  }, [isAuthenticated, loadSessions])

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
  }
}

