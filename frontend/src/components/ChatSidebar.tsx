import React from 'react'
import { useChat, ChatSession } from '../hooks/useChat'

interface ChatSidebarProps {
  isOpen: boolean
  onClose?: () => void
}

export default function ChatSidebar({ isOpen, onClose }: ChatSidebarProps) {
  const { sessions, currentSessionId, selectSession, startNewChat, loading } = useChat()

  return (
    <>
      {/* 모바일 오버레이 */}
      {isOpen && onClose && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 sm:hidden"
          onClick={onClose}
        />
      )}

      {/* 사이드바 */}
      <div
        className={`fixed top-0 left-0 h-full w-80 bg-white shadow-xl z-50 transform transition-transform duration-300 ease-in-out ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        } sm:translate-x-0 sm:static sm:w-80 flex flex-col`}
      >
        <div className="h-full flex flex-col overflow-hidden">
          {/* 헤더 */}
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">채팅</h2>
              {onClose && (
                <button
                  onClick={onClose}
                  className="sm:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              )}
            </div>
            
            {/* 새 채팅 버튼 */}
            <button
              onClick={startNewChat}
              className="w-full flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 active:bg-blue-800 transition-colors font-medium text-sm"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              새 채팅
            </button>
          </div>

          {/* 세션 목록 */}
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="p-4 text-center text-sm text-gray-500">
                로딩 중...
              </div>
            ) : sessions.length === 0 ? (
              <div className="p-4 text-center text-sm text-gray-500">
                채팅 기록이 없습니다
              </div>
            ) : (
              <div className="p-2">
                {sessions.map((session) => (
                  <button
                    key={session.id}
                    onClick={() => {
                      selectSession(session.id)
                      onClose?.()
                    }}
                    className={`w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                      currentSessionId === session.id
                        ? 'bg-blue-50 text-blue-900'
                        : 'hover:bg-gray-50 text-gray-900'
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">{session.title}</p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {new Date(session.updated_at).toLocaleDateString('ko-KR', {
                            month: 'short',
                            day: 'numeric',
                          })}
                        </p>
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}

