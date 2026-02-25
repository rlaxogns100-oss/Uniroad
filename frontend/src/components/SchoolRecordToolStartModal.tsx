import React from 'react'

interface SchoolRecordToolStartModalProps {
  isOpen: boolean
  linked: boolean | null
  loading?: boolean
  dontAskAgain: boolean
  confirmLabel: string
  onToggleDontAskAgain: (value: boolean) => void
  onClose: () => void
  onConfirm: () => void
  /** 지정 시 제목/설명/상태문구를 덮어씀 (합격 예측 등 다른 플로우용) */
  title?: string
  description?: string
  statusText?: string
  /** 합격 예측용: 저장된 모의고사 성적 목록. 있으면 회색 영역에 목록 렌더 */
  scoreSets?: Array<{ id: string; name: string }>
  /** 성적 항목 클릭 시 (이름으로 채팅 자동완성 등) */
  onSelectScoreSet?: (item: { id: string; name: string }) => void
}

export default function SchoolRecordToolStartModal({
  isOpen,
  linked,
  loading = false,
  dontAskAgain,
  confirmLabel,
  onToggleDontAskAgain,
  onClose,
  onConfirm,
  title: titleOverride,
  description: descriptionOverride,
  statusText: statusTextOverride,
  scoreSets,
  onSelectScoreSet,
}: SchoolRecordToolStartModalProps) {
  if (!isOpen) return null

  const defaultStatusText = loading
    ? '생기부 연동 상태를 확인하는 중...'
    : linked
      ? '연동된 생기부를 읽어 새 채팅에서 더 정확하게 답합니다.'
      : '아직 연동된 생기부가 없어요. 먼저 연동이 필요해요.'

  const title = titleOverride ?? '생기부 분석을 시작하시겠습니까?'
  const description = descriptionOverride ?? '연동된 생기부를 읽어 새 채팅에서 더 정확하게 답합니다.'
  const statusText = statusTextOverride ?? defaultStatusText
  const showScoreList = Array.isArray(scoreSets) && scoreSets.length > 0 && onSelectScoreSet

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" onClick={onClose} aria-hidden />

      <div
        className="relative w-full max-w-2xl rounded-2xl bg-white shadow-2xl border border-gray-200"
        role="dialog"
        aria-modal="true"
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 p-2 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          aria-label="닫기"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="px-6 py-6 sm:px-8">
          <h2 className="text-xl font-bold text-gray-900">{title}</h2>
          <p className="mt-3 text-sm text-gray-600 leading-relaxed">
            {description}
          </p>

          <div className="mt-4 rounded-xl bg-gray-50 border border-gray-200 px-4 py-3 text-sm text-gray-700">
            {showScoreList ? (
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {scoreSets!.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onSelectScoreSet!(item)}
                    className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-200/80 transition-colors font-medium text-gray-900"
                  >
                    {item.name.replace(/^@/, '') || item.name}
                  </button>
                ))}
              </div>
            ) : (
              statusText
            )}
          </div>

          <div className="mt-6 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600">다시 묻지 않음</span>
              <button
                type="button"
                onClick={() => onToggleDontAskAgain(!dontAskAgain)}
                className={[
                  'relative inline-flex h-7 w-12 items-center rounded-full transition-colors',
                  dontAskAgain ? 'bg-blue-600' : 'bg-gray-300',
                ].join(' ')}
                aria-pressed={dontAskAgain}
              >
                <span
                  className={[
                    'inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform',
                    dontAskAgain ? 'translate-x-6' : 'translate-x-1',
                  ].join(' ')}
                />
              </button>
            </div>

            <button
              type="button"
              disabled={loading}
              onClick={onConfirm}
              className="px-5 py-2.5 rounded-xl bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 active:bg-blue-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
