import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  getLogs, 
  fetchLogs, 
  clearLogs, 
  updateLogEvaluation, 
  migrateLocalStorageLogs,
  hasLocalStorageLogs,
  ExecutionLog 
} from '../utils/adminLogger'

// Admin Agent 평가 함수 (백그라운드에서 비동기 실행, 백엔드 API 호출)
async function evaluateLog(log: ExecutionLog): Promise<void> {
  const evaluation: ExecutionLog['evaluation'] = {
    routerStatus: 'pending',
    functionStatus: 'pending',
    answerStatus: 'pending',
    timeStatus: 'ok',
  }
  
  // 소요시간 평가 (프론트엔드에서 처리) - 5초/10초 기준
  if (log.elapsedTime > 10000) {
    evaluation.timeStatus = 'error'
    evaluation.timeComment = '10초 초과'
  } else if (log.elapsedTime > 5000) {
    evaluation.timeStatus = 'warning'
    evaluation.timeComment = '5초 초과'
  } else {
    evaluation.timeStatus = 'ok'
    // ok 상태에서는 코멘트 없음
  }
  
  // Router 출력이 없으면 바로 에러
  if (!log.routerOutput) {
    evaluation.routerStatus = 'error'
    evaluation.routerComment = 'Router 출력이 없습니다'
    await updateLogEvaluation(log.id, evaluation)
    return
  }
  
  // routerOutput을 문자열로 변환 (기존 로그는 객체, 새 로그는 문자열)
  const routerOutputStr = typeof log.routerOutput === 'string'
    ? log.routerOutput
    : JSON.stringify(log.routerOutput, null, 2)
  
  // 1. Router 평가 API 호출
  try {
    const response = await fetch('/api/admin/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_question: log.userQuestion.replace(/^\[추가실행 \d+\] /, ''), // 추가실행 태그 제거
        router_output: routerOutputStr
      })
    })
    
    if (response.ok) {
      const result = await response.json()
      evaluation.routerStatus = result.status as 'ok' | 'warning' | 'error'
      
      if (evaluation.routerStatus !== 'ok') {
        evaluation.routerComment = result.overall_comment || ''
      }
    } else {
      evaluation.routerStatus = 'warning'
      evaluation.routerComment = 'API 호출 실패'
    }
  } catch (error) {
    evaluation.routerStatus = 'warning'
    evaluation.routerComment = 'API 호출 오류'
  }
  
  // 2. Function 결과 평가 API 호출
  if (log.functionResult) {
    try {
      // routerOutput에서 function_calls 추출
      let routerObj = log.routerOutput
      if (typeof routerObj === 'string') {
        try { routerObj = JSON.parse(routerObj) } catch { routerObj = {} }
      }
      const functionCalls = routerObj?.function_calls || []
      
      const response = await fetch('/api/admin/evaluate-function', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_question: log.userQuestion.replace(/^\[추가실행 \d+\] /, ''),
          function_calls: functionCalls,
          function_results: log.functionResult
        })
      })
      
      if (response.ok) {
        const result = await response.json()
        evaluation.functionStatus = result.status as 'ok' | 'warning' | 'error'
        
        if (evaluation.functionStatus !== 'ok') {
          evaluation.functionComment = result.comment || ''
        } else {
          evaluation.functionComment = `${result.total_chunks}개 청크`
        }
      } else {
        evaluation.functionStatus = 'warning'
        evaluation.functionComment = 'API 호출 실패'
      }
    } catch (error) {
      evaluation.functionStatus = 'warning'
      evaluation.functionComment = 'API 호출 오류'
    }
  } else {
    evaluation.functionStatus = 'pending'
    evaluation.functionComment = '결과 없음'
  }
  
  // 3. 최종 답변 평가 API 호출 (LLM 기반)
  if (log.finalAnswer && log.functionResult) {
    try {
      const response = await fetch('/api/admin/evaluate-final', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_question: log.userQuestion.replace(/^\[추가실행 \d+\] /, ''),
          conversation_history: log.conversationHistory || [],
          function_results: log.functionResult,
          final_response: log.finalAnswer
        })
      })
      
      if (response.ok) {
        const result = await response.json()
        evaluation.answerStatus = result.status as 'ok' | 'warning' | 'error'
        
        // 문제가 있는 항목들 코멘트로 수집
        const issues: string[] = []
        if (!result.source_accuracy?.valid) issues.push('출처')
        if (!result.hallucination_check?.valid) issues.push('할루시네이션')
        if (!result.length_check?.valid) issues.push('길이')
        if (!result.context_relevance?.valid) issues.push('맥락')
        if (!result.format_check?.valid) issues.push('형식')
        
        if (issues.length > 0) {
          evaluation.answerComment = `문제: ${issues.join(', ')}`
        } else if (result.overall_comment) {
          evaluation.answerComment = result.overall_comment.substring(0, 50)
        }
      } else {
        evaluation.answerStatus = 'warning'
        evaluation.answerComment = 'API 호출 실패'
      }
    } catch (error) {
      evaluation.answerStatus = 'warning'
      evaluation.answerComment = 'API 호출 오류'
    }
  } else {
    evaluation.answerStatus = 'pending'
    evaluation.answerComment = log.finalAnswer ? 'Function 결과 없음' : '답변 없음'
  }
  
  await updateLogEvaluation(log.id, evaluation)
}

