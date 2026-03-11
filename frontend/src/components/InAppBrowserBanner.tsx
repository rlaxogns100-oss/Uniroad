import { useState, useCallback } from 'react'
import { isInAppBrowser } from '../config'

export default function InAppBrowserBanner() {
  const [dismissed, setDismissed] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopyUrl = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(window.location.href)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      const input = document.createElement('input')
      input.value = window.location.href
      document.body.appendChild(input)
      input.select()
      document.execCommand('copy')
      document.body.removeChild(input)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }, [])

  if (!isInAppBrowser() || dismissed) return null

  const isIOS = /iPhone|iPad|iPod/i.test(navigator.userAgent)

  return (
    <div className="fixed inset-x-0 top-0 z-[10000] safe-area-top">
      <div className="mx-auto max-w-lg bg-amber-50 border-b border-amber-200 px-4 py-3 shadow-sm">
        <div className="flex items-start gap-2.5">
          <span className="mt-0.5 text-base leading-none">⚠️</span>
          <div className="flex-1 min-w-0">
            <p className="text-[13px] font-semibold text-amber-900 leading-5">
              인앱 브라우저에서는 PDF 다운로드 등 일부 기능이 제한됩니다.
            </p>
            <p className="mt-1 text-[12px] text-amber-700 leading-4">
              {isIOS
                ? '우측 하단 Safari 아이콘(나침반)을 눌러 Safari에서 열어주세요.'
                : '우측 상단 ⋮ 메뉴 → "외부 브라우저에서 열기"를 눌러주세요.'}
            </p>
            <button
              type="button"
              onClick={handleCopyUrl}
              className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-[12px] font-bold text-white shadow-sm active:scale-[0.97] transition"
            >
              {copied ? '복사 완료!' : 'URL 복사하기'}
            </button>
          </div>
          <button
            type="button"
            onClick={() => setDismissed(true)}
            className="flex-shrink-0 -mr-1 -mt-1 flex h-7 w-7 items-center justify-center rounded-full text-amber-400 hover:text-amber-600 transition"
            aria-label="닫기"
          >
            <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
