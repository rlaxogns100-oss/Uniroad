import { useState } from 'react'
import * as React from 'react'

interface RouterOutput {
  function_calls?: Array<{
    function: string
    params: Record<string, any>
  }>
  raw_response?: string
  tokens?: {
    input: number
    output: number
  }
  error?: string
}

interface FunctionResult {
  university?: string
  query?: string
  count?: number
  chunks?: Array<{
    content: string
    score: number
    page_number?: number
    document_id?: string
    chunk_id?: string
  }>
  document_titles?: Record<string, string>
  document_urls?: Record<string, string>
  document_summaries?: Record<string, string>
  error?: string
}

interface AgentPanelProps {
  routerOutput: RouterOutput | null
  functionResults: Record<string, FunctionResult> | null
  mainAgentOutput: string | null
  rawAnswer?: string | null
  logs: string[]
  isOpen: boolean
  onClose: () => void
}

type TabType = 'query' | 'functions' | 'main' | 'logs'

export default function AgentPanel({
  routerOutput,
  functionResults,
  mainAgentOutput,
  rawAnswer,
  logs,
  isOpen,
  onClose
}: AgentPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('query')

  if (!isOpen) return null

  const tabs: { id: TabType; label: string }[] = [
    { id: 'query', label: 'Query Agent' },
    { id: 'functions', label: 'Functions Result' },
    { id: 'main', label: 'Main Agent' },
    { id: 'logs', label: '실시간 로그' }
  ]

  return (
    <div className="w-1/2 h-screen bg-slate-900 border-r border-slate-700 flex flex-col overflow-hidden">
      {/* 헤더 */}
      <div className="bg-slate-800 border-b border-slate-700 px-4 py-3">
        <div className="flex justify-between items-center">
          <div>
            <h2 className="text-emerald-400 font-bold text-sm">Multi-Agent Pipeline v2</h2>
            <p className="text-slate-500 text-xs">Router → Functions → Main Agent</p>
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
        {activeTab === 'query' && (
          <QueryAgentTab result={routerOutput} />
        )}
        {activeTab === 'functions' && (
          <FunctionsResultTab results={functionResults} />
        )}
        {activeTab === 'main' && (
          <MainAgentTab answer={mainAgentOutput} rawAnswer={rawAnswer} />
        )}
        {activeTab === 'logs' && (
          <LogsTab logs={logs} />
        )}
      </div>
    </div>
  )
}

