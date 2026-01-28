import { useState, useEffect } from 'react'
import * as React from 'react'
import axios from 'axios'

// @ts-ignore
const API_BASE = import.meta.env?.VITE_API_URL || 'http://localhost:8000'

interface OrchestrationResult {
  plan_id?: string
  user_intent?: string
  execution_plan?: Array<{
    step: number
    agent: string
    query: string
  }>
  answer_structure?: Array<{
    section: number
    type: string
    title?: string
    source_from?: string
    instruction: string
  }>
  notes?: string
  error?: string
}

interface SubAgentResult {
  agent: string
  status: string
  result: string
  sources?: string[]
  source_urls?: string[]
  citations?: Array<{
    text: string
    source: string
    url: string
  }>
}

interface AgentPanelProps {
  orchestrationResult: OrchestrationResult | null
  subAgentResults: Record<string, SubAgentResult> | null
  finalAnswer: string | null
  rawAnswer?: string | null  // ✅ 원본 답변 추가
  logs: string[]
  isOpen: boolean
  onClose: () => void
}

type TabType = 'orchestration' | 'subagents' | 'final' | 'logs' | 'models'

export default function AgentPanel({
  orchestrationResult,
  subAgentResults,
  finalAnswer,
  rawAnswer,  // ✅ 원본 답변
  logs,
  isOpen,
  onClose
}: AgentPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('orchestration')

  if (!isOpen) return null

  const tabs: { id: TabType; label: string }[] = [
    { id: 'orchestration', label: 'Orchestration' },
    { id: 'subagents', label: 'Sub Agents' },
    { id: 'final', label: 'Final Answer' },
    { id: 'logs', label: '실시간 로그' },
    { id: 'models', label: '⚙️ 모델 설정' }
  ]

  return (
    <div className="w-1/2 h-screen bg-slate-900 border-r border-slate-700 flex flex-col overflow-hidden">
      {/* 헤더 */}
      <div className="bg-slate-800 border-b border-slate-700 px-4 py-3">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-emerald-400 font-bold text-sm">Multi-Agent Pipeline</h2>
            <p className="text-slate-500 text-xs">Orchestration → Sub Agents → Final Agent</p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition-colors p-1"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* 탭 네비게이션 */}
      <div className="flex bg-slate-800 border-b border-slate-700">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2 text-xs font-medium transition-colors border-b-2 ${
              activeTab === tab.id
                ? 'text-emerald-400 border-emerald-400'
                : 'text-slate-400 border-transparent hover:text-slate-300'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* 탭 컨텐츠 */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'orchestration' && (
          <OrchestrationTab result={orchestrationResult} />
        )}
        {activeTab === 'subagents' && (
          <SubAgentsTab results={subAgentResults} />
        )}
        {activeTab === 'final' && (
          <FinalAnswerTab answer={finalAnswer} rawAnswer={rawAnswer} />
        )}
        {activeTab === 'logs' && (
          <LogsTab logs={logs} />
        )}
        {activeTab === 'models' && (
          <ModelsTab />
        )}
      </div>
    </div>
  )
}

