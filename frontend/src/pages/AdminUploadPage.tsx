import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadDocument, getDocuments, deleteDocument, Document } from '../api/client'

/** API 오류에서 사용자에게 보여줄 메시지 추출 (FastAPI detail, 배열/문자열/plain text 모두 처리) */
function getUploadErrorMessage(error: any): string {
  if (!error) return '알 수 없는 오류'
  const data = error.response?.data
  if (data != null) {
    if (typeof data === 'string') return data.trim() || '서버 오류. 백엔드 터미널 로그를 확인하세요.'
    if (typeof data.detail === 'string') return data.detail.trim() || '서버 오류. 백엔드 터미널 로그를 확인하세요.'
    if (Array.isArray(data.detail)) return data.detail.map((e: any) => e?.msg ?? String(e)).join(', ') || '서버 오류.'
    if (data.detail != null && typeof data.detail === 'object') return JSON.stringify(data.detail)
    if (data.message) return String(data.message).trim() || '서버 오류.'
  }
  const fallback = error.message || '요청 처리 중 오류가 발생했습니다.'
  return (typeof fallback === 'string' ? fallback.trim() : String(fallback)) || '서버 오류. 백엔드 터미널에서 [process_pdf] 또는 [전역 예외] 로그를 확인하세요.'
}

interface UploadTask {
  id: string
  file: File
  schoolName: string
  status: 'waiting' | 'uploading' | 'success' | 'error'
  progress: string
  logs: string[]
  result?: {
    totalPages?: number
    chunksTotal?: number
    processingTime?: string
  }
}

interface UploadResult {
  filename: string
  schoolName: string
  status: '성공' | '실패'
  pages: number
  chunks: number
  time: string
  errorMessage?: string
}

// 학교 폴더 카드 (이름 편집 가능)
function SchoolFolderCard({
  school,
  files,
  onRename,
  onRemove,
}: {
  school: string
  files: File[]
  onRename: (newName: string) => void
  onRemove: () => void
}) {
  const [editing, setEditing] = useState(false)
  const [value, setValue] = useState(school)
  useEffect(() => {
    setValue(school)
  }, [school])
  const handleSave = () => {
    const v = value.trim()
    if (!v) {
      alert('학교명을 입력해주세요')
      return
    }
    if (v && v !== school) onRename(v)
    setEditing(false)
  }
  return (
    <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
      <div className="flex items-center justify-between mb-2">
        {editing ? (
          <div className="flex gap-2 flex-1">
            <input
              type="text"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSave()}
              placeholder="예: 연세대학교, 고려대학교"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
              autoFocus
            />
            <button onClick={handleSave} className="px-3 py-2 bg-blue-600 text-white rounded-lg text-sm whitespace-nowrap">
              저장
            </button>
            <button onClick={() => { setValue(school); setEditing(false) }} className="px-3 py-2 bg-gray-200 rounded-lg text-sm whitespace-nowrap">
              취소
            </button>
          </div>
        ) : (
          <button
            onClick={() => setEditing(true)}
            className="text-left flex-1 font-medium text-gray-900 hover:bg-gray-100 rounded px-2 py-1 -ml-2"
            title="클릭하여 학교명 수정"
          >
            🏫 {school}
          </button>
        )}
        <button onClick={onRemove} className="text-red-600 hover:text-red-700 text-sm">
          ✕ 제거
        </button>
      </div>
      <div className="text-xs text-gray-500 pl-2">
        {files.length}개 PDF
        {files.slice(0, 3).map((f) => f.name).join(', ')}
        {files.length > 3 && ` 외 ${files.length - 3}개`}
      </div>
      <div className="text-xs text-blue-600 mt-2 pl-2">
        💡 학교명을 클릭하여 입력·수정 (예: 연세대학교). 미지정은 반드시 수정해주세요.
      </div>
    </div>
  )
}

// 폴더 내 파일 → 학교별 그룹 (파일의 상위 폴더명 = 학교명). 폴더 선택 시에만 사용.
function groupFilesBySchool(files: File[]): Record<string, File[]> {
  const grouped: Record<string, File[]> = {}
  for (const file of files) {
    const path = (file as File & { webkitRelativePath?: string }).webkitRelativePath || ''
    const parts = path.split('/').filter(Boolean)
    const school = parts.length > 1 ? parts[parts.length - 2] : '미지정'
    if (!grouped[school]) grouped[school] = []
    grouped[school].push(file)
  }
  return grouped
}

