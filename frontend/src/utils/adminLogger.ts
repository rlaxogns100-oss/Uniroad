/**
 * Admin Logger - 모든 실행 로그를 로컬 스토리지에 저장
 */

export interface ExecutionLog {
  id: string
  timestamp: string
  conversationHistory: string[]  // 이전 대화 기록
  userQuestion: string           // 사용자 질문
  routerOutput: any              // Router 출력 (JSON)
  functionResult: any            // Function 결과
  finalAnswer: string            // 최종 답변
  elapsedTime: number            // 소요시간 (ms)
  
  // Admin Agent 평가 결과
  evaluation?: {
    routerStatus: 'ok' | 'warning' | 'error' | 'pending'
    functionStatus: 'ok' | 'warning' | 'error' | 'pending'
    answerStatus: 'ok' | 'warning' | 'error' | 'pending'
    timeStatus: 'ok' | 'warning' | 'error' | 'pending'
    routerComment?: string
    functionComment?: string
    answerComment?: string
    timeComment?: string
  }
}

const STORAGE_KEY = 'admin_execution_logs'
const MAX_LOGS = 500  // 최대 저장 로그 수

/**
 * 모든 로그 가져오기
 */
export function getLogs(): ExecutionLog[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    if (!data) return []
    return JSON.parse(data)
  } catch {
    return []
  }
}

/**
 * 새 로그 추가
 */
export function addLog(log: Omit<ExecutionLog, 'id' | 'timestamp'>): ExecutionLog {
  const logs = getLogs()
  
  const newLog: ExecutionLog = {
    ...log,
    id: `log-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    timestamp: new Date().toISOString(),
    evaluation: {
      routerStatus: 'pending',
      functionStatus: 'pending',
      answerStatus: 'pending',
      timeStatus: 'pending',
    }
  }
  
  logs.unshift(newLog)  // 최신이 위로
  
  // 최대 개수 제한
  if (logs.length > MAX_LOGS) {
    logs.splice(MAX_LOGS)
  }
  
  localStorage.setItem(STORAGE_KEY, JSON.stringify(logs))
  
  // 커스텀 이벤트 발생 (AdminAgentPage가 실시간으로 감지)
  window.dispatchEvent(new CustomEvent('admin-log-updated', { detail: newLog }))
  
  return newLog
}

/**
 * 로그 평가 결과 업데이트
 */
export function updateLogEvaluation(
  logId: string, 
  evaluation: Partial<ExecutionLog['evaluation']>
): void {
  const logs = getLogs()
  const index = logs.findIndex(log => log.id === logId)
  
  if (index !== -1) {
    logs[index].evaluation = {
      ...logs[index].evaluation!,
      ...evaluation
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(logs))
    
    // 커스텀 이벤트 발생
    window.dispatchEvent(new CustomEvent('admin-log-evaluated', { detail: logs[index] }))
  }
}

/**
 * 모든 로그 삭제
 */
export function clearLogs(): void {
  localStorage.removeItem(STORAGE_KEY)
  window.dispatchEvent(new CustomEvent('admin-log-cleared'))
}

/**
 * 특정 로그 삭제
 */
export function deleteLog(logId: string): void {
  const logs = getLogs().filter(log => log.id !== logId)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(logs))
  window.dispatchEvent(new CustomEvent('admin-log-deleted', { detail: logId }))
}
