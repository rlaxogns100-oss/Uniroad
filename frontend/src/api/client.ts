import axios from 'axios'
import { API_BASE, isCapacitorApp, getApiBaseUrl } from '../config'

const API_BASE_URL = API_BASE ? `${API_BASE}/api` : '/api'

/** 요청 시점의 API 베이스 URL (Capacitor 앱에서 env 미설정 시 https://uni2road.com 사용) */
const getEffectiveApiBaseUrl = (): string => {
  const base = getApiBaseUrl()
  return base ? `${base}/api` : '/api'
}

const AUTH_REQUIRED_ERROR = '__AUTH_REQUIRED__'

const refreshAccessToken = async (apiUrl: string): Promise<string | null> => {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return null

  try {
    const response = await fetch(`${apiUrl}/auth/refresh?refresh_token=${encodeURIComponent(refreshToken)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) return null

    const data = await response.json()
    const newAccessToken = data?.access_token
    const newRefreshToken = data?.refresh_token
    if (!newAccessToken) return null

    localStorage.setItem('access_token', newAccessToken)
    if (newRefreshToken) {
      localStorage.setItem('refresh_token', newRefreshToken)
    }
    return newAccessToken
  } catch {
    return null
  }
}

const withBearerHeader = (headers: Record<string, string>, token?: string): Record<string, string> => {
  if (!token) return headers
  return { ...headers, Authorization: `Bearer ${token}` }
}

const fetchWithAuthRetry = async (
  url: string,
  init: RequestInit,
  apiUrl: string,
  token?: string
): Promise<Response> => {
  const initialToken = token || localStorage.getItem('access_token') || undefined
  let response = await fetch(url, { ...init, headers: withBearerHeader((init.headers || {}) as Record<string, string>, initialToken) })

  if (response.status !== 401 || !initialToken) {
    return response
  }

  const refreshed = await refreshAccessToken(apiUrl)
  if (!refreshed) {
    return response
  }

  response = await fetch(url, { ...init, headers: withBearerHeader((init.headers || {}) as Record<string, string>, refreshed) })
  return response
}

const normalizeSseText = (text: string): string => text.replace(/\r\n/g, '\n').replace(/\r/g, '\n')

const extractSseDataPayload = (block: string): string | null => {
  const dataLines = block
    .split('\n')
    .map((line) => line.trimEnd())
    .filter((line) => line.startsWith('data:'))
  if (dataLines.length === 0) return null
  return dataLines.map((line) => line.slice(5).trimStart()).join('\n')
}

const splitSseBlocks = (buffer: string): { blocks: string[]; remainder: string } => {
  const normalized = normalizeSseText(buffer)
  const parts = normalized.split('\n\n')
  const remainder = parts.pop() || ''
  return { blocks: parts, remainder }
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 180000, // 180초 (멀티에이전트 파이프라인은 시간이 더 걸릴 수 있음)
})

// iOS/Android WebView에서는 런타임에 API base가 달라질 수 있어 요청마다 재계산한다.
api.interceptors.request.use((config) => {
  config.baseURL = getEffectiveApiBaseUrl()
  return config
})

export interface ChatRequest {
  message: string
  session_id?: string
  thinking?: boolean  // Thinking 모드 활성화 여부
  score_id?: string
  use_school_record?: boolean  // 생기부 컨텍스트 사용 여부
  use_linked_naesin?: boolean // '@내신 성적' 선택 시 연동 내신 카드 강제
}

// 멀티에이전트 응답 타입
export interface OrchestrationResult {
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
  // Router Agent 결과
  router_result?: {
    function_calls?: Array<{
      function: string
      params: Record<string, any>
    }>
    raw_response?: string
    tokens?: {
      in: number
      out: number
      total: number
    }
  }
  // Function 실행 결과
  function_results?: Record<string, any>
}

export interface SubAgentResult {
  agent: string
  status: string
  result: string
  query?: string
  sources?: string[]
  source_urls?: string[]
  citations?: Array<{
    text: string
    source: string
    url: string
  }>
}

export interface UsedChunk {
  id: string
  content: string
  title: string
  source: string
  file_url: string
  metadata?: Record<string, any>
}

export interface ChatResponse {
  response: string
  raw_answer?: string  // ✅ Final Agent 원본 출력
  sources: string[]
  source_urls: string[]
  used_chunks?: UsedChunk[]  // 답변에 사용된 청크
  // 멀티에이전트 디버그 데이터
  router_output?: Record<string, any>  // Router 출력 (최상위)
  function_results?: Record<string, any>  // Function 결과 (최상위)
  orchestration_result?: OrchestrationResult
  sub_agent_results?: Record<string, SubAgentResult>
  metadata?: Record<string, any>
  require_login?: boolean  // 비로그인 3회째 질문 시 마스킹 필요
  score_id?: string
}

export interface StreamChatRequest extends ChatRequest {
  score_id?: string
}

export interface ScoreReviewRequiredEvent {
  pending_id: string
  title_auto: string
  scores: Record<string, any>
  constraints?: Record<string, any>
  actions?: string[]
  /** true면 연동된 모의고사 성적 카드 확인 → continue-after-score-confirm 호출 */
  use_existing_score_id?: boolean
}

export interface SchoolGradeSavedEvent {
  overall_average: number
  core_average: number
  semester_averages?: Record<string, { overall: string; core: string }>
}

export interface ScoreSetSuggestItem {
  id: string
  name: string
}

export interface ScoreSetItem {
  id: string
  name: string
  scores: Record<string, any>
  created_at?: string
  updated_at?: string
}

export interface UploadResponse {
  success: boolean
  message: string
  stats: {
    totalPages: number
    chunksTotal: number
    chunksSuccess: number
    chunksFailed: number
    processingTime: string
    markdownSize: string
  }
  preview: {
    firstChunk: string
  }
}

export interface Document {
  id: string
  title: string
  source: string
  fileName: string
  fileUrl?: string
  category: string
  uploadedAt: string
  hashtags?: string[]
  schoolName?: string
}

export interface Agent {
  name: string
  description: string
}

// 비스트리밍 채팅 API (iOS WebView용)
const sendMessageNonStream = async (
  message: string,
  sessionId: string,
  onLog: (log: string) => void,
  onResult: (result: ChatResponse) => void,
  onError?: (error: string) => void,
  abortSignal?: AbortSignal,
  token?: string,
  useSchoolRecord?: boolean,
  thinking?: boolean,
  onScoreReviewRequired?: (payload: ScoreReviewRequiredEvent) => void,
  scoreId?: string,
  onSchoolGradeSaved?: (payload: SchoolGradeSavedEvent) => void,
  useLinkedNaesin?: boolean,
  skipScoreReview?: boolean,
): Promise<void> => {
  const apiUrl = getEffectiveApiBaseUrl()
  console.log('[sendMessageNonStream] Starting non-streaming v2 request')
  console.log('API_BASE_URL:', apiUrl)
  
  try {
    onLog('🔍 질문을 분석하는 중...')

    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    // iOS WebView 등 ReadableStream 이슈 환경에서도 동일한 v2 이벤트를 텍스트로 파싱해 처리
    const response = await fetchWithAuthRetry(`${apiUrl}/chat/v2/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message,
        session_id: sessionId,
        thinking: thinking || false,
        score_id: scoreId || null,
        skip_score_review: !!scoreId || !!skipScoreReview,
        use_school_record: useSchoolRecord || false,
        use_linked_naesin: useLinkedNaesin || false,
      }),
      signal: abortSignal,
    }, apiUrl, token)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('API 에러:', response.status, errorText)

      if (response.status === 401) {
        onError?.(AUTH_REQUIRED_ERROR)
        return
      }
      
      if (response.status === 429) {
        if (errorText.includes('로그인을 통해')) {
          onError?.('__RATE_LIMIT_GUEST__')
        } else {
          try {
            const parsed = JSON.parse(errorText)
            onError?.(parsed.detail || '일일 사용량을 초과했습니다.')
          } catch {
            onError?.('일일 사용량을 초과했습니다. 내일 00:00에 초기화됩니다.')
          }
        }
        return
      }
      
      onError?.(`서버 오류 (${response.status}): ${errorText}`)
      return
    }

    const text = await response.text()
    let fullResponse = ''
    let finalData: any = null

    const blocks = normalizeSseText(text).split('\n\n')
    for (const block of blocks) {
      const payload = extractSseDataPayload(block)
      if (!payload) continue
      try {
        const event = JSON.parse(payload)
        if (event.type === 'status') {
          const logMessage = event.detail
            ? `${event.message || ''}|||${JSON.stringify({ step: event.step, detail: event.detail })}`
            : event.message || ''
          onLog(logMessage)
        } else if (event.type === 'log') {
          onLog(event.content || '')
        } else if (event.type === 'chunk') {
          fullResponse += event.text || ''
        } else if (event.type === 'score_review_required') {
          onScoreReviewRequired?.(event as ScoreReviewRequiredEvent)
          return
        } else if (event.type === 'school_grade_saved') {
          onSchoolGradeSaved?.(event as SchoolGradeSavedEvent)
          return
        } else if (event.type === 'done') {
          finalData = event
        } else if (event.type === 'error') {
          onError?.(event.message || '알 수 없는 오류')
          return
        }
      } catch (e) {
        console.warn('[sendMessageNonStream] SSE 파싱 오류:', e)
      }
    }

    onLog('✨ 답변 완료!')
    const chatResponse: ChatResponse = {
      response: finalData?.response || fullResponse,
      raw_answer: finalData?.response || fullResponse,
      sources: finalData?.sources || [],
      source_urls: finalData?.source_urls || [],
      used_chunks: finalData?.used_chunks || [],
      router_output: finalData?.router_output,
      function_results: finalData?.function_results,
      orchestration_result: undefined,
      sub_agent_results: undefined,
      metadata: {
        timing: finalData?.timing,
        pipeline_time: finalData?.pipeline_time,
      },
      require_login: finalData?.require_login || false,
      score_id: finalData?.score_id,
    }
    onResult(chatResponse)
    
  } catch (error: any) {
    if (error?.name === 'AbortError') {
      console.log('요청이 취소되었습니다')
      return
    }
    
    console.error('채팅 오류:', error)
    onError?.(error?.message || '네트워크 오류가 발생했습니다')
  }
}

