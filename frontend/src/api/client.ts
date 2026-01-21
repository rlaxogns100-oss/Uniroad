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

export interface ChatResponse {
  response: string
  raw_answer?: string  // ✅ Final Agent 원본 출력
  sources: string[]
  source_urls: string[]
  // 멀티에이전트 디버그 데이터
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
}

export interface Agent {
  name: string
  description: string
}

// 채팅 API (스트리밍)
export const sendMessageStream = async (
  message: string,
  sessionId: string,
  onLog: (log: string) => void,
  onResult: (result: ChatResponse) => void,
  onError?: (error: string) => void,
  abortSignal?: AbortSignal
): Promise<void> => {
  const response = await fetch('/api/chat/stream', {
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
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const reader = response.body?.getReader()
  const decoder = new TextDecoder()

  if (!reader) {
    throw new Error('No reader available')
  }

  let buffer = ''
  
  while (true) {
    const { done, value } = await reader.read()
    
    if (done) break
    
    buffer += decoder.decode(value, { stream: true })
    
    // SSE 메시지 파싱
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        
        if (data.type === 'log') {
          onLog(data.message)
        } else if (data.type === 'result') {
          onResult(data.data)
        } else if (data.type === 'error') {
          onError?.(data.data.response || '오류가 발생했습니다')
        }
      }
    }
  }
}

// 업로드 API
export const uploadDocument = async (
  file: File
): Promise<UploadResponse> => {
  const formData = new FormData()
  formData.append('file', file)

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