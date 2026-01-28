import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getLogs, clearLogs, updateLogEvaluation, ExecutionLog } from '../utils/adminLogger'

// Admin Agent 평가 함수 (백그라운드에서 비동기 실행, 백엔드 API 호출)
async function evaluateLog(log: ExecutionLog): Promise<void> {
  const evaluation: ExecutionLog['evaluation'] = {
    routerStatus: 'pending',
    functionStatus: 'pending',
    answerStatus: 'pending',
    timeStatus: 'ok',
  }
  
  // 소요시간 평가 (프론트엔드에서 처리)
  if (log.elapsedTime > 6000) {
    evaluation.timeStatus = 'error'
    evaluation.timeComment = '6초 초과'
  } else if (log.elapsedTime > 3000) {
    evaluation.timeStatus = 'warning'
    evaluation.timeComment = '3초 초과'
  } else {
    evaluation.timeStatus = 'ok'
    // ok 상태에서는 코멘트 없음
  }
  
  // Router 출력이 없으면 바로 에러
  if (!log.routerOutput) {
    evaluation.routerStatus = 'error'
    evaluation.routerComment = 'Router 출력이 없습니다'
    updateLogEvaluation(log.id, evaluation)
    return
  }
  
  // 백엔드 Admin Agent API 호출
  try {
    const response = await fetch('/api/admin/evaluate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_question: log.userQuestion.replace(/^\[추가실행 \d+\] /, ''), // 추가실행 태그 제거
        router_output: log.routerOutput
      })
    })
    
    if (response.ok) {
      const result = await response.json()
      
      // 상태 매핑
      evaluation.routerStatus = result.status as 'ok' | 'warning' | 'error'
      
      // 코멘트 구성
      const comments = []
      if (result.format_check?.comment) comments.push(`[형식] ${result.format_check.comment}`)
      if (result.function_check?.comment) comments.push(`[함수] ${result.function_check.comment}`)
      if (result.params_check?.comment) comments.push(`[변수] ${result.params_check.comment}`)
      
      evaluation.routerComment = result.overall_comment || comments.join(' | ')
      
    } else {
      // API 오류 시 기본 평가
      evaluation.routerStatus = 'warning'
      evaluation.routerComment = 'Admin Agent API 호출 실패'
    }
  } catch (error) {
    // 네트워크 오류 시 기본 평가 로직
    console.error('Admin Agent 평가 오류:', error)
    
    if (log.routerOutput.error) {
      evaluation.routerStatus = 'error'
      evaluation.routerComment = `오류: ${log.routerOutput.error}`
    } else if (!log.routerOutput.function_calls || log.routerOutput.function_calls.length === 0) {
      evaluation.routerStatus = 'warning'
      evaluation.routerComment = '함수 호출이 없습니다'
    } else {
      evaluation.routerStatus = 'ok'
      evaluation.routerComment = `${log.routerOutput.function_calls.length}개 함수 호출 (API 오프라인)`
    }
  }
  
  // 평가 결과 저장
  updateLogEvaluation(log.id, evaluation)
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
    case 'ok': return ''
    case 'warning': return 'bg-yellow-50'
    case 'error': return 'bg-red-50'
    default: return ''
  }
}

// routerOutput에서 불필요한 필드 제거
function cleanRouterOutput(output: any): any {
  if (!output || typeof output !== 'object') return output
  
  const cleaned = { ...output }
  delete cleaned.raw_response  // raw_response 제거
  delete cleaned.tokens        // tokens도 제거 (필요시)
  return cleaned
}