export default function AdminUploadPage() {
  const navigate = useNavigate()
  
  // 학교별 파일: { 학교명: File[] }
  const [schoolFiles, setSchoolFiles] = useState<Record<string, File[]>>({})
  
  const [uploadQueue, setUploadQueue] = useState<UploadTask[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [isDragging, setIsDragging] = useState(false)
  
  // 업로드 결과
  const [uploadResults, setUploadResults] = useState<UploadResult[]>([])
  
  // 문서 목록
  const [documents, setDocuments] = useState<Document[]>([])
  const [selectedSchool, setSelectedSchool] = useState<string | null>(null)
  
  // 탭
  const [activeTab, setActiveTab] = useState<'upload' | 'documents'>('upload')

  // 파일 선택 후 학교명 입력 (단일/다중 파일 업로드용)
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [pendingSchoolName, setPendingSchoolName] = useState('')

  // 학교 이름 추출 함수
  const extractSchoolName = (doc: Document): string => {
    // 1. schoolName 필드가 있으면 사용
    if (doc.schoolName) return doc.schoolName
    
    // 2. 해시태그에서 대학교 이름 찾기
    const universityKeywords = ['대학교', '대학', '대']
    if (doc.hashtags) {
      for (const tag of doc.hashtags) {
        for (const keyword of universityKeywords) {
          if (tag.includes(keyword)) {
            return tag.replace('#', '')
          }
        }
      }
    }
    
    // 3. 제목에서 대학교 이름 찾기
    const titleMatch = doc.title.match(/([가-힣]+대학교?)/)?.[1]
    if (titleMatch) return titleMatch
    
    // 4. 파일명에서 대학교 이름 찾기
    const fileMatch = doc.fileName.match(/([가-힣]+대학교?)/)?.[1]
    if (fileMatch) return fileMatch
    
    return '미분류'
  }

  // 학교별 문서 그룹화
  const documentsBySchool = useMemo(() => {
    const grouped: Record<string, Document[]> = {}
    documents.forEach((doc) => {
      const school = extractSchoolName(doc)
      if (!grouped[school]) {
        grouped[school] = []
      }
      grouped[school].push(doc)
    })
    return grouped
  }, [documents])

  // 학교 목록 정렬 (미분류는 맨 뒤로)
  const schools = Object.keys(documentsBySchool).sort((a, b) => {
    if (a === '미분류') return 1
    if (b === '미분류') return -1
    return a.localeCompare(b, 'ko')
  })

  useEffect(() => {
    loadDocuments()
  }, [])

  const loadDocuments = async () => {
    try {
      const docs = await getDocuments()
      setDocuments(docs)
    } catch (error) {
      console.error('문서 목록 로드 오류:', error)
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const items = e.dataTransfer?.items
    if (!items) return
    const pathToFiles: Record<string, File[]> = {}
    const readEntries = async (reader: FileSystemDirectoryReader, prefix: string): Promise<void> => {
      const entries = await new Promise<FileSystemEntry[]>((res, rej) =>
        reader.readEntries(res, rej)
      )
      for (const entry of entries) {
        if (entry.isDirectory) {
          const dirReader = (entry as FileSystemDirectoryEntry).createReader()
          await readEntries(dirReader, prefix ? `${prefix}/${entry.name}` : entry.name)
        } else if (entry.isFile) {
          const file = await new Promise<File>((res, rej) =>
            (entry as FileSystemFileEntry).file(res, rej)
          )
          if (file.type === 'application/pdf') {
            const relPath = prefix ? `${prefix}/${entry.name}` : entry.name
            ;(file as File & { webkitRelativePath?: string }).webkitRelativePath = relPath
            const parts = relPath.split('/').filter(Boolean)
            const school = parts.length > 1 ? parts[parts.length - 2] : '미지정'
            if (!pathToFiles[school]) pathToFiles[school] = []
            pathToFiles[school].push(file)
          }
        }
      }
    }
    for (let i = 0; i < items.length; i++) {
      const entry = items[i].webkitGetAsEntry()
      if (entry?.isDirectory) {
        const reader = (entry as FileSystemDirectoryEntry).createReader()
        await readEntries(reader, entry.name)
      } else if (entry?.isFile) {
        const file = items[i].getAsFile()
        if (file?.type === 'application/pdf') {
          if (!pathToFiles['미지정']) pathToFiles['미지정'] = []
          pathToFiles['미지정'].push(file)
        }
      }
    }
    const files = Object.values(pathToFiles).flat()
    if (files.length === 0) {
      alert('PDF 파일 또는 PDF가 포함된 폴더를 선택해주세요.')
      return
    }
    setSchoolFiles((prev) => {
      const merged = { ...prev }
      for (const [school, flist] of Object.entries(pathToFiles)) {
        merged[school] = [...(merged[school] || []), ...flist]
      }
      return merged
    })
  }

  const handleFolderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files
    if (!selected || selected.length === 0) return
    const files = Array.from(selected).filter((f) => f.type === 'application/pdf')
    if (files.length === 0) {
      alert('선택한 폴더에 PDF 파일이 없습니다.')
      return
    }
    const grouped = groupFilesBySchool(files)
    setSchoolFiles((prev) => ({ ...prev, ...grouped }))
    e.target.value = ''
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files
    if (!selected || selected.length === 0) return
    const files = Array.from(selected).filter((f) => f.type === 'application/pdf')
    if (files.length === 0) {
      alert('PDF 파일만 선택할 수 있습니다.')
      e.target.value = ''
      return
    }
    setPendingFiles(files)
    setPendingSchoolName('')
    e.target.value = ''
  }

  const addPendingFilesToSchool = () => {
    const school = pendingSchoolName.trim()
    if (!school) {
      alert('학교명을 입력해주세요.')
      return
    }
    if (pendingFiles.length === 0) return
    setSchoolFiles((prev) => ({
      ...prev,
      [school]: [...(prev[school] || []), ...pendingFiles]
    }))
    setPendingFiles([])
    setPendingSchoolName('')
  }

  const cancelPendingFiles = () => {
    setPendingFiles([])
    setPendingSchoolName('')
  }

  const updateSchoolName = (oldName: string, newName: string) => {
    const trimmed = newName.trim()
    if (!trimmed || oldName === trimmed) return
    setSchoolFiles((prev) => {
      const next = { ...prev }
      const files = next[oldName] || []
      next[trimmed] = [...(next[trimmed] || []), ...files]
      delete next[oldName]
      return next
    })
  }

  const removeSchool = (school: string) => {
    setSchoolFiles((prev) => {
      const next = { ...prev }
      delete next[school]
      return next
    })
  }

  const totalFiles = Object.values(schoolFiles).flat().length

  const handleUpload = async () => {
    if (totalFiles === 0) {
      alert('파일 또는 폴더를 선택해주세요.')
      return
    }
    if (schoolFiles['미지정']?.length) {
      alert('학교명이 "미지정"인 항목이 있습니다. 카드에서 학교명을 입력·수정한 뒤 업로드해주세요.')
      return
    }

    setIsUploading(true)
    
    // 학교별 순서대로 태스크 생성 (학교명 가나다순)
    const sortedSchools = Object.keys(schoolFiles).sort((a, b) => a.localeCompare(b, 'ko'))
    const tasks: UploadTask[] = []
    for (const school of sortedSchools) {
      for (const file of schoolFiles[school]) {
        tasks.push({
          id: `${Date.now()}-${Math.random()}`,
          file,
          schoolName: school,
          status: 'waiting',
          progress: '대기 중...',
          logs: []
        })
      }
    }
    
    setUploadQueue(tasks)

    // 학교별로 순서대로 처리, 같은 학교 내 파일은 병렬 업로드
    const processSchoolFiles = async (school: string) => {
      const schoolTasks = tasks.filter((t) => t.schoolName === school)
      await Promise.all(
        schoolTasks.map(async (task) => {
          setUploadQueue((prev) =>
            prev.map((t) =>
              t.id === task.id
                ? {
                    ...t,
                    status: 'uploading',
                    progress: '업로드 중...',
                    logs: [
                      '📦 모델 초기화 중...',
                      `🏫 학교: ${task.schoolName}`,
                      `📄 파일: ${task.file.name}`
                    ]
                  }
                : t
            )
          )

          try {
            setUploadQueue((prev) =>
              prev.map((t) =>
                t.id === task.id ? { ...t, logs: [...t.logs, '📝 PDF → Markdown 변환 중...'] } : t
              )
            )

            const result = await uploadDocument(task.file, task.schoolName)

            setUploadQueue((prev) =>
              prev.map((t) =>
                t.id === task.id
                  ? {
                      ...t,
                      status: 'success',
                      progress: '완료',
                      logs: [
                        ...t.logs,
                        '✅ Markdown 변환 완료',
                        '📝 요약 + 출처 + 해시태그 추출 중...',
                        '✅ 메타데이터 추출 완료',
                        '🔢 임베딩 생성 중...',
                        '✅ 임베딩 생성 완료',
                        '📤 Supabase 저장 중...',
                        '✅ Supabase 저장 완료',
                        `🎉 처리 완료! (${result.stats.processingTime})`,
                        `   📄 ${result.stats.totalPages}페이지`,
                        `   📦 ${result.stats.chunksTotal}개 청크`
                      ],
                      result: {
                        totalPages: result.stats.totalPages,
                        chunksTotal: result.stats.chunksTotal,
                        processingTime: result.stats.processingTime
                      }
                    }
                  : t
              )
            )

            setUploadResults((prev) => [
              ...prev,
              {
                filename: task.file.name,
                schoolName: task.schoolName,
                status: '성공',
                pages: result.stats.totalPages,
                chunks: result.stats.chunksTotal,
                time: result.stats.processingTime
              }
            ])
          } catch (error: any) {
            const errorMessage = getUploadErrorMessage(error)
            setUploadQueue((prev) =>
              prev.map((t) =>
                t.id === task.id
                  ? {
                      ...t,
                      status: 'error',
                      progress: '실패',
                      logs: [...t.logs, `❌ 오류: ${errorMessage}`]
                    }
                  : t
              )
            )

            setUploadResults((prev) => [
              ...prev,
              {
                filename: task.file.name,
                schoolName: task.schoolName,
                status: '실패',
                pages: 0,
                chunks: 0,
                time: '-',
                errorMessage
              }
            ])
          }
        })
      )
    }

    for (const school of sortedSchools) {
      await processSchoolFiles(school)
    }

    setIsUploading(false)
    setSchoolFiles({})
    await loadDocuments()
  }

  const clearResults = () => {
    setUploadQueue([])
    setUploadResults([])
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

  // 통계 계산
  const stats = useMemo(() => {
    const total = uploadResults.length
    const success = uploadResults.filter((r) => r.status === '성공').length
    const failed = total - success
    const totalChunks = uploadResults.reduce((sum, r) => sum + r.chunks, 0)
    return { total, success, failed, totalChunks }
  }, [uploadResults])

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-purple-50 flex">
      {/* 사이드바 */}
      <aside className="w-80 bg-white border-r border-gray-200 p-6 flex flex-col">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-gray-900 mb-1">📤 PDF 업로드</h1>
          <p className="text-sm text-gray-600">문서를 처리하고 Supabase에 업로드</p>
        </div>

        <div className="border-t border-gray-200 my-4"></div>

        {/* 사용 방법 */}
        <div className="mb-6 p-4 bg-blue-50 rounded-lg">
          <p className="text-sm text-blue-800">
            💡 <strong>사용 방법</strong>
          </p>
          <ol className="text-sm text-blue-700 mt-2 space-y-1 list-decimal list-inside">
            <li><strong>파일 선택</strong>: PDF 선택 후 학교명 직접 입력</li>
            <li><strong>폴더 선택</strong>: 학교폴더/파일.pdf (폴더명=학교명)</li>
            <li>드래그도 가능 (파일 → 미지정, 폴더 → 폴더명=학교명)</li>
            <li>학교명 수정 후 업로드</li>
          </ol>
        </div>

        {/* 결과 초기화 */}
        {uploadResults.length > 0 && (
          <button
            onClick={clearResults}
            className="w-full py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors text-sm"
          >
            🗑️ 결과 초기화
          </button>
        )}

        <div className="border-t border-gray-200 my-4"></div>

        {/* 학교별 문서 요약 */}
        <div className="flex-1 overflow-y-auto">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">📂 업로드된 문서</h2>
          <button
            onClick={loadDocuments}
            className="w-full mb-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm"
          >
            🔄 새로고침
          </button>
          
          {schools.length === 0 ? (
            <p className="text-sm text-gray-500">업로드된 문서가 없습니다.</p>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 mb-2">
                총 {schools.length}개 학교, {documents.length}개 문서
              </p>
              {schools.map((school) => (
                <div
                  key={school}
                  className="p-3 bg-gray-50 rounded-lg cursor-pointer hover:bg-gray-100 transition-colors"
                  onClick={() => {
                    setSelectedSchool(school)
                    setActiveTab('documents')
                  }}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-700">
                      🏫 {school}
                    </span>
                    <span className="text-xs text-gray-500">
                      {documentsBySchool[school].length}개
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 네비게이션 */}
        <div className="border-t border-gray-200 pt-4 mt-4 space-y-2">
          <button
            onClick={() => navigate('/chat/admin')}
            className="w-full py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm"
          >
            📚 관리자 페이지
          </button>
          <button
            onClick={() => navigate('/')}
            className="w-full py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm"
          >
            💬 채팅으로
          </button>
        </div>
      </aside>

      {/* 메인 콘텐츠 */}
      <main className="flex-1 p-8 overflow-y-auto">
        {/* 탭 */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab('upload')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === 'upload'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            📤 업로드
          </button>
          <button
            onClick={() => setActiveTab('documents')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === 'documents'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            📂 문서 목록
          </button>
        </div>

        {activeTab === 'upload' ? (
          <div className="space-y-6">
            {/* 선택한 파일 → 학교명 입력 */}
            {pendingFiles.length > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-amber-800 mb-3">📄 선택한 파일에 학교명 입력</h3>
                <p className="text-xs text-amber-700 mb-3">{pendingFiles.length}개 PDF: {pendingFiles.map(f => f.name).join(', ').slice(0, 60)}{pendingFiles.length > 1 ? '…' : ''}</p>
                <div className="flex flex-wrap items-center gap-2">
                  <input
                    type="text"
                    value={pendingSchoolName}
                    onChange={(e) => setPendingSchoolName(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && addPendingFilesToSchool()}
                    placeholder="예: 연세대학교, 고려대학교"
                    className="px-3 py-2 border border-amber-300 rounded-lg text-sm w-56"
                    autoFocus
                  />
                  <button
                    onClick={addPendingFilesToSchool}
                    className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700"
                  >
                    추가
                  </button>
                  <button
                    onClick={cancelPendingFiles}
                    className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg text-sm hover:bg-gray-300"
                  >
                    취소
                  </button>
                </div>
              </div>
            )}

            {/* 업로드 영역 */}
            <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
              <h2 className="text-xl font-bold text-gray-900 mb-6">📤 파일 또는 폴더 업로드 (학교명 직접 입력 가능)</h2>

              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 mb-6 text-center transition-all ${
                  isDragging
                    ? 'border-blue-500 bg-blue-50'
                    : totalFiles > 0
                    ? 'border-green-500 bg-green-50'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
              >
                {totalFiles > 0 ? (
                  <div>
                    <div className="text-6xl mb-2">✅</div>
                    <p className="text-lg font-semibold text-green-700 mb-3">
                      {Object.keys(schoolFiles).length}개 학교, {totalFiles}개 파일
                    </p>
                    <div className="flex flex-wrap justify-center gap-2">
                      <label className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 transition-colors">
                        + 파일 추가
                        <input
                          type="file"
                          accept=".pdf,application/pdf"
                          multiple
                          onChange={handleFileChange}
                          className="hidden"
                        />
                      </label>
                      <label className="inline-block px-4 py-2 bg-indigo-600 text-white rounded-lg cursor-pointer hover:bg-indigo-700 transition-colors">
                        + 폴더 추가
                        <input
                          type="file"
                          {...({ webkitdirectory: '' } as React.InputHTMLAttributes<HTMLInputElement>)}
                          multiple
                          onChange={handleFolderChange}
                          className="hidden"
                        />
                      </label>
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="text-6xl mb-2">📤</div>
                    <p className="text-lg font-semibold text-gray-700 mb-2">
                      파일 또는 폴더를 드래그하거나 아래에서 선택
                    </p>
                    <p className="text-sm text-gray-500 mb-4">
                      파일 선택 시 학교명을 직접 입력하고, 폴더 선택 시 폴더명이 학교명으로 사용됩니다.
                    </p>
                    <div className="flex flex-wrap justify-center gap-3">
                      <label className="inline-block px-5 py-2.5 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 transition-colors font-medium">
                        📄 파일 선택
                        <input
                          type="file"
                          accept=".pdf,application/pdf"
                          multiple
                          onChange={handleFileChange}
                          className="hidden"
                        />
                      </label>
                      <label className="inline-block px-5 py-2.5 bg-indigo-600 text-white rounded-lg cursor-pointer hover:bg-indigo-700 transition-colors font-medium">
                        📁 폴더 선택
                        <input
                          type="file"
                          {...({ webkitdirectory: '' } as React.InputHTMLAttributes<HTMLInputElement>)}
                          multiple
                          onChange={handleFolderChange}
                          className="hidden"
                        />
                      </label>
                    </div>
                  </div>
                )}
              </div>

              {/* 학교별 파일 목록 (학교명 편집 가능) */}
              {Object.keys(schoolFiles).length > 0 && (
                <div className="mb-6 space-y-4">
                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                    <h3 className="text-sm font-semibold text-blue-900 mb-2">⚠️ 중요: 학교명 확인</h3>
                    <p className="text-xs text-blue-800">
                      각 학교명을 클릭하여 정확한 학교명으로 수정해주세요. 
                      <br />
                      예: "연세대" → "연세대학교", "고려대" → "고려대학교"
                      <br />
                      정확한 학교명이 저장되어야 채팅에서 자료를 검색할 수 있습니다.
                    </p>
                  </div>
                  <h3 className="text-sm font-semibold text-gray-700">🏫 학교별 파일 (클릭하여 학교명 수정)</h3>
                  {Object.entries(schoolFiles)
                    .sort(([a], [b]) => a.localeCompare(b, 'ko'))
                    .map(([school, flist]) => (
                      <SchoolFolderCard
                        key={school}
                        school={school}
                        files={flist}
                        onRename={(newName) => updateSchoolName(school, newName)}
                        onRemove={() => removeSchool(school)}
                      />
                    ))}
                </div>
              )}

              {/* 업로드 버튼 */}
              <button
                onClick={handleUpload}
                disabled={isUploading || totalFiles === 0}
                className="w-full py-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed transition-all transform hover:scale-[1.02] shadow-lg"
              >
                {isUploading ? '⏳ 처리 중...' : `🚀 학교별 병렬 업로드 (${totalFiles}개)`}
              </button>
            </div>

            {/* 업로드 로그 */}
            {uploadQueue.length > 0 && (
              <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
                <div className="flex justify-between items-center mb-4">
                  <h2 className="text-xl font-bold text-gray-900">📊 업로드 진행 상황</h2>
                  <span className="text-sm text-gray-600">
                    {uploadQueue.filter((t) => t.status === 'success').length}/{uploadQueue.length} 완료
                  </span>
                </div>

                <div className="space-y-4 max-h-96 overflow-y-auto">
                  {uploadQueue.map((task, index) => (
                    <div
                      key={task.id}
                      className={`p-4 rounded-lg border-2 ${
                        task.status === 'waiting'
                          ? 'bg-gray-50 border-gray-200'
                          : task.status === 'uploading'
                          ? 'bg-blue-50 border-blue-300'
                          : task.status === 'success'
                          ? 'bg-green-50 border-green-300'
                          : 'bg-red-50 border-red-300'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-semibold text-gray-900">
                          [{index + 1}/{uploadQueue.length}] {task.file.name}
                        </p>
                        <span
                          className={`text-xs font-semibold px-3 py-1 rounded-full ${
                            task.status === 'waiting'
                              ? 'bg-gray-200 text-gray-700'
                              : task.status === 'uploading'
                              ? 'bg-blue-200 text-blue-700'
                              : task.status === 'success'
                              ? 'bg-green-200 text-green-700'
                              : 'bg-red-200 text-red-700'
                          }`}
                        >
                          {task.progress}
                        </span>
                      </div>
                      {task.logs.length > 0 && (
                        <div className="bg-gray-900 rounded-lg p-3 font-mono text-xs max-h-40 overflow-y-auto">
                          {task.logs.map((log, idx) => (
                            <p
                              key={idx}
                              className={log.startsWith('❌') ? 'text-red-400 font-semibold' : 'text-green-400'}
                            >
                              {log}
                            </p>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 업로드 결과 요약 */}
            {uploadResults.length > 0 && (
              <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
                <h2 className="text-xl font-bold text-gray-900 mb-4">📊 업로드 결과 요약</h2>

                {/* 통계 */}
                <div className="grid grid-cols-4 gap-4 mb-6">
                  <div className="bg-gray-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
                    <p className="text-sm text-gray-600">총 파일 수</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-green-600">{stats.success}</p>
                    <p className="text-sm text-gray-600">성공</p>
                  </div>
                  <div className="bg-red-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
                    <p className="text-sm text-gray-600">실패</p>
                  </div>
                  <div className="bg-blue-50 rounded-lg p-4 text-center">
                    <p className="text-2xl font-bold text-blue-600">{stats.totalChunks}</p>
                    <p className="text-sm text-gray-600">총 청크 수</p>
                  </div>
                </div>

                {/* 결과 테이블 */}
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="bg-gray-100">
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">파일명</th>
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">학교</th>
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">상태</th>
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">페이지</th>
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">청크</th>
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">소요시간</th>
                        <th className="px-4 py-2 text-left text-sm font-semibold text-gray-700">오류 사유</th>
                      </tr>
                    </thead>
                    <tbody>
                      {uploadResults.map((result, index) => (
                        <tr key={index} className="border-b border-gray-200">
                          <td className="px-4 py-3 text-sm text-gray-900">{result.filename}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{result.schoolName}</td>
                          <td className="px-4 py-3">
                            <span
                              className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                result.status === '성공'
                                  ? 'bg-green-100 text-green-700'
                                  : 'bg-red-100 text-red-700'
                              }`}
                            >
                              {result.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600">{result.pages}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{result.chunks}</td>
                          <td className="px-4 py-3 text-sm text-gray-600">{result.time}</td>
                          <td className="px-4 py-3 text-sm text-red-600 max-w-md">
                            {result.status === '실패' && result.errorMessage ? result.errorMessage : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : (
          /* 문서 목록 탭 */
          <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">📂 학교별 문서 목록</h2>
              <button
                onClick={loadDocuments}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors text-sm"
              >
                🔄 새로고침
              </button>
            </div>

            {schools.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <p className="text-lg">📭 업로드된 문서가 없습니다.</p>
              </div>
            ) : (
              <div>
                {/* 학교 통계 */}
                <p className="text-sm text-gray-600 mb-4">
                  🏫 {schools.length}개 학교 | 📄 {documents.length}개 문서
                </p>

                {/* 학교 폴더 그리드 */}
                <div className="grid grid-cols-4 gap-4 mb-6">
                  {schools.map((school) => (
                    <button
                      key={school}
                      onClick={() => setSelectedSchool(selectedSchool === school ? null : school)}
                      className={`p-4 rounded-lg border-2 text-left transition-all ${
                        selectedSchool === school
                          ? 'bg-blue-50 border-blue-500'
                          : 'bg-gray-50 border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="text-2xl mb-1">📁</div>
                      <p className="text-sm font-semibold text-gray-900 truncate">{school}</p>
                      <p className="text-xs text-gray-500">{documentsBySchool[school].length}개 문서</p>
                    </button>
                  ))}
                </div>

                {/* 선택된 학교의 문서 목록 */}
                {selectedSchool && documentsBySchool[selectedSchool] && (
                  <div className="border-t border-gray-200 pt-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold text-gray-900">
                        📂 {selectedSchool}
                      </h3>
                      <button
                        onClick={() => setSelectedSchool(null)}
                        className="text-sm text-gray-500 hover:text-gray-700"
                      >
                        ✕ 닫기
                      </button>
                    </div>

                    <div className="space-y-3">
                      {documentsBySchool[selectedSchool].map((doc, index) => (
                        <div
                          key={doc.id}
                          className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                        >
                          <div className="flex-1">
                            <p className="text-sm font-semibold text-gray-900">
                              {index + 1}. {doc.title}
                            </p>
                            <p className="text-xs text-gray-500">
                              {doc.fileName} | {new Date(doc.uploadedAt).toLocaleDateString('ko-KR')}
                            </p>
                            {doc.hashtags && doc.hashtags.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1">
                                {doc.hashtags.map((tag) => (
                                  <span
                                    key={tag}
                                    className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full"
                                  >
                                    {tag}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                          <div className="flex gap-2">
                            {doc.fileUrl && (
                              <a
                                href={doc.fileUrl}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="px-3 py-1 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors text-sm"
                              >
                                📥
                              </a>
                            )}
                            <button
                              onClick={() => handleDelete(doc.id)}
                              className="px-3 py-1 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors text-sm"
                            >
                              🗑️
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
