import React, { useState, useEffect } from 'react'

interface Step {
  id: string
  label: string
  status: 'pending' | 'active' | 'completed'
  details?: string
}

interface ThinkingProcessProps {
  logs: string[]
}

export default function ThinkingProcess({ logs }: ThinkingProcessProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const [steps, setSteps] = useState<Step[]>([
    { id: '1', label: '질문 분석', status: 'pending' },
    { id: '2', label: '정보 수집', status: 'pending' },
    { id: '3', label: '답변 작성', status: 'pending' },
    { id: '4', label: '답변 완료', status: 'pending' },
  ])

  const [currentThought, setCurrentThought] = useState<string>('질문을 확인하고 있어요')
  const [userIntent, setUserIntent] = useState<string>('')
  const [queries, setQueries] = useState<Array<{ text: string; status: 'pending' | 'active' | 'completed' }>>([])
  const [foundSources, setFoundSources] = useState<number>(0)
  const [thinkingSteps, setThinkingSteps] = useState<Array<{ title: string; description: string }>>([])

  useEffect(() => {
    if (logs.length === 0) {
      setSteps(prev => {
        const newSteps = [...prev]
        newSteps[0].status = 'active'
        newSteps[0].details = '질문을 확인하고 있어요'
        return newSteps
      })
      return
    }

    const latestLog = logs[logs.length - 1]
    const latestLogLower = latestLog.toLowerCase()
    
    // 모든 로그를 순회하며 정보 추출
    logs.forEach(log => {
      // 사용자 의도 추출
      if (log.includes('사용자 의도:')) {
        const match = log.match(/사용자 의도:\s*(.+)/)
        if (match) {
          const intent = match[1].trim()
          setUserIntent(prev => prev !== intent ? intent : prev)
          // 생각하는 과정에 추가
          setThinkingSteps(prev => {
            if (!prev.find(s => s.title === '목표 이해하기')) {
              return [{
                title: '목표 이해하기',
                description: `사용자의 질문을 분석하고 있습니다. 사용자가 "${intent}"에 대한 정보를 원하고 있습니다. 적절한 수준의 정보를 제공하기 위해 답변 구조를 계획하고 있습니다.`
              }, ...prev]
            }
            return prev
          })
        }
      }
      
      // 실행 계획 추출
      if (log.includes('실행 계획:') && log.match(/\d+개/)) {
        const match = log.match(/실행 계획:\s*(\d+)개/)
        if (match) {
          const planCount = parseInt(match[1])
          setThinkingSteps(prev => {
            if (!prev.find(s => s.title === '답변 구조 설계하기')) {
              return [{
                title: '답변 구조 설계하기',
                description: `답변을 위한 프레임워크를 구축하고 있습니다. ${planCount}개의 전문 에이전트를 활용하여 정보를 수집할 계획입니다. 각 섹션별로 적절한 정보를 제공하기 위해 구조를 설계하고 있습니다.`
              }, ...prev]
            }
            return prev
          })
        }
      }
      
      // Query 추출 (Query:로 시작하는 것들)
      if (log.includes('Query:')) {
        const match = log.match(/Query:\s*(.+)/)
        if (match) {
          const queryText = match[1].trim()
          setQueries(prev => {
            // 이미 있는 query인지 확인
            const exists = prev.find(q => q.text === queryText)
            if (!exists) {
              return [...prev, { text: queryText, status: 'active' }]
            }
            // 있으면 active로 업데이트
            return prev.map(q => q.text === queryText ? { ...q, status: 'active' } : q)
          })
          
          // 핵심 개념 탐색 중
          setThinkingSteps(prev => {
            if (!prev.find(s => s.title === '핵심 개념 탐색 중')) {
              return [{
                title: '핵심 개념 탐색 중',
                description: `"${queryText.substring(0, 30)}${queryText.length > 30 ? '...' : ''}"에 대한 관련 정보를 찾고 있습니다. 신뢰할 수 있는 출처에서 최신 정보를 수집하고 있습니다.`
              }, ...prev]
            }
            return prev
          })
        }
      }
      
      // 출처 개수 추출
      if (log.includes('출처') && log.match(/\d+개/)) {
        const match = log.match(/출처\s*(\d+)개/)
        if (match) {
          const count = parseInt(match[1])
          setFoundSources(prev => Math.max(prev, count))
        }
      }
      
      // Final Agent 실행
      if (log.includes('Final Agent 실행') || log.includes('📝')) {
        setThinkingSteps(prev => {
          if (!prev.find(s => s.title === '답변 작성 중')) {
            return [{
              title: '답변 작성 중',
              description: '수집한 정보를 바탕으로 답변을 작성하고 있습니다. 사용자가 이해하기 쉽도록 구조화하고, 중요한 개념을 명확하게 설명하고 있습니다.'
            }, ...prev]
          }
          return prev
        })
      }
    })

    // 단계별 상태 업데이트 - 함수형 업데이트로 변경하여 최신 상태 참조
    setSteps(prev => {
      const newSteps = [...prev]
      
      // userIntent, queries, foundSources를 함수형 업데이트로 가져오기
      let currentUserIntent = ''
      let currentQueries: Array<{ text: string; status: 'pending' | 'active' | 'completed' }> = []
      let currentFoundSources = 0
      
      // 로그에서 직접 추출
      logs.forEach(log => {
        if (log.includes('사용자 의도:')) {
          const match = log.match(/사용자 의도:\s*(.+)/)
          if (match) currentUserIntent = match[1].trim()
        }
        if (log.includes('Query:')) {
          const match = log.match(/Query:\s*(.+)/)
          if (match) {
            const queryText = match[1].trim()
            if (!currentQueries.find(q => q.text === queryText)) {
              currentQueries.push({ text: queryText, status: 'active' })
            }
          }
        }
        if (log.includes('출처') && log.match(/\d+개/)) {
          const match = log.match(/출처\s*(\d+)개/)
          if (match) {
            const count = parseInt(match[1])
            currentFoundSources = Math.max(currentFoundSources, count)
          }
        }
        if (log.includes('✅') && currentQueries.length > 0) {
          currentQueries = currentQueries.map((q, idx) => {
            if (idx === currentQueries.length - 1 && q.status === 'active') {
              return { ...q, status: 'completed' as const }
            }
            return q
          })
        }
      })
      
      // 1단계: 질문 분석
      if (latestLogLower.includes('orchestration') || latestLogLower.includes('🎯') || logs.length > 0) {
        newSteps[0].status = 'active'
        newSteps[0].details = currentUserIntent || '질문을 분석하고 있어요'
      }
      
      if (latestLogLower.includes('실행 계획') || currentUserIntent) {
        newSteps[0].status = 'completed'
        newSteps[0].details = currentUserIntent || '의도를 파악했어요'
      }

      // 2단계: 정보 수집
      if (latestLogLower.includes('query:') || currentQueries.length > 0 || latestLogLower.includes('sub')) {
        newSteps[1].status = currentQueries.length > 0 ? 'active' : 'pending'
        const activeQueries = currentQueries.filter(q => q.status === 'active').length
        const completedQueries = currentQueries.filter(q => q.status === 'completed').length
        if (activeQueries > 0) {
          newSteps[1].details = `관련 정보를 찾고 있어요 (${completedQueries}/${currentQueries.length})`
        } else if (currentQueries.length > 0) {
          newSteps[1].details = '정보 수집 완료'
        } else {
          newSteps[1].details = '관련 자료를 찾고 있어요'
        }
      }
      
      if (currentFoundSources > 0 && latestLogLower.includes('✅')) {
        newSteps[1].status = 'completed'
        newSteps[1].details = `${currentFoundSources}개의 참고 자료를 찾았어요`
      }

      // 3단계: 답변 작성
      if (latestLogLower.includes('final') || latestLogLower.includes('답변') || latestLogLower.includes('📝')) {
        newSteps[2].status = 'active'
        newSteps[2].details = '찾은 정보로 답변을 작성하고 있어요'
      }
      
      if (latestLogLower.includes('최종 답변') || latestLogLower.includes('답변 생성')) {
        newSteps[2].status = 'completed'
        newSteps[2].details = '답변 작성 완료'
      }

      // 4단계: 완료
      if (latestLogLower.includes('완료') || latestLogLower.includes('✅ 파이프라인')) {
        newSteps[3].status = 'completed'
        newSteps[3].details = '답변 준비 완료!'
      }

      return newSteps
    })

    // 현재 생각 업데이트
    const thought = formatThought(latestLog)
    if (thought) {
      setCurrentThought(thought)
    }
  }, [logs]) // 의존성 배열을 logs만 남김

  const formatThought = (log: string): string => {
    const logLower = log.toLowerCase()
    
    // 질문 분석
    if (log.includes('사용자 의도:')) {
      const match = log.match(/사용자 의도:\s*(.+)/)
      return match ? `${match[1].substring(0, 40)}${match[1].length > 40 ? '...' : ''}` : '질문을 확인하고 있어요'
    }
    if (logLower.includes('orchestration') || logLower.includes('🎯')) {
      return '질문을 분석하고 있어요'
    }
    
    // 정보 수집
    if (log.includes('Query:')) {
      const match = log.match(/Query:\s*(.+)/)
      return match ? `"${match[1].substring(0, 35)}${match[1].length > 35 ? '...' : ''}"를 찾고 있어요` : '관련 정보를 찾고 있어요'
    }
    if (log.includes('✅') && log.includes('출처')) {
      const match = log.match(/출처\s*(\d+)개/)
      return match ? `관련 자료 ${match[1]}개를 찾았어요!` : '정보를 찾았어요'
    }
    if (logLower.includes('sub') || logLower.includes('🤖')) {
      return '관련 정보를 수집하고 있어요'
    }
    
    // 답변 작성
    if (logLower.includes('final') || logLower.includes('답변') || logLower.includes('📝')) {
      return '찾은 정보로 답변을 작성하고 있어요'
    }
    
    // 완료
    if (log.includes('✅ 파이프라인 완료') || logLower.includes('완료')) {
      return '답변을 준비했어요!'
    }
    
    // 기본
    return '질문을 확인하고 있어요'
  }

  const getStepIcon = (status: Step['status']) => {
    if (status === 'completed') {
      return (
        <svg className="w-5 h-5 text-green-500" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
        </svg>
      )
    }
    if (status === 'active') {
      return (
        <div className="relative">
          <svg className="animate-spin w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
        </div>
      )
    }
    return (
      <div className="w-5 h-5 rounded-full border-2 border-gray-300"></div>
    )
  }

  return (
    <div className="bg-white rounded-2xl p-4 sm:p-5 shadow-lg border border-gray-100 max-w-[90%] sm:max-w-[80%] animate-fadeIn">
      {/* 생각하는 과정 표시 헤더 - 접기/펼치기 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between mb-4 hover:bg-gray-50 rounded-lg p-2 -m-2 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
          </svg>
          <span className="text-sm font-semibold text-gray-900">생각하는 과정 표시</span>
        </div>
        <svg 
          className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isExpanded && (
        <>
          {/* AI 생각 중 상태 */}
          <div className="mb-5 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-100">
            <div className="flex items-center gap-3">
              <div className="flex-shrink-0">
                <div className="w-10 h-10 sm:w-12 sm:h-12 bg-gradient-to-br from-blue-400 to-indigo-500 rounded-full flex items-center justify-center shadow-md">
                  <div className="w-6 h-6 sm:w-7 sm:h-7 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs sm:text-sm text-gray-500 mb-1">AI가 생각 중...</p>
                <p className="text-sm sm:text-base text-gray-800 font-medium leading-relaxed">{currentThought}</p>
              </div>
            </div>
          </div>

          {/* 생각하는 과정 단계들 */}
          {thinkingSteps.length > 0 && (
            <div className="mb-5 space-y-4">
              {thinkingSteps.map((step, idx) => (
                <div key={idx} className="border-l-2 border-blue-200 pl-4">
                  <h4 className="text-sm font-semibold text-gray-900 mb-1.5">{step.title}</h4>
                  <p className="text-xs sm:text-sm text-gray-600 leading-relaxed">{step.description}</p>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {isExpanded && (
        <>
          {/* 진행 단계 - 간단한 버전 */}
          <div className="space-y-3 sm:space-y-4 relative pl-2">
            {steps.map((step, index) => (
          <div key={step.id} className="relative">
            <div className="flex items-start gap-3">
              {/* 아이콘 */}
              <div className="flex-shrink-0 mt-0.5 relative z-10">
                {getStepIcon(step.status)}
              </div>

              {/* 내용 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`text-sm sm:text-base font-semibold transition-colors duration-300 ${
                    step.status === 'completed' ? 'text-green-600' :
                    step.status === 'active' ? 'text-blue-600' :
                    'text-gray-400'
                  }`}>
                    {step.label}
                  </span>
                  {step.status === 'active' && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700 font-medium">
                      진행중
                    </span>
                  )}
                </div>
                
                {step.details && (step.status === 'active' || step.status === 'completed') && (
                  <p className="text-xs sm:text-sm text-gray-600 mt-1.5 leading-relaxed">{step.details}</p>
                )}
              </div>
            </div>

            {/* 연결선 */}
            {index < steps.length - 1 && (
              <div className="absolute left-[10px] top-7 w-0.5 h-6 sm:h-8 transition-all duration-500">
                <div className={`h-full rounded-full ${
                  step.status === 'completed' ? 'bg-green-400' : 'bg-gray-200'
                }`} />
              </div>
            )}
          </div>
            ))}
          </div>

          {/* 사용자 의도 - 간단하게 */}
          {userIntent && (
        <div className="mt-5 pt-4 border-t border-gray-100">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 bg-purple-100 rounded-full flex items-center justify-center flex-shrink-0">
              <span className="text-base">🎯</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-gray-500 mb-1.5 font-medium">파악한 의도</p>
              <p className="text-sm text-gray-800 leading-relaxed bg-purple-50 rounded-lg px-3 py-2 border border-purple-100">
                {userIntent}
              </p>
            </div>
          </div>
        </div>
          )}

          {/* 검색 중인 Query들 - 간단하게 */}
          {queries.length > 0 && (
        <div className="mt-5 pt-4 border-t border-gray-100">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-2 h-2 bg-blue-500 rounded-full animate-pulse"></div>
            <span className="text-xs text-gray-600 font-medium">찾고 있는 정보</span>
          </div>
          <div className="space-y-2">
            {queries.map((query, idx) => (
              <div 
                key={idx} 
                className="flex items-center gap-2 bg-gray-50 rounded-lg px-3 py-2 border border-gray-100"
              >
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  query.status === 'completed' ? 'bg-green-500' :
                  query.status === 'active' ? 'bg-blue-500 animate-pulse' :
                  'bg-gray-300'
                }`}></div>
                <p className="text-xs sm:text-sm text-gray-700 flex-1 leading-relaxed">
                  {query.text.length > 50 ? `${query.text.substring(0, 50)}...` : query.text}
                </p>
              </div>
            ))}
          </div>
        </div>
          )}

          {/* 하단 상태 */}
          <div className="mt-5 pt-3 border-t border-gray-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex gap-1">
                  <div className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce"></div>
                  <div className="w-1.5 h-1.5 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                  <div className="w-1.5 h-1.5 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                </div>
                <span className="text-xs text-gray-500">
                  {foundSources > 0 ? `${foundSources}개 자료 발견` : '정보를 찾는 중...'}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-blue-600">
                <div className="w-3 h-3 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
                <span className="font-medium hidden sm:inline">처리 중</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

