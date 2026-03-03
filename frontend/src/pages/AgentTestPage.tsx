import { useState, useCallback, useRef, useEffect } from 'react'
import * as XLSX from 'xlsx'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// 처리 로그 타입
interface ProcessLog {
  time: string
  message: string
  type: 'info' | 'success' | 'error'
}

// 타입 정의
interface ExcelRow {
  row_index: number
  history: string
  question: string
  router_output: string
  function_result: string
  final_answer: string
}

interface EvalResult {
  row_index: number
  history: string
  question: string
  router_output: string
  function_result: string
  final_answer: string
  router_score?: number
  main_score?: number
  total_score?: number
  router_eval?: {
    intent_understanding?: boolean
    function_selection?: boolean
    query_params?: boolean
    json_format?: boolean
    score_conversion?: boolean
    comment?: string
  }
  main_eval?: {
    answer_relevance?: boolean
    source_based?: boolean
    output_format?: boolean
    citation_accuracy?: boolean
    no_confusion?: boolean
    comment?: string
  }
  error?: string
}

interface BatchResponse {
  results: EvalResult[]
  total_rows: number
  success_count: number
  error_count: number
  avg_router_score?: number
  avg_main_score?: number
  avg_total_score?: number
}

type TabType = 'router' | 'main' | 'pipeline' | 'admin'

// JSON 포맷팅 함수
function formatJsonContent(content: string): string {
  if (!content) return content
  try {
    const parsed = JSON.parse(content)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return content
  }
}

// 드롭다운 셀 컴포넌트
function ExpandableCell({ content, maxLength = 30, isExpanded = false, isJson = false }: { content: string, maxLength?: number, isExpanded?: boolean, isJson?: boolean }) {
  const formattedContent = isJson && isExpanded ? formatJsonContent(content) : content
  const displayContent = isExpanded 
    ? formattedContent 
    : (content?.length > maxLength ? content.substring(0, maxLength) + '...' : content)
  
  return (
    <div className="relative">
      {isExpanded ? (
        <pre className="text-xs whitespace-pre-wrap font-mono max-h-[400px] overflow-y-auto bg-gray-50 p-2 rounded">
          {formattedContent || '-'}
        </pre>
      ) : (
        <span className="text-xs font-mono text-gray-700 truncate block">{displayContent || '-'}</span>
      )}
    </div>
  )
}

// O/X 표시 컴포넌트
function OXBadge({ value }: { value?: boolean }) {
  if (value === undefined) return <span className="text-gray-400">-</span>
  return value 
    ? <span className="text-green-600 font-bold">O</span>
    : <span className="text-red-600 font-bold">X</span>
}

// 점수 배지 컴포넌트
function ScoreBadge({ score, max }: { score?: number, max: number }) {
  if (score === undefined) return <span className="text-gray-400 text-xs">-</span>
  
  const ratio = score / max
  let colorClass = 'bg-red-100 text-red-800'
  if (ratio >= 0.8) colorClass = 'bg-green-100 text-green-800'
  else if (ratio >= 0.6) colorClass = 'bg-yellow-100 text-yellow-800'
  else if (ratio >= 0.4) colorClass = 'bg-orange-100 text-orange-800'
  
  return (
    <span className={`px-1 py-0.5 rounded text-xs font-bold ${colorClass}`}>
      {score}/{max}
    </span>
  )
}

