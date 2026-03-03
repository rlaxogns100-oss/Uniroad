import React from 'react'
import type { MajorCategory, StepKey } from '../data/bestPractices'
import { getDefaultPractice, getRepresentativePractice } from '../data/bestPractices'

const STEP_LABELS: Record<StepKey, string> = {
  계기: '계기(동기)',
  심화: '심화(탐구)',
  역량: '역량(결과)',
  변화: '변화(성장)',
}

const STEP_STYLES: Record<StepKey, string> = {
  계기: 'bg-amber-100 text-amber-900',
  심화: 'bg-sky-100 text-sky-900',
  역량: 'bg-emerald-100 text-emerald-900',
  변화: 'bg-violet-100 text-violet-900',
}

/** content에서 stepHighlights 기준으로 4단계 구간 하이라이트 렌더링 */
function renderContentWithStepHighlights(
  content: string,
  stepHighlights?: { step: StepKey; quote: string }[]
): React.ReactNode {
  if (!stepHighlights || stepHighlights.length === 0) {
    return content
  }
  const indices: { start: number; end: number; step: StepKey }[] = []
  for (const { step, quote } of stepHighlights) {
    const start = content.indexOf(quote)
    if (start === -1) continue
    indices.push({ start, end: start + quote.length, step })
  }
  indices.sort((a, b) => a.start - b.start)
  const nonOverlapping: typeof indices = []
  for (const seg of indices) {
    const overlaps = nonOverlapping.some((s) => seg.start < s.end && seg.end > s.start)
    if (!overlaps) nonOverlapping.push(seg)
  }
  if (nonOverlapping.length === 0) return content

  const parts: React.ReactNode[] = []
  let last = 0
  nonOverlapping.forEach(({ start, end, step }) => {
    if (start > last) parts.push(<span key={`t-${last}`}>{content.slice(last, start)}</span>)
    parts.push(
      <span key={`h-${start}`} className={`rounded px-0.5 ${STEP_STYLES[step]}`} title={STEP_LABELS[step]}>
        {content.slice(start, end)}
      </span>
    )
    last = end
  })
  if (last < content.length) parts.push(<span key={`t-${last}`}>{content.slice(last)}</span>)
  return <>{parts}</>
}

export type BestPracticeCardProps = {
  /** 전공 계열. 없으면 기본 추천 사례(경영·경제 등) 표시 */
  majorCategory?: MajorCategory | string | null
}

export function BestPracticeCard({ majorCategory }: BestPracticeCardProps) {
  const practice = majorCategory
    ? getRepresentativePractice(majorCategory)
    : getDefaultPractice()
  const displayPractice = practice ?? getDefaultPractice()
  const hasStepHighlights = (displayPractice.stepHighlights?.length ?? 0) > 0

  return (
    <div className="rounded-xl bg-slate-50/80 overflow-hidden border border-gray-200/80">
      {/* Header — 원문 영역과 동일한 톤 */}
      <div className="px-6 pt-5 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">🏆</span>
          <div>
            <h5 className="font-sans font-bold text-gray-800 text-sm">
              {displayPractice.category} S등급 합격자 표준
            </h5>
            <p className="text-xs text-gray-500 mt-0.5">입학사정관이 주목하는 포인트</p>
          </div>
        </div>
      </div>

      {/* Content Body — 4단계 하이라이트 적용 */}
      <div className="px-6 pb-4">
        <p className="leading-relaxed text-sm text-gray-700 whitespace-pre-wrap font-sans">
          {hasStepHighlights
            ? renderContentWithStepHighlights(displayPractice.content, displayPractice.stepHighlights)
            : displayPractice.content}
        </p>
        {hasStepHighlights && (
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-gray-500 font-sans">
            <span className="font-medium text-gray-600">4단계:</span>
            {(['계기', '심화', '역량', '변화'] as StepKey[]).map((step) => (
              <span key={step} className={`inline-flex items-center gap-1 ${STEP_STYLES[step]} rounded px-1.5 py-0.5`}>
                {STEP_LABELS[step]}
              </span>
            ))}
          </div>
        )}
        <p className="mt-3 text-xs text-gray-500 font-sans">
          과목: {displayPractice.subject} · 도서: {displayPractice.book}
        </p>
      </div>

      {/* Key Point — 같은 글꼴·색상 */}
      <div className="border-t border-gray-200/80 bg-white/50 px-6 py-3 rounded-b-xl">
        <span className="inline-block px-2 py-0.5 rounded bg-emerald-100 text-emerald-700 font-bold text-xs mb-2">
          💡 합격 포인트
        </span>
        <p className="font-sans text-sm text-gray-700 leading-relaxed">{displayPractice.keyPoint}</p>
      </div>
    </div>
  )
}
