import React, { useState } from 'react'
import { ChatSession } from '../hooks/useChatHistory'

interface ChatHistorySidebarProps {
  sessions: ChatSession[]
  currentSessionId: string | null
  onNewChat: () => void
  onSelectSession: (sessionId: string) => void
  onDeleteSession: (sessionId: string) => void
  onClearAll: () => void
  isOpen: boolean
  onToggle: () => void
}

export default function ChatHistorySidebar({
  sessions,
  currentSessionId,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onClearAll,
  isOpen,
  onToggle,
}: ChatHistorySidebarProps) {
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null)

  const formatDate = (timestamp: number) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24))

    if (diffDays === 0) return '오늘'
    if (diffDays === 1) return '어제'
    if (diffDays < 7) return `${diffDays}일 전`
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}주 전`
    return date.toLocaleDateString('ko-KR', { month: 'long', day: 'numeric' })
  }

  // 날짜별 그룹화 (이미 정렬된 세션 목록을 기준으로)
  const groupedSessions = sessions.reduce((acc, session) => {
    const dateKey = formatDate(session.updatedAt)
    if (!acc[dateKey]) {
      acc[dateKey] = []
    }
    acc[dateKey].push(session)
    return acc
  }, {} as Record<string, ChatSession[]>)

  // 그룹 내 세션들을 updatedAt 기준으로 정렬 (최신순)
  Object.keys(groupedSessions).forEach(dateKey => {
    groupedSessions[dateKey].sort((a, b) => b.updatedAt - a.updatedAt)
  })

  // 날짜 그룹을 정렬 (최신 날짜가 위로)
  const sortedDateKeys = Object.keys(groupedSessions).sort((a, b) => {
    // '오늘', '어제', 'N일 전', 'N주 전' 등의 순서를 고려
    if (a === '오늘') return -1
    if (b === '오늘') return 1
    if (a === '어제') return -1
    if (b === '어제') return 1
    
    // 같은 그룹의 첫 번째 세션의 updatedAt으로 비교
    const dateA = groupedSessions[a][0]?.updatedAt || 0
    const dateB = groupedSessions[b][0]?.updatedAt || 0
    return dateB - dateA
  })

  return (
    <>
      {/* 사이드바 */}
      <div
        className={`fixed top-0 left-0 h-full bg-white shadow-xl z-40 transition-transform duration-300 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ width: '280px' }}
      >
        <div className="flex flex-col h-full">
          {/* 헤더 */}
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center gap-2 mb-4">
              <img src="/로고.png" alt="UniZ Logo" className="h-8" />
              <span className="font-bold text-gray-800">유니로드</span>
            </div>
            
            {/* 새 채팅 버튼 */}
            <button
              onClick={onNewChat}
              className="w-full px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 font-medium"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              새 대화
            </button>
          </div>

          {/* 채팅 목록 */}
          <div className="flex-1 overflow-y-auto p-3">
            {sessions.length === 0 ? (
              <div className="text-center py-8 text-gray-500 text-sm">
                <svg className="w-12 h-12 mx-auto mb-2 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <p>아직 대화가 없습니다</p>
                <p className="text-xs mt-1">새 대화를 시작해보세요</p>
              </div>
            ) : (
              sortedDateKeys.map((dateKey) => {
                const sessionGroup = groupedSessions[dateKey]
                return (
                <div key={dateKey} className="mb-4">
                  <div className="text-xs font-semibold text-gray-500 mb-2 px-2">{dateKey}</div>
                  <div className="space-y-1">
                    {sessionGroup.map((session) => (
                      <div
                        key={session.id}
                        className={`group relative rounded-lg transition-all ${
                          currentSessionId === session.id
                            ? 'bg-blue-50 border border-blue-200'
                            : 'hover:bg-gray-50 border border-transparent'
                        }`}
                        onMouseEnter={() => setHoveredSessionId(session.id)}
                        onMouseLeave={() => setHoveredSessionId(null)}
                      >
                        <button
                          onClick={() => onSelectSession(session.id)}
                          className="w-full text-left px-3 py-2.5 flex items-start gap-2"
                        >
                          <svg className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                          </svg>
                          <div className="flex-1 min-w-0">
                            <p className={`text-sm truncate ${
                              currentSessionId === session.id ? 'text-blue-700 font-medium' : 'text-gray-700'
                            }`}>
                              {session.title}
                            </p>
                            <p className="text-xs text-gray-500 mt-0.5">
                              {session.messages.length}개 메시지
                            </p>
                          </div>
                        </button>

                        {/* 삭제 버튼 */}
                        {hoveredSessionId === session.id && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              if (confirm('이 대화를 삭제하시겠습니까?')) {
                                onDeleteSession(session.id)
                              }
                            }}
                            className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                            title="삭제"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
                )
              })
            )}
          </div>

          {/* 푸터 */}
          {sessions.length > 0 && (
            <div className="p-3 border-t border-gray-200">
              <button
                onClick={() => {
                  if (confirm('모든 대화 기록을 삭제하시겠습니까?')) {
                    onClearAll()
                  }
                }}
                className="w-full px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
                모든 대화 삭제
              </button>
            </div>
          )}
        </div>
      </div>

      {/* 오버레이 (모바일) */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-30 z-30 md:hidden"
          onClick={onToggle}
        />
      )}
    </>
  )
}

