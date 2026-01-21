import React, { useState, useEffect } from 'react'

interface Step {
  id: string
  label: string
  status: 'pending' | 'active' | 'completed'
  details?: string
  startTime?: number
  endTime?: number
}

interface AgentExecution {
  name: string
  step: number
  query: string
  status: 'pending' | 'running' | 'success' | 'failed'
  sources?: number
  time?: string
}

interface ThinkingProcessProps {
  logs: string[]
}

export default function ThinkingProcess({ logs }: ThinkingProcessProps) {
  const [steps, setSteps] = useState<Step[]>([
    { id: '1', label: 'Orchestration', status: 'pending' },
    { id: '2', label: 'Sub Agents', status: 'pending' },
    { id: '3', label: 'Final Agent', status: 'pending' },
    { id: '4', label: '답변 완료', status: 'pending' },
  ])

  const [foundDocuments, setFoundDocuments] = useState<string[]>([])
  const [currentThought, setCurrentThought] = useState<string>('')
  const [userIntent, setUserIntent] = useState<string>('')
  const [executionPlanCount, setExecutionPlanCount] = useState<number>(0)
  const [answerStructureCount, setAnswerStructureCount] = useState<number>(0)
  const [agentExecutions, setAgentExecutions] = useState<AgentExecution[]>([])
  const [timeStats, setTimeStats] = useState<{
    orchestration?: string
    subAgents?: string
    finalAgent?: string
    total?: string
  }>({})

  useEffect(() => {
    // 로그가 없을 때 기본 상태
    if (logs.length === 0) {
      setSteps(prev => {
        const newSteps = [...prev]
        newSteps[0].status = 'active'
        newSteps[0].details = '파이프라인을 시작하고 있습니다...'
        return newSteps
      })
      setCurrentThought('질문을 확인하고 있어요')
      return
    }

    const latestLog = logs[logs.length - 1]
    const latestLogLower = latestLog.toLowerCase()
    
    // 모든 로그를 순회하며 정보 추출
    logs.forEach(log => {
      const logLower = log.toLowerCase()
      
      // 사용자 의도 추출
      if (log.includes('사용자 의도:')) {
        const match = log.match(/사용자 의도:\s*(.+)/)
        if (match) setUserIntent(match[1].trim())
      }
      
      // 실행 계획 개수
      if (log.includes('실행 계획:') && log.includes('개 step')) {
        const match = log.match(/실행 계획:\s*(\d+)개/)
        if (match) setExecutionPlanCount(parseInt(match[1]))
      }
      
      // 답변 구조 개수
      if (log.includes('답변 구조:') && log.includes('개 섹션')) {
        const match = log.match(/답변 구조:\s*(\d+)개/)
        if (match) setAnswerStructureCount(parseInt(match[1]))
      }
      
      // Sub Agent Step 실행 계획
      if (log.match(/Step\s+\d+:/)) {
        const stepMatch = log.match(/Step\s+(\d+):\s+(.+)/)
        if (stepMatch) {
          const step = parseInt(stepMatch[1])
          const agentName = stepMatch[2].trim()
          
          setAgentExecutions(prev => {
            const exists = prev.find(a => a.step === step)
            if (!exists) {
              return [...prev, {
                name: agentName,
                step: step,
                query: '',
                status: 'pending'
              }]
            }
            return prev
          })
        }
      }
      
      // Sub Agent Query
      if (log.includes('Query:')) {
        const match = log.match(/Query:\s*(.+)/)
        if (match) {
          setAgentExecutions(prev => {
            const updated = [...prev]
            if (updated.length > 0) {
              updated[updated.length - 1].query = match[1].trim()
            }
            return updated
          })
        }
      }
      
      // Sub Agent 실행 결과 (✅/❌ 패턴)
      if (log.match(/[✅❌]\s*step\d+/i)) {
        const resultMatch = log.match(/([✅❌])\s*step(\d+)\s*\(([^)]+)\):\s*(\w+)\s*\(출처\s*(\d+)개,\s*⏱️\s*([\d.]+)초\)/)
        if (resultMatch) {
          const [, icon, stepNum, agentName, status, sources, time] = resultMatch
          const step = parseInt(stepNum)
          
          setAgentExecutions(prev => {
            return prev.map(a => {
              if (a.step === step) {
                return {
                  ...a,
                  status: icon === '✅' ? 'success' : 'failed',
                  sources: parseInt(sources),
                  time: `${time}초`
                }
              }
              return a
            })
          })
          
          // 출처 문서 추가
          if (parseInt(sources) > 0) {
            setFoundDocuments(prev => [...new Set([...prev, `${agentName}에서 ${sources}개 문서 발견`])])
          }
        }
      }
      
      // 시간 통계 추출
      if (log.includes('• Orchestration:')) {
        const match = log.match(/Orchestration:\s*([\d.]+)초/)
        if (match) setTimeStats(prev => ({ ...prev, orchestration: match[1] }))
      }
      if (log.includes('• Sub Agents:')) {
        const match = log.match(/Sub Agents:\s*([\d.]+)초/)
        if (match) setTimeStats(prev => ({ ...prev, subAgents: match[1] }))
      }
      if (log.includes('• Final Agent:')) {
        const match = log.match(/Final Agent:\s*([\d.]+)초/)
        if (match) setTimeStats(prev => ({ ...prev, finalAgent: match[1] }))
      }
      if (log.includes('• 전체:')) {
        const match = log.match(/전체:\s*([\d.]+)초/)
        if (match) setTimeStats(prev => ({ ...prev, total: match[1] }))
      }
    })

    // 단계별 상태 업데이트 (latestLogLower는 위에서 이미 선언됨)
    setSteps(prev => {
      const newSteps = [...prev]
      
      // 1단계: Orchestration Agent
      if (latestLogLower.includes('orchestration agent 실행') || latestLogLower.includes('🎯')) {
        newSteps[0].status = 'active'
        newSteps[0].details = '질문을 분석하고 실행 계획을 수립하는 중...'
      }
      
      if (latestLogLower.includes('📋 orchestration 결과') || latestLog.includes('실행 계획:')) {
        newSteps[0].status = 'completed'
        newSteps[0].details = `의도 파악 완료: ${executionPlanCount}개 에이전트 호출 예정`
      }

      // 2단계: Sub Agents 실행
      if (latestLogLower.includes('sub agents 실행') || latestLogLower.includes('🤖')) {
        newSteps[1].status = 'active'
        newSteps[1].details = `${executionPlanCount}개의 전문 에이전트를 실행하는 중...`
      }
      
      // Sub Agent 실행 중
      if (latestLog.match(/step\d+/i) && (latestLogLower.includes('query:') || latestLog.includes('✅') || latestLog.includes('❌'))) {
        newSteps[1].status = 'active'
        const completed = agentExecutions.filter(a => a.status === 'success' || a.status === 'failed').length
        if (executionPlanCount > 0) {
          newSteps[1].details = `에이전트 실행 중... (${completed}/${executionPlanCount})`
        }
      }
      
      if (latestLog.includes('총 Sub Agents 처리 시간')) {
        newSteps[1].status = 'completed'
        newSteps[1].details = `${executionPlanCount}개 에이전트 실행 완료`
      }

      // 3단계: Final Agent - 최종 답변 생성
      if (latestLogLower.includes('final agent 실행') || latestLogLower.includes('📝')) {
        newSteps[2].status = 'active'
        newSteps[2].details = `수집한 정보를 바탕으로 ${answerStructureCount}개 섹션 답변 작성 중...`
      }
      
      if (latestLog.includes('최종 답변 길이:')) {
        newSteps[2].status = 'completed'
        newSteps[2].details = '답변 생성 완료'
      }

      // 4단계: 완료
      if (latestLog.includes('✅ 파이프라인 완료') || latestLog.includes('⏱️ 처리 시간 분석')) {
        newSteps[3].status = 'completed'
        newSteps[3].details = `총 ${timeStats.total || '?'}초 소요`
      }

      return newSteps
    })

    // 현재 생각 업데이트
    const thought = formatThought(logs[logs.length - 1])
    if (thought) {
      setCurrentThought(thought)
    }
  }, [logs])

  const formatThought = (log: string): string => {
    const logLower = log.toLowerCase()
    
    // 파이프라인 시작
    if (log.includes('🚀') || logLower.includes('파이프라인 시작')) {
      return '멀티에이전트 시스템을 시작했어요'
    }
    
    // Orchestration Agent
    if (log.includes('🎯') || logLower.includes('orchestration agent 실행')) {
      return '질문을 분석하고 실행 계획을 세우고 있어요'
    }
    if (log.includes('📋') || log.includes('Orchestration 결과')) {
      return '실행 계획이 완성되었어요!'
    }
    if (log.includes('사용자 의도:')) {
      const match = log.match(/사용자 의도:\s*(.+)/)
      return match ? `의도 파악: ${match[1].substring(0, 30)}...` : '의도를 파악했어요'
    }
    if (log.includes('실행 계획:')) {
      const match = log.match(/(\d+)개 step/)
      return match ? `${match[1]}개 전문 에이전트를 동원할 계획이에요` : '실행 계획을 수립했어요'
    }
    
    // Sub Agents 실행
    if (log.includes('🤖') || logLower.includes('sub agents 실행')) {
      return '전문 에이전트들을 실행하고 있어요'
    }
    if (log.match(/Step\s+\d+:/)) {
      const match = log.match(/Step\s+\d+:\s*(.+agent)/i)
      return match ? `${match[1]}를 실행 중...` : '에이전트를 실행하고 있어요'
    }
    if (log.includes('Query:')) {
      return '에이전트에게 구체적인 질문을 전달했어요'
    }
    if (log.includes('✅')) {
      const match = log.match(/\(출처\s*(\d+)개/)
      return match ? `관련 자료 ${match[1]}개를 찾았어요!` : '에이전트가 작업을 완료했어요!'
    }
    if (log.includes('총 Sub Agents 처리 시간')) {
      return '모든 에이전트가 작업을 마쳤어요'
    }
    
    // Final Agent
    if (log.includes('📝') || logLower.includes('final agent 실행')) {
      return '수집한 정보로 답변을 작성하고 있어요'
    }
    if (log.includes('섹션 수:')) {
      const match = log.match(/(\d+)/)
      return match ? `${match[1]}개 섹션으로 구성된 답변을 작성 중...` : '답변을 구성하고 있어요'
    }
    if (log.includes('최종 답변 길이:')) {
      return '답변 작성이 완료되었어요!'
    }
    
    // 완료
    if (log.includes('✅ 파이프라인 완료')) {
      return '모든 작업이 성공적으로 완료되었어요!'
    }
    if (log.includes('⏱️ 처리 시간 분석')) {
      return '작업 시간을 분석하고 있어요'
    }
    
    // 기타
    if (log.length > 50) {
      return log.substring(0, 47) + '...'
    }
    return log
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
    <div className="bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 rounded-2xl p-5 shadow-lg border border-blue-200 max-w-[80%] animate-fadeIn">
      {/* AI 아바타와 현재 생각 */}
      {currentThought && (
        <div className="mb-4 bg-white rounded-xl p-3 shadow-sm border border-blue-100 animate-slideIn">
          <div className="flex items-center gap-3">
            <div className="flex-shrink-0">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-400 to-indigo-500 rounded-full flex items-center justify-center shadow-md">
                <span className="text-xl">🤖</span>
              </div>
            </div>
            <div className="flex-1">
              <p className="text-xs text-gray-500 mb-0.5">AI가 생각 중...</p>
              <p className="text-sm text-gray-800 font-medium">{currentThought}</p>
            </div>
          </div>
        </div>
      )}

      {/* 진행 단계 */}
      <div className="space-y-4 relative">
        {steps.map((step, index) => (
          <div key={step.id} className="relative">
            <div className="flex items-start gap-3">
              {/* 아이콘 */}
              <div className="flex-shrink-0 mt-0.5 relative z-10">
                {getStepIcon(step.status)}
              </div>

              {/* 내용 */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-semibold transition-colors duration-300 ${
                    step.status === 'completed' ? 'text-green-700' :
                    step.status === 'active' ? 'text-blue-700' :
                    'text-gray-400'
                  }`}>
                    {step.label}
                  </span>
                  {step.status === 'active' && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] bg-blue-100 text-blue-700 animate-pulse">
                      진행중
                    </span>
                  )}
                  {step.status === 'completed' && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] bg-green-100 text-green-700 animate-fadeIn">
                      완료
                    </span>
                  )}
                </div>
                
                {step.details && step.status === 'active' && (
                  <p className="text-xs text-gray-600 mt-1 animate-fadeIn">{step.details}</p>
                )}
              </div>
            </div>

            {/* 연결선 */}
            {index < steps.length - 1 && (
              <div className="absolute left-[10px] top-6 w-0.5 h-8 transition-all duration-500">
                <div className={`h-full rounded-full ${
                  step.status === 'completed' ? 'bg-gradient-to-b from-green-400 to-green-300' : 'bg-gray-200'
                }`} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* 사용자 의도 */}
      {userIntent && (
        <div className="mt-4 pt-4 border-t border-blue-200 animate-fadeIn">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-7 h-7 bg-purple-100 rounded-full flex items-center justify-center">
              <span className="text-sm">🎯</span>
            </div>
            <span className="text-xs font-semibold text-gray-700">파악한 의도</span>
          </div>
          <div className="bg-white rounded-lg px-3 py-2 text-xs text-gray-700 shadow-sm border border-purple-100">
            {userIntent}
          </div>
        </div>
      )}

      {/* 에이전트 실행 상태 */}
      {agentExecutions.length > 0 && (
        <div className="mt-4 pt-4 border-t border-blue-200 animate-fadeIn">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 bg-indigo-100 rounded-full flex items-center justify-center">
              <span className="text-sm">🤖</span>
            </div>
            <div>
              <span className="text-xs font-semibold text-gray-700 block">실행 중인 에이전트</span>
              <span className="text-[10px] text-gray-500">총 {agentExecutions.length}개</span>
            </div>
          </div>
          <div className="space-y-2">
            {agentExecutions.map((agent, idx) => (
              <div 
                key={idx} 
                className="bg-white rounded-lg px-3 py-2 shadow-sm border border-indigo-100 animate-slideIn"
                style={{ animationDelay: `${idx * 0.1}s` }}
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    {agent.status === 'success' && <span className="text-green-500 text-sm">✅</span>}
                    {agent.status === 'failed' && <span className="text-red-500 text-sm">❌</span>}
                    {agent.status === 'running' && (
                      <svg className="animate-spin w-3 h-3 text-blue-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    )}
                    {agent.status === 'pending' && <span className="w-3 h-3 rounded-full border-2 border-gray-300"></span>}
                    <span className="text-xs font-medium text-gray-700">{agent.name}</span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-gray-500">
                    {agent.sources !== undefined && (
                      <span className="bg-green-50 text-green-700 px-1.5 py-0.5 rounded">📄 {agent.sources}개</span>
                    )}
                    {agent.time && (
                      <span className="bg-blue-50 text-blue-700 px-1.5 py-0.5 rounded">⏱️ {agent.time}</span>
                    )}
                  </div>
                </div>
                {agent.query && (
                  <div className="text-[10px] text-gray-500 ml-5 mt-1">
                    Query: {agent.query}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 찾은 문서 */}
      {foundDocuments.length > 0 && (
        <div className="mt-4 pt-4 border-t border-blue-200 animate-fadeIn">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 bg-green-100 rounded-full flex items-center justify-center">
              <span className="text-sm">📚</span>
            </div>
            <div>
              <span className="text-xs font-semibold text-gray-700 block">참고 자료</span>
              <span className="text-[10px] text-gray-500">{foundDocuments.length}개 발견</span>
            </div>
          </div>
          <div className="space-y-1.5">
            {foundDocuments.slice(0, 5).map((doc, idx) => (
              <div 
                key={idx} 
                className="text-xs text-gray-700 bg-white rounded-lg px-3 py-2 flex items-center gap-2 shadow-sm border border-green-100 animate-slideIn"
                style={{ animationDelay: `${idx * 0.1}s` }}
              >
                <span className="text-green-500 text-sm">✓</span>
                <span className="truncate flex-1">{doc}</span>
              </div>
            ))}
            {foundDocuments.length > 5 && (
              <div className="text-[10px] text-gray-500 text-center py-1">
                +{foundDocuments.length - 5}개 더 있음
              </div>
            )}
          </div>
        </div>
      )}

      {/* 시간 통계 */}
      {timeStats.total && (
        <div className="mt-4 pt-4 border-t border-blue-200 animate-fadeIn">
          <div className="flex items-center gap-2 mb-3">
            <div className="w-7 h-7 bg-yellow-100 rounded-full flex items-center justify-center">
              <span className="text-sm">⏱️</span>
            </div>
            <div>
              <span className="text-xs font-semibold text-gray-700 block">처리 시간</span>
              <span className="text-[10px] text-gray-500">전체 {timeStats.total}초</span>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {timeStats.orchestration && (
              <div className="bg-purple-50 rounded-lg px-2 py-1.5 text-center">
                <div className="text-[10px] text-purple-600 font-medium">Orchestration</div>
                <div className="text-xs text-purple-800 font-bold">{timeStats.orchestration}초</div>
              </div>
            )}
            {timeStats.subAgents && (
              <div className="bg-indigo-50 rounded-lg px-2 py-1.5 text-center">
                <div className="text-[10px] text-indigo-600 font-medium">Sub Agents</div>
                <div className="text-xs text-indigo-800 font-bold">{timeStats.subAgents}초</div>
              </div>
            )}
            {timeStats.finalAgent && (
              <div className="bg-blue-50 rounded-lg px-2 py-1.5 text-center">
                <div className="text-[10px] text-blue-600 font-medium">Final Agent</div>
                <div className="text-xs text-blue-800 font-bold">{timeStats.finalAgent}초</div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 로그 카운터 및 상태 */}
      <div className="mt-4 pt-3 border-t border-blue-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce"></div>
              <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
              <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
            </div>
            <span className="text-[10px] text-gray-600 font-medium">
              {logs.length}개 로그 수신
            </span>
          </div>
          {!timeStats.total && (
            <div className="flex items-center gap-1.5 text-[10px] text-blue-600">
              <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <span className="font-medium">멀티에이전트 실행 중</span>
            </div>
          )}
          {timeStats.total && (
            <div className="flex items-center gap-1.5 text-[10px] text-green-600">
              <span className="text-sm">✨</span>
              <span className="font-medium">완료!</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

