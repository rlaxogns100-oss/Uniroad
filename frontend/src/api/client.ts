import axios from 'axios'

const API_BASE_URL = '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 180000, // 180초 (멀티에이전트 파이프라인은 시간이 더 걸릴 수 있음)
})

export interface ChatRequest {
  message: string
  session_id?: string
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

// 채팅 API (Router Agent) - 비스트리밍 폴백
export const sendMessageStream = async (
  message: string,
  sessionId: string,
  onLog: (log: string) => void,
  onResult: (result: ChatResponse) => void,
  onError?: (error: string) => void,
  abortSignal?: AbortSignal,
  onChunk?: (chunk: string) => void  // 실시간 텍스트 청크 콜백
): Promise<void> => {
  try {
    onLog('🔍 질문을 분석하는 중...')
    
    // 실시간 스트리밍 엔드포인트 사용
    const response = await fetch('/api/chat/v2/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        session_id: sessionId,
      }),
      signal: abortSignal,
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('API 에러:', response.status, errorText)
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
      
      // SSE 메시지 파싱 (data: {...}\n\n 형식)
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''  // 마지막 불완전한 청크는 버퍼에 유지

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        
        try {
          const jsonStr = line.slice(6)  // 'data: ' 제거
          const event = JSON.parse(jsonStr)
          
          if (event.type === 'status') {
            // 상태 업데이트 - detail 정보를 JSON으로 직렬화하여 전달
            const logMessage = event.detail 
              ? `${event.message || ''}|||${JSON.stringify({ step: event.step, detail: event.detail })}`
              : event.message || ''
            onLog(logMessage)
          } else if (event.type === 'chunk') {
            // 텍스트 청크 - 실시간으로 화면에 표시
            const chunkText = event.text || ''
            fullResponse += chunkText
            onChunk?.(chunkText)
          } else if (event.type === 'done') {
            // 완료
            finalData = event
            onLog('✨ 답변 완료!')
          } else if (event.type === 'error') {
            onError?.(event.message || '알 수 없는 오류')
            return
          }
        } catch (e) {
          console.warn('SSE 파싱 오류:', e, line)
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
      }
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

// 이미지와 함께 채팅 API (스트리밍)
export const sendMessageStreamWithImage = async (
  message: string,
  sessionId: string,
  image: File,
  onLog: (log: string) => void,
  onResult: (result: ChatResponse) => void,
  onError?: (error: string) => void,
  abortSignal?: AbortSignal,
  onChunk?: (chunk: string) => void
): Promise<void> => {
  try {
    onLog('🖼️ 이미지를 분석하는 중...')
    
    // FormData로 이미지와 메시지 전송
    const formData = new FormData()
    formData.append('message', message)
    formData.append('session_id', sessionId)
    formData.append('image', image)
    
    const response = await fetch('/api/chat/v2/stream/with-image', {
      method: 'POST',
      body: formData,
      signal: abortSignal,
    })

    if (!response.ok) {
      const errorText = await response.text()
      console.error('API 에러:', response.status, errorText)
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
      
      // SSE 메시지 파싱 (data: {...}\n\n 형식)
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        
        try {
          const jsonStr = line.slice(6)
          const event = JSON.parse(jsonStr)
          
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
          } else if (event.type === 'done') {
            finalData = event
            onLog('✨ 이미지 분석 완료!')
          } else if (event.type === 'error') {
            onError?.(event.message || '알 수 없는 오류')
            return
          }
        } catch (e) {
          console.warn('SSE 파싱 오류:', e, line)
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
      }
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
    timeout: 180000,
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
  const response = await api.get<{ documents: Document[] }>('/documents')
  return response.data.documents
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
}

// 프로필 조회
export const getProfile = async (token: string): Promise<UserProfile> => {
  const response = await api.get<UserProfile>('/profile/me', {
    headers: { Authorization: `Bearer ${token}` }
  })
  return response.data
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