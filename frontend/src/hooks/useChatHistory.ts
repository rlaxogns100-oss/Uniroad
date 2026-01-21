import { useState, useEffect } from 'react'
import axios from 'axios'

export interface ChatSession {
  id: string
  title: string
  messages: Array<{
    id: string
    text: string
    isUser: boolean
    sources?: string[]
    source_urls?: string[]
  }>
  createdAt: number
  updatedAt: number
  message_count?: number
}

export function useChatHistory() {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // API에서 세션 목록 불러오기
  useEffect(() => {
    loadSessions()
  }, [])

  const loadSessions = async () => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        setLoading(false)
        return
      }

      const response = await axios.get('/api/sessions/', {
        headers: { Authorization: `Bearer ${token}` }
      })
      
      const sessionsData = response.data.map((s: any) => ({
        id: s.id,
        title: s.title,
        messages: [],
        createdAt: new Date(s.created_at).getTime(),
        updatedAt: new Date(s.updated_at).getTime(),
        message_count: s.message_count,
      }))
      
      // 최신순 정렬 (updatedAt 기준 내림차순)
      sessionsData.sort((a, b) => b.updatedAt - a.updatedAt)
      
      setSessions(sessionsData)
      setLoading(false)
    } catch (error) {
      console.error('세션 목록 로드 실패:', error)
      setLoading(false)
    }
  }

  // 새 세션 생성
  const createNewSession = async () => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        console.error('토큰이 없습니다')
        return null
      }

      const response = await axios.post('/api/sessions/', 
        { title: '새 대화' },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      
      console.log('세션 생성 성공:', response.data)
      
      // 세션 목록을 다시 불러오기 (최신 상태 보장)
      await loadSessions()
      
      // 생성된 세션 ID 설정
      const newSessionId = response.data.id
      setCurrentSessionId(newSessionId)
      
      return newSessionId
    } catch (error: any) {
      console.error('세션 생성 실패:', error)
      if (error.response) {
        console.error('응답 데이터:', error.response.data)
        console.error('상태 코드:', error.response.status)
      }
      return null
    }
  }

  // 현재 세션 가져오기
  const getCurrentSession = () => {
    if (!currentSessionId) return null
    return sessions.find(s => s.id === currentSessionId) || null
  }

  // 세션의 메시지 불러오기
  const loadSessionMessages = async (sessionId: string) => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) return []

      const response = await axios.get(`/api/sessions/${sessionId}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      
      return response.data.map((m: any) => ({
        id: m.id,
        text: m.content,
        isUser: m.role === 'user',
        sources: m.sources || [],
        source_urls: m.source_urls || [],
      }))
    } catch (error) {
      console.error('메시지 로드 실패:', error)
      return []
    }
  }

  // 세션 업데이트 (제목만)
  const updateSession = async (sessionId: string, messages: ChatSession['messages']) => {
    // 첫 번째 사용자 메시지로 제목 자동 생성
    if (messages.length > 0 && messages[0].isUser) {
      const title = messages[0].text.substring(0, 30) + (messages[0].text.length > 30 ? '...' : '')
      
      try {
        const token = localStorage.getItem('access_token')
        if (!token) return

        await axios.patch(`/api/sessions/${sessionId}`,
          { title },
          { headers: { Authorization: `Bearer ${token}` } }
        )
        
        // 로컬 상태 업데이트 (업데이트된 세션을 최신순으로 재정렬)
        const updatedSessions = sessions.map(s => 
          s.id === sessionId ? { ...s, title, updatedAt: Date.now() } : s
        )
        // 최신순 정렬 (updatedAt 기준 내림차순)
        updatedSessions.sort((a, b) => b.updatedAt - a.updatedAt)
        setSessions(updatedSessions)
      } catch (error) {
        console.error('세션 업데이트 실패:', error)
      }
    }
  }

  // 세션 삭제
  const deleteSession = async (sessionId: string) => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      await axios.delete(`/api/sessions/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      
      setSessions(sessions.filter(s => s.id !== sessionId))
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null)
      }
    } catch (error) {
      console.error('세션 삭제 실패:', error)
    }
  }

  // 세션 선택
  const selectSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId)
    
    // 메시지 로드
    const messages = await loadSessionMessages(sessionId)
    setSessions(sessions.map(s => 
      s.id === sessionId ? { ...s, messages } : s
    ))
  }

  // 모든 히스토리 삭제
  const clearAllHistory = async () => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) return

      // 모든 세션 삭제
      await Promise.all(
        sessions.map(s => 
          axios.delete(`/api/sessions/${s.id}`, {
            headers: { Authorization: `Bearer ${token}` }
          })
        )
      )
      
      setSessions([])
      setCurrentSessionId(null)
    } catch (error) {
      console.error('전체 삭제 실패:', error)
    }
  }

  return {
    sessions,
    currentSessionId,
    currentSession: getCurrentSession(),
    loading,
    createNewSession,
    updateSession,
    deleteSession,
    selectSession,
    clearAllHistory,
    loadSessions,
  }
}