// 채팅 API (Router Agent) - 비스트리밍 폴백
export const sendMessageStream = async (
  message: string,
  sessionId: string,
  onLog: (log: string) => void,
  onResult: (result: ChatResponse) => void,
  onError?: (error: string) => void,
  abortSignal?: AbortSignal,
  onChunk?: (chunk: string) => void,  // 실시간 텍스트 청크 콜백
  token?: string,  // 인증 토큰
  thinking?: boolean,  // Thinking 모드
  onScoreReviewRequired?: (payload: ScoreReviewRequiredEvent) => void,
  scoreId?: string,
  useSchoolRecord?: boolean,
  onSchoolGradeSaved?: (payload: SchoolGradeSavedEvent) => void,
  useLinkedNaesin?: boolean,
  skipScoreReview?: boolean,
): Promise<void> => {
  const IS_CAPACITOR_APP = isCapacitorApp()
  console.log('[sendMessageStream] IS_CAPACITOR_APP:', IS_CAPACITOR_APP)
  
  // iOS WebView에서 SSE ReadableStream이 제대로 동작하지 않아 비스트리밍 API 사용
  if (IS_CAPACITOR_APP) {
    console.log('[sendMessageStream] Using non-streaming API for iOS')
    return sendMessageNonStream(
      message,
      sessionId,
      onLog,
      onResult,
      onError,
      abortSignal,
      token,
      useSchoolRecord,
      thinking,
      onScoreReviewRequired,
      scoreId,
      onSchoolGradeSaved,
      useLinkedNaesin,
      skipScoreReview,
    )
  }
  
  console.log('[sendMessageStream] Using streaming API for web')
  
  try {
    onLog(thinking ? '🧠 Thinking 모드로 분석 중...' : '🔍 질문을 분석하는 중...')
    
    // 헤더 구성
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    
    // 실시간 스트리밍 엔드포인트 사용
    const response = await fetchWithAuthRetry(`${API_BASE_URL}/chat/v2/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        message,
        session_id: sessionId,
        thinking: thinking || false,
        score_id: scoreId || null,
        skip_score_review: !!scoreId || !!skipScoreReview,
        use_school_record: useSchoolRecord || false,
        use_linked_naesin: useLinkedNaesin || false,
      }),
      signal: abortSignal,
    }, API_BASE_URL, token)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('API 에러:', response.status, errorText)

      if (response.status === 401) {
        onError?.(AUTH_REQUIRED_ERROR)
        return
      }
      
      // 429 에러 (Rate Limit)
      if (response.status === 429) {
        // 비로그인 사용자 (로그인 유도 메시지가 포함된 경우)
        if (errorText.includes('로그인을 통해')) {
          onError?.('__RATE_LIMIT_GUEST__')
        } else {
          // 로그인 사용자 - 백엔드 메시지 그대로 표시
          try {
            const parsed = JSON.parse(errorText)
            onError?.(parsed.detail || '일일 사용량을 초과했습니다.')
          } catch {
            onError?.('일일 사용량을 초과했습니다. 내일 00:00에 초기화됩니다.')
          }
        }
        return
      }
      
      onError?.(`서버 오류 (${response.status}): ${errorText}`)
      return
    }

    // SSE 스트리밍 처리
    const reader = response.body?.getReader()
    if (!reader) {
      onError?.('스트리밍을 지원하지 않습니다')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let fullResponse = ''
    let finalData: any = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      
      const { blocks, remainder } = splitSseBlocks(buffer)
      buffer = remainder

      for (const block of blocks) {
        const payload = extractSseDataPayload(block)
        if (!payload) continue

        try {
          const event = JSON.parse(payload)
          
          if (event.type === 'status') {
            // 상태 업데이트 - detail 정보를 JSON으로 직렬화하여 전달
            const logMessage = event.detail 
              ? `${event.message || ''}|||${JSON.stringify({ step: event.step, detail: event.detail })}`
              : event.message || ''
            onLog(logMessage)
          } else if (event.type === 'log') {
            // Thinking 모드 로그 - step, iteration, detail 정보 포함
            if (event.step || event.iteration || event.detail) {
              const logMessage = `${event.content || ''}|||${JSON.stringify({ 
                step: event.step, 
                iteration: event.iteration,
                detail: event.detail 
              })}`
              onLog(logMessage)
            } else {
              onLog(event.content || '')
            }
          } else if (event.type === 'chunk') {
            // 텍스트 청크 - 실시간으로 화면에 표시
            const chunkText = event.text || ''
            fullResponse += chunkText
            onChunk?.(chunkText)
          } else if (event.type === 'score_review_required') {
            onScoreReviewRequired?.(event as ScoreReviewRequiredEvent)
            return
          } else if (event.type === 'school_grade_saved') {
            onSchoolGradeSaved?.(event as SchoolGradeSavedEvent)
            return
          } else if (event.type === 'done') {
            // 완료
            finalData = event
            onLog('✨ 답변 완료!')
          } else if (event.type === 'error') {
            onError?.(event.message || '알 수 없는 오류')
            return
          }
        } catch (e) {
          console.warn('SSE 파싱 오류:', e, payload)
        }
      }
    }

    // 최종 결과 전달 (출처 정보 포함)
    const chatResponse: ChatResponse = {
      response: finalData?.response || fullResponse,
      raw_answer: finalData?.response || fullResponse,
      sources: finalData?.sources || [],
      source_urls: finalData?.source_urls || [],
      used_chunks: finalData?.used_chunks || [],
      router_output: finalData?.router_output,
      function_results: finalData?.function_results,
      orchestration_result: undefined,
      sub_agent_results: undefined,
      metadata: {
        timing: finalData?.timing,
        pipeline_time: finalData?.pipeline_time
      },
      require_login: finalData?.require_login || false,  // 비로그인 3회째 질문 시 마스킹
      score_id: finalData?.score_id
    }
    
    onResult(chatResponse)
    
  } catch (error: any) {
    // AbortError는 무시
    if (error?.name === 'AbortError') {
      console.log('요청이 취소되었습니다')
      return
    }
    
    console.error('채팅 오류:', error)
    onError?.(error?.message || '네트워크 오류가 발생했습니다')
  }
}

/** 내신 카드에서 수정한 성적 (확인 시 서버에 반영) */
export interface NaesinGradeSummary {
  overallAverage: string
  coreAverage: string
  semesterAverages: Record<string, { overall: string; core: string }>
}

/** 내신 카드 '확인' 후 답변 생성만 스트리밍 (사용량 차감 없음) */
export const sendContinueAfterNaesin = async (
  sessionId: string,
  onLog: (log: string) => void,
  onResult: (result: ChatResponse) => void,
  onError?: (error: string) => void,
  abortSignal?: AbortSignal,
  onChunk?: (chunk: string) => void,
  scoreId?: string,
  token?: string,
  gradeSummary?: NaesinGradeSummary
): Promise<void> => {
  try {
    onLog('답변을 생성하는 중...')
    const apiUrl = getEffectiveApiBaseUrl()
    const body: { session_id: string; score_id: string | null; grade_summary?: NaesinGradeSummary } = {
      session_id: sessionId,
      score_id: scoreId || null,
    }
    if (gradeSummary) {
      body.grade_summary = gradeSummary
    }
    const response = await fetchWithAuthRetry(`${apiUrl}/chat/v2/stream/continue-after-naesin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: abortSignal,
    }, apiUrl, token)

    if (!response.ok) {
      const errorText = await response.text()
      if (response.status === 401) {
        onError?.(AUTH_REQUIRED_ERROR)
        return
      }
      try {
        const parsed = JSON.parse(errorText)
        onError?.(parsed.detail || errorText)
      } catch {
        onError?.(errorText || '요청에 실패했습니다.')
      }
      return
    }

    if (isCapacitorApp()) {
      const text = await response.text()
      let fullResponse = ''
      let finalData: any = null

      const blocks = normalizeSseText(text).split('\n\n')
      for (const block of blocks) {
        const payload = extractSseDataPayload(block)
        if (!payload) continue
        try {
          const event = JSON.parse(payload)
          if (event.type === 'status') {
            const logMessage = event.detail
              ? `${event.message || ''}|||${JSON.stringify({ step: event.step, detail: event.detail })}`
              : event.message || ''
            onLog(logMessage)
          } else if (event.type === 'chunk') {
            const chunkText = event.text || ''
            fullResponse += chunkText
            onChunk?.(chunkText)
          } else if (event.type === 'done') {
            finalData = event
            onLog('✨ 답변 완료!')
          } else if (event.type === 'error') {
            onError?.(event.message || '알 수 없는 오류')
            return
          }
        } catch (e) {
          console.warn('SSE 파싱 오류:', e, payload)
        }
      }

      const chatResponse: ChatResponse = {
        response: finalData?.response || fullResponse,
        raw_answer: finalData?.response || fullResponse,
        sources: finalData?.sources || [],
        source_urls: finalData?.source_urls || [],
        used_chunks: finalData?.used_chunks || [],
        router_output: finalData?.router_output,
        function_results: finalData?.function_results,
        orchestration_result: undefined,
        sub_agent_results: undefined,
        metadata: { timing: finalData?.timing, pipeline_time: finalData?.pipeline_time },
        require_login: false,
        score_id: finalData?.score_id,
      }
      onResult(chatResponse)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      onError?.('스트리밍을 지원하지 않습니다')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let fullResponse = ''
    let finalData: any = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const { blocks, remainder } = splitSseBlocks(buffer)
      buffer = remainder

      for (const block of blocks) {
        const payload = extractSseDataPayload(block)
        if (!payload) continue
        try {
          const event = JSON.parse(payload)
          if (event.type === 'status') {
            const logMessage = event.detail
              ? `${event.message || ''}|||${JSON.stringify({ step: event.step, detail: event.detail })}`
              : event.message || ''
            onLog(logMessage)
          } else if (event.type === 'chunk') {
            const chunkText = event.text || ''
            fullResponse += chunkText
            onChunk?.(chunkText)
          } else if (event.type === 'done') {
            finalData = event
            onLog('✨ 답변 완료!')
          } else if (event.type === 'error') {
            onError?.(event.message || '알 수 없는 오류')
            return
          }
        } catch (e) {
          console.warn('SSE 파싱 오류:', e, payload)
        }
      }
    }

    const chatResponse: ChatResponse = {
      response: finalData?.response || fullResponse,
      raw_answer: finalData?.response || fullResponse,
      sources: finalData?.sources || [],
      source_urls: finalData?.source_urls || [],
      used_chunks: finalData?.used_chunks || [],
      router_output: finalData?.router_output,
      function_results: finalData?.function_results,
      orchestration_result: undefined,
      sub_agent_results: undefined,
      metadata: { timing: finalData?.timing, pipeline_time: finalData?.pipeline_time },
      require_login: false,
      score_id: finalData?.score_id,
    }
    onResult(chatResponse)
  } catch (error: any) {
    if (error?.name === 'AbortError') return
    console.error('continue-after-naesin 오류:', error)
    onError?.(error?.message || '네트워크 오류가 발생했습니다')
  }
}

