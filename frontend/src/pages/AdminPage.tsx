import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadDocument, getDocuments, deleteDocument, updateDocument, Document } from '../api/client'

interface UploadTask {
  id: string
  file: File
  status: 'waiting' | 'uploading' | 'success' | 'error'
  progress: string
  logs: string[]
}

interface PaymentRequestRow {
  user_id: string
  email?: string
  user_name?: string
  name?: string
  phone?: string
  amount: number
  source?: string
  status: string
  created_at: string
}

interface UserOverviewRow {
  id: string
  email?: string
  name?: string
  recent_signup_at: string
  total_chat_count: number
  last_active_at: string
  plan_status: 'Pro' | 'Basic'
}

interface UsersOverviewResponse {
  bank_transfer_requests: PaymentRequestRow[]
  card_checkout_requests: PaymentRequestRow[]
  premium_users: UserOverviewRow[]
  basic_users: UserOverviewRow[]
  total_users: number
  total_users_users_table?: number
}

export default function AdminPage() {
  const navigate = useNavigate()
  const [files, setFiles] = useState<File[]>([])
  const [uploadQueue, setUploadQueue] = useState<UploadTask[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [documents, setDocuments] = useState<Document[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editSource, setEditSource] = useState('')
  const [editHashtags, setEditHashtags] = useState<string[]>([])
  const [newHashtag, setNewHashtag] = useState('')
  const [selectedHashtags, setSelectedHashtags] = useState<string[]>([])
  const [showLogs, setShowLogs] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  
  // 피드백 관련 state
  const [showFeedback, setShowFeedback] = useState(false)
  const [feedbacks, setFeedbacks] = useState<any[]>([])
  const [feedbackLoading, setFeedbackLoading] = useState(false)
  
  // 유저 관리 관련 state
  const [showUsers, setShowUsers] = useState(false)
  const [usersLoading, setUsersLoading] = useState(false)
  const [usersOverview, setUsersOverview] = useState<UsersOverviewResponse>({
    bank_transfer_requests: [],
    card_checkout_requests: [],
    premium_users: [],
    basic_users: [],
    total_users: 0,
    total_users_users_table: 0,
  })
  const [premiumSearch, setPremiumSearch] = useState('')
  const [basicSearch, setBasicSearch] = useState('')
  const [premiumFilter, setPremiumFilter] = useState<'all' | 'chat' | 'no_chat' | 'active' | 'inactive'>('all')
  const [basicFilter, setBasicFilter] = useState<'all' | 'chat' | 'no_chat' | 'active' | 'inactive'>('all')
  
  // 모든 문서에서 고유 해시태그 추출
  const allHashtags = Array.from(
    new Set(documents.flatMap((doc) => doc.hashtags || []))
  ).sort()
  
  // 필터링된 문서
  const filteredDocuments = selectedHashtags.length === 0
    ? documents
    : documents.filter((doc) =>
        selectedHashtags.some((tag) => doc.hashtags?.includes(tag))
      )

  useEffect(() => {
    loadDocuments()
  }, [])

  useEffect(() => {
    if (showFeedback && feedbacks.length === 0) {
      loadFeedbacks()
    }
  }, [showFeedback])

  useEffect(() => {
    if (showUsers && usersOverview.total_users === 0) {
      loadUsersOverview()
    }
  }, [showUsers])

  const loadUsersOverview = async () => {
    setUsersLoading(true)
    try {
      const accessToken = localStorage.getItem('access_token')
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/payments/admin/users-overview`, {
        headers: {
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {})
        }
      })
      if (response.ok) {
        const data = await response.json()
        setUsersOverview({
          bank_transfer_requests: data.bank_transfer_requests || [],
          card_checkout_requests: data.card_checkout_requests || [],
          premium_users: data.premium_users || [],
          basic_users: data.basic_users || [],
          total_users: data.total_users || 0,
          total_users_users_table: data.total_users_users_table || 0,
        })
      }
    } catch (error) {
      console.error('유저 목록 로드 오류:', error)
    } finally {
      setUsersLoading(false)
    }
  }

  const loadFeedbacks = async () => {
    setFeedbackLoading(true)
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/feedback`)
      if (response.ok) {
        const data = await response.json()
        setFeedbacks(data)
      }
    } catch (error) {
      console.error('피드백 로드 오류:', error)
    } finally {
      setFeedbackLoading(false)
    }
  }

  const loadDocuments = async () => {
    try {
      setIsLoading(true)
      setLoadError(null)
      console.log('📥 문서 목록 로드 시작...')
      const docs = await getDocuments()
      console.log('✅ 문서 목록 로드 완료:', docs.length, '개')
      setDocuments(docs)
    } catch (error: any) {
      console.error('❌ 문서 목록 로드 오류:', error)
      const errorMessage = error?.message || '문서 목록을 불러올 수 없습니다.'
      setLoadError(errorMessage)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      (file) => file.type === 'application/pdf'
    )
    
    if (droppedFiles.length === 0) {
      alert('PDF 파일만 업로드 가능합니다.')
      return
    }
    
    setFiles((prev) => [...prev, ...droppedFiles])
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files).filter(
        (file) => file.type === 'application/pdf'
      )
      setFiles((prev) => [...prev, ...selectedFiles])
    }
  }

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleUpload = async () => {
    if (files.length === 0) {
      alert('파일을 선택해주세요.')
      return
    }

    setIsUploading(true)
    setShowLogs(true)
    
    // 업로드 큐 생성
    const tasks: UploadTask[] = files.map((file) => ({
      id: `${Date.now()}-${Math.random()}`,
      file,
      status: 'waiting',
      progress: '대기 중...',
      logs: []
    }))
    
    setUploadQueue(tasks)

    // 순차 업로드
    for (let i = 0; i < tasks.length; i++) {
      const task = tasks[i]
      
      // 상태 업데이트: uploading
      setUploadQueue((prev) =>
        prev.map((t) =>
          t.id === task.id
            ? { ...t, status: 'uploading', progress: '업로드 중...', logs: ['⏳ 업로드 시작...'] }
            : t
        )
      )

      try {
        // 실제 업로드
        const result = await uploadDocument(task.file)
        
        // 상태 업데이트: success
        setUploadQueue((prev) =>
          prev.map((t) =>
            t.id === task.id
              ? {
                  ...t,
                  status: 'success',
                  progress: '완료',
                  logs: [
                    ...t.logs,
                    `✅ 업로드 완료 (${result.stats.processingTime})`,
                    `📄 ${result.stats.totalPages}페이지`,
                    `📦 ${result.stats.chunksTotal}개 청크`
                  ]
                }
              : t
          )
        )
      } catch (error: any) {
        // 상태 업데이트: error
        setUploadQueue((prev) =>
          prev.map((t) =>
            t.id === task.id
              ? {
                  ...t,
                  status: 'error',
                  progress: '실패',
                  logs: [...t.logs, `❌ 오류: ${error.response?.data?.detail || error.message}`]
                }
              : t
          )
        )
      }
    }

    // 완료 후 정리
    setIsUploading(false)
    setFiles([])
    await loadDocuments()
  }

  const clearQueue = () => {
    setUploadQueue([])
    setShowLogs(false)
  }

  const handleEdit = (doc: Document) => {
    setEditingId(doc.id)
    setEditTitle(doc.title)
    setEditSource(doc.source)
    setEditHashtags(doc.hashtags || [])
    setNewHashtag('')
  }

  const handleSaveEdit = async (id: string) => {
    try {
      await updateDocument(id, editTitle, editSource, editHashtags)
      setEditingId(null)
      await loadDocuments()
    } catch (error) {
      console.error('수정 오류:', error)
      alert('수정에 실패했습니다.')
    }
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditTitle('')
    setEditSource('')
    setEditHashtags([])
    setNewHashtag('')
  }

  const handleAddHashtag = () => {
    const tag = newHashtag.trim()
    if (!tag) return
    
    const formattedTag = tag.startsWith('#') ? tag : `#${tag}`
    
    if (editHashtags.includes(formattedTag)) {
      alert('이미 존재하는 해시태그입니다.')
      return
    }
    
    setEditHashtags([...editHashtags, formattedTag])
    setNewHashtag('')
  }

  const handleRemoveHashtag = (tagToRemove: string) => {
    setEditHashtags(editHashtags.filter((tag) => tag !== tagToRemove))
  }

  const handleDelete = async (id: string) => {
    if (!confirm('정말 삭제하시겠습니까?')) return

    try {
      await deleteDocument(id)
      await loadDocuments()
    } catch (error) {
      console.error('삭제 오류:', error)
      alert('삭제에 실패했습니다.')
    }
  }

  const applyUserFilter = (
    list: UserOverviewRow[],
    search: string,
    filter: 'all' | 'chat' | 'no_chat' | 'active' | 'inactive'
  ) => {
    const q = search.trim().toLowerCase()
    return list.filter((u) => {
      const matchSearch =
        !q ||
        u.id.toLowerCase().includes(q) ||
        (u.email || '').toLowerCase().includes(q) ||
        (u.name || '').toLowerCase().includes(q)

      const hasChat = (u.total_chat_count || 0) > 0
      const hasActive = !!u.last_active_at
      const matchFilter =
        filter === 'all' ||
        (filter === 'chat' && hasChat) ||
        (filter === 'no_chat' && !hasChat) ||
        (filter === 'active' && hasActive) ||
        (filter === 'inactive' && !hasActive)

      return matchSearch && matchFilter
    })
  }

  const filteredPremiumUsers = applyUserFilter(usersOverview.premium_users, premiumSearch, premiumFilter)
  const filteredBasicUsers = applyUserFilter(usersOverview.basic_users, basicSearch, basicFilter)

  const updatePlanStatus = async (targetUserId: string, isPremium: boolean) => {
    const accessToken = localStorage.getItem('access_token')
    if (!accessToken) {
      alert('관리자 인증 토큰이 없습니다. 다시 로그인해 주세요.')
      return
    }
    try {
      const res = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/v1/payments/admin/user-plan`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ user_id: targetUserId, is_premium: isPremium }),
      })
      if (!res.ok) {
        const e = await res.json().catch(() => ({}))
        throw new Error(e?.detail || '요금제 상태 변경 실패')
      }
      await loadUsersOverview()
    } catch (e: any) {
      alert(e?.message || '요금제 상태 변경 중 오류가 발생했습니다.')
    }
  }

  // 로딩 중 표시
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-600 text-lg font-medium">문서 목록을 불러오는 중...</p>
          <p className="text-gray-500 text-sm mt-2">잠시만 기다려주세요</p>
        </div>
      </div>
    )
  }

  // 에러 표시
  if (loadError) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50 flex items-center justify-center">
        <div className="text-center bg-white rounded-2xl shadow-xl p-8 max-w-md">
          <div className="text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">문서 목록 로드 실패</h2>
          <p className="text-gray-600 mb-6">{loadError}</p>
          <button
            onClick={loadDocuments}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
          >
            다시 시도
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50">
      {/* 헤더 */}
      <header className="bg-white shadow-sm border-b border-gray-200 px-6 py-4">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">📚 관리자 페이지</h1>
            <p className="text-sm text-gray-600">문서 업로드 및 관리</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => navigate('/upload')}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
            >
              📤 업로드 페이지
            </button>
            <button
              onClick={() => navigate('/chat/login')}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
            >
              ← 채팅으로
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* 관리 메뉴 - 모든 관리 기능 진입 */}
        <div className="bg-white rounded-2xl shadow-xl p-6 mb-8 border border-gray-100">
          <h2 className="text-lg font-bold text-gray-800 mb-4">⚙️ 관리 메뉴</h2>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <button
              onClick={() => navigate('/upload')}
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-green-100 text-green-800 hover:bg-green-200 transition-colors font-medium border border-green-200"
            >
              <span className="text-2xl">📤</span>
              <span className="text-sm text-center">학교별 업로드</span>
            </button>
            <button
              onClick={() => navigate('/adminagent')}
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-violet-100 text-violet-800 hover:bg-violet-200 transition-colors font-medium border border-violet-200"
            >
              <span className="text-2xl">📋</span>
              <span className="text-sm text-center">로그/평가</span>
            </button>
            <button
              onClick={() => navigate('/auto-reply')}
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-rose-100 text-rose-800 hover:bg-rose-200 transition-colors font-medium border border-rose-200"
            >
              <span className="text-2xl">💬</span>
              <span className="text-sm text-center">댓글 봇</span>
            </button>
            <button
              onClick={() => navigate('/admin-analytics')}
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-amber-100 text-amber-800 hover:bg-amber-200 transition-colors font-medium border border-amber-200"
            >
              <span className="text-2xl">📊</span>
              <span className="text-sm text-center">관리자 분석</span>
            </button>
            <button
              onClick={() => setShowFeedback(!showFeedback)}
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-teal-100 text-teal-800 hover:bg-teal-200 transition-colors font-medium border border-teal-200"
            >
              <span className="text-2xl">💡</span>
              <span className="text-sm text-center">의견 보기</span>
            </button>
            <button
              onClick={() => setShowUsers(!showUsers)}
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors font-medium border border-blue-200"
            >
              <span className="text-2xl">👤</span>
              <span className="text-sm text-center">유저</span>
            </button>
            <button
              onClick={() => navigate('/chat/admin/review')}
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-slate-100 text-slate-800 hover:bg-slate-200 transition-colors font-medium border border-slate-200"
            >
              <span className="text-2xl">📝</span>
              <span className="text-sm text-center">로그리뷰</span>
            </button>
          </div>
        </div>

        {/* 피드백 섹션 */}
        {showFeedback && (
          <div className="bg-white rounded-2xl shadow-xl p-6 mb-8 border border-gray-100">
            <h2 className="text-lg font-bold text-gray-800 mb-4">💡 사용자 의견</h2>
            {feedbackLoading ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p className="mt-2 text-gray-600">로딩 중...</p>
              </div>
            ) : feedbacks.length === 0 ? (
              <p className="text-center py-8 text-gray-500">아직 의견이 없습니다.</p>
            ) : (
              <div className="space-y-3">
                {feedbacks.map((feedback) => (
                  <div key={feedback.id} className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          {feedback.user_name && (
                            <span className="text-sm font-medium text-gray-900">{feedback.user_name}</span>
                          )}
                          {feedback.user_email && (
                            <span className="text-xs text-gray-500">({feedback.user_email})</span>
                          )}
                          {!feedback.user_name && !feedback.user_email && (
                            <span className="text-sm text-gray-500">익명</span>
                          )}
                          <span className="text-xs text-gray-400">
                            {new Date(feedback.created_at).toLocaleString('ko-KR')}
                          </span>
                        </div>
                        <p className="text-sm text-gray-700 whitespace-pre-wrap break-words">{feedback.content}</p>
                      </div>
                      <button
                        onClick={async () => {
                          if (!confirm('이 의견을 삭제하시겠습니까?')) return
                          
                          try {
                            const response = await fetch(`${import.meta.env.VITE_API_URL || 'http://localhost:8000'}/api/feedback/${feedback.id}`, {
                              method: 'DELETE'
                            })
                            
                            if (response.ok) {
                              setFeedbacks(feedbacks.filter(f => f.id !== feedback.id))
                            } else {
                              alert('삭제에 실패했습니다.')
                            }
                          } catch (error) {
                            console.error('피드백 삭제 오류:', error)
                            alert('삭제에 실패했습니다.')
                          }
                        }}
                        className="px-3 py-1.5 text-xs bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors flex-shrink-0"
                      >
                        삭제
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 유저 섹션 */}
        {showUsers && (
          <div className="bg-white rounded-2xl shadow-xl p-6 mb-8 border border-gray-100">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold text-gray-800">👤 유저</h2>
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-600">총 <span className="font-bold text-blue-600">{usersOverview.total_users}</span>명</span>
                <span className="text-xs text-gray-500">(users 테이블: {usersOverview.total_users_users_table || 0}명)</span>
                <button
                  onClick={loadUsersOverview}
                  className="px-3 py-1.5 text-xs bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors"
                >
                  새로고침
                </button>
              </div>
            </div>
            {usersLoading ? (
              <div className="text-center py-8">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p className="mt-2 text-gray-600">로딩 중...</p>
              </div>
            ) : (
              <div className="space-y-8">
                {/* 신청 내역 */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                    <h3 className="font-semibold text-amber-900 mb-3">무통장입금 신청 내역</h3>
                    {usersOverview.bank_transfer_requests.length === 0 ? (
                      <p className="text-sm text-amber-800/70">내역이 없습니다.</p>
                    ) : (
                      <div className="space-y-2 max-h-56 overflow-y-auto">
                        {usersOverview.bank_transfer_requests.map((row, idx) => (
                          <div key={`${row.user_id}-${idx}`} className="text-xs bg-white/70 rounded-lg p-2 border border-amber-200">
                            <p><span className="font-semibold">날짜:</span> {row.created_at ? new Date(row.created_at).toLocaleString('ko-KR') : '-'}</p>
                            <p><span className="font-semibold">유저:</span> {row.user_id}</p>
                            <p><span className="font-semibold">이름/메일:</span> {row.user_name || '-'} / {row.email || '-'}</p>
                            <p><span className="font-semibold">이름/전화:</span> {row.name || '-'} / {row.phone || '-'}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
                    <h3 className="font-semibold text-blue-900 mb-3">카드결제 신청 내역</h3>
                    {usersOverview.card_checkout_requests.length === 0 ? (
                      <p className="text-sm text-blue-800/70">내역이 없습니다.</p>
                    ) : (
                      <div className="space-y-2 max-h-56 overflow-y-auto">
                        {usersOverview.card_checkout_requests.map((row, idx) => (
                          <div key={`${row.user_id}-${idx}`} className="text-xs bg-white/70 rounded-lg p-2 border border-blue-200">
                            <p><span className="font-semibold">날짜:</span> {row.created_at ? new Date(row.created_at).toLocaleString('ko-KR') : '-'}</p>
                            <p><span className="font-semibold">유저:</span> {row.user_id}</p>
                            <p><span className="font-semibold">이름/메일:</span> {row.user_name || '-'} / {row.email || '-'}</p>
                            <p><span className="font-semibold">금액:</span> {(row.amount || 0).toLocaleString()}원</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Pro 유저 */}
                <div>
                  <h3 className="font-semibold text-gray-900 mb-3">Pro 유저</h3>
                  <div className="mb-3 flex flex-col sm:flex-row gap-2">
                    <input
                      value={premiumSearch}
                      onChange={(e) => setPremiumSearch(e.target.value)}
                      placeholder="Pro 유저 검색 (id/email/name)"
                      className="w-full sm:w-80 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                    <select
                      value={premiumFilter}
                      onChange={(e) => setPremiumFilter(e.target.value as any)}
                      className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    >
                      <option value="all">전체</option>
                      <option value="chat">채팅 있음</option>
                      <option value="no_chat">채팅 없음</option>
                      <option value="active">최근 접속 있음</option>
                      <option value="inactive">최근 접속 없음</option>
                    </select>
                  </div>
                  <div className="overflow-x-auto rounded-xl border border-gray-200">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                          <th className="text-left py-3 px-4">id</th>
                          <th className="text-left py-3 px-4">이름</th>
                          <th className="text-left py-3 px-4">메일</th>
                          <th className="text-left py-3 px-4">최근 가입일</th>
                          <th className="text-left py-3 px-4">총 채팅 개수</th>
                          <th className="text-left py-3 px-4">최근 접속일</th>
                          <th className="text-left py-3 px-4">요금제 상태</th>
                          <th className="text-left py-3 px-4">변경</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredPremiumUsers.length === 0 ? (
                          <tr><td colSpan={8} className="py-6 text-center text-gray-500">Pro 유저가 없습니다.</td></tr>
                        ) : (
                          filteredPremiumUsers.map((u) => (
                            <tr key={`pro-${u.id}`} className="border-b border-gray-100 hover:bg-gray-50">
                              <td className="py-3 px-4 font-mono text-xs">{u.id}</td>
                              <td className="py-3 px-4">{u.name || '-'}</td>
                              <td className="py-3 px-4 text-xs">{u.email || '-'}</td>
                              <td className="py-3 px-4">{u.recent_signup_at ? new Date(u.recent_signup_at).toLocaleString('ko-KR') : '-'}</td>
                              <td className="py-3 px-4">{u.total_chat_count}</td>
                              <td className="py-3 px-4">{u.last_active_at ? new Date(u.last_active_at).toLocaleString('ko-KR') : '-'}</td>
                              <td className="py-3 px-4"><span className="px-2 py-1 rounded-full text-xs bg-indigo-100 text-indigo-700">Pro</span></td>
                              <td className="py-3 px-4">
                                <button
                                  onClick={() => updatePlanStatus(u.id, false)}
                                  className="px-2 py-1 text-xs rounded bg-gray-100 text-gray-700 hover:bg-gray-200"
                                >
                                  Basic로 변경
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Basic 유저 */}
                <div>
                  <h3 className="font-semibold text-gray-900 mb-3">Basic 유저</h3>
                  <div className="mb-3 flex flex-col sm:flex-row gap-2">
                    <input
                      value={basicSearch}
                      onChange={(e) => setBasicSearch(e.target.value)}
                      placeholder="Basic 유저 검색 (id/email/name)"
                      className="w-full sm:w-80 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                    <select
                      value={basicFilter}
                      onChange={(e) => setBasicFilter(e.target.value as any)}
                      className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    >
                      <option value="all">전체</option>
                      <option value="chat">채팅 있음</option>
                      <option value="no_chat">채팅 없음</option>
                      <option value="active">최근 접속 있음</option>
                      <option value="inactive">최근 접속 없음</option>
                    </select>
                  </div>
                  <div className="overflow-x-auto rounded-xl border border-gray-200">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 border-b border-gray-200">
                        <tr>
                          <th className="text-left py-3 px-4">id</th>
                          <th className="text-left py-3 px-4">이름</th>
                          <th className="text-left py-3 px-4">메일</th>
                          <th className="text-left py-3 px-4">최근 가입일</th>
                          <th className="text-left py-3 px-4">총 채팅 개수</th>
                          <th className="text-left py-3 px-4">최근 접속일</th>
                          <th className="text-left py-3 px-4">요금제 상태</th>
                          <th className="text-left py-3 px-4">변경</th>
                        </tr>
                      </thead>
                      <tbody>
                        {filteredBasicUsers.length === 0 ? (
                          <tr><td colSpan={8} className="py-6 text-center text-gray-500">Basic 유저가 없습니다.</td></tr>
                        ) : (
                          filteredBasicUsers.map((u) => (
                            <tr key={`basic-${u.id}`} className="border-b border-gray-100 hover:bg-gray-50">
                              <td className="py-3 px-4 font-mono text-xs">{u.id}</td>
                              <td className="py-3 px-4">{u.name || '-'}</td>
                              <td className="py-3 px-4 text-xs">{u.email || '-'}</td>
                              <td className="py-3 px-4">{u.recent_signup_at ? new Date(u.recent_signup_at).toLocaleString('ko-KR') : '-'}</td>
                              <td className="py-3 px-4">{u.total_chat_count}</td>
                              <td className="py-3 px-4">{u.last_active_at ? new Date(u.last_active_at).toLocaleString('ko-KR') : '-'}</td>
                              <td className="py-3 px-4"><span className="px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-700">Basic</span></td>
                              <td className="py-3 px-4">
                                <button
                                  onClick={() => updatePlanStatus(u.id, true)}
                                  className="px-2 py-1 text-xs rounded bg-indigo-100 text-indigo-700 hover:bg-indigo-200"
                                >
                                  Pro로 변경
                                </button>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

