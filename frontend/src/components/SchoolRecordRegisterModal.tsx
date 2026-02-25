import React, { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

export type RegisterMethod = 'doc_number' | 'file'

interface SchoolRecordRegisterModalProps {
  isOpen: boolean
  onClose: () => void
  onSave: (method: RegisterMethod, value: { docNumber?: string; file?: File }) => void
  isSaving?: boolean
}

export default function SchoolRecordRegisterModal({
  isOpen,
  onClose,
  onSave,
  isSaving = false,
}: SchoolRecordRegisterModalProps) {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleSave = () => {
    if (!file) return
    onSave('file', { file })
  }

  const canSave = !!file

  const handleOpenGuide = () => {
    navigate('/guide')
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-[2px] animate-fadeIn" onClick={onClose} aria-hidden />
      <div
        className="relative w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl animate-slideUp"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        <div className="h-1 w-full bg-[#0e6093]" />
        {/* 헤더 */}
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h2 id="modal-title" className="flex items-center gap-2 text-lg font-semibold text-[#0e6093] font-sans">
            <svg className="w-5 h-5 text-[#0e6093]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            학교생활기록부 등록
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg text-gray-500 hover:bg-[#0e6093]/10 hover:text-[#0e6093] transition-colors"
            aria-label="닫기"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="px-5 py-5 space-y-5">
          <p className="text-sm font-medium text-gray-900 font-sans">
            <span className="text-[#0e6093] bg-[#0e6093]/10 px-1.5 py-0.5 rounded font-semibold">PDF</span> 파일만 업로드할 수 있어요.
            <span className="ml-2 text-xs font-semibold text-[#0e6093] bg-[#0e6093]/10 px-2 py-0.5 rounded-full">PDF</span>
          </p>

          {/* PDF 파일 업로드 */}
          <div className="flex-1 min-w-0 rounded-xl border border-[#0e6093]/20 bg-[#0e6093]/5 p-4">
            <span className="text-sm font-semibold text-gray-900 font-sans">PDF 파일 업로드</span>
            <div className="mt-3 flex gap-2">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
              <input
                type="text"
                readOnly
                value={file ? file.name : 'PDF 파일을 선택해 주세요.'}
                placeholder="PDF 파일을 선택해 주세요."
                className={[
                  "flex-1 min-w-0 px-3 py-2.5 border rounded-lg text-sm font-sans",
                  "bg-white border-gray-200",
                  file ? "text-gray-900" : "text-gray-500",
                ].join(' ')}
              />
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="px-4 py-2.5 rounded-lg text-sm font-semibold text-white bg-[#0e6093] hover:bg-[#0b4f78] shadow-sm transition-colors font-sans whitespace-nowrap"
              >
                파일 찾기
              </button>
            </div>
            <p className="mt-2 text-[11px] text-gray-700 font-sans">
              <span className="font-semibold text-[#0e6093]">정부24</span>, <span className="font-semibold text-[#0e6093]">카카오톡 전자문서지갑</span>에서 받은{' '}
              <span className="font-semibold text-[#0e6093] bg-[#0e6093]/10 px-1 py-0.5 rounded">PDF</span>를 그대로 업로드할 수 있어요.
            </p>
          </div>

          {/* 안내 */}
          <div className="rounded-lg bg-[#0e6093]/5 border border-[#0e6093]/20 px-4 py-3 flex gap-3">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-[#0e6093] flex items-center justify-center text-white text-xs font-bold font-sans">i</span>
            <div className="text-sm text-gray-800 font-sans">
              <p>
                학교생활기록부는 <span className="font-semibold text-[#0e6093]">카카오톡</span>과 <span className="font-semibold text-[#0e6093]">네이버</span>를 통해 간편하게 업로드할 수 있습니다.
              </p>
              <button
                type="button"
                onClick={handleOpenGuide}
                className="mt-2 inline-flex items-center rounded-md bg-white px-2 py-1 text-[#0e6093] hover:bg-white/90 font-semibold transition-colors border border-[#0e6093]/20"
              >
                학교생활기록부 다운로드 안내를 차근차근 따라해보세요.
              </button>
            </div>
          </div>
        </div>

        {/* 저장 버튼 */}
        <div className="px-5 pb-6 flex justify-center">
          <button
            type="button"
            disabled={!canSave || isSaving}
            onClick={handleSave}
            className="w-full max-w-[200px] py-3 rounded-xl bg-[#0e6093] text-white text-sm font-semibold hover:bg-[#0b4f78] shadow-sm disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-sans"
          >
            {isSaving ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  )
}