/** 모의고사 성적 카드 '확인' 후 답변 생성만 스트리밍 (사용량 차감 없음) */
export const sendContinueAfterScoreConfirm = async (
  sessionId: string,
  scoreId: string,
  onLog: (log: string) => void,
  onResult: (result: ChatResponse) => void,
  onError?: (error: string) => void,
  abortSignal?: AbortSignal,
  onChunk?: (chunk: string) => void,
  token?: string
): Promise<void> => {
  try {
    onLog('답변을 생성하는 중...')
    const apiUrl = getEffectiveApiBaseUrl()
    const response = await fetchWithAuthRetry(
      `${apiUrl}/chat/v2/stream/continue-after-score-confirm`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, score_id: scoreId }),
        signal: abortSignal,
      },
      apiUrl,
      token
    )

    if (!response.ok) {
      const errorText = await response.text()
      if (response.status === 401) {
        onError?.(AUTH_REQUIRED_ERROR)
        return
      }
      try {
        const parsed = JSON.parse(errorText)
        onError?.(parsed.detail || errorText)
      } catch {
        onError?.(errorText || '요청에 실패했습니다.')
      }
      return
    }

    if (isCapacitorApp()) {
      const text = await response.text()
      let fullResponse = ''
      let finalData: any = null

      const blocks = normalizeSseText(text).split('\n\n')
      for (const block of blocks) {
        const payload = extractSseDataPayload(block)
        if (!payload) continue
        try {
          const event = JSON.parse(payload)
          if (event.type === 'status') {
            const logMessage = event.detail
              ? `${event.message || ''}|||${JSON.stringify({ step: event.step, detail: event.detail })}`
              : event.message || ''
            onLog(logMessage)
          } else if (event.type === 'chunk') {
            const chunkText = event.text || ''
            fullResponse += chunkText
            onChunk?.(chunkText)
          } else if (event.type === 'done') {
            finalData = event
            onLog('✨ 답변 완료!')
          } else if (event.type === 'error') {
            onError?.(event.message || '알 수 없는 오류')
            return
          }
        } catch (e) {
          console.warn('SSE 파싱 오류:', e, payload)
        }
      }

      const chatResponse: ChatResponse = {
        response: finalData?.response || fullResponse,
        raw_answer: finalData?.response || fullResponse,
        sources: finalData?.sources || [],
        source_urls: finalData?.source_urls || [],
        used_chunks: finalData?.used_chunks || [],
        router_output: finalData?.router_output,
        function_results: finalData?.function_results,
        orchestration_result: undefined,
        sub_agent_results: undefined,
        metadata: { timing: finalData?.timing, pipeline_time: finalData?.pipeline_time },
        require_login: false,
        score_id: finalData?.score_id,
      }
      onResult(chatResponse)
      return
    }

    const reader = response.body?.getReader()
    if (!reader) {
      onError?.('스트리밍을 지원하지 않습니다')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let fullResponse = ''
    let finalData: any = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const { blocks, remainder } = splitSseBlocks(buffer)
      buffer = remainder

      for (const block of blocks) {
        const payload = extractSseDataPayload(block)
        if (!payload) continue
        try {
          const event = JSON.parse(payload)
          if (event.type === 'status') {
            const logMessage = event.detail
              ? `${event.message || ''}|||${JSON.stringify({ step: event.step, detail: event.detail })}`
              : event.message || ''
            onLog(logMessage)
          } else if (event.type === 'chunk') {
            const chunkText = event.text || ''
            fullResponse += chunkText
            onChunk?.(chunkText)
          } else if (event.type === 'done') {
            finalData = event
            onLog('✨ 답변 완료!')
          } else if (event.type === 'error') {
            onError?.(event.message || '알 수 없는 오류')
            return
          }
        } catch (e) {
          console.warn('SSE 파싱 오류:', e, payload)
        }
      }
    }

    const chatResponse: ChatResponse = {
      response: finalData?.response || fullResponse,
      raw_answer: finalData?.response || fullResponse,
      sources: finalData?.sources || [],
      source_urls: finalData?.source_urls || [],
      used_chunks: finalData?.used_chunks || [],
      router_output: finalData?.router_output,
      function_results: finalData?.function_results,
      orchestration_result: undefined,
      sub_agent_results: undefined,
      metadata: { timing: finalData?.timing, pipeline_time: finalData?.pipeline_time },
      require_login: false,
      score_id: finalData?.score_id,
    }
    onResult(chatResponse)
  } catch (error: any) {
    if (error?.name === 'AbortError') return
    console.error('continue-after-score-confirm 오류:', error)
    onError?.(error?.message || '네트워크 오류가 발생했습니다')
  }
}

