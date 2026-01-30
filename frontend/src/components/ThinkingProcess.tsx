import React, { useState, useEffect, useRef } from 'react'

interface SearchQuery {
  type: string
  university?: string
  query?: string
  target_univ?: string[]
}

interface SearchResult {
  university: string
  query: string
  doc_count: number
  documents: string[]
}

interface ThinkingStep {
  title: string
  description: string
  queries?: SearchQuery[]
  searchResults?: SearchResult[]
}

interface ThinkingProcessProps {
  logs: string[]
}

// 로그에서 메시지와 상세 정보 분리
const parseLog = (log: string): { message: string; step?: string; detail?: any } => {
  const parts = log.split('|||')
  if (parts.length === 2) {
    try {
      const parsed = JSON.parse(parts[1])
      return { message: parts[0], step: parsed.step, detail: parsed.detail }
    } catch {
      return { message: log }
    }
  }
  return { message: log }
}

export default function ThinkingProcess({ logs }: ThinkingProcessProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([])
  const [currentStatus, setCurrentStatus] = useState('Analyzing question...')
  const [displayedStatus, setDisplayedStatus] = useState('')
  const typingIndexRef = useRef(0)
  const typingIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // 로그에서 상태 및 thinking steps 추출
  useEffect(() => {
    if (logs.length === 0) {
      setCurrentStatus('질문을 분석하고 있어요...')
      return
    }

    const newSteps: ThinkingStep[] = []
    let currentQueries: SearchQuery[] = []
    let currentSearchResults: SearchResult[] = []
    
    logs.forEach(log => {
      const { message, step, detail } = parseLog(log)
      
      // Router 완료 단계 (상세 정보 포함)
      if (step === 'router_complete' && detail?.function_calls) {
        currentQueries = detail.function_calls
        const queryCount = detail.count || currentQueries.length
        setCurrentStatus('검색 전략을 수립하고 있어요...')
        newSteps.push({
          title: '질문 이해하기',
          description: `질문을 분석하여 ${queryCount}개의 검색 쿼리를 생성했습니다.`,
          queries: currentQueries
        })
      }
      // Router 시작 (기존 호환)
      else if (message.includes('[1/3]') || message.includes('Router')) {
        if (message.includes('🔄')) {
          setCurrentStatus('질문을 분석하고 있어요...')
        }
        // 기존 방식 호환 (detail 없는 경우)
        if (message.includes('✅') && !step) {
          const match = message.match(/(\d+)개 함수 호출/)
          if (match) {
            setCurrentStatus('검색 전략을 수립하고 있어요...')
            newSteps.push({
              title: '질문 이해하기',
              description: `질문을 분석하여 ${match[1]}개의 검색 쿼리를 생성했습니다.`
            })
          }
        }
      }
      
      // 검색 시작 (개별 검색)
      if (step === 'search_start' && detail) {
        if (detail.university) {
          setCurrentStatus(`${detail.university} 정보를 검색하고 있어요...`)
        } else if (detail.type === 'consult') {
          setCurrentStatus('성적을 분석하고 있어요...')
        }
      }
      
      // 검색 완료 (상세 정보 포함)
      if (step === 'search_complete' && detail?.results) {
        currentSearchResults = detail.results
        const totalCount = detail.total_count || 0
        setCurrentStatus('검색 결과를 분석하고 있어요...')
        newSteps.push({
          title: '정보 수집하기',
          description: `${totalCount}개의 관련 자료를 찾았습니다.`,
          searchResults: currentSearchResults
        })
      }
      
      // Function 단계 (기존 호환)
      if ((message.includes('[2/3]') || message.includes('Functions')) && !step) {
        if (message.includes('🔄')) {
          setCurrentStatus('관련 정보를 검색하고 있어요...')
        }
        if (message.includes('✅')) {
          const match = message.match(/(\d+)개 결과/)
          if (match && !currentSearchResults.length) {
            setCurrentStatus('검색 결과를 분석하고 있어요...')
            newSteps.push({
              title: '정보 수집하기',
              description: `${match[1]}개의 관련 자료를 찾았습니다.`
            })
          }
        }
        if (message.includes('ℹ️') && message.includes('함수 호출 없음')) {
          setCurrentStatus('답변을 준비하고 있어요...')
          newSteps.push({
            title: '일반 대화',
            description: '일반적인 대화로 판단하여 데이터베이스 검색 없이 직접 답변을 생성합니다.'
          })
        }
      }
      
      // Main Agent 단계
      if (message.includes('[3/3]') || message.includes('Main Agent')) {
        if (message.includes('🔄')) {
          setCurrentStatus('답변을 작성하고 있어요...')
          newSteps.push({
            title: '답변 작성하기',
            description: '수집한 정보를 종합하여 질문에 맞는 명확하고 이해하기 쉬운 답변을 작성하고 있습니다.'
          })
        }
        if (message.includes('✅')) {
          setCurrentStatus('답변이 준비되었어요!')
        }
      }
    })

    if (newSteps.length > 0) {
      setThinkingSteps(newSteps)
    }
  }, [logs])

  // 타이핑 애니메이션
  useEffect(() => {
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current)
    }
    
    typingIndexRef.current = 0
    setDisplayedStatus('')
    
    typingIntervalRef.current = setInterval(() => {
      if (typingIndexRef.current < currentStatus.length) {
        setDisplayedStatus(currentStatus.substring(0, typingIndexRef.current + 1))
        typingIndexRef.current++
      } else {
        if (typingIntervalRef.current) {
          clearInterval(typingIntervalRef.current)
        }
      }
    }, 25)

    return () => {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current)
      }
    }
  }, [currentStatus])

  return (
    <div className="max-w-[90%] sm:max-w-[80%] animate-fadeIn">
      {/* 메인 헤더 - 아이콘 + 상태 텍스트 + 화살표 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-3 py-3 transition-colors group"
      >
        {/* 아이콘 애니메이션 */}
        <div className="relative w-8 h-8 flex-shrink-0">
          {/* 파란 다이아몬드 */}
          <svg 
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-4 h-4 text-blue-500"
            viewBox="0 0 24 24" 
            fill="currentColor"
          >
            <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
          </svg>
          {/* 파란 곡선 애니메이션 */}
          <svg 
            className="absolute top-1/2 left-1/2 w-7 h-7 animate-spin-slow"
            style={{ transform: 'translate(-50%, -50%)' }}
            viewBox="0 0 28 28"
          >
            <path
              d="M14 4 A10 10 0 0 1 14 24"
              fill="none"
              stroke="#3b82f6"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </div>

        {/* 상태 텍스트 */}
        <span className="text-base text-gray-800 font-medium flex-1 text-left">
          {displayedStatus}
          <span className="animate-blink text-gray-400">|</span>
        </span>

        {/* 접기/펼치기 화살표 */}
        <svg 
          className={`w-5 h-5 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* 펼쳐진 내용 */}
      {isExpanded && thinkingSteps.length > 0 && (
        <div className="pl-11 pb-3 space-y-4">
          {thinkingSteps.map((step, idx) => (
            <div key={idx} className="space-y-2">
              <h4 className="text-base font-bold text-gray-900">{step.title}</h4>
              <p className="text-sm text-gray-600 italic leading-relaxed">{step.description}</p>
              
              {/* 검색 쿼리 태그 표시 */}
              {step.queries && step.queries.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {step.queries.map((q, qIdx) => (
                    <span 
                      key={qIdx}
                      className="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-50 text-blue-700 text-xs rounded-full border border-blue-200"
                    >
                      {q.type === 'univ' ? (
                        <>
                          <span className="font-medium">{q.university}</span>
                          <span className="text-blue-400">:</span>
                          <span>{q.query}</span>
                        </>
                      ) : q.type === 'consult' ? (
                        <>
                          <span className="font-medium">성적 분석</span>
                          {q.target_univ && q.target_univ.length > 0 && (
                            <>
                              <span className="text-blue-400">:</span>
                              <span>{q.target_univ.join(', ')}</span>
                            </>
                          )}
                        </>
                      ) : (
                        <span>{q.query || '검색'}</span>
                      )}
                    </span>
                  ))}
                </div>
              )}
              
              {/* 검색 결과 문서 목록 표시 */}
              {step.searchResults && step.searchResults.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  {step.searchResults.map((result, rIdx) => (
                    <div key={rIdx}>
                      {result.documents && result.documents.length > 0 && (
                        <div className="space-y-1">
                          {result.documents.map((doc, dIdx) => (
                            <div 
                              key={dIdx}
                              className="flex items-center gap-2 text-xs text-gray-600"
                            >
                              <svg className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                              <span className="truncate">{doc}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
