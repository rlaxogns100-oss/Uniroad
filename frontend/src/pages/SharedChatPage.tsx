import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import ChatMessage from '../components/ChatMessage'

interface SharedChat {
  share_id: string
  user_query: string
  assistant_response: string
  sources: string[]
  source_urls: string[]
  created_at: string
  view_count: number
}

export default function SharedChatPage() {
  const { shareId } = useParams<{ shareId: string }>()
  const navigate = useNavigate()
  const [sharedChat, setSharedChat] = useState<SharedChat | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchSharedChat = async () => {
      if (!shareId) {
        setError('공유 ID가 없습니다.')
        setLoading(false)
        return
      }

      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/share/${shareId}`)
        
        if (!response.ok) {
          if (response.status === 404) {
            setError('공유된 채팅을 찾을 수 없습니다.')
          } else {
            setError('채팅을 불러오는데 실패했습니다.')
          }
          setLoading(false)
          return
        }

        const data = await response.json()
        setSharedChat(data)
      } catch (err) {
        console.error('공유 채팅 조회 실패:', err)
        setError('채팅을 불러오는데 실패했습니다.')
      } finally {
        setLoading(false)
      }
    }

    fetchSharedChat()
  }, [shareId])

  const handleGoToChat = () => {
    navigate('/chat')
  }

  // 로딩 중
  if (loading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600">공유된 채팅을 불러오는 중...</p>
        </div>
      </div>
    )
  }

  // 에러 발생
  if (error) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-center p-8">
          <div className="text-6xl mb-4">😢</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">앗!</h1>
          <p className="text-gray-600 mb-6">{error}</p>
          <button
            onClick={handleGoToChat}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors"
          >
            유니로드에서 질문하기
          </button>
        </div>
      </div>
    )
  }

  // 공유된 채팅 표시
  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* 헤더 */}
      <header className="border-b border-gray-200 bg-white sticky top-0 z-10">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img 
              src="/로고.png" 
              alt="유니로드" 
              className="h-8 w-auto cursor-pointer"
              onClick={handleGoToChat}
            />
            <span className="text-sm text-gray-500">공유된 대화</span>
          </div>
          <button
            onClick={handleGoToChat}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            유니로드에서 더 물어보기
          </button>
        </div>
      </header>

      {/* 채팅 내용 */}
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {sharedChat && (
            <div className="space-y-4">
              {/* 사용자 질문 */}
              <ChatMessage
                message={sharedChat.user_query}
                isUser={true}
              />
              
              {/* AI 답변 */}
              <ChatMessage
                message={sharedChat.assistant_response}
                isUser={false}
                sources={sharedChat.sources}
                source_urls={sharedChat.source_urls}
                userQuery={sharedChat.user_query}
                isStreaming={false}
              />
            </div>
          )}
        </div>
      </main>

      {/* 하단 CTA */}
      <footer className="border-t border-gray-200 bg-gradient-to-r from-blue-50 to-purple-50 py-6">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h2 className="text-lg font-bold text-gray-900 mb-2">
            입시 관련 궁금한 점이 있으신가요?
          </h2>
          <p className="text-gray-600 mb-4">
            유니로드에서 AI 입시 상담을 받아보세요!
          </p>
          <button
            onClick={handleGoToChat}
            className="px-8 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-medium rounded-lg transition-all shadow-lg hover:shadow-xl"
          >
            무료로 질문하기
          </button>
        </div>
      </footer>
    </div>
  )
}