// 비스트리밍 이미지 채팅 API (iOS WebView용)
const sendMessageNonStreamWithImage = async (
  message: string,
  sessionId: string,
  image: File,
  onLog: (log: string) => void,
  onResult: (result: ChatResponse) => void,
  onError?: (error: string) => void,
  abortSignal?: AbortSignal,
  token?: string,
  useSchoolRecord?: boolean,
  useLinkedNaesin?: boolean,
  skipScoreReview?: boolean,
): Promise<void> => {
  try {
    onLog('🖼️ 이미지를 분석하는 중...')
    
    const formData = new FormData()
    formData.append('message', message)
    formData.append('session_id', sessionId)
    formData.append('image', image)
    formData.append('use_school_record', useSchoolRecord ? 'true' : 'false')
    formData.append('use_linked_naesin', useLinkedNaesin ? 'true' : 'false')
    formData.append('skip_score_review', skipScoreReview ? 'true' : 'false')
    
    const headers: Record<string, string> = {}
    
    const apiUrl = getEffectiveApiBaseUrl()
    // 스트리밍 엔드포인트를 사용하되, 전체 응답을 한번에 받음
    const response = await fetchWithAuthRetry(`${apiUrl}/chat/v2/stream/with-image`, {
      method: 'POST',
      headers,
      body: formData,
      signal: abortSignal,
    }, apiUrl, token)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('API 에러:', response.status, errorText)

      if (response.status === 401) {
        onError?.(AUTH_REQUIRED_ERROR)
        return
      }
      
      // 413 에러 (파일 크기 초과)
      if (response.status === 413) {
        onError?.('이미지 크기가 너무 큽니다. 10MB 이하의 이미지를 선택해주세요.')
        return
      }
      
      if (response.status === 429) {
        if (errorText.includes('로그인을 통해')) {
          onError?.('__RATE_LIMIT_GUEST__')
        } else {
          try {
            const parsed = JSON.parse(errorText)
            onError?.(parsed.detail || '일일 사용량을 초과했습니다.')
          } catch {
            onError?.('일일 사용량을 초과했습니다. 내일 00:00에 초기화됩니다.')
          }
        }
        return
      }
      
      onError?.(`서버 오류 (${response.status}): ${errorText}`)
      return
    }

    // SSE 응답을 텍스트로 받아서 파싱
    const text = await response.text()
    let fullResponse = ''
    let finalData: any = null
    
    const blocks = normalizeSseText(text).split('\n\n')
    for (const block of blocks) {
      const payload = extractSseDataPayload(block)
      if (!payload) continue
      try {
        const event = JSON.parse(payload)
        if (event.type === 'chunk') {
          fullResponse += event.text || ''
        } else if (event.type === 'done') {
          finalData = event
        }
      } catch (e) {
        // 파싱 오류 무시
      }
    }
    
    onLog('✨ 답변 완료!')
    
    const chatResponse: ChatResponse = {
      response: finalData?.response || fullResponse,
      raw_answer: finalData?.response || fullResponse,
      sources: finalData?.sources || [],
      source_urls: finalData?.source_urls || [],
      used_chunks: finalData?.used_chunks || [],
      router_output: finalData?.router_output,
      function_results: finalData?.function_results,
      orchestration_result: finalData?.orchestration_result,
      sub_agent_results: finalData?.sub_agent_results,
      metadata: finalData?.metadata
    }
    
    onResult(chatResponse)
    
  } catch (error: any) {
    if (error?.name === 'AbortError') {
      console.log('요청이 취소되었습니다')
      return
    }
    
    console.error('이미지 채팅 오류:', error)
    onError?.(error?.message || '네트워크 오류가 발생했습니다')
  }
}

