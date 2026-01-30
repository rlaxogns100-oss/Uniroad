/**
 * Admin Logger - 실행 로그를 Supabase에 저장
 */

export interface ExecutionLog {
  id: string
  userId?: string  // 사용자 ID (Supabase Auth)
  timestamp: string
  conversationHistory: string[]  // 이전 대화 기록
  userQuestion: string           // 사용자 질문
  routerOutput: any              // Router 출력 (JSON)
  functionResult: any            // Function 결과
  finalAnswer: string            // 최종 답변
  elapsedTime: number            // 소요시간 (ms)
  
  // 단계별 시간 측정 (ms)
  timing?: {
    router: number      // Router Agent 시간
    function: number    // Function 실행 시간
    main_agent: number  // Main Agent 시간
  }
  
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

// 로컬 캐시 (API 호출 최소화)
let logsCache: ExecutionLog[] = []
let cacheLoaded = false

/**
 * 모든 로그 가져오기 (Supabase에서)
 */
export async function fetchLogs(): Promise<ExecutionLog[]> {
  try {
    const response = await fetch('/api/admin/logs')
    if (!response.ok) {
      throw new Error('로그 조회 실패')
    }
    const data = await response.json()
    logsCache = data.logs || []
    cacheLoaded = true
    return logsCache
  } catch (error) {
    console.error('❌ 로그 조회 오류:', error)
    return []
  }
}

/**
 * 캐시된 로그 가져오기 (동기)
 */
export function getLogs(): ExecutionLog[] {
  return logsCache
}

/**
 * 새 로그 추가 (Supabase에)
 */
export async function addLog(
  log: Omit<ExecutionLog, 'id' | 'timestamp' | 'evaluation'>
): Promise<ExecutionLog | null> {
  try {
    // 현재 로그인한 사용자 ID 가져오기
    const storedUser = localStorage.getItem('user')
    let userId: string | undefined
    if (storedUser) {
      try {
        const user = JSON.parse(storedUser)
        userId = user.id
      } catch {}
    }

    const response = await fetch('/api/admin/logs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...log,
        userId
      })
    })
    
    if (!response.ok) {
      throw new Error('로그 저장 실패')
    }
    
    const newLog = await response.json() as ExecutionLog
    
    // 캐시 업데이트
    logsCache.unshift(newLog)
    
    // 커스텀 이벤트 발생 (AdminAgentPage가 실시간으로 감지)
    window.dispatchEvent(new CustomEvent('admin-log-updated', { detail: newLog }))
    
    return newLog
  } catch (error) {
    console.error('❌ 로그 추가 오류:', error)
    return null
  }
}

/**
 * 로그 평가 결과 업데이트 (Supabase에)
 */
export async function updateLogEvaluation(
  logId: string, 
  evaluation: Partial<ExecutionLog['evaluation']>
): Promise<void> {
  try {
    const response = await fetch(`/api/admin/logs/${logId}/evaluation`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(evaluation)
    })
    
    if (!response.ok) {
      throw new Error('평가 업데이트 실패')
    }
    
    // 캐시 업데이트
    const index = logsCache.findIndex(log => log.id === logId)
    if (index !== -1) {
      logsCache[index].evaluation = {
        ...logsCache[index].evaluation!,
        ...evaluation
      }
    }
    
    // 커스텀 이벤트 발생
    window.dispatchEvent(new CustomEvent('admin-log-evaluated', { 
      detail: logsCache[index] 
    }))
  } catch (error) {
    console.error('❌ 평가 업데이트 오류:', error)
  }
}

/**
 * 모든 로그 삭제 (Supabase에서)
 */
export async function clearLogs(): Promise<void> {
  try {
    const response = await fetch('/api/admin/logs', {
      method: 'DELETE'
    })
    
    if (!response.ok) {
      throw new Error('로그 삭제 실패')
    }
    
    logsCache = []
    window.dispatchEvent(new CustomEvent('admin-log-cleared'))
  } catch (error) {
    console.error('❌ 로그 삭제 오류:', error)
  }
}

/**
 * 특정 로그 삭제 (Supabase에서)
 */
export async function deleteLog(logId: string): Promise<void> {
  try {
    const response = await fetch(`/api/admin/logs/${logId}`, {
      method: 'DELETE'
    })
    
    if (!response.ok) {
      throw new Error('로그 삭제 실패')
    }
    
    logsCache = logsCache.filter(log => log.id !== logId)
    window.dispatchEvent(new CustomEvent('admin-log-deleted', { detail: logId }))
  } catch (error) {
    console.error('❌ 로그 삭제 오류:', error)
  }
}

/**
 * 기존 localStorage 로그를 Supabase로 마이그레이션
 */
export async function migrateLocalStorageLogs(): Promise<{
  migrated: number
  total: number
  errors: any[]
}> {
  const STORAGE_KEY = 'admin_execution_logs'
  
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    if (!data) {
      return { migrated: 0, total: 0, errors: [] }
    }
    
    const logs = JSON.parse(data) as any[]
    if (logs.length === 0) {
      return { migrated: 0, total: 0, errors: [] }
    }
    
    // 마이그레이션 API 호출
    const response = await fetch('/api/admin/logs/migrate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(logs)
    })
    
    if (!response.ok) {
      throw new Error('마이그레이션 실패')
    }
    
    const result = await response.json()
    
    // 마이그레이션 성공 시 localStorage 삭제
    if (result.migrated > 0) {
      localStorage.removeItem(STORAGE_KEY)
      console.log(`✅ ${result.migrated}개 로그 마이그레이션 완료, localStorage 삭제됨`)
    }
    
    return result
  } catch (error) {
    console.error('❌ 마이그레이션 오류:', error)
    return { migrated: 0, total: 0, errors: [String(error)] }
  }
}

/**
 * localStorage에 미마이그레이션 로그가 있는지 확인
 */
export function hasLocalStorageLogs(): boolean {
  const STORAGE_KEY = 'admin_execution_logs'
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    if (!data) return false
    const logs = JSON.parse(data)
    return Array.isArray(logs) && logs.length > 0
  } catch {
    return false
  }
}
