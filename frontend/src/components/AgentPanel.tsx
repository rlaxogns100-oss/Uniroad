import { useState } from 'react'
import * as React from 'react'

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
  logs: string[]
  isOpen: boolean
  onClose: () => void
}

type TabType = 'orchestration' | 'subagents' | 'final' | 'logs'

export default function AgentPanel({
  orchestrationResult,
  subAgentResults,
  finalAnswer,
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
    { id: 'logs', label: '실시간 로그' }
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
          <FinalAnswerTab answer={finalAnswer} />
        )}
        {activeTab === 'logs' && (
          <LogsTab logs={logs} />
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
  if (!results || Object.keys(results).length === 0) {
    return <EmptyState message="Sub Agent 실행 결과가 여기에 표시됩니다" />
  }

  return (
    <div className="space-y-3">
      {Object.entries(results).map(([key, result]) => (
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
          <div className="text-slate-300 text-xs whitespace-pre-wrap max-h-48 overflow-y-auto">
            {result.result || '결과 없음'}
          </div>
          {result.sources && result.sources.length > 0 && (
            <div className="mt-2 pt-2 border-t border-slate-700">
              <div className="text-slate-500 text-xs">출처: {result.sources.join(', ')}</div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// Final Answer 탭
function FinalAnswerTab({ answer }: { answer: string | null }) {
  if (!answer) {
    return <EmptyState message="최종 답변이 여기에 표시됩니다" />
  }

  return (
    <div className="bg-slate-800 rounded-lg p-4 border-2 border-emerald-500">
      <div className="text-slate-200 text-sm whitespace-pre-wrap leading-relaxed">
        {answer}
      </div>
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