// 이미지와 함께 채팅 API (스트리밍)
export const sendMessageStreamWithImage = async (
  message: string,
  sessionId: string,
  image: File,
  onLog: (log: string) => void,
  onResult: (result: ChatResponse) => void,
  onError?: (error: string) => void,
  abortSignal?: AbortSignal,
  onChunk?: (chunk: string) => void,
  token?: string,  // 인증 토큰
  onScoreReviewRequired?: (payload: ScoreReviewRequiredEvent) => void,
  scoreId?: string,
  useSchoolRecord?: boolean,
  onSchoolGradeSaved?: (payload: SchoolGradeSavedEvent) => void,
  useLinkedNaesin?: boolean,
  skipScoreReview?: boolean,
): Promise<void> => {
  const IS_CAPACITOR_APP = isCapacitorApp()
  
  // iOS WebView에서 SSE ReadableStream이 제대로 동작하지 않아 비스트리밍 API 사용
  if (IS_CAPACITOR_APP) {
    return sendMessageNonStreamWithImage(message, sessionId, image, onLog, onResult, onError, abortSignal, token, useSchoolRecord, useLinkedNaesin, skipScoreReview)
  }
  
  try {
    onLog('🖼️ 이미지를 분석하는 중...')
    
    // FormData로 이미지와 메시지 전송
    const formData = new FormData()
    formData.append('message', message)
    formData.append('session_id', sessionId)
    formData.append('image', image)
    formData.append('use_school_record', useSchoolRecord ? 'true' : 'false')
    formData.append('use_linked_naesin', useLinkedNaesin ? 'true' : 'false')
    formData.append('skip_score_review', skipScoreReview ? 'true' : 'false')
    if (scoreId) {
      formData.append('score_id', scoreId)
    }
    
    // 헤더 구성
    const headers: Record<string, string> = {}
    
    const response = await fetchWithAuthRetry(`${API_BASE_URL}/chat/v2/stream/with-image`, {
      method: 'POST',
      headers,
      body: formData,
      signal: abortSignal,
    }, API_BASE_URL, token)

    if (!response.ok) {
      const errorText = await response.text()
      console.error('API 에러:', response.status, errorText)

      if (response.status === 401) {
        onError?.(AUTH_REQUIRED_ERROR)
        return
      }
      
      // 413 에러 (파일 크기 초과)
      if (response.status === 413) {
        onError?.('이미지 크기가 너무 큽니다. 10MB 이하의 이미지를 선택해주세요.')
        return
      }
      
      // 429 에러 (Rate Limit)
      if (response.status === 429) {
        // 비로그인 사용자 (로그인 유도 메시지가 포함된 경우)
        if (errorText.includes('로그인을 통해')) {
          onError?.('__RATE_LIMIT_GUEST__')
        } else {
          // 로그인 사용자 - 백엔드 메시지 그대로 표시
          try {
            const parsed = JSON.parse(errorText)
            onError?.(parsed.detail || '일일 사용량을 초과했습니다.')
          } catch {
            onError?.('일일 사용량을 초과했습니다. 내일 00:00에 초기화됩니다.')
          }
        }
        return
      }
      
      onError?.(`서버 오류 (${response.status}): ${errorText}`)
      return
    }

    // SSE 스트리밍 처리
    const reader = response.body?.getReader()
    if (!reader) {
      onError?.('스트리밍을 지원하지 않습니다')
      return
    }

    const decoder = new TextDecoder()
    let buffer = ''
    let fullResponse = ''
    let finalData: any = null

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      
      const { blocks, remainder } = splitSseBlocks(buffer)
      buffer = remainder

      for (const block of blocks) {
        const payload = extractSseDataPayload(block)
        if (!payload) continue

        try {
          const event = JSON.parse(payload)
          
          if (event.type === 'status') {
            // 상태 업데이트 - detail 정보를 JSON으로 직렬화하여 전달
            const logMessage = event.detail 
              ? `${event.message || ''}|||${JSON.stringify({ step: event.step, detail: event.detail })}`
              : event.message || ''
            onLog(logMessage)
          } else if (event.type === 'chunk') {
            const chunkText = event.text || ''
            fullResponse += chunkText
            onChunk?.(chunkText)
          } else if (event.type === 'score_review_required') {
            onScoreReviewRequired?.(event as ScoreReviewRequiredEvent)
            return
          } else if (event.type === 'school_grade_saved') {
            onSchoolGradeSaved?.(event as SchoolGradeSavedEvent)
            return
          } else if (event.type === 'done') {
            finalData = event
            onLog('✨ 이미지 분석 완료!')
          } else if (event.type === 'error') {
            onError?.(event.message || '알 수 없는 오류')
            return
          }
        } catch (e) {
          console.warn('SSE 파싱 오류:', e, payload)
        }
      }
    }

    // 최종 결과 전달
    const chatResponse: ChatResponse = {
      response: finalData?.response || fullResponse,
      raw_answer: finalData?.response || fullResponse,
      sources: finalData?.sources || [],
      source_urls: finalData?.source_urls || [],
      used_chunks: finalData?.used_chunks || [],
      router_output: undefined,
      function_results: undefined,
      orchestration_result: undefined,
      sub_agent_results: undefined,
      metadata: {
        image_analysis: finalData?.image_analysis,
        pipeline_time: finalData?.pipeline_time
      },
      require_login: finalData?.require_login || false,  // 비로그인 3회째 질문 시 마스킹
      score_id: finalData?.score_id
    }
    
    onResult(chatResponse)
    
  } catch (error: any) {
    if (error?.name === 'AbortError') {
      console.log('요청이 취소되었습니다')
      return
    }
    
    console.error('이미지 채팅 오류:', error)
    onError?.(error?.message || '네트워크 오류가 발생했습니다')
  }
}

