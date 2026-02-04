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
              onClick={() => navigate('/analytics')}
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-indigo-100 text-indigo-800 hover:bg-indigo-200 transition-colors font-medium border border-indigo-200"
            >
              <span className="text-2xl">📊</span>
              <span className="text-sm text-center">실시간 분석</span>
            </button>
            <button
              onClick={() => navigate('/admin-analytics')}
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-purple-100 text-purple-800 hover:bg-purple-200 transition-colors font-medium border border-purple-200"
            >
              <span className="text-2xl">📉</span>
              <span className="text-sm text-center">관리자 분석</span>
            </button>
            <a
              href="https://analytics.google.com/analytics/web/#/analysis/a382271955p521910579/edit/iAeobtq1RAOuwPn3j53_fA"
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-col items-center justify-center gap-2 p-4 rounded-xl bg-blue-100 text-blue-800 hover:bg-blue-200 transition-colors font-medium border border-blue-200"
              title="GA4 계정으로 로그인 후 방문하면 자동으로 분석 페이지가 열립니다"
            >
              <span className="text-2xl">📈</span>
              <span className="text-sm text-center">GA4 Analytics</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

