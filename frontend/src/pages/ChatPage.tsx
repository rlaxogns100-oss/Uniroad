import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { sendMessageStream, ChatResponse } from '../api/client'
import ChatMessage from '../components/ChatMessage'
import AgentPanel from '../components/AgentPanel'

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

export default function ChatPage() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId] = useState(() => `session-${Date.now()}`)
  const [isAgentPanelOpen, setIsAgentPanelOpen] = useState(false)
  const [agentData, setAgentData] = useState<AgentData>({
    orchestrationResult: null,
    subAgentResults: null,
    finalAnswer: null,
    rawAnswer: null,
    logs: []
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const sendingRef = useRef(false) // 중복 전송 방지

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

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
    
    const userMessage: Message = {
      id: Date.now().toString(),
      text: input,
      isUser: true,
    }

    setMessages((prev) => [...prev, userMessage])
    const userInput = input
    setInput('')
    setIsLoading(true)

    // 로그 초기화
    setAgentData({
      orchestrationResult: null,
      subAgentResults: null,
      finalAnswer: null,
      rawAnswer: null,
      logs: []
    })

    try {
      await sendMessageStream(
        userInput,
        sessionId,
        // 로그 콜백
        (log: string) => {
          setAgentData((prev) => ({
            ...prev,
            logs: [...prev.logs, log]
          }))
        },
        // 결과 콜백
        (response: ChatResponse) => {
          const botMessage: Message = {
            id: (Date.now() + 1).toString(),
            text: response.response,
            isUser: false,
            sources: response.sources,
            source_urls: response.source_urls,
          }

          setMessages((prev) => [...prev, botMessage])

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
          const errorMessage: Message = {
            id: (Date.now() + 1).toString(),
            text: error,
            isUser: false,
          }
          setMessages((prev) => [...prev, errorMessage])
        }
      )
    } catch (error) {
      console.error('채팅 오류:', error)
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        text: '죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해주세요.',
        isUser: false,
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
      sendingRef.current = false
      console.log('✅ 메시지 전송 완료')
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      console.log('⌨️ Enter 키 감지')
      handleSend()
    }
  }

  const toggleAgentPanel = () => {
    setIsAgentPanelOpen(!isAgentPanelOpen)
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

      {/* 메인 채팅 영역 */}
      <div className={`flex flex-col bg-gradient-to-br from-blue-50 to-indigo-100 transition-all duration-300 ${
        isAgentPanelOpen ? 'w-1/2' : 'w-full'
      }`}>
        {/* 헤더 */}
        <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4 flex justify-between items-center">
          <div>
            <img src="/로고.png" alt="UniZ Logo" className="h-16" />
          </div>
          <div className="flex gap-2">
            {/* Agent 버튼 */}
            <button
              onClick={toggleAgentPanel}
              className={`px-4 py-2 rounded-lg transition-colors flex items-center gap-2 ${
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
            {/* 관리자 버튼 */}
            <button
              onClick={() => navigate('/admin')}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
            >
              관리자
            </button>
          </div>
        </header>

        {/* 채팅 영역 */}
        <div className="flex-1 overflow-y-auto px-4 py-6">
          <div className="max-w-4xl mx-auto">
            {messages.length === 0 && (
              <div className="text-center mt-20">
                <h2 className="text-3xl font-bold text-gray-800 mb-8">무엇을 도와드릴까요?</h2>
                <div className="grid grid-cols-2 gap-4 max-w-2xl mx-auto">
                  <div 
                    className="bg-white rounded-xl p-6 shadow-md hover:shadow-lg transition-shadow cursor-pointer"
                    onClick={() => setInput('서울대 2028 정시 변경사항 알려줘')}
                  >
                    <div className="text-4xl mb-3">📋</div>
                    <p className="text-gray-700 font-medium">대입 정책 조회</p>
                  </div>
                  <div 
                    className="bg-white rounded-xl p-6 shadow-md hover:shadow-lg transition-shadow cursor-pointer"
                    onClick={() => setInput('내신 2.5등급인데 서울대 연세대 고려대 비교해줘')}
                  >
                    <div className="text-4xl mb-3">🎓</div>
                    <p className="text-gray-700 font-medium">대학별 입결</p>
                  </div>
                  <div 
                    className="bg-white rounded-xl p-6 shadow-md hover:shadow-lg transition-shadow cursor-pointer"
                    onClick={() => setInput('백분위 95%면 어느 대학 갈 수 있어?')}
                  >
                    <div className="text-4xl mb-3">📊</div>
                    <p className="text-gray-700 font-medium">합격 가능성 분석</p>
                  </div>
                  <div 
                    className="bg-white rounded-xl p-6 shadow-md hover:shadow-lg transition-shadow cursor-pointer"
                    onClick={() => setInput('수능까지 3개월 남았는데 공부 계획 세워줘')}
                  >
                    <div className="text-4xl mb-3">📚</div>
                    <p className="text-gray-700 font-medium">공부 계획 세우기</p>
                  </div>
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
                <div className="bg-gray-100 rounded-2xl px-4 py-3">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* 입력 영역 */}
        <div className="bg-white border-t border-gray-200 px-4 py-4">
          <div className="max-w-4xl mx-auto flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="메시지를 입력하세요..."
              disabled={isLoading}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
            />
            <button
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              전송
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
