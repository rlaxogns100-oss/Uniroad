import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadDocument, getDocuments, deleteDocument, Document } from '../api/client'

interface UploadTask {
  id: string
  file: File
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
}

export default function AdminUploadPage() {
  const navigate = useNavigate()
  
  // 설정
  const [schoolName, setSchoolName] = useState('고려대학교')
  
  // 파일 업로드
  const [files, setFiles] = useState<File[]>([])
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

    if (!schoolName.trim()) {
      alert('학교 이름을 입력해주세요.')
      return
    }

    setIsUploading(true)
    
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
            ? { 
                ...t, 
                status: 'uploading', 
                progress: '업로드 중...', 
                logs: [
                  '📦 모델 초기화 중...',
                  `🏫 학교: ${schoolName}`,
                  `📄 파일: ${task.file.name}`
                ] 
              }
            : t
        )
      )

      try {
        // PDF 처리 시작 로그
        setUploadQueue((prev) =>
          prev.map((t) =>
            t.id === task.id
              ? { 
                  ...t, 
                  logs: [
                    ...t.logs,
                    '📝 PDF → Markdown 변환 중...'
                  ] 
                }
              : t
          )
        )

        // 실제 업로드
        const result = await uploadDocument(task.file, schoolName)
        
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

        // 결과 추가
        setUploadResults((prev) => [
          ...prev,
          {
            filename: task.file.name,
            schoolName,
            status: '성공',
            pages: result.stats.totalPages,
            chunks: result.stats.chunksTotal,
            time: result.stats.processingTime
          }
        ])
      } catch (error: any) {
        // 상태 업데이트: error
        setUploadQueue((prev) =>
          prev.map((t) =>
            t.id === task.id
              ? {
                  ...t,
                  status: 'error',
                  progress: '실패',
                  logs: [
                    ...t.logs,
                    `❌ 오류: ${error.response?.data?.detail || error.message}`
                  ]
                }
              : t
          )
        )

        // 결과 추가
        setUploadResults((prev) => [
          ...prev,
          {
            filename: task.file.name,
            schoolName,
            status: '실패',
            pages: 0,
            chunks: 0,
            time: '-'
          }
        ])
      }
    }

    // 완료 후 정리
    setIsUploading(false)
    setFiles([])
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

        {/* 설정 */}
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">⚙️ 설정</h2>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              🏫 학교 이름
            </label>
            <input
              type="text"
              value={schoolName}
              onChange={(e) => setSchoolName(e.target.value)}
              placeholder="예: 고려대학교, 서울대학교"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="border-t border-gray-200 my-4"></div>

        {/* 사용 방법 */}
        <div className="mb-6 p-4 bg-blue-50 rounded-lg">
          <p className="text-sm text-blue-800">
            💡 <strong>사용 방법</strong>
          </p>
          <ol className="text-sm text-blue-700 mt-2 space-y-1 list-decimal list-inside">
            <li>PDF 파일을 업로드</li>
            <li>학교 이름 입력</li>
            <li>업로드 버튼 클릭</li>
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
            onClick={() => navigate('/admin')}
            className="w-full py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors text-sm"
          >
            📚 문서 관리 페이지
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
            {/* 업로드 영역 */}
            <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
              <h2 className="text-xl font-bold text-gray-900 mb-6">📄 PDF 파일 선택</h2>

              {/* 파일 드래그 앤 드롭 */}
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`border-2 border-dashed rounded-xl p-8 mb-6 text-center transition-all ${
                  isDragging
                    ? 'border-blue-500 bg-blue-50'
                    : files.length > 0
                    ? 'border-green-500 bg-green-50'
                    : 'border-gray-300 hover:border-gray-400'
                }`}
              >
                {files.length > 0 ? (
                  <div>
                    <div className="text-6xl mb-2">✅</div>
                    <p className="text-lg font-semibold text-green-700 mb-3">
                      {files.length}개 파일 선택됨
                    </p>
                    <div className="max-h-40 overflow-y-auto space-y-2 mb-3">
                      {files.map((file, index) => (
                        <div
                          key={index}
                          className="flex items-center justify-between bg-white px-3 py-2 rounded-lg"
                        >
                          <div className="flex-1 text-left">
                            <p className="text-sm font-medium text-gray-700">{file.name}</p>
                            <p className="text-xs text-gray-500">
                              {(file.size / 1024 / 1024).toFixed(2)}MB
                            </p>
                          </div>
                          <button
                            onClick={() => removeFile(index)}
                            className="ml-2 text-red-600 hover:text-red-700 font-bold"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                    <label className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 transition-colors">
                      + 파일 추가
                      <input
                        type="file"
                        accept="application/pdf"
                        multiple
                        onChange={handleFileChange}
                        className="hidden"
                      />
                    </label>
                  </div>
                ) : (
                  <div>
                    <div className="text-6xl mb-2">📄</div>
                    <p className="text-lg font-semibold text-gray-700 mb-2">
                      PDF 파일을 드래그하거나 클릭하여 선택 (여러 개 가능)
                    </p>
                    <label className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg cursor-pointer hover:bg-blue-700 transition-colors">
                      파일 선택
                      <input
                        type="file"
                        accept="application/pdf"
                        multiple
                        onChange={handleFileChange}
                        className="hidden"
                      />
                    </label>
                  </div>
                )}
              </div>

              {/* 선택된 학교 표시 */}
              {schoolName && (
                <div className="mb-6 p-4 bg-indigo-50 border border-indigo-200 rounded-lg">
                  <p className="text-sm text-indigo-800">
                    🏫 <strong>학교:</strong> {schoolName}
                  </p>
                </div>
              )}

              {/* 업로드 버튼 */}
              <button
                onClick={handleUpload}
                disabled={isUploading || files.length === 0 || !schoolName.trim()}
                className="w-full py-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg font-semibold hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed transition-all transform hover:scale-[1.02] shadow-lg"
              >
                {isUploading ? '⏳ 처리 중...' : `🚀 순차 업로드 시작 (${files.length}개)`}
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
                            <p key={idx} className="text-green-400">
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
