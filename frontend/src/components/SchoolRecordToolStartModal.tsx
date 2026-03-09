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
  title?: string
  description?: string
  statusText?: string
  scoreSets?: Array<{ id: string; name: string }>
  onSelectScoreSet?: (item: { id: string; name: string }) => void
  showNaesinOption?: boolean
  onSelectNaesin?: () => void
  showLinkRequiredHighlight?: boolean
  linkRequiredMessage?: string
  quickActions?: Array<{ id: string; title: string; description?: string }>
  onSelectQuickAction?: (id: string) => void
}

const ACTION_ICONS: Record<string, React.ReactNode> = {
  'next-activity': (
    <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  ),
  'core-weakness': (
    <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  ),
  'compare-winners': (
    <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    </svg>
  ),
}

const ACTION_COLORS: Record<string, { bg: string; text: string; ring: string; gradient: string }> = {
  'next-activity': {
    bg: 'bg-amber-50',
    text: 'text-amber-600',
    ring: 'ring-amber-200',
    gradient: 'from-amber-50 via-orange-50 to-yellow-50',
  },
  'core-weakness': {
    bg: 'bg-rose-50',
    text: 'text-rose-600',
    ring: 'ring-rose-200',
    gradient: 'from-rose-50 via-pink-50 to-fuchsia-50',
  },
  'compare-winners': {
    bg: 'bg-indigo-50',
    text: 'text-indigo-600',
    ring: 'ring-indigo-200',
    gradient: 'from-indigo-50 via-violet-50 to-purple-50',
  },
}

const DEFAULT_COLOR = {
  bg: 'bg-violet-50',
  text: 'text-violet-600',
  ring: 'ring-violet-200',
  gradient: 'from-violet-50 via-fuchsia-50 to-purple-50',
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
  showNaesinOption = false,
  onSelectNaesin,
  showLinkRequiredHighlight = false,
  linkRequiredMessage = '내신 성적과 모의고사 성적을 연동하세요.',
  quickActions,
  onSelectQuickAction,
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
  const showNaesin = showNaesinOption && onSelectNaesin
  const showOnlyLinkRequiredHighlight = showLinkRequiredHighlight && !showScoreList && !showNaesin
  const showQuickActions = linked === true && Array.isArray(quickActions) && quickActions.length > 0 && onSelectQuickAction

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px]" onClick={onClose} aria-hidden />

      <div
        className={`relative rounded-2xl bg-white shadow-2xl border border-gray-200 ${showQuickActions ? 'w-full max-w-3xl' : 'w-full max-w-2xl'}`}
        role="dialog"
        aria-modal="true"
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 z-10 p-2 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
          aria-label="닫기"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <div className="px-6 py-6 sm:px-8">
          {showQuickActions ? (
            <>
              <div className="mb-6 text-center">
                <h2 className="text-2xl font-extrabold tracking-[-0.03em] text-gray-900">
                  생기부 분석, 무엇을 해볼까요?
                </h2>
                <p className="mt-2 text-sm text-gray-500">
                  원하는 분석을 선택하면 바로 시작됩니다.
                </p>
              </div>

              <div className="grid grid-cols-3 gap-4">
                {quickActions!.map((action) => {
                  const colors = ACTION_COLORS[action.id] ?? DEFAULT_COLOR
                  const icon = ACTION_ICONS[action.id] ?? (
                    <svg className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M7 17L17 7M17 7H7M17 7V17" />
                    </svg>
                  )
                  return (
                    <button
                      key={action.id}
                      type="button"
                      onClick={() => onSelectQuickAction!(action.id)}
                      className={`group relative flex min-h-[200px] flex-col items-center justify-center gap-4 overflow-hidden rounded-2xl border bg-gradient-to-br ${colors.gradient} p-6 text-center shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_16px_40px_rgba(0,0,0,0.12)] active:scale-[0.98] border-gray-200 hover:border-gray-300`}
                    >
                      <div className={`flex h-16 w-16 items-center justify-center rounded-2xl ${colors.bg} ${colors.text} ring-1 ${colors.ring} transition-transform duration-200 group-hover:scale-110`}>
                        {icon}
                      </div>
                      <div>
                        <div className="text-lg font-extrabold leading-[1.2] tracking-[-0.02em] text-gray-900">
                          {action.title}
                        </div>
                        {action.description && (
                          <p className="mt-2 text-[13px] leading-5 text-gray-500 line-clamp-3">{action.description}</p>
                        )}
                      </div>
                    </button>
                  )
                })}
              </div>
            </>
          ) : (
            <>
              <h2 className="text-xl font-bold text-gray-900">{title}</h2>
              <p className="mt-3 text-sm text-gray-600 leading-relaxed">
                {description}
              </p>

              <div
                className={
                  showOnlyLinkRequiredHighlight
                    ? 'mt-4 text-sm text-gray-700'
                    : 'mt-4 rounded-xl bg-gray-50 border border-gray-200 px-4 py-3 text-sm text-gray-700'
                }
              >
                {showLinkRequiredHighlight && (
                  <div
                    className={
                      showOnlyLinkRequiredHighlight
                        ? 'rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800'
                        : 'mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-800'
                    }
                  >
                    {linkRequiredMessage}
                  </div>
                )}
                {showNaesin && (
                  <div className="space-y-1.5 mb-3">
                    <button
                      type="button"
                      onClick={onSelectNaesin}
                      className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-200/80 transition-colors font-medium text-gray-900"
                    >
                      내신 성적
                    </button>
                  </div>
                )}
                {showScoreList ? (
                  <div className={`space-y-1.5 overflow-y-auto ${showNaesin ? 'max-h-36' : 'max-h-48'}`}>
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
                ) : showOnlyLinkRequiredHighlight ? null : !showNaesin ? (
                  statusText
                ) : (
                  <p className="text-gray-600 text-xs mt-1">{statusText}</p>
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
            </>
          )}
        </div>
      </div>
    </div>
  )
}