// 업로드 API
export const uploadDocument = async (
  file: File,
  schoolName?: string
): Promise<UploadResponse> => {
  const formData = new FormData()
  formData.append('file', file)
  if (schoolName) {
    formData.append('school_name', schoolName)
  }

  const response = await api.post<UploadResponse>('/upload/', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 600000, // 10분 (대형 PDF는 요약·목차·Vision·청킹·Supabase까지 오래 걸림)
  })
  return response.data
}

// 문서 수정 API
export const updateDocument = async (
  id: string,
  title: string,
  source: string,
  hashtags?: string[]
): Promise<void> => {
  await api.patch(`/documents/${id}`, {
    title,
    source,
    hashtags,
  })
}

// 문서 목록 API
export const getDocuments = async (): Promise<Document[]> => {
  try {
    console.log('📡 API 요청: GET /documents')
    const response = await api.get<{ documents: Document[] }>('/documents', {
      timeout: 10000 // 10초 타임아웃
    })
    console.log('✅ API 응답 성공:', response.data.documents.length, '개 문서')
    return response.data.documents
  } catch (error: any) {
    console.error('❌ API 요청 실패:', {
      status: error.response?.status,
      statusText: error.response?.statusText,
      message: error.message,
      data: error.response?.data
    })
    
    if (error.code === 'ECONNABORTED') {
      throw new Error('요청 시간 초과 (10초). 서버가 응답하지 않습니다.')
    }
    if (error.response?.status === 404) {
      throw new Error('API 엔드포인트를 찾을 수 없습니다. (/api/documents)')
    }
    if (error.response?.status === 500) {
      throw new Error('서버 오류가 발생했습니다. 관리자에게 문의하세요.')
    }
    if (!error.response) {
      throw new Error('서버에 연결할 수 없습니다. 네트워크를 확인하세요.')
    }
    
    throw error
  }
}