export default function AgentTestPage() {
  const [activeTab, setActiveTab] = useState<TabType>('router')
  const [rows, setRows] = useState<ExcelRow[]>([])
  const [results, setResults] = useState<EvalResult[]>([])
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [stats, setStats] = useState<{ avgRouter?: number, avgMain?: number, avgTotal?: number }>({})
  const [logs, setLogs] = useState<ProcessLog[]>([])
  const logRef = useRef<HTMLDivElement>(null)
  
  // 프롬프트 관련 상태
  const [showPromptEditor, setShowPromptEditor] = useState(false)
  const [routerPrompt, setRouterPrompt] = useState('')
  const [isDefaultPrompt, setIsDefaultPrompt] = useState(true)
  const [promptLoading, setPromptLoading] = useState(false)

  // 프롬프트 로드
  const loadPrompt = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/test/router-prompt`)
      if (response.ok) {
        const data = await response.json()
        setRouterPrompt(data.prompt)
        setIsDefaultPrompt(data.is_default)
      }
    } catch (err) {
      console.error('프롬프트 로드 실패:', err)
    }
  }, [])

  // 프롬프트 저장
  const savePrompt = useCallback(async () => {
    setPromptLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/test/router-prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: routerPrompt })
      })
      if (response.ok) {
        setIsDefaultPrompt(false)
        addLog('Router 프롬프트가 업데이트되었습니다. 즉시 반영됩니다.', 'success')
      } else {
        throw new Error('프롬프트 저장 실패')
      }
    } catch (err: any) {
      addLog(`프롬프트 저장 실패: ${err.message}`, 'error')
    } finally {
      setPromptLoading(false)
    }
  }, [routerPrompt])

  // 프롬프트 리셋
  const resetPrompt = useCallback(async () => {
    if (!confirm('기본 프롬프트로 리셋하시겠습니까?')) return
    
    setPromptLoading(true)
    try {
      const response = await fetch(`${API_BASE}/api/test/router-prompt/reset`, {
        method: 'POST'
      })
      if (response.ok) {
        await loadPrompt()
        addLog('Router 프롬프트가 기본값으로 리셋되었습니다.', 'success')
      }
    } catch (err: any) {
      addLog(`프롬프트 리셋 실패: ${err.message}`, 'error')
    } finally {
      setPromptLoading(false)
    }
  }, [loadPrompt])

  // 컴포넌트 마운트 시 프롬프트 로드
  useEffect(() => {
    loadPrompt()
  }, [])

  // 로그 추가 함수
  const addLog = (message: string, type: ProcessLog['type'] = 'info') => {
    const time = new Date().toLocaleTimeString('ko-KR')
    setLogs(prev => [...prev, { time, message, type }])
    setTimeout(() => {
      if (logRef.current) {
        logRef.current.scrollTop = logRef.current.scrollHeight
      }
    }, 50)
  }

  // Excel 업로드
  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setLoading(true)
    setLogs([])
    addLog(`파일 업로드 시작: ${file.name}`)
    
    try {
      const formData = new FormData()
      formData.append('file', file)

      const response = await fetch(`${API_BASE}/api/test/upload-excel`, {
        method: 'POST',
        body: formData
      })

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || 'Excel 업로드 실패')
      }

      const data = await response.json()
      setRows(data.rows)
      setResults([])
      setExpandedRows(new Set())
      setStats({})
      addLog(`${data.total_rows}개 행 로드 완료`, 'success')
    } catch (err: any) {
      addLog(`오류: ${err.message}`, 'error')
      alert(`오류: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [])

  // 평가 실행
  const runEvaluation = useCallback(async () => {
    if (rows.length === 0) {
      alert('먼저 Excel 파일을 업로드하세요')
      return
    }

    setLoading(true)
    setProgress({ current: 0, total: rows.length })
    setLogs([])
    
    const startTime = Date.now()
    addLog(`평가 시작: ${rows.length}개 행, ${activeTab} 모드`)

    try {
      const endpoint = {
        router: '/api/test/router-evaluate',
        main: '/api/test/main-evaluate',
        pipeline: '/api/test/pipeline-evaluate',
        admin: '/api/test/admin-evaluate'
      }[activeTab]

      addLog(`API 호출 중... (타임아웃: 30분)`)
      
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 30 * 60 * 1000) // 30분 타임아웃
      
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rows }),
        signal: controller.signal
      })
      
      clearTimeout(timeoutId)

      if (!response.ok) {
        const error = await response.json()
        throw new Error(error.detail || '평가 실패')
      }

      const data: BatchResponse = await response.json()
      setResults(data.results)
      setStats({
        avgRouter: data.avg_router_score,
        avgMain: data.avg_main_score,
        avgTotal: data.avg_total_score
      })
      setProgress({ current: data.total_rows, total: data.total_rows })

      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
      addLog(`평가 완료: 성공 ${data.success_count}개, 실패 ${data.error_count}개 (${elapsed}초)`, 'success')
    } catch (err: any) {
      if (err.name === 'AbortError') {
        addLog('타임아웃: 30분 초과', 'error')
      } else {
        addLog(`오류: ${err.message}`, 'error')
      }
      alert(`오류: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [rows, activeTab])

  // Excel 내보내기
  const exportExcel = useCallback(async () => {
    if (results.length === 0) {
      alert('먼저 평가를 실행하세요')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/api/test/export-excel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results, eval_type: activeTab })
      })

      if (!response.ok) {
        throw new Error('Excel 내보내기 실패')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `eval_${activeTab}_${new Date().toISOString().slice(0, 10)}.xlsx`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      alert(`오류: ${err.message}`)
    }
  }, [results, activeTab])

  // CSV 내보내기 (Google Sheets용)
  const exportCSV = useCallback(async () => {
    if (results.length === 0) {
      alert('먼저 평가를 실행하세요')
      return
    }

    try {
      const response = await fetch(`${API_BASE}/api/test/export-csv`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results, eval_type: activeTab })
      })

      if (!response.ok) {
        throw new Error('CSV 내보내기 실패')
      }

      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `eval_${activeTab}_${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch (err: any) {
      alert(`오류: ${err.message}`)
    }
  }, [results, activeTab])

  // 행 토글
  const toggleRow = (index: number) => {
    setExpandedRows(prev => {
      const next = new Set(prev)
      if (next.has(index)) {
        next.delete(index)
      } else {
        next.add(index)
      }
      return next
    })
  }

  // 탭 변경 시 결과 초기화
  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab)
    setResults([])
    setExpandedRows(new Set())
    setStats({})
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* 프롬프트 편집 모달 */}
      {showPromptEditor && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-[90vw] h-[90vh] flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-bold text-gray-900">Router System Prompt 편집</h2>
                {!isDefaultPrompt && (
                  <span className="px-2 py-0.5 bg-yellow-100 text-yellow-800 text-xs rounded">커스텀</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={resetPrompt}
                  disabled={promptLoading || isDefaultPrompt}
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900 disabled:opacity-50"
                >
                  기본값으로 리셋
                </button>
                <button
                  onClick={savePrompt}
                  disabled={promptLoading}
                  className="px-4 py-1.5 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700 disabled:opacity-50"
                >
                  {promptLoading ? '저장 중...' : '저장 (즉시 반영)'}
                </button>
                <button
                  onClick={() => setShowPromptEditor(false)}
                  className="px-3 py-1.5 text-gray-500 hover:text-gray-700"
                >
                  닫기
                </button>
              </div>
            </div>
            <div className="flex-1 p-4 overflow-hidden">
              <textarea
                value={routerPrompt}
                onChange={(e) => setRouterPrompt(e.target.value)}
                className="w-full h-full p-4 font-mono text-sm border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500"
                placeholder="Router System Prompt를 입력하세요..."
              />
            </div>
            <div className="px-4 py-2 border-t border-gray-200 text-xs text-gray-500">
              저장하면 즉시 반영됩니다. 서버 재시작 필요 없음.
            </div>
          </div>
        </div>
      )}

      {/* 헤더 */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="px-6 py-3">
          <h1 className="text-xl font-bold text-gray-900">Agent Test Environment</h1>
          <p className="text-xs text-gray-500">Router/Main/Pipeline 평가 시스템</p>
        </div>
      </header>

      {/* 탭 네비게이션 */}
      <nav className="bg-white border-b border-gray-200 px-6">
        <div className="flex gap-1">
          {(['router', 'main', 'pipeline', 'admin'] as TabType[]).map(tab => (
            <button
              key={tab}
              onClick={() => handleTabChange(tab)}
              className={`px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${
                activeTab === tab
                  ? 'bg-indigo-100 text-indigo-800 border-b-2 border-indigo-600 -mb-px'
                  : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
              }`}
            >
              {tab === 'router' && 'Router 평가'}
              {tab === 'main' && 'Main 평가'}
              {tab === 'pipeline' && 'Pipeline 평가'}
              {tab === 'admin' && 'Admin 평가'}
            </button>
          ))}
        </div>
      </nav>

      {/* 메인 컨텐츠 - 전체 너비 사용 */}
      <main className="px-4 py-4">
        {/* 컨트롤 패널 */}
        <div className="bg-white rounded-lg shadow-sm p-3 mb-4">
          <div className="flex flex-wrap items-center gap-3">
            {/* Excel 업로드 */}
            <label className="px-3 py-1.5 bg-blue-600 text-white text-sm rounded cursor-pointer hover:bg-blue-700 transition-colors">
              Excel 업로드
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={handleFileUpload}
                className="hidden"
              />
            </label>

            {/* 평가 실행 */}
            <button
              onClick={runEvaluation}
              disabled={loading || rows.length === 0}
              className="px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? '평가 중...' : '평가 실행'}
            </button>

            {/* 내보내기 */}
            <button
              onClick={exportExcel}
              disabled={results.length === 0}
              className="px-3 py-1.5 bg-emerald-100 text-emerald-800 text-sm rounded hover:bg-emerald-200 transition-colors disabled:opacity-50"
            >
              Excel 내보내기
            </button>

            <button
              onClick={exportCSV}
              disabled={results.length === 0}
              className="px-3 py-1.5 bg-purple-100 text-purple-800 text-sm rounded hover:bg-purple-200 transition-colors disabled:opacity-50"
            >
              CSV (Google Sheets)
            </button>

            {/* 프롬프트 편집 버튼 */}
            <button
              onClick={() => setShowPromptEditor(true)}
              className={`px-3 py-1.5 text-sm rounded transition-colors ${
                isDefaultPrompt 
                  ? 'bg-gray-100 text-gray-700 hover:bg-gray-200' 
                  : 'bg-yellow-100 text-yellow-800 hover:bg-yellow-200'
              }`}
            >
              Router 프롬프트 {!isDefaultPrompt && '(커스텀)'}
            </button>

            {/* 상태 표시 */}
            <div className="ml-auto flex items-center gap-4 text-xs text-gray-600">
              <span>로드된 행: {rows.length}개</span>
              {results.length > 0 && <span>평가 완료: {results.length}개</span>}
            </div>
          </div>

          {/* 진행률 + 로그 */}
          {loading && (
            <div className="mt-3">
              <div className="flex justify-between text-xs text-gray-600 mb-1">
                <span>처리 중...</span>
                <span>{rows.length}개 행 처리 대기</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-1.5">
                <div className="bg-indigo-600 h-1.5 rounded-full animate-pulse" style={{ width: '100%' }} />
              </div>
            </div>
          )}

          {/* 처리 로그 */}
          {logs.length > 0 && (
            <div 
              ref={logRef}
              className="mt-3 bg-gray-900 text-gray-100 rounded p-2 text-xs font-mono max-h-24 overflow-y-auto"
            >
              {logs.map((log, i) => (
                <div key={i} className={`${log.type === 'error' ? 'text-red-400' : log.type === 'success' ? 'text-green-400' : 'text-gray-300'}`}>
                  [{log.time}] {log.message}
                </div>
              ))}
            </div>
          )}

          {/* 통계 */}
          {(stats.avgRouter != null || stats.avgMain != null || stats.avgTotal != null) && (
            <div className="mt-3 flex gap-6 text-xs">
              {stats.avgRouter != null && (
                <span>평균 Router 점수: <strong>{stats.avgRouter.toFixed(2)}/5</strong></span>
              )}
              {stats.avgMain != null && (
                <span>평균 Main 점수: <strong>{stats.avgMain.toFixed(2)}/5</strong></span>
              )}
              {stats.avgTotal != null && (
                <span>평균 총점: <strong>{stats.avgTotal.toFixed(2)}/10</strong></span>
              )}
            </div>
          )}
        </div>

        {/* 결과 테이블 */}
        <div className="bg-white rounded-lg shadow-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-0.5 py-2 text-left text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>#</th>
                  <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: 'auto'}}>이전대화</th>
                  <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: 'auto'}}>사용자질문</th>
                  <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: 'auto'}}>Router출력</th>
                  
                  {(activeTab === 'main' || activeTab === 'pipeline' || activeTab === 'admin') && (
                    <>
                      <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: 'auto'}}>Function결과</th>
                      <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: 'auto'}}>최종답변</th>
                    </>
                  )}

                  {/* 점수 컬럼 - 최소 너비 */}
                  {activeTab === 'router' && (
                    <>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '36px', width: '36px'}}>점수</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>의도</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>함수</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>쿼리</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>JSON</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>성적</th>
                    </>
                  )}

                  {activeTab === 'main' && (
                    <>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '36px', width: '36px'}}>점수</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>답변</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>자료</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>형식</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>인용</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '24px', width: '24px'}}>혼동</th>
                    </>
                  )}

                  {(activeTab === 'pipeline' || activeTab === 'admin') && (
                    <>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '36px', width: '36px'}}>총점</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '32px', width: '32px'}}>R점수</th>
                      <th className="px-0.5 py-2 text-center text-xs font-semibold text-gray-600" style={{minWidth: '32px', width: '32px'}}>M점수</th>
                    </>
                  )}
                </tr>
              </thead>
              <tbody>
                {(results.length > 0 ? results : rows).map((item, idx) => {
                  const result = results.find(r => r.row_index === (item as any).row_index) || item as EvalResult
                  const isExpanded = expandedRows.has(result.row_index)
                  const hasError = result.error

                  return (
                    <tr
                      key={result.row_index}
                      onClick={() => toggleRow(result.row_index)}
                      className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${
                        hasError ? 'bg-red-50' : idx % 2 === 0 ? '' : 'bg-gray-25'
                      }`}
                    >
                      <td className="px-0.5 py-1 text-xs text-gray-500 align-top">{result.row_index + 1}</td>
                      <td className="px-2 py-1 align-top">
                        <ExpandableCell content={result.history} isExpanded={isExpanded} />
                      </td>
                      <td className="px-2 py-1 align-top">
                        <ExpandableCell content={result.question} isExpanded={isExpanded} />
                      </td>
                      <td className="px-2 py-1 align-top">
                        <ExpandableCell content={result.router_output} isExpanded={isExpanded} isJson={true} />
                      </td>

                      {(activeTab === 'main' || activeTab === 'pipeline' || activeTab === 'admin') && (
                        <>
                          <td className="px-2 py-1 align-top">
                            <ExpandableCell content={result.function_result} isExpanded={isExpanded} isJson={true} />
                          </td>
                          <td className="px-2 py-1 align-top">
                            <ExpandableCell content={result.final_answer} isExpanded={isExpanded} />
                          </td>
                        </>
                      )}

                      {/* Router 평가 컬럼 */}
                      {activeTab === 'router' && (
                        <>
                          <td className="px-0.5 py-1 text-center align-top">
                            <ScoreBadge score={result.router_score} max={5} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.router_eval?.intent_understanding} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.router_eval?.function_selection} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.router_eval?.query_params} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.router_eval?.json_format} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.router_eval?.score_conversion} />
                          </td>
                        </>
                      )}

                      {/* Main 평가 컬럼 */}
                      {activeTab === 'main' && (
                        <>
                          <td className="px-0.5 py-1 text-center align-top">
                            <ScoreBadge score={result.main_score} max={5} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.main_eval?.answer_relevance} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.main_eval?.source_based} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.main_eval?.output_format} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.main_eval?.citation_accuracy} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <OXBadge value={result.main_eval?.no_confusion} />
                          </td>
                        </>
                      )}

                      {/* Pipeline/Admin 평가 컬럼 */}
                      {(activeTab === 'pipeline' || activeTab === 'admin') && (
                        <>
                          <td className="px-0.5 py-1 text-center align-top">
                            <ScoreBadge score={result.total_score} max={10} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <ScoreBadge score={result.router_score} max={5} />
                          </td>
                          <td className="px-0.5 py-1 text-center align-top">
                            <ScoreBadge score={result.main_score} max={5} />
                          </td>
                        </>
                      )}
                    </tr>
                  )
                })}

                {rows.length === 0 && (
                  <tr>
                    <td colSpan={20} className="px-4 py-8 text-center text-gray-500 text-sm">
                      Excel 파일을 업로드하세요
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 탭별 설명 */}
        <div className="mt-4 bg-white rounded-lg shadow-sm p-3">
          <h3 className="font-semibold text-gray-900 text-sm mb-1">
            {activeTab === 'router' && 'Router 평가 기준 (5점 만점)'}
            {activeTab === 'main' && 'Main 평가 기준 (5점 만점)'}
            {activeTab === 'pipeline' && 'Pipeline 평가 기준 (10점 만점)'}
            {activeTab === 'admin' && 'Admin 평가 기준 (10점 만점)'}
          </h3>
          
          {activeTab === 'router' && (
            <ul className="text-sm text-gray-600 space-y-1">
              <li><strong>의도파악:</strong> 사용자의 질문 의도를 제대로 파악했는가?</li>
              <li><strong>함수선택:</strong> 적절한 함수를 호출하고 불필요한 함수를 호출하지 않았는가?</li>
              <li><strong>쿼리변수:</strong> 함수 호출시 쿼리와 변수가 적절한가?</li>
              <li><strong>JSON형식:</strong> JSON 형식을 준수하였는가?</li>
              <li><strong>성적환산:</strong> 성적 환산을 올바르게 하였는가? (성적 언급 없으면 O)</li>
            </ul>
          )}

          {activeTab === 'main' && (
            <ul className="text-sm text-gray-600 space-y-1">
              <li><strong>답변적절:</strong> 사용자의 의도에 맞는 적절한 대답인가?</li>
              <li><strong>자료기반:</strong> 자체적으로 정보를 생성하지 않고, 주어진 자료에 근거해서 대답하였는가?</li>
              <li><strong>출력형식:</strong> 출력 형식을 준수하였는가?</li>
              <li><strong>인용정확:</strong> 인용 자료의 출처가 정확하게 명시되었는가?</li>
              <li><strong>혼동없음:</strong> 주어진 자료를 학생 정보로 혼동하지 않았는가?</li>
            </ul>
          )}

          {(activeTab === 'pipeline' || activeTab === 'admin') && (
            <ul className="text-sm text-gray-600 space-y-1">
              <li><strong>Router 5점:</strong> 의도파악, 함수선택, 쿼리변수, JSON형식, 성적환산</li>
              <li><strong>Main 5점:</strong> 답변적절, 자료기반, 출력형식, 인용정확, 혼동없음</li>
              <li className="mt-2 text-indigo-600">
                {activeTab === 'pipeline' 
                  ? '* Pipeline: 이전대화 + 사용자질문만 입력 → Router/Function/Main 전체 실행 후 평가'
                  : '* Admin: 모든 데이터가 입력된 상태에서 평가만 수행 (생성 없음)'}
              </li>
            </ul>
          )}
        </div>
      </main>
    </div>
  )
}