// 상태 색상 반환
function getStatusColor(status: string): string {
  switch (status) {
    case 'ok': return 'bg-green-100 text-green-800'
    case 'warning': return 'bg-yellow-100 text-yellow-800'
    case 'error': return 'bg-red-100 text-red-800'
    default: return 'bg-gray-100 text-gray-600'
  }
}

function getStatusBgColor(status: string): string {
  switch (status) {
    case 'ok': return 'bg-green-50'
    case 'warning': return 'bg-yellow-50'
    case 'error': return 'bg-red-50'
    default: return ''
  }
}

// routerOutput에서 불필요한 필드 제거
function cleanRouterOutput(output: any): any {
  if (!output) return output
  
  // 문자열이면 먼저 파싱
  let obj = output
  if (typeof output === 'string') {
    try {
      obj = JSON.parse(output)
    } catch {
      return output
    }
  }
  
  if (typeof obj !== 'object') return obj
  
  const cleaned = { ...obj }
  delete cleaned.raw_response
  delete cleaned.tokens
  return cleaned
}

// functionResult 포맷팅 (청크 내용 전체 표시)
function formatFunctionResult(result: any): any {
  if (!result) return null
  
  // 문자열이면 파싱
  let obj = result
  if (typeof result === 'string') {
    try {
      obj = JSON.parse(result)
    } catch {
      return result
    }
  }
  
  if (typeof obj !== 'object') return obj
  
  // 각 함수 결과에서 chunks 정보 포맷팅 (내용 전체 표시)
  const formatted: any = {}
  for (const [key, value] of Object.entries(obj)) {
    if (typeof value === 'object' && value !== null && 'chunks' in (value as any)) {
      const funcResult = value as any
      formatted[key] = {
        count: funcResult.count,
        university: funcResult.university,
        query: funcResult.query,
        chunks: funcResult.chunks?.map((chunk: any) => ({
          chunk_id: chunk.chunk_id,
          document_id: chunk.document_id,
          page: chunk.page_number,
          score: chunk.weighted_score?.toFixed(3) || chunk.score?.toFixed(3),
          // 청크 내용 전체 표시
          content: chunk.content
        }))
      }
    } else {
      formatted[key] = value
    }
  }
  
  return formatted
}

// 드롭다운 셀 컴포넌트 (행 단위 제어)
function ExpandableCell({ content, maxLength = 30, cleanRouter = false, isExpanded = false }: { content: any, maxLength?: number, cleanRouter?: boolean, isExpanded?: boolean }) {
  let processedContent = cleanRouter ? cleanRouterOutput(content) : content
  
  // 문자열인 경우 JSON 파싱 시도 (이미 stringify된 경우)
  if (typeof processedContent === 'string') {
    try {
      const parsed = JSON.parse(processedContent)
      processedContent = parsed
    } catch {
      // 파싱 실패하면 원본 문자열 사용
    }
  }
  
  const stringContent = typeof processedContent === 'object' 
    ? JSON.stringify(processedContent, null, 2) 
    : String(processedContent || '-')
  
  const needsExpansion = stringContent.length > maxLength
  const displayContent = needsExpansion && !isExpanded 
    ? stringContent.substring(0, maxLength) + '...'
    : stringContent
  
  return (
    <div className="relative">
      {isExpanded ? (
        <pre className="text-xs whitespace-pre-wrap font-mono max-h-[500px] overflow-y-auto bg-gray-50 p-2 rounded">
          {stringContent}
        </pre>
      ) : (
        <span className="text-xs font-mono text-gray-700">{displayContent}</span>
      )}
    </div>
  )
}

