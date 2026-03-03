import { useState, useEffect } from 'react'

interface ShareModalProps {
  isOpen: boolean
  onClose: () => void
  userQuery: string
  assistantResponse: string
  sources?: string[]
  sourceUrls?: string[]
}

export default function ShareModal({
  isOpen,
  onClose,
  userQuery,
  assistantResponse,
  sources,
  sourceUrls,
}: ShareModalProps) {
  const [summary, setSummary] = useState<string>('')
  const [shareUrl, setShareUrl] = useState<string>('')
  const [isLoadingSummary, setIsLoadingSummary] = useState(false)
  const [isLoadingShare, setIsLoadingShare] = useState(false)
  const [copiedField, setCopiedField] = useState<string | null>(null)

  // 모달 열릴 때 링크 먼저 생성 → 완료 후 요약 생성
  useEffect(() => {
    if (isOpen && !shareUrl && !isLoadingShare) {
      generateShareUrlThenSummary()
    }
  }, [isOpen])

  // 링크 먼저 생성하고, 완료되면 요약 생성
  const generateShareUrlThenSummary = async () => {
    // 1. 링크 먼저 생성
    setIsLoadingShare(true)
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/share`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_query: userQuery,
          assistant_response: assistantResponse,
          sources: sources || [],
          source_urls: sourceUrls || [],
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setShareUrl(data.share_url)
      }
    } catch (error) {
      console.error('공유 URL 생성 실패:', error)
    } finally {
      setIsLoadingShare(false)
    }

    // 2. 링크 완료 후 요약 생성 시작
    if (!summary && !isLoadingSummary) {
      generateSummary()
    }
  }

  // 요약 생성
  const generateSummary = async () => {
    setIsLoadingSummary(true)
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL || ''}/api/share/summary`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_query: userQuery,
          assistant_response: assistantResponse,
        }),
      })

      if (response.ok) {
        const data = await response.json()
        setSummary(data.summary)
      } else {
        const errorData = await response.json().catch(() => ({}))
        console.error('요약 API 에러:', errorData)
        setSummary('요약을 생성할 수 없습니다.')
      }
    } catch (error) {
      console.error('요약 생성 실패:', error)
      setSummary('요약을 생성할 수 없습니다.')
    } finally {
      setIsLoadingSummary(false)
    }
  }

  // 복사 함수
  const copyToClipboard = async (text: string, field: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedField(field)
      setTimeout(() => setCopiedField(null), 2000)
    } catch (error) {
      console.error('복사 실패:', error)
    }
  }

  // 전체 복사 (요약 + 링크)
  const copyAll = () => {
    const fullText = `${summary}\n\n${shareUrl}`
    copyToClipboard(fullText, 'all')
  }

  // 요약만 복사
  const copySummary = () => {
    copyToClipboard(summary, 'summary')
  }

  // 링크만 복사
  const copyLink = () => {
    copyToClipboard(shareUrl, 'link')
  }

  // 모달 닫기 시 상태 초기화
  const handleClose = () => {
    setSummary('')
    setShareUrl('')
    setCopiedField(null)
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 배경 오버레이 */}
      <div 
        className="absolute inset-0 bg-black/50" 
        onClick={handleClose}
      />
      
      {/* 모달 컨텐츠 */}
      <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-md mx-4 overflow-hidden select-text">
        {/* 헤더 */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-gray-900">공유</h2>
            <button
              onClick={copyAll}
              disabled={isLoadingSummary || !summary || !shareUrl}
              className={`p-1.5 rounded-lg transition-colors ${
                copiedField === 'all'
                  ? 'text-green-600 bg-green-100'
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
              title="전체 복사"
            >
              {copiedField === 'all' ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
          </div>
          <button
            onClick={handleClose}
            className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 핵심 요약 섹션 (위에 표시) */}
        <div className="px-5 py-4 border-b border-gray-100">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-700">핵심 요약</h3>
            <button
              onClick={copySummary}
              disabled={isLoadingSummary || !summary || summary === '요약을 생성할 수 없습니다.'}
              className={`p-1.5 rounded-lg transition-colors ${
                copiedField === 'summary'
                  ? 'text-green-600 bg-green-100'
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
              title="요약 복사"
            >
              {copiedField === 'summary' ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
          </div>
          <div className="bg-gray-50 rounded-lg p-3 min-h-[80px]">
            {isLoadingSummary ? (
              <div className="flex items-center gap-2 text-gray-500">
                <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <span className="text-sm">핵심 내용 요약 중...</span>
              </div>
            ) : summary ? (
              <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{summary}</p>
            ) : (
              <div className="flex items-center gap-2 text-gray-400">
                <span className="text-sm">링크 생성 후 요약을 시작합니다...</span>
              </div>
            )}
          </div>
        </div>

        {/* 링크 섹션 (아래에 표시) */}
        <div className="px-5 py-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-gray-700">링크</h3>
            <button
              onClick={copyLink}
              disabled={!shareUrl}
              className={`p-1.5 rounded-lg transition-colors ${
                copiedField === 'link'
                  ? 'text-green-600 bg-green-100'
                  : 'text-gray-400 hover:text-gray-600 hover:bg-gray-100'
              } disabled:opacity-50 disabled:cursor-not-allowed`}
              title="링크 복사"
            >
              {copiedField === 'link' ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            {isLoadingShare ? (
              <div className="flex items-center gap-2 text-gray-500">
                <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
                <span className="text-sm">링크 생성 중...</span>
              </div>
            ) : shareUrl ? (
              <p className="text-sm text-blue-600 break-all">{shareUrl}</p>
            ) : (
              <p className="text-sm text-gray-400">링크 생성 실패</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