// Query Agent 탭 (Router 출력)
function QueryAgentTab({ result }: { result: RouterOutput | null }) {
  const [showRaw, setShowRaw] = useState(false)

  if (!result) {
    return <EmptyState message="채팅창에서 질문을 입력하면 Router Agent 결과가 표시됩니다" />
  }

  if (result.error) {
    return <div className="text-red-400 text-sm">{result.error}</div>
  }

  const functionCalls = result.function_calls || []

  return (
    <div className="space-y-4">
      {/* Function Calls */}
      <Section title="Function Calls">
        {functionCalls.length > 0 ? (
          <div className="space-y-2">
            {functionCalls.map((call, index) => (
              <div
                key={index}
                className="bg-slate-800 rounded-lg p-3 border border-slate-700"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="bg-emerald-500 text-slate-900 px-2 py-0.5 rounded text-xs font-bold">
                    {call.function}
                  </span>
                  <span className="text-slate-500 text-xs">#{index + 1}</span>
                </div>
                <div className="space-y-1">
                  {Object.entries(call.params || {}).map(([key, value]) => (
                    <div key={key} className="flex gap-2 text-xs">
                      <span className="text-rose-400 font-medium min-w-[80px]">{key}:</span>
                      <span className="text-slate-300 break-all">
                        {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-slate-500 text-sm bg-slate-800 rounded p-3">
            함수 호출 없음 (일반 대화)
          </div>
        )}
      </Section>

      {/* Tokens */}
      {result.tokens && (
        <Section title="Token Usage">
          <div className="bg-slate-800 rounded p-3 flex gap-4">
            <div className="text-center">
              <div className="text-emerald-400 font-bold text-lg">{result.tokens.input}</div>
              <div className="text-slate-500 text-xs">Input</div>
            </div>
            <div className="text-center">
              <div className="text-rose-400 font-bold text-lg">{result.tokens.output}</div>
              <div className="text-slate-500 text-xs">Output</div>
            </div>
          </div>
        </Section>
      )}

      {/* Raw Response 토글 */}
      {result.raw_response && (
        <Section title="Raw Response">
          <button
            onClick={() => setShowRaw(!showRaw)}
            className="text-xs text-emerald-400 hover:text-emerald-300 mb-2"
          >
            {showRaw ? '▲ 접기' : '▼ LLM 원본 출력 보기'}
          </button>
          {showRaw && (
            <div className="bg-slate-950 rounded p-3 text-xs text-slate-400 font-mono whitespace-pre-wrap max-h-64 overflow-y-auto">
              {result.raw_response}
            </div>
          )}
        </Section>
      )}
    </div>
  )
}

// Functions Result 탭 (RAG 검색 결과)
function FunctionsResultTab({ results }: { results: Record<string, FunctionResult> | null }) {
  const [expandedItems, setExpandedItems] = useState<Set<string>>(new Set())
  const [expandedChunks, setExpandedChunks] = useState<Set<string>>(new Set())

  if (!results || Object.keys(results).length === 0) {
    return <EmptyState message="Functions 실행 결과가 여기에 표시됩니다" />
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

  const toggleChunk = (chunkKey: string) => {
    setExpandedChunks(prev => {
      const newSet = new Set(prev)
      if (newSet.has(chunkKey)) {
        newSet.delete(chunkKey)
      } else {
        newSet.add(chunkKey)
      }
      return newSet
    })
  }

  return (
    <div className="space-y-4">
      {Object.entries(results).map(([key, result]) => {
        const isExpanded = expandedItems.has(key)
        const chunks = result.chunks || []
        const docTitles = result.document_titles || {}
        
        // 함수 타입 파싱 (univ_0, consult_jungsi_1 등)
        const funcType = key.split('_')[0]
        const funcColor = funcType === 'univ' ? 'emerald' : funcType === 'consult' ? 'rose' : 'blue'
        
        return (
          <div key={key} className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
            {/* 헤더 */}
            <div 
              className="p-3 cursor-pointer hover:bg-slate-750 transition-colors"
              onClick={() => toggleExpand(key)}
            >
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className={`bg-${funcColor}-500 text-slate-900 px-2 py-0.5 rounded text-xs font-bold`}>
                    {key}
                  </span>
                  {result.university && (
                    <span className="text-slate-300 text-sm">{result.university}</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-slate-500 text-xs">{chunks.length}개 청크</span>
                  <span className="text-slate-400">{isExpanded ? '▲' : '▼'}</span>
                </div>
              </div>
              {result.query && (
                <div className="text-slate-400 text-xs mt-1">검색어: {result.query}</div>
              )}
            </div>

            {/* 확장된 내용 */}
            {isExpanded && (
              <div className="border-t border-slate-700 p-3 space-y-3">
                {/* 문서 목록 */}
                {Object.keys(docTitles).length > 0 && (
                  <div>
                    <div className="text-rose-400 text-xs font-bold mb-1">참조 문서</div>
                    <div className="flex flex-wrap gap-1">
                      {Object.values(docTitles).filter((v, i, a) => a.indexOf(v) === i).map((title, idx) => (
                        <span key={idx} className="bg-slate-700 text-slate-300 px-2 py-0.5 rounded text-xs">
                          {title}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* 청크 목록 */}
                <div>
                  <div className="text-rose-400 text-xs font-bold mb-2">검색된 청크</div>
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {chunks.map((chunk, idx) => {
                      const chunkKey = `${key}-${idx}`
                      const isChunkExpanded = expandedChunks.has(chunkKey)
                      const docTitle = chunk.document_id ? docTitles[chunk.document_id] : ''
                      
                      return (
                        <div 
                          key={idx} 
                          className="bg-slate-900 rounded p-2 border border-slate-700"
                        >
                          <div 
                            className="flex justify-between items-start cursor-pointer"
                            onClick={() => toggleChunk(chunkKey)}
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-emerald-400 text-xs font-bold">#{idx + 1}</span>
                              {chunk.page_number && (
                                <span className="text-slate-500 text-xs">p.{chunk.page_number}</span>
                              )}
                              <span className="text-yellow-400 text-xs">
                                score: {chunk.score?.toFixed(3) || 'N/A'}
                              </span>
                            </div>
                            <span className="text-slate-400 text-xs">{isChunkExpanded ? '▲' : '▼'}</span>
                          </div>
                          {docTitle && (
                            <div className="text-slate-500 text-xs mt-1">{docTitle}</div>
                          )}
                          <div className={`text-slate-300 text-xs mt-2 whitespace-pre-wrap ${
                            isChunkExpanded ? '' : 'line-clamp-3'
                          }`}>
                            {chunk.content}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// Main Agent 탭 (최종 답변)
function MainAgentTab({ answer, rawAnswer }: { answer: string | null, rawAnswer?: string | null }) {
  const [showRaw, setShowRaw] = useState(false)
  
  if (!answer) {
    return <EmptyState message="Main Agent 답변이 여기에 표시됩니다" />
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
          이것은 Main Agent가 출력한 원본입니다. <code className="text-rose-400">===SECTION_START===</code>와 <code className="text-rose-400">===SECTION_END===</code> 마커를 확인하세요.
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
        if (log.includes('🔄') || log.includes('[1/3]') || log.includes('[2/3]') || log.includes('[3/3]')) {
          textColor = 'text-blue-400 font-bold'
        } else if (log.includes('✅') || log.includes('완료')) {
          textColor = 'text-green-400'
        } else if (log.includes('❌') || log.includes('오류') || log.includes('⚠️')) {
          textColor = 'text-red-400'
        } else if (log.includes('🔍') || log.includes('검색')) {
          textColor = 'text-yellow-400'
        } else if (log.includes('📊') || log.includes('분석')) {
          textColor = 'text-purple-400'
        } else if (log.includes('Router')) {
          textColor = 'text-emerald-400'
        } else if (log.includes('Function')) {
          textColor = 'text-rose-400'
        } else if (log.includes('Main Agent')) {
          textColor = 'text-cyan-400'
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