export default function AdminAgentPage() {
  const navigate = useNavigate()
  const [logs, setLogs] = useState<ExecutionLog[]>([])
  const [loading, setLoading] = useState(true)
  const [evaluatingIds, setEvaluatingIds] = useState<Set<string>>(new Set())
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [showMigrateBanner, setShowMigrateBanner] = useState(false)
  const [migrating, setMigrating] = useState(false)

  // 로그 로드 (Supabase에서)
  const loadLogs = useCallback(async () => {
    setLoading(true)
    try {
      const fetchedLogs = await fetchLogs()
      setLogs(fetchedLogs)
    } catch (error) {
      console.error('로그 로드 오류:', error)
    } finally {
      setLoading(false)
    }
  }, [])

  // pending 로그 자동 평가
  const evaluatePendingLogs = useCallback(async (logsToCheck: ExecutionLog[]) => {
    const pendingLogs = logsToCheck.filter(
      log => log.evaluation?.routerStatus === 'pending' && !evaluatingIds.has(log.id)
    )
    
    for (const log of pendingLogs) {
      setEvaluatingIds(prev => new Set([...prev, log.id]))
      evaluateLog(log).finally(() => {
        setEvaluatingIds(prev => {
          const next = new Set(prev)
          next.delete(log.id)
          return next
        })
        // 캐시 업데이트 후 상태 반영
        setLogs(getLogs())
      })
    }
  }, [evaluatingIds])

  // 마이그레이션 처리
  const handleMigrate = async () => {
    setMigrating(true)
    try {
      const result = await migrateLocalStorageLogs()
      if (result.migrated > 0) {
        alert(`${result.migrated}개의 로그가 마이그레이션되었습니다.`)
        await loadLogs()
      }
      setShowMigrateBanner(false)
    } catch (error) {
      alert('마이그레이션 중 오류가 발생했습니다.')
    } finally {
      setMigrating(false)
    }
  }

  // 초기 로드 및 이벤트 리스너
  useEffect(() => {
    // localStorage에 미마이그레이션 로그가 있는지 확인
    if (hasLocalStorageLogs()) {
      setShowMigrateBanner(true)
    }

    // Supabase에서 로그 로드
    loadLogs().then(() => {
      const cached = getLogs()
      evaluatePendingLogs(cached)
    })
    
    // 실시간 업데이트 리스너
    const handleLogUpdated = async (e: CustomEvent) => {
      // 새 로그 자동 평가
      const newLog = e.detail as ExecutionLog
      setLogs(getLogs())
      
      if (!evaluatingIds.has(newLog.id)) {
        setEvaluatingIds(prev => new Set([...prev, newLog.id]))
        evaluateLog(newLog).finally(() => {
          setEvaluatingIds(prev => {
            const next = new Set(prev)
            next.delete(newLog.id)
            return next
          })
          setLogs(getLogs())
        })
      }
    }
    
    const handleLogEvaluated = () => setLogs(getLogs())
    const handleLogCleared = () => setLogs([])
    
    window.addEventListener('admin-log-updated', handleLogUpdated as EventListener)
    window.addEventListener('admin-log-evaluated', handleLogEvaluated)
    window.addEventListener('admin-log-cleared', handleLogCleared)
    
    return () => {
      window.removeEventListener('admin-log-updated', handleLogUpdated as EventListener)
      window.removeEventListener('admin-log-evaluated', handleLogEvaluated)
      window.removeEventListener('admin-log-cleared', handleLogCleared)
    }
  }, [loadLogs, evaluatingIds, evaluatePendingLogs])

  // 수동 평가 재실행
  const handleReEvaluate = async (log: ExecutionLog) => {
    if (evaluatingIds.has(log.id)) return
    
    setEvaluatingIds(prev => new Set([...prev, log.id]))
    await evaluateLog(log)
    setEvaluatingIds(prev => {
      const next = new Set(prev)
      next.delete(log.id)
      return next
    })
    setLogs(getLogs())
  }

  // 전체 삭제 핸들러
  const handleClearLogs = async () => {
    if (confirm('모든 로그를 삭제하시겠습니까?')) {
      await clearLogs()
      setLogs([])
    }
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* 마이그레이션 배너 */}
      {showMigrateBanner && (
        <div className="bg-yellow-50 border-b border-yellow-200 px-4 py-3">
          <div className="flex items-center justify-between max-w-full mx-auto">
            <div className="flex items-center gap-2">
              <svg className="w-5 h-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <span className="text-sm text-yellow-800">
                기존 브라우저에 저장된 로그가 있습니다. Supabase로 마이그레이션하시겠습니까?
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleMigrate}
                disabled={migrating}
                className="px-3 py-1.5 bg-yellow-600 hover:bg-yellow-700 text-white rounded text-sm disabled:opacity-50"
              >
                {migrating ? '마이그레이션 중...' : '마이그레이션'}
              </button>
              <button
                onClick={() => setShowMigrateBanner(false)}
                className="px-3 py-1.5 bg-gray-200 hover:bg-gray-300 text-gray-700 rounded text-sm"
              >
                나중에
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 헤더 */}
      <header className="bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-full mx-auto px-4 py-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <h1 className="text-xl font-bold text-gray-900">Admin Agent</h1>
            <span className="text-sm text-gray-500">실행 로그 ({logs.length}건)</span>
          </div>
          
          <div className="flex items-center gap-3">
            <button
              onClick={loadLogs}
              disabled={loading}
              className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors text-sm disabled:opacity-50"
            >
              {loading ? '로딩...' : '새로고침'}
            </button>
            <button
              onClick={handleClearLogs}
              className="px-3 py-2 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg transition-colors text-sm"
            >
              전체 삭제
            </button>
          </div>
        </div>
      </header>

      {/* 테이블 */}
      <div className="p-4 overflow-x-auto">
        {loading && logs.length === 0 ? (
          <div className="text-center py-20">
            <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
            <p className="text-gray-500">로그를 불러오는 중...</p>
          </div>
        ) : logs.length === 0 ? (
          <div className="text-center py-20">
            <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-gray-500">아직 실행 로그가 없습니다</p>
            <p className="text-sm text-gray-400 mt-1">채팅 페이지에서 질문을 하면 여기에 로그가 기록됩니다</p>
          </div>
        ) : (
          <table className="w-full bg-white rounded-lg shadow-sm border border-gray-200 table-fixed">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: '80px'}}>ID/User</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: '80px'}}>이전 대화</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: '120px'}}>사용자 질문</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: '140px'}}>Router 출력</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: '40%'}}>Function 결과</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: '20%'}}>최종 답변</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600" style={{width: '70px'}}>시간</th>
                <th className="px-2 py-2 text-center text-xs font-semibold text-gray-600" style={{width: '50px'}}>액션</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log, index) => {
                const isExpanded = expandedRows.has(log.id)
                const isEvaluating = evaluatingIds.has(log.id)
                const routerBg = getStatusBgColor(log.evaluation?.routerStatus || 'pending')
                const timeBg = getStatusBgColor(log.evaluation?.timeStatus || 'pending')
                
                return (
                  <tr 
                    key={log.id} 
                    onClick={(e) => {
                      // 재평가 버튼 클릭은 제외
                      if ((e.target as HTMLElement).closest('button')) return
                      
                      setExpandedRows(prev => {
                        const next = new Set(prev)
                        if (next.has(log.id)) {
                          next.delete(log.id)
                        } else {
                          next.add(log.id)
                        }
                        return next
                      })
                    }}
                    className={`border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${index % 2 === 0 ? '' : 'bg-gray-25'}`}
                  >
                    {/* ID/User - 두 줄로 표시 */}
                    <td className="px-2 py-1.5 align-middle">
                      <div className="text-[10px] text-gray-700 font-mono font-semibold">{log.id}</div>
                      <div className="text-[9px] text-gray-400 truncate" title={log.userId || '비회원'}>
                        {log.userId ? log.userId.substring(0, 8) + '...' : '비회원'}
                      </div>
                      <div className="text-[9px] text-gray-400">
                        {new Date(log.timestamp).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                      </div>
                    </td>
                    
                    {/* 이전 대화 */}
                    <td className="px-2 py-1.5 align-middle">
                      <ExpandableCell 
                        content={log.conversationHistory.length > 0 ? log.conversationHistory.join('\n') : '-'} 
                        maxLength={20}
                        isExpanded={isExpanded}
                      />
                    </td>
                    
                    {/* 사용자 질문 */}
                    <td className="px-2 py-1.5 align-middle">
                      <div className="text-xs text-gray-900">{log.userQuestion}</div>
                    </td>
                    
                    {/* Router 출력 */}
                    <td className={`px-2 py-1.5 align-middle ${routerBg}`}>
                      <div className="flex-1 min-w-0">
                        <ExpandableCell content={log.routerOutput} maxLength={35} cleanRouter={true} isExpanded={isExpanded} />
                      </div>
                      {log.evaluation?.routerComment && (
                        <div className={`text-[9px] mt-0.5 truncate ${log.evaluation?.routerStatus === 'ok' ? 'text-green-600' : 'text-gray-500'}`} title={log.evaluation.routerComment}>
                          {log.evaluation.routerComment.length > 50 ? log.evaluation.routerComment.substring(0, 50) + '...' : log.evaluation.routerComment}
                        </div>
                      )}
                    </td>
                    
                    {/* Function 결과 */}
                    <td className={`px-2 py-1.5 align-middle ${getStatusBgColor(log.evaluation?.functionStatus || 'pending')}`}>
                      {log.functionResult ? (
                        <div className="flex-1 min-w-0">
                          <ExpandableCell 
                            content={formatFunctionResult(log.functionResult)} 
                            maxLength={50} 
                            isExpanded={isExpanded} 
                          />
                          {log.evaluation?.functionComment && (
                            <div className={`text-[9px] mt-0.5 truncate ${log.evaluation?.functionStatus === 'ok' ? 'text-green-600' : 'text-gray-500'}`} title={log.evaluation.functionComment}>
                              {log.evaluation.functionComment.length > 50 ? log.evaluation.functionComment.substring(0, 50) + '...' : log.evaluation.functionComment}
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-[10px] text-gray-400">-</span>
                      )}
                    </td>
                    
                    {/* 최종 답변 */}
                    <td className={`px-2 py-1.5 align-middle ${getStatusBgColor(log.evaluation?.answerStatus || 'pending')}`}>
                      <ExpandableCell content={log.finalAnswer || '-'} maxLength={25} isExpanded={isExpanded} />
                      {log.evaluation?.answerComment && (
                        <div className={`text-[9px] mt-0.5 truncate ${log.evaluation?.answerStatus === 'ok' ? 'text-green-600' : 'text-gray-500'}`} title={log.evaluation.answerComment}>
                          {log.evaluation.answerComment.length > 40 ? log.evaluation.answerComment.substring(0, 40) + '...' : log.evaluation.answerComment}
                        </div>
                      )}
                    </td>
                    
                    {/* 소요시간 - 3등분 (Router/Function/Main Agent) */}
                    <td className={`px-2 py-1.5 align-middle ${timeBg}`}>
                      <div className="flex flex-col text-[10px] font-mono leading-tight">
                        <span className="text-blue-600">R: {((log.timing?.router || 0) / 1000).toFixed(2)}s</span>
                        <span className="text-green-600">F: {((log.timing?.function || 0) / 1000).toFixed(2)}s</span>
                        <span className="text-purple-600">M: {((log.timing?.main_agent || 0) / 1000).toFixed(2)}s</span>
                      </div>
                      {log.evaluation?.timeStatus && log.evaluation?.timeStatus !== 'ok' && (
                        <div className="text-[9px] text-gray-500 mt-0.5">
                          ({log.evaluation.timeComment})
                        </div>
                      )}
                    </td>
                    
                    {/* 재평가 */}
                    <td className="px-2 py-1.5 align-middle text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          handleReEvaluate(log)
                        }}
                        disabled={isEvaluating}
                        className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                          isEvaluating 
                            ? 'bg-gray-100 text-gray-400 cursor-not-allowed' 
                            : 'bg-blue-100 text-blue-700 hover:bg-blue-200'
                        }`}
                      >
                        {isEvaluating ? '...' : '재평가'}
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
