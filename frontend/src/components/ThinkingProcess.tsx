import React, { useState, useEffect, useRef } from 'react'

interface ThinkingProcessProps {
  logs: string[]
}

interface StepStatus {
  status: 'waiting' | 'active' | 'completed'
  detail?: string
}

interface ParsedInfo {
  intent?: string
  searchQueries?: string[]
  foundDocuments?: string
  agentActivity?: string
}

export default function ThinkingProcess({ logs }: ThinkingProcessProps) {
  const [steps, setSteps] = useState<Record<string, StepStatus>>({
    analyze: { status: 'active', detail: '질문을 분석하고 있어요' },
    collect: { status: 'waiting' },
    compose: { status: 'waiting' },
    complete: { status: 'waiting' }
  })
  
  const [parsedInfo, setParsedInfo] = useState<ParsedInfo>({})
  const [currentMessage, setCurrentMessage] = useState('질문을 확인하고 있어요')
  const processedLogsRef = useRef<Set<string>>(new Set())

  // 로그를 실시간으로 파싱하여 UI 업데이트
  useEffect(() => {
    if (logs.length === 0) {
      // 초기화
      setSteps({
        analyze: { status: 'active', detail: '질문을 분석하고 있어요' },
        collect: { status: 'waiting' },
        compose: { status: 'waiting' },
        complete: { status: 'waiting' }
      })
      setParsedInfo({})
      setCurrentMessage('질문을 확인하고 있어요')
      processedLogsRef.current.clear()
      return
    }

    logs.forEach((log, index) => {
      const logKey = `${index}-${log}`
      if (processedLogsRef.current.has(logKey)) return
      
      processedLogsRef.current.add(logKey)
      processLog(log)
    })
  }, [logs])

  const processLog = (log: string) => {
    const logLower = log.toLowerCase()

    // 1단계: 질문 분석 (Orchestration)
    if (log.includes('1단계') || log.includes('Orchestration') || log.includes('질문 분석')) {
      setSteps(prev => ({
        ...prev,
        analyze: { status: 'active', detail: '질문을 분석하고 있어요' }
      }))
      setCurrentMessage('질문을 분석하고 있어요')
    }

    // 사용자 의도 파악
    if (log.includes('사용자 의도') || log.includes('💡')) {
      const match = log.match(/(?:사용자 의도|💡 사용자 의도 파악):\s*(.+)/)
      if (match) {
        const intent = match[1].trim()
        if (intent && intent !== 'N/A' && intent.length > 3) {
          setParsedInfo(prev => ({ ...prev, intent }))
          setSteps(prev => ({
            ...prev,
            analyze: { status: 'completed', detail: '질문 분석 완료' }
          }))
        }
      }
    }

    // 2단계: 정보 수집 (Sub Agents)
    if (log.includes('2단계') || log.includes('Sub Agents') || log.includes('정보 수집')) {
      setSteps(prev => ({
        ...prev,
        analyze: { status: 'completed', detail: '질문 분석 완료' },
        collect: { status: 'active', detail: '관련 정보를 찾고 있어요' }
      }))
      setCurrentMessage('필요한 정보를 수집하고 있어요')
    }

    // Query 검색
    if (log.includes('Query:') || log.includes('📝 Query:')) {
      const match = log.match(/(?:📝\s*)?Query:\s*(.+)/)
      if (match) {
        const query = match[1].trim()
        if (query && query.length > 3) {
          setParsedInfo(prev => ({
            ...prev,
            searchQueries: [...(prev.searchQueries || []), query].slice(-3) // 최근 3개만
          }))
          setSteps(prev => ({
            ...prev,
            collect: { status: 'active', detail: `"${query.substring(0, 30)}..." 검색 중` }
          }))
        }
      }
    }

    // Step 실행 (Agent 활동)
    if (log.includes('Step') && (log.includes(':') || log.includes('시작'))) {
      const match = log.match(/Step\s*(\d+)[:\s]+(.+?)(?:\s+시작|\s*$|Query)/)
      if (match) {
        const agentName = match[2].trim()
        if (agentName && agentName.length > 0) {
          setParsedInfo(prev => ({ ...prev, agentActivity: agentName }))
          setSteps(prev => ({
            ...prev,
            collect: { status: 'active', detail: `${agentName} 실행 중` }
          }))
        }
      }
    }

    // 문서 발견
    if (log.includes('발견된 문서') || log.includes('선별된 문서')) {
      const match = log.match(/(\d+)개/)
      if (match) {
        const count = match[1]
        setParsedInfo(prev => ({ ...prev, foundDocuments: `${count}개` }))
        setSteps(prev => ({
          ...prev,
          collect: { status: 'active', detail: `관련 문서 ${count}개 발견` }
        }))
      }
    }

    // 3단계: 답변 작성 (Final Agent)
    if (log.includes('3단계') || log.includes('Final Agent') || log.includes('답변 작성')) {
      setSteps(prev => ({
        ...prev,
        collect: { status: 'completed', detail: '정보 수집 완료' },
        compose: { status: 'active', detail: '답변을 작성하고 있어요' }
      }))
      setCurrentMessage('답변을 작성하고 있어요')
    }

    // 답변 생성 중
    if (logLower.includes('generat') || logLower.includes('작성')) {
      setSteps(prev => ({
        ...prev,
        compose: { status: 'active', detail: '최종 답변 생성 중' }
      }))
    }

    // 완료
    if (log.includes('파이프라인 완료') || log.includes('답변 완료')) {
      setSteps(prev => ({
        ...prev,
        compose: { status: 'completed', detail: '답변 작성 완료' },
        complete: { status: 'completed', detail: '답변 준비 완료' }
      }))
      setCurrentMessage('답변이 준비되었어요!')
    }
  }

  const getStepIcon = (status: StepStatus['status']) => {
    switch (status) {
      case 'completed':
        return (
          <div className="w-6 h-6 bg-green-500 rounded-full flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
          </div>
        )
      case 'active':
        return (
          <div className="relative w-6 h-6">
            <div className="absolute inset-0 bg-blue-400 rounded-full animate-ping opacity-30"></div>
            <div className="relative w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center">
              <div className="w-2 h-2 bg-white rounded-full"></div>
            </div>
          </div>
        )
      default:
        return <div className="w-6 h-6 bg-gray-300 rounded-full"></div>
    }
  }

  const isCompleted = steps.complete.status === 'completed'
  const currentActiveStep = Object.entries(steps).find(([_, step]) => step.status === 'active')?.[1]

  return (
    <div className="bg-white rounded-2xl shadow-lg border border-gray-200 max-w-[95%] sm:max-w-[85%] overflow-hidden">
      {/* 헤더 */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          <span className="text-sm font-semibold text-gray-700">생각하는 과정 표시</span>
        </div>
        <button className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* 본문 */}
      <div className="p-4 space-y-4">
        {/* 상단 메시지 카드 */}
        <div className="bg-blue-50 rounded-xl p-4 flex items-center gap-3">
          <div className="flex-shrink-0">
            {!isCompleted ? (
              <div className="w-12 h-12 bg-blue-500 rounded-full flex items-center justify-center animate-pulse">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
            ) : (
              <div className="w-12 h-12 bg-green-500 rounded-full flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              </div>
            )}
          </div>
          <div className="flex-1">
            <div className="text-xs text-gray-500 mb-1">AI가 생각 중...</div>
            <div className="text-sm font-medium text-gray-800">{currentMessage}</div>
          </div>
        </div>

        {/* 단계별 진행 상황 */}
        <div className="space-y-3">
          {/* 질문 분석 */}
          <div className="flex items-start gap-3">
            {getStepIcon(steps.analyze.status)}
            <div className="flex-1 pt-0.5">
              <div className="flex items-center gap-2">
                <span className={`text-sm font-medium ${steps.analyze.status === 'active' ? 'text-blue-600' : steps.analyze.status === 'completed' ? 'text-green-600' : 'text-gray-400'}`}>
                  질문 분석
                </span>
                {steps.analyze.status === 'active' && (
                  <span className="text-xs text-blue-500 bg-blue-50 px-2 py-0.5 rounded-full animate-pulse">
                    진행중
                  </span>
                )}
              </div>
              {steps.analyze.detail && steps.analyze.status !== 'waiting' && (
                <div className="text-xs text-gray-500 mt-1">{steps.analyze.detail}</div>
              )}
            </div>
          </div>

          {/* 정보 수집 */}
          <div className="flex items-start gap-3">
            {getStepIcon(steps.collect.status)}
            <div className="flex-1 pt-0.5">
              <div className="flex items-center gap-2">
                <span className={`text-sm font-medium ${steps.collect.status === 'active' ? 'text-blue-600' : steps.collect.status === 'completed' ? 'text-green-600' : 'text-gray-400'}`}>
                  정보 수집
                </span>
                {steps.collect.status === 'active' && (
                  <span className="text-xs text-blue-500 bg-blue-50 px-2 py-0.5 rounded-full animate-pulse">
                    진행중
                  </span>
                )}
              </div>
              {steps.collect.detail && steps.collect.status !== 'waiting' && (
                <div className="text-xs text-gray-500 mt-1">{steps.collect.detail}</div>
              )}
            </div>
          </div>

          {/* 답변 작성 */}
          <div className="flex items-start gap-3">
            {getStepIcon(steps.compose.status)}
            <div className="flex-1 pt-0.5">
              <div className="flex items-center gap-2">
                <span className={`text-sm font-medium ${steps.compose.status === 'active' ? 'text-blue-600' : steps.compose.status === 'completed' ? 'text-green-600' : 'text-gray-400'}`}>
                  답변 작성
                </span>
                {steps.compose.status === 'active' && (
                  <span className="text-xs text-blue-500 bg-blue-50 px-2 py-0.5 rounded-full animate-pulse">
                    진행중
                  </span>
                )}
              </div>
              {steps.compose.detail && steps.compose.status !== 'waiting' && (
                <div className="text-xs text-gray-500 mt-1">{steps.compose.detail}</div>
              )}
            </div>
          </div>

          {/* 답변 완료 */}
          <div className="flex items-start gap-3">
            {getStepIcon(steps.complete.status)}
            <div className="flex-1 pt-0.5">
              <span className={`text-sm font-medium ${steps.complete.status === 'completed' ? 'text-green-600' : 'text-gray-400'}`}>
                답변 완료
              </span>
            </div>
          </div>
        </div>

        {/* 파악한 의도 */}
        {parsedInfo.intent && (
          <div className="bg-purple-50 rounded-lg p-3 border border-purple-100 animate-fadeIn">
            <div className="flex items-center gap-2 mb-2">
              <svg className="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-xs font-semibold text-purple-700">파악한 의도</span>
            </div>
            <div className="text-sm text-gray-700 bg-white rounded px-3 py-2">
              {parsedInfo.intent}
            </div>
          </div>
        )}

        {/* 찾고 있는 정보 */}
        {parsedInfo.searchQueries && parsedInfo.searchQueries.length > 0 && (
          <div className="animate-fadeIn">
            <div className="flex items-center gap-1.5 mb-2">
              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
              <span className="text-xs font-medium text-gray-600">찾고 있는 정보</span>
            </div>
            <div className="space-y-1.5 pl-3.5">
              {parsedInfo.searchQueries.map((query, idx) => (
                <div key={idx} className="flex items-center gap-2 text-xs text-gray-600 animate-slideIn">
                  <div className="w-1.5 h-1.5 bg-blue-400 rounded-full"></div>
                  <span>{query.length > 60 ? query.substring(0, 60) + '...' : query}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 하단 로딩 메시지 */}
        {!isCompleted && (
          <div className="flex items-center justify-center gap-2 pt-2">
            <div className="flex gap-1">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
            <span className="text-xs text-gray-500">정보를 찾는 중...</span>
            <button className="text-xs text-blue-600 hover:text-blue-700 font-medium ml-2">
              처리 중
            </button>
          </div>
        )}
      </div>

      {/* CSS 애니메이션 */}
      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-5px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes slideIn {
          from { opacity: 0; transform: translateX(-10px); }
          to { opacity: 1; transform: translateX(0); }
        }
        .animate-fadeIn {
          animation: fadeIn 0.4s ease-out;
        }
        .animate-slideIn {
          animation: slideIn 0.3s ease-out;
        }
      `}</style>
    </div>
  )
}