// Orchestration 탭
function OrchestrationTab({ result }: { result: OrchestrationResult | null }) {
  if (!result) {
    return <EmptyState message="채팅창에서 질문을 입력하면 Orchestration 결과가 표시됩니다" />
  }

  if (result.error) {
    return <div className="text-red-400 text-sm">{result.error}</div>
  }

  return (
    <div className="space-y-4">
      {/* 사용자 의도 */}
      {result.user_intent && (
        <Section title="사용자 의도">
          <div className="bg-slate-800 rounded p-3 text-sm text-slate-300">
            {result.user_intent}
          </div>
        </Section>
      )}

      {/* Execution Plan */}
      {result.execution_plan && result.execution_plan.length > 0 && (
        <Section title="Execution Plan">
          <div className="space-y-2">
            {result.execution_plan.map((step) => (
              <div
                key={step.step}
                className="bg-slate-800 rounded p-3 border-l-2 border-rose-500 ml-4 relative"
              >
                <div className="absolute -left-6 top-1/2 -translate-y-1/2 w-5 h-5 bg-rose-500 rounded-full flex items-center justify-center text-xs font-bold text-white">
                  {step.step}
                </div>
                <div className="text-emerald-400 font-medium text-sm">{step.agent}</div>
                <div className="text-slate-400 text-xs mt-1">{step.query}</div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Answer Structure */}
      {result.answer_structure && result.answer_structure.length > 0 && (
        <Section title="Answer Structure">
          <div className="space-y-2">
            {result.answer_structure.map((section) => (
              <div
                key={section.section}
                className="bg-slate-800 rounded p-3 border-l-2 border-emerald-400"
              >
                <span className="inline-block bg-emerald-500 text-slate-900 px-2 py-0.5 rounded text-xs font-bold mb-1">
                  {section.type}
                </span>
                {section.title && (
                  <div className="text-slate-200 text-sm font-medium">{section.title}</div>
                )}
                <div className="text-slate-400 text-xs mt-1">{section.instruction}</div>
                {section.source_from && (
                  <div className="text-rose-400 text-xs mt-1">← {section.source_from}</div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Notes */}
      {result.notes && (
        <Section title="Notes">
          <div className="bg-slate-800 rounded p-3 text-sm text-slate-300">
            {result.notes}
          </div>
        </Section>
      )}
    </div>
  )
}

// Sub Agents 탭
function SubAgentsTab({ results }: { results: Record<string, SubAgentResult> | null }) {
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())

  if (!results || Object.keys(results).length === 0) {
    return <EmptyState message="Sub Agent 실행 결과가 여기에 표시됩니다" />
  }

  const toggleExpand = (key: string) => {
    setExpandedItems(prev => {
      const newSet = new Set(prev)
      if (newSet.has(key)) {
        newSet.delete(key)
      } else {
        newSet.add(key)
      }
      return newSet
    })
  }

  return (
    <div className="space-y-3">
      {Object.entries(results).map(([key, result]) => {
        const isExpanded = expandedItems.has(key)
        const resultText = result.result || '결과 없음'
        const isLong = resultText.length > 500
        
        return (
          <div key={key} className="bg-slate-800 rounded-lg p-4 border border-slate-700">
            <div className="flex justify-between items-center mb-2">
              <span className="text-emerald-400 font-medium text-sm">
                {key} ({result.agent})
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded ${
                  result.status === 'success'
                    ? 'bg-emerald-500 text-white'
                    : 'bg-rose-500 text-white'
                }`}
              >
                {result.status}
              </span>
            </div>
            <div 
              className={`text-slate-300 text-xs whitespace-pre-wrap overflow-y-auto ${
                isExpanded ? 'max-h-none' : 'max-h-64'
              }`}
            >
              {resultText}
            </div>
            {isLong && (
              <button 
                onClick={() => toggleExpand(key)}
                className="mt-2 text-xs text-emerald-400 hover:text-emerald-300"
              >
                {isExpanded ? '▲ 접기' : '▼ 전체 보기'}
              </button>
            )}
            {result.sources && result.sources.length > 0 && (
              <div className="mt-2 pt-2 border-t border-slate-700">
                <div className="text-slate-500 text-xs">출처: {result.sources.join(', ')}</div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// Final Answer 탭
function FinalAnswerTab({ answer, rawAnswer }: { answer: string | null, rawAnswer?: string | null }) {
  const [showRaw, setShowRaw] = useState(false)
  
  if (!answer) {
    return <EmptyState message="최종 답변이 여기에 표시됩니다" />
  }

  // 표 렌더링 함수
  const renderWithTables = (text: string) => {
    const lines = text.split('\n')
    const result: React.ReactNode[] = []
    let i = 0
    let keyIdx = 0
    
    while (i < lines.length) {
      const line = lines[i]
      
      // 표 시작 감지
      if (line.trim().match(/^\|.+\|$/) && 
          i + 1 < lines.length && 
          lines[i + 1].trim().match(/^\|[-:\s|]+\|$/)) {
        
        // 표 줄들 수집
        const tableLines: string[] = []
        let j = i
        while (j < lines.length && (lines[j].trim().match(/^\|.+\|$/) || lines[j].trim().match(/^\|[-:\s|]+\|$/))) {
          tableLines.push(lines[j])
          j++
        }
        
        if (tableLines.length >= 3) {
          // 헤더, 데이터 파싱
          const headers = tableLines[0].split('|').filter(h => h.trim()).map(h => h.trim())
          const rows = tableLines.slice(2).map(l => 
            l.split('|').filter(c => c.trim() !== '' || c.includes(' ')).map(c => c.trim())
          ).filter(r => r.length > 0)
          
          result.push(
            <table key={`table-${keyIdx++}`} className="w-full my-2 border-collapse border border-slate-600 text-sm">
              <thead className="bg-slate-700">
                <tr>
                  {headers.map((h, idx) => (
                    <th key={idx} className="border border-slate-600 px-2 py-1 text-left text-slate-200">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rIdx) => (
                  <tr key={rIdx} className={rIdx % 2 === 0 ? 'bg-slate-800' : 'bg-slate-750'}>
                    {row.map((cell, cIdx) => (
                      <td key={cIdx} className="border border-slate-600 px-2 py-1 text-slate-300">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )
          i = j
          continue
        }
      }
      
      // 일반 텍스트 줄
      result.push(<span key={`line-${keyIdx++}`}>{line}{'\n'}</span>)
      i++
    }
    
    return result
  }

  return (
    <div className="space-y-3">
      {/* 토글 버튼 */}
      {rawAnswer && (
        <div className="flex gap-2">
          <button
            onClick={() => setShowRaw(false)}
            className={`px-3 py-1.5 text-xs rounded ${
              !showRaw
                ? 'bg-emerald-500 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            후처리 결과 (사용자용)
          </button>
          <button
            onClick={() => setShowRaw(true)}
            className={`px-3 py-1.5 text-xs rounded ${
              showRaw
                ? 'bg-rose-500 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            원본 출력 (섹션 마커 포함)
          </button>
        </div>
      )}
      
      {/* 내용 */}
      <div className={`rounded-lg p-4 border-2 ${showRaw ? 'border-rose-500 bg-slate-950' : 'border-emerald-500 bg-slate-800'}`}>
        <div className="text-slate-200 text-sm whitespace-pre-wrap leading-relaxed font-mono">
          {showRaw ? rawAnswer : renderWithTables(answer)}
        </div>
      </div>
      
      {/* 안내 메시지 */}
      {showRaw && (
        <div className="text-xs text-slate-500 bg-slate-800 rounded p-2">
          💡 이것은 Final Agent가 출력한 원본입니다. <code className="text-rose-400">===SECTION_START===</code>와 <code className="text-rose-400">===SECTION_END===</code> 마커를 확인하세요.
        </div>
      )}
    </div>
  )
}

// 실시간 로그 탭
function LogsTab({ logs }: { logs: string[] }) {
  const logsEndRef = React.useRef<HTMLDivElement>(null)

  // 로그가 추가될 때마다 자동 스크롤
  React.useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  if (!logs || logs.length === 0) {
    return <EmptyState message="파이프라인 실행 로그가 여기에 표시됩니다" />
  }

  return (
    <div className="bg-slate-950 rounded-lg p-4 font-mono text-xs space-y-0.5 max-h-full overflow-y-auto">
      {logs.map((log, index) => {
        // 로그 타입에 따라 색상 변경
        let textColor = 'text-slate-300'
        if (log.includes('🚀') || log.includes('시작')) {
          textColor = 'text-emerald-400 font-bold'
        } else if (log.includes('✅') || log.includes('완료')) {
          textColor = 'text-green-400'
        } else if (log.includes('❌') || log.includes('오류')) {
          textColor = 'text-red-400'
        } else if (log.includes('📝') || log.includes('📋') || log.includes('🤖') || log.includes('🎯')) {
          textColor = 'text-blue-400'
        } else if (log.startsWith('#')) {
          textColor = 'text-emerald-400'
        } else if (log.startsWith('=')) {
          textColor = 'text-slate-600'
        }

        return (
          <div key={index} className={`${textColor} leading-relaxed`}>
            {log}
          </div>
        )
      })}
      <div ref={logsEndRef} />
    </div>
  )
}

// 공통 컴포넌트
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="text-rose-400 text-xs font-bold mb-2 flex items-center gap-1">
        <span className="w-0.5 h-3 bg-rose-400 rounded"></span>
        {title}
      </h3>
      {children}
    </div>
  )
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-slate-500">
      <svg className="w-12 h-12 mb-3 opacity-30" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
      </svg>
      <p className="text-xs text-center">{message}</p>
    </div>
  )
}

// 모델 설정 탭
function ModelsTab() {
  const [availableModels, setAvailableModels] = useState<string[]>([])
  const [agentModels, setAgentModels] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)

  const agentList = [
    { name: '서울대 agent', desc: '서울대학교 입시 정보' },
    { name: '연세대 agent', desc: '연세대학교 입시 정보' },
    { name: '고려대 agent', desc: '고려대학교 입시 정보' },
    { name: '성균관대 agent', desc: '성균관대학교 입시 정보' },
    { name: '경희대 agent', desc: '경희대학교 입시 정보' },
    { name: '컨설팅 agent', desc: '합격 데이터 분석' },
    { name: '선생님 agent', desc: '학습 계획 및 멘탈 관리' }
  ]

  useEffect(() => {
    loadModels()
    loadAgentModels()
  }, [])

  const loadModels = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/agent/models`)
      setAvailableModels(res.data.models || [])
    } catch (error) {
      console.error('모델 목록 로드 실패:', error)
    }
  }

  const loadAgentModels = async () => {
    try {
      const res = await axios.get(`${API_BASE}/api/agent/agents/models/config`)
      setAgentModels(res.data.agent_models || {})
    } catch (error) {
      console.error('에이전트 모델 설정 로드 실패:', error)
    } finally {
      setLoading(false)
    }
  }

  const updateAgentModel = async (agentName: string, modelName: string) => {
    try {
      await axios.put(`${API_BASE}/api/agent/agents/${encodeURIComponent(agentName)}/model`, {
        model_name: modelName
      })
      
      setAgentModels(prev => ({ ...prev, [agentName]: modelName }))
      
      // 성공 알림
      const toast = document.createElement('div')
      toast.className = 'fixed top-4 right-4 bg-emerald-500 text-white px-4 py-2 rounded-lg shadow-lg text-sm z-50'
      toast.textContent = `✅ ${agentName} → ${modelName} 저장 완료`
      document.body.appendChild(toast)
      setTimeout(() => toast.remove(), 2000)
    } catch (error: any) {
      console.error('모델 변경 실패:', error)
      alert(`❌ 모델 변경 실패: ${error.response?.data?.detail || error.message}`)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400 mx-auto mb-2"></div>
          <p className="text-xs">로딩 중...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="bg-slate-800 rounded-lg p-4 border border-slate-700">
        <h3 className="text-emerald-400 font-bold text-sm mb-2">💡 모델 설정 안내</h3>
        <p className="text-slate-400 text-xs leading-relaxed">
          각 에이전트가 사용할 LLM 모델을 선택할 수 있습니다. 
          변경 즉시 저장되며, 다음 실행부터 적용됩니다.
        </p>
      </div>

      <div className="space-y-2">
        {agentList.map((agent) => {
          const currentModel = agentModels[agent.name] || 'gemini-2.5-flash-lite'
          return (
            <div key={agent.name} className="bg-slate-800 rounded-lg p-3 border border-slate-700">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-emerald-400 font-medium text-sm">{agent.name}</div>
                  <div className="text-slate-500 text-xs mt-0.5">{agent.desc}</div>
                </div>
                <select
                  value={currentModel}
                  onChange={(e) => updateAgentModel(agent.name, e.target.value)}
                  className="bg-slate-900 text-slate-200 text-xs border border-slate-600 rounded px-2 py-1.5 focus:ring-2 focus:ring-emerald-500 focus:outline-none cursor-pointer"
                >
                  {availableModels.map(model => (
                    <option key={model} value={model}>{model}</option>
                  ))}
                </select>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