// 문서 삭제 API
export const deleteDocument = async (id: string): Promise<void> => {
  await api.delete(`/documents/${id}`)
}

// 에이전트 목록 API
export const getAgents = async (): Promise<Agent[]> => {
  const response = await api.get<{ agents: Agent[] }>('/chat/agents')
  return response.data.agents
}

// 에이전트 추가 API
export const addAgent = async (agent: Agent): Promise<void> => {
  await api.post('/chat/agents', agent)
}

// 에이전트 삭제 API
export const deleteAgent = async (agentName: string): Promise<void> => {
  await api.delete(`/chat/agents/${encodeURIComponent(agentName)}`)
}

// 세션 초기화 API
export const resetSession = async (sessionId: string): Promise<void> => {
  await api.post(`/chat/reset?session_id=${sessionId}`)
}

// ============================================================
// 프로필 API
// ============================================================

export interface ScoreEntry {
  등급?: number
  표준점수?: number
  백분위?: number
  선택과목?: string  // 모든 과목의 선택과목
}

export interface UserProfile {
  user_id: string
  scores: Record<string, ScoreEntry>
  created_at: string
  updated_at: string
  image_url?: string | null
  banner_image_url?: string | null
  is_premium?: boolean
  display_name?: string | null
  bio?: string | null
  description?: string | null
}