// 드롭다운 셀 컴포넌트 (행 단위 제어)
function ExpandableCell({ content, maxLength = 30, cleanRouter = false, isExpanded = false }: { content: any, maxLength?: number, cleanRouter?: boolean, isExpanded?: boolean }) {
  const processedContent = cleanRouter ? cleanRouterOutput(content) : content
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
        <pre className="text-xs whitespace-pre-wrap font-mono max-h-64 overflow-y-auto">
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
  const [evaluatingIds, setEvaluatingIds] = useState<Set<string>>(new Set())
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  // 로그 로드
  const loadLogs = useCallback(() => {
    setLogs(getLogs())
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
        loadLogs()
      })
    }
  }, [evaluatingIds, loadLogs])

  // 초기 로드 및 이벤트 리스너
  useEffect(() => {
    const initialLogs = getLogs()
    setLogs(initialLogs)
    
    // 초기 로드 시 pending 로그 자동 평가
    evaluatePendingLogs(initialLogs)
    
    // 실시간 업데이트 리스너
    const handleLogUpdated = (e: CustomEvent) => {
      loadLogs()
      // 새 로그 자동 평가
      const newLog = e.detail as ExecutionLog
      if (!evaluatingIds.has(newLog.id)) {
        setEvaluatingIds(prev => new Set([...prev, newLog.id]))
        evaluateLog(newLog).finally(() => {
          setEvaluatingIds(prev => {
            const next = new Set(prev)
            next.delete(newLog.id)
            return next
          })
          loadLogs()
        })
      }
    }
    
    const handleLogEvaluated = () => loadLogs()
    const handleLogCleared = () => setLogs([])
    
    window.addEventListener('admin-log-updated', handleLogUpdated as EventListener)
    window.addEventListener('admin-log-evaluated', handleLogEvaluated)
    window.addEventListener('admin-log-cleared', handleLogCleared)
    
    return () => {
      window.removeEventListener('admin-log-updated', handleLogUpdated as EventListener)
      window.removeEventListener('admin-log-evaluated', handleLogEvaluated)
      window.removeEventListener('admin-log-cleared', handleLogCleared)
    }
  }, [loadLogs, evaluatingIds])

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
    loadLogs()
  }

  return (
    <div className="min-h-screen bg-gray-100">
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
              className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors text-sm"
            >
              새로고침
            </button>
            <button
              onClick={() => {
                if (confirm('모든 로그를 삭제하시겠습니까?')) {
                  clearLogs()
                }
              }}
              className="px-3 py-2 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg transition-colors text-sm"
            >
              전체 삭제
            </button>
          </div>
        </div>
      </header>

      {/* 테이블 */}
      <div className="p-4 overflow-x-auto">
        {logs.length === 0 ? (
          <div className="text-center py-20">
            <svg className="w-16 h-16 text-gray-300 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-gray-500">아직 실행 로그가 없습니다</p>
            <p className="text-sm text-gray-400 mt-1">채팅 페이지에서 질문을 하면 여기에 로그가 기록됩니다</p>
          </div>
        ) : (
          <table className="w-full bg-white rounded-lg shadow-sm border border-gray-200">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600 w-20">ID</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600 w-32">이전 대화</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600 w-48">사용자 질문</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600 w-56">Router 출력</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600 w-32">Function 결과</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600 w-40">최종 답변</th>
                <th className="px-2 py-2 text-left text-xs font-semibold text-gray-600 w-20">시간</th>
                <th className="px-2 py-2 text-center text-xs font-semibold text-gray-600 w-16">액션</th>
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
                    {/* ID */}
                    <td className="px-2 py-1.5 align-middle">
                      <div className="text-[10px] text-gray-500 font-mono">{log.id.substring(4, 17)}</div>
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
                      {log.evaluation?.routerStatus !== 'ok' && log.evaluation?.routerComment && (
                        <div className="text-[9px] text-gray-500 mt-0.5 truncate" title={log.evaluation.routerComment}>
                          {log.evaluation.routerComment.length > 50 ? log.evaluation.routerComment.substring(0, 50) + '...' : log.evaluation.routerComment}
                        </div>
                      )}
                    </td>
                    
                    {/* Function 결과 */}
                    <td className="px-2 py-1.5 align-middle text-gray-400">
                      <span className="text-[10px]">미구현</span>
                    </td>
                    
                    {/* 최종 답변 */}
                    <td className="px-2 py-1.5 align-middle text-gray-400">
                      <ExpandableCell content={log.finalAnswer || '-'} maxLength={25} isExpanded={isExpanded} />
                    </td>
                    
                    {/* 소요시간 */}
                    <td className={`px-2 py-1.5 align-middle ${timeBg}`}>
                      <div className="flex items-center gap-1">
                        <span className="text-xs font-mono">{(log.elapsedTime / 1000).toFixed(2)}s</span>
                        {log.evaluation?.timeStatus && log.evaluation?.timeStatus !== 'ok' && (
                          <span className="text-[9px] text-gray-500">
                            ({log.evaluation.timeComment})
                          </span>
                        )}
                      </div>
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
