import React, { useEffect, useRef, useState } from 'react'

interface ChatToolsMenuProps {
  disabled?: boolean
  compact?: boolean
  onSelectSchoolRecordAnalysis: () => void
}

export default function ChatToolsMenu({
  disabled = false,
  compact = false,
  onSelectSchoolRecordAnalysis,
}: ChatToolsMenuProps) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  const buttonClasses = compact
    ? 'px-2.5 py-1 text-xs'
    : 'px-3.5 py-1.5 text-sm'

  const iconClasses = compact ? 'w-4 h-4' : 'w-4 h-4'

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className={[
          'inline-flex items-center gap-1.5 rounded-full bg-white text-gray-700 border border-gray-200',
          'border border-gray-200 hover:bg-gray-50 active:bg-gray-100 transition-colors',
          buttonClasses,
          disabled ? 'opacity-50 cursor-not-allowed' : '',
        ].join(' ')}
        title="도구"
      >
        <svg className={iconClasses} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 6v0M16 12v0M10 18v0" />
        </svg>
        <span className="font-medium">도구</span>
        <svg className={compact ? 'w-3.5 h-3.5 text-gray-400' : 'w-4 h-4 text-gray-400'} fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute bottom-11 left-0 z-50 min-w-[220px] overflow-hidden rounded-2xl border border-gray-200 bg-white">
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              onSelectSchoolRecordAnalysis()
            }}
            className="w-full px-4 py-3 text-left hover:bg-gray-50 active:bg-gray-100 transition-colors flex items-center gap-3"
          >
            <svg className="w-5 h-5 text-uniroad-navy" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span className="text-sm font-semibold text-gray-800">생기부 분석하기</span>
          </button>
        </div>
      )}
    </div>
  )
}