// 프로필 조회
export const getProfile = async (token: string): Promise<UserProfile> => {
  const response = await api.get<UserProfile>('/profile/me', {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

// 프로필 수정 (image_url, banner_image_url, display_name, bio, description 등)
export const updateProfile = async (
  token: string,
  payload: { image_url?: string; banner_image_url?: string; display_name?: string; bio?: string; description?: string }
): Promise<UserProfile> => {
  const response = await api.patch<UserProfile>('/profile/me', payload, {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

// 프로필 사진 업로드 (user_profiles.metadata.image_url 에 저장)
export const uploadProfileAvatar = async (token: string, file: File): Promise<UserProfile> => {
  const form = new FormData()
  form.append('file', file)
  const apiUrl = getEffectiveApiBaseUrl()
  const res = await fetch(`${apiUrl}/profile/me/avatar`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '업로드 실패')
  }
  return res.json()
}

// 프로필 배경 이미지 업로드 (user_profiles.metadata.banner_image_url 에 저장)
export const uploadProfileBanner = async (token: string, file: File): Promise<UserProfile> => {
  const form = new FormData()
  form.append('file', file)
  const apiUrl = getEffectiveApiBaseUrl()
  const res = await fetch(`${apiUrl}/profile/me/banner`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || '업로드 실패')
  }
  return res.json()
}

// 생기부 연동 상태 (연동 완료 개수 표시용)
export const getSchoolRecordStatus = async (token: string): Promise<{ linked: boolean }> => {
  const response = await api.get<{ linked: boolean }>('/school-record/status', {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
}

export const getMySchoolGradeInput = async (
  token: string
): Promise<{ school_grade_input: Record<string, any> }> => {
  const response = await api.get<{ school_grade_input: Record<string, any> }>('/profile/me/school-grade-input', {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data || { school_grade_input: {} }
}

// 프로필 저장/수정
export const saveProfile = async (
  token: string,
  scores: Record<string, ScoreEntry>
): Promise<UserProfile> => {
  const response = await api.post<UserProfile>(
    '/profile/me',
    { scores },
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data
}

// 프로필 삭제
export const deleteProfile = async (token: string): Promise<void> => {
  await api.delete('/profile/me', {
    headers: { Authorization: `Bearer ${token}` }
  })
}

// ============================================================
// 채팅 마이그레이션 API
// ============================================================

export interface MigrateMessageItem {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  source_urls?: string[]
}

export interface MigrateMessagesResponse {
  session_id: string
  message_count: number
  message: string
}

// 비로그인 채팅 내역을 로그인한 사용자의 세션으로 마이그레이션
export const migrateMessages = async (
  token: string,
  messages: MigrateMessageItem[],
  browserSessionId: string
): Promise<MigrateMessagesResponse> => {
  const response = await api.post<MigrateMessagesResponse>(
    '/sessions/migrate',
    { messages, browser_session_id: browserSessionId },
    { headers: { Authorization: `Bearer ${token}` } }
  )
  return response.data
}

// ============================================================
// Score Review / Score Sets API
// ============================================================

export const approveScoreReview = async (
  pendingId: string,
  sessionId: string,
  title: string,
  scores: Record<string, any>,
  token?: string
): Promise<{ pending_id: string; score_id: string; score_name: string }> => {
  const response = await api.post(
    '/chat/v2/score-review/approve',
    {
      pending_id: pendingId,
      session_id: sessionId,
      title,
      scores,
    },
    {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    }
  )
  return response.data
}

export const skipScoreReviewSession = async (
  sessionId: string,
  pendingId?: string,
  token?: string
): Promise<void> => {
  await api.post(
    '/chat/v2/score-review/skip-session',
    {
      session_id: sessionId,
      pending_id: pendingId || null,
    },
    {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    }
  )
}

export const suggestScoreSets = async (
  query: string,
  sessionId: string,
  token?: string
): Promise<ScoreSetSuggestItem[]> => {
  const response = await api.get('/chat/v2/score-sets/suggest', {
    params: { q: query, session_id: sessionId },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  return response.data?.items || []
}

export const getScoreSetByName = async (
  name: string,
  sessionId: string,
  token?: string
): Promise<{ id: string; name: string; scores: Record<string, any> }> => {
  const encoded = encodeURIComponent(name.startsWith('@') ? name.slice(1) : name)
  const response = await api.get(`/chat/v2/score-set/${encoded}`, {
    params: { session_id: sessionId },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
  return response.data
}

export const listScoreSets = async (
  sessionId: string,
  token?: string
): Promise<ScoreSetItem[]> => {
  try {
    const response = await api.get('/chat/v2/score-sets', {
      params: { session_id: sessionId },
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    })
    return response.data?.items || []
  } catch (e: any) {
    // 모바일 등에서 경로 404 시 빈 목록으로 처리해 "Not Found" 문구 노출 방지
    if (e?.response?.status === 404) return []
    throw e
  }
}

export const createScoreSet = async (
  sessionId: string,
  name: string,
  scores: Record<string, any>,
  token?: string
): Promise<ScoreSetItem> => {
  const response = await api.post(
    '/chat/v2/score-sets',
    { session_id: sessionId, name, scores },
    { headers: token ? { Authorization: `Bearer ${token}` } : undefined }
  )
  return response.data
}

export const updateScoreSet = async (
  scoreSetId: string,
  sessionId: string,
  name: string,
  scores: Record<string, any>,
  token?: string
): Promise<ScoreSetItem> => {
  const response = await api.put(
    `/chat/v2/score-sets/${scoreSetId}`,
    { session_id: sessionId, name, scores },
    { headers: token ? { Authorization: `Bearer ${token}` } : undefined }
  )
  return response.data
}

export const deleteScoreSet = async (
  scoreSetId: string,
  sessionId: string,
  token?: string
): Promise<void> => {
  await api.delete(`/chat/v2/score-sets/${scoreSetId}`, {
    params: { session_id: sessionId },
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  })
}
