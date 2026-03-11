import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getApiBaseUrl } from '../config'
import { BestPracticeCard } from '../components/BestPracticeCard'
import { getMajorCategoryFromHopeMajor } from '../data/bestPractices'
import { captureBusinessEvent } from '../utils/tracking'
import { TrackingEventNames } from '../utils/trackingSchema'

interface EvalResult {
  success: boolean
  message?: string
  result?: {
    feedback?: string
    grade?: string
    benchmark?: string
    rewrite?: string
  }
  scores?: unknown
}

const CRITERIA_LABELS: Record<string, { label: string; bg: string; border: string; badge: string }> = {
  계기: {
    label: '계기(동기)',
    bg: 'bg-amber-50',
    border: 'border-l-4 border-amber-500',
    badge: 'bg-amber-100 text-amber-800',
  },
  심화: {
    label: '심화(독서/탐구)',
    bg: 'bg-sky-50',
    border: 'border-l-4 border-sky-500',
    badge: 'bg-sky-100 text-sky-800',
  },
  역량: {
    label: '역량(결과)',
    bg: 'bg-emerald-50',
    border: 'border-l-4 border-emerald-500',
    badge: 'bg-emerald-100 text-emerald-800',
  },
  변화: {
    label: '변화(성장)',
    bg: 'bg-violet-50',
    border: 'border-l-4 border-violet-500',
    badge: 'bg-violet-100 text-violet-800',
  },
}

function stripCriteriaTags(html: string): string {
  return html.replace(/<criteria\s+id="[^"]*">([\s\S]*?)<\/criteria>/g, '$1').trim()
}

function parseRewriteWithCriteria(rewrite: string): React.ReactNode {
  const parts: React.ReactNode[] = []
  const regex = /<criteria\s+id="(계기|심화|역량|변화)">([\s\S]*?)<\/criteria>/g
  let lastIndex = 0
  let match
  let key = 0

  while ((match = regex.exec(rewrite)) !== null) {
    if (match.index > lastIndex) {
      const raw = rewrite.slice(lastIndex, match.index)
      parts.push(<span key={`t-${key++}`}>{raw}</span>)
    }
    const id = match[1]
    const content = match[2].trim()
    const style = CRITERIA_LABELS[id]
    if (style && content) {
      parts.push(
        <span
          key={`c-${key++}`}
          title={style.label}
          className={`inline border-l-2 pl-1.5 pr-1 py-0.5 rounded-r ${style.bg} ${style.border} cursor-default transition-colors hover:opacity-90`}
        >
          <span className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{content}</span>
        </span>
      )
    } else {
      parts.push(<span key={`t-${key++}`}>{content}</span>)
    }
    lastIndex = regex.lastIndex
  }
  if (lastIndex < rewrite.length) {
    parts.push(<span key={`t-${key++}`}>{rewrite.slice(lastIndex)}</span>)
  }
  return parts.length ? <>{parts}</> : rewrite
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const copy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }
  return (
    <button
      type="button"
      onClick={copy}
      className="px-4 py-2.5 text-sm font-medium rounded-xl bg-slate-800 hover:bg-slate-700 text-white shadow-[0_4px_14px_rgb(0,0,0,0.08)] transition-all duration-200"
    >
      {copied ? '✓ 복사 완료' : '📋 수정본 복사하기'}
    </button>
  )
}

type ViewMode = 'list' | 'detail'
type ListTab = 'all' | 'creative' | 'academicSubject' | 'academicIndividual' | 'behavior'

/** 창의적체험활동상황 — 학년별 데이터 */
export type CreativeActivityGrade = { autonomousNotes: string; clubNotes: string; careerNotes: string }
export type CreativeActivityData = { byGrade: Record<1 | 2 | 3, CreativeActivityGrade> }

const EMPTY_CREATIVE_GRADE: CreativeActivityGrade = { autonomousNotes: '', clubNotes: '', careerNotes: '' }

function CreativeActivityForm({
  selectedGrade,
  onGradeChange,
  data,
  onChange,
}: {
  selectedGrade: 1 | 2 | 3
  onGradeChange: (g: 1 | 2 | 3) => void
  data: CreativeActivityGrade
  onChange: (d: CreativeActivityGrade) => void
}) {
  return (
    <div className="rounded-b-lg border border-t-0 border-gray-200 overflow-hidden">
      <div className="bg-gray-700 text-white px-4 py-3 font-bold text-base">
        창의적체험활동상황
      </div>
      <div className="border border-gray-200 overflow-x-auto">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50">
          <span className="text-sm font-semibold text-gray-700">학년</span>
          {([1, 2, 3] as const).map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => onGradeChange(g)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${selectedGrade === g ? 'bg-blue-600 text-white' : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'}`}
            >
              {g}학년
            </button>
          ))}
        </div>
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="w-28 py-3 px-3 border-r border-gray-200 font-semibold text-gray-900">영역</th>
              <th className="py-3 px-3 font-semibold text-gray-900">특기사항</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            <tr className="border-b border-gray-200 align-top">
              <td className="py-2 px-3 border-r border-gray-200 align-middle">자율활동</td>
              <td className="py-2 px-3">
                <textarea placeholder="입력" value={data.autonomousNotes} onChange={(e) => onChange({ ...data, autonomousNotes: e.target.value })} className="w-full min-h-[80px] px-3 py-2 border border-gray-300 rounded resize-y" rows={3} />
              </td>
            </tr>
            <tr className="border-b border-gray-200 align-top">
              <td className="py-2 px-3 border-r border-gray-200 align-middle">동아리활동</td>
              <td className="py-2 px-3">
                <textarea placeholder="입력" value={data.clubNotes} onChange={(e) => onChange({ ...data, clubNotes: e.target.value })} className="w-full min-h-[80px] px-3 py-2 border border-gray-300 rounded resize-y" rows={3} />
              </td>
            </tr>
            <tr className="border-b border-gray-200 align-top">
              <td className="py-2 px-3 border-r border-gray-200 align-middle">진로활동</td>
              <td className="py-2 px-3">
                <textarea placeholder="입력" value={data.careerNotes} onChange={(e) => onChange({ ...data, careerNotes: e.target.value })} className="w-full min-h-[80px] px-3 py-2 border border-gray-300 rounded resize-y" rows={3} />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

export type AcademicDevGrade = { subjects: string[]; notes: string[] }
export type AcademicDevData = { byGrade: Record<1 | 2 | 3, AcademicDevGrade> }

/** 4단계 필승 구조 라벨 */
const STEP_LABELS: Record<string, string> = { 계기: '계기(동기)', 심화: '심화(탐구)', 역량: '역량(결과)', 변화: '변화(성장)' }

/** 하이라이트 타입 (백엔드 API 응답 스키마) */
interface Highlight {
  type: 'good' | 'bad'
  step: string
  label: string
  feedback: string
  indices: [number, number]
  quote: string
}

/** 4단계 구조 분석 (계기/심화/역량/변화) */
interface StructureStep {
  status: 'ok' | 'warn' | 'missing'
  summary: string
  detail: string
}

/** 합격 체크리스트 */
interface ChecklistResult {
  actionVerbs: boolean
  concreteData: boolean
  curriculumLink: boolean
  uniqueQuestion: boolean
}

/** 새로운 진단 결과 타입 */
interface DiagnosisResultV2 {
  success: boolean
  original_text: string
  highlights: Highlight[]
  goodPoints: Array<{ step: string; label: string; feedback: string; quote: string }>
  reconsiderPoints: Array<{ step: string; label: string; feedback: string; quote: string }>
  rewritten_version?: string
  structure_analysis?: Record<string, StructureStep>
  checklist?: ChecklistResult
  admission_comment?: string
  error: string | null
}

/** indices 기반 하이라이팅 렌더링 */
function renderHighlightedText(
  text: string,
  highlights: Highlight[],
  activeHighlightIndex: number | null,
  onHighlightClick: (index: number) => void
): React.ReactNode {
  if (!highlights || highlights.length === 0) return text

  // 유효한 인덱스를 가진 하이라이트만 필터링
  const validHighlights = highlights
    .map((h, originalIndex) => ({ ...h, originalIndex }))
    .filter(h => h.indices[0] >= 0 && h.indices[1] > h.indices[0] && h.indices[1] <= text.length)
    .sort((a, b) => a.indices[0] - b.indices[0])

  if (validHighlights.length === 0) return text

  // 겹치는 구간 제거 (먼저 나온 것 우선)
  const nonOverlapping: typeof validHighlights = []
  for (const h of validHighlights) {
    const overlaps = nonOverlapping.some(
      existing => h.indices[0] < existing.indices[1] && h.indices[1] > existing.indices[0]
    )
    if (!overlaps) {
      nonOverlapping.push(h)
    }
  }

  // JSX 생성
  const parts: React.ReactNode[] = []
  let lastIdx = 0

  nonOverlapping.forEach((h, i) => {
    // 하이라이트 전 텍스트
    if (h.indices[0] > lastIdx) {
      parts.push(<span key={`text-${i}`}>{text.slice(lastIdx, h.indices[0])}</span>)
    }

    // 하이라이트 영역
    const isActive = activeHighlightIndex === h.originalIndex
    const baseClass = h.type === 'good'
      ? 'bg-emerald-100 text-emerald-900'
      : 'bg-red-100 text-red-900'
    const activeClass = isActive ? 'ring-2 ring-offset-1 ring-blue-500 animate-pulse' : ''

    parts.push(
      <span
        key={`highlight-${i}`}
        id={`highlight-${h.originalIndex}`}
        className={`${baseClass} ${activeClass} cursor-pointer rounded px-0.5 transition-all duration-300`}
        onClick={() => onHighlightClick(h.originalIndex)}
        title={`[${h.step}] ${h.label}`}
      >
        {text.slice(h.indices[0], h.indices[1])}
      </span>
    )
    lastIdx = h.indices[1]
  })

  // 마지막 텍스트
  if (lastIdx < text.length) {
    parts.push(<span key="text-end">{text.slice(lastIdx)}</span>)
  }

  return <>{parts}</>
}

/** 과목별 진단 결과 표시 (2-Column Layout) — indices 기반 하이라이팅 */
function SubjectDiagnosisPanel({
  subject,
  content,
  diagnosis,
  loading,
  majorCategory,
}: {
  subject: string
  content: string
  diagnosis: DiagnosisResultV2 | null
  loading: boolean
  majorCategory?: string | null
}) {
  const [activeHighlight, setActiveHighlight] = useState<number | null>(null)
  const textContainerRef = useRef<HTMLDivElement>(null)

  // 피드백 카드 클릭 시 해당 하이라이트로 스크롤
  const scrollToHighlight = (index: number) => {
    setActiveHighlight(index)
    const element = document.getElementById(`highlight-${index}`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    // 3초 후 활성 상태 해제
    setTimeout(() => setActiveHighlight(null), 3000)
  }

  // 하이라이트 클릭 시 해당 피드백 카드로 스크롤
  const scrollToFeedback = (index: number) => {
    setActiveHighlight(index)
    const element = document.getElementById(`feedback-${index}`)
    if (element) {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
    setTimeout(() => setActiveHighlight(null), 3000)
  }

  const highlights = diagnosis?.highlights || []
  const [textView, setTextView] = useState<'original' | 'rewritten'>('original')
  const hasRewritten = Boolean(diagnosis?.rewritten_version)
  const charCount = content.length
  const charLimit = 4000

  return (
    <div className="rounded-2xl bg-white shadow-[0_8px_30px_rgb(0,0,0,0.06)] overflow-hidden mb-6">
      <div className="px-6 py-4 bg-slate-800">
        <h4 className="text-base font-semibold text-white font-sans">{subject || '과목명 없음'}</h4>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.4fr)_minmax(360px,1fr)] gap-12 lg:gap-16 p-6 lg:p-8">
        {/* 왼쪽: 원문 / S등급 수정본 탭 + 본문 (에디토리얼) */}
        <div className="min-w-0">
          <div className="flex items-center justify-between mb-4">
            <div className="flex rounded-lg bg-slate-100/80 p-1 font-sans">
              <button
                type="button"
                onClick={() => setTextView('original')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors duration-200 ${
                  textView === 'original' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-600 hover:text-slate-800'
                }`}
              >
                📄 원본 보기
              </button>
              <button
                type="button"
                onClick={() => setTextView('rewritten')}
                disabled={!hasRewritten}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed ${
                  textView === 'rewritten' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-600 hover:text-slate-800'
                }`}
              >
                ✨ S등급 수정본
              </button>
            </div>
            {textView === 'original' && (
              <div className="flex items-center gap-4 text-xs text-slate-500 font-sans">
                <span className="tabular-nums">{charCount} / {charLimit}</span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-3 h-3 rounded bg-emerald-100 border border-emerald-300" />
                  <span>잘된 점</span>
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="inline-block w-3 h-3 rounded bg-red-100 border border-red-300" />
                  <span>보완점</span>
                </span>
              </div>
            )}
          </div>
          <div
            ref={textContainerRef}
            className={`whitespace-pre-wrap rounded-xl p-6 min-h-[320px] max-h-[520px] overflow-y-auto leading-relaxed text-sm text-gray-700 ${
              textView === 'original' ? 'bg-slate-50/80' : 'bg-indigo-50/30'
            }`}
          >
            {textView === 'original' ? (
              content ? (
                loading ? content : renderHighlightedText(content, highlights, activeHighlight, scrollToFeedback)
              ) : (
                <span className="text-gray-400">(내용 없음)</span>
              )
            ) : hasRewritten ? (
              <p className="leading-relaxed text-gray-700">{diagnosis!.rewritten_version}</p>
            ) : (
              <span className="text-gray-400">진단 후 S등급 수정본을 확인할 수 있습니다.</span>
            )}
          </div>
          {textView === 'rewritten' && hasRewritten && diagnosis?.rewritten_version && (
            <div className="mt-4">
              <CopyButton text={diagnosis.rewritten_version} />
            </div>
          )}
          {/* 원문 아래: 비교용 S등급 합격자 표준 사례 */}
          <div className="mt-6">
            <BestPracticeCard majorCategory={majorCategory} />
          </div>
        </div>

        {/* 오른쪽: 입학사정관 분석 노트 — 스티키 + 페이퍼 섀도우 */}
        <div className="lg:sticky lg:top-8 lg:self-start min-w-0 flex flex-col">
          <div className="rounded-2xl bg-white shadow-[0_8px_30px_rgb(0,0,0,0.04)] p-5 lg:p-6 flex-1 min-h-0 overflow-hidden flex flex-col">
            <h5 className="text-sm font-semibold text-slate-800 mb-4 font-sans">📌 입학사정관 분석 노트</h5>
          {loading ? (
            <div className="rounded-xl bg-slate-50/80 p-8 text-center">
              <div className="animate-spin w-6 h-6 border-2 border-slate-300 border-t-slate-600 rounded-full mx-auto mb-2" />
              <p className="text-sm text-slate-500 font-sans">4단계 필승구조 기준으로 분석 중...</p>
            </div>
          ) : diagnosis?.error ? (
            <div className="rounded-xl bg-rose-50/60 p-5">
              <p className="text-sm text-rose-700 font-sans">{diagnosis.error}</p>
            </div>
          ) : diagnosis ? (
            <div className="space-y-5 flex-1 min-h-0 overflow-y-auto pr-1 font-sans">
              {diagnosis.admission_comment && (
                <div className="rounded-xl bg-amber-50/40 p-4">
                  <p className="text-xs font-semibold text-amber-800/90 mb-1">💡 입학사정관의 코멘트</p>
                  <p className="text-sm text-slate-700 leading-relaxed">{diagnosis.admission_comment}</p>
                </div>
              )}

              {highlights.filter(h => h.type === 'good').map((h, i) => {
                const originalIndex = highlights.findIndex(x => x === h)
                const isActive = activeHighlight === originalIndex
                return (
                  <div
                    key={`good-${i}`}
                    id={`feedback-${originalIndex}`}
                    onClick={() => h.indices[0] >= 0 && scrollToHighlight(originalIndex)}
                    className={`p-4 rounded-xl cursor-pointer transition-all duration-200 ${
                      isActive ? 'bg-emerald-100/80 ring-2 ring-emerald-300/50' : 'bg-emerald-50/50 hover:bg-emerald-100/60'
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-emerald-600 text-lg flex-shrink-0">👍</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          {h.step && (
                            <span className="inline-block px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-200/80 text-emerald-800">
                              {STEP_LABELS[h.step] || h.step}
                            </span>
                          )}
                          {h.label && <span className="text-xs font-medium text-emerald-700">{h.label}</span>}
                        </div>
                        <p className="text-sm text-slate-700 leading-relaxed">{h.feedback}</p>
                        {h.quote && h.indices[0] >= 0 && (
                          <p className="mt-2 text-xs text-emerald-600/90 italic truncate">
                            "{h.quote.slice(0, 50)}{h.quote.length > 50 ? '...' : ''}"
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}

              {highlights.filter(h => h.type === 'bad').map((h, i) => {
                const originalIndex = highlights.findIndex(x => x === h)
                const isActive = activeHighlight === originalIndex
                const hasQuote = h.indices[0] >= 0
                return (
                  <div
                    key={`bad-${i}`}
                    id={`feedback-${originalIndex}`}
                    onClick={() => hasQuote && scrollToHighlight(originalIndex)}
                    className={`p-4 rounded-xl transition-all duration-200 ${
                      hasQuote ? 'cursor-pointer' : 'cursor-default'
                    } ${isActive ? 'bg-rose-100/80 ring-2 ring-rose-300/50' : 'bg-rose-50/50 hover:bg-rose-100/60'}`}
                  >
                    <div className="flex items-start gap-3">
                      <span className="text-rose-500 text-lg flex-shrink-0">💡</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          {h.step && (
                            <span className="inline-block px-2 py-0.5 rounded-md text-[10px] font-semibold bg-rose-200/80 text-rose-800">
                              {STEP_LABELS[h.step] || h.step}
                            </span>
                          )}
                          {h.label && <span className="text-xs font-medium text-rose-700">{h.label}</span>}
                        </div>
                        <p className="text-sm text-slate-700 leading-relaxed">{h.feedback}</p>
                        {!hasQuote && (
                          <p className="mt-2 text-xs text-rose-500 italic">(원문에 해당 내용이 없습니다 - 추가 작성 필요)</p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}

              {highlights.length === 0 && (
                <div className="rounded-xl bg-slate-50/60 p-5">
                  <p className="text-sm text-slate-500">진단 결과가 없습니다.</p>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-xl bg-slate-50/80 p-5">
              <p className="text-sm text-slate-400">진단 받기를 눌러주세요.</p>
            </div>
          )}
          </div>
        </div>
      </div>
    </div>
  )
}

function AcademicDevForm({
  selectedGrade,
  onGradeChange,
  data,
  onChange,
}: {
  selectedGrade: 1 | 2 | 3
  onGradeChange: (g: 1 | 2 | 3) => void
  data: AcademicDevGrade
  onChange: (d: AcademicDevGrade) => void
}) {
  const setSubject = (i: number, v: string) => {
    const next = [...data.subjects]
    next[i] = v
    onChange({ ...data, subjects: next })
  }
  const setNote = (i: number, v: string) => {
    const next = [...data.notes]
    next[i] = v
    onChange({ ...data, notes: next })
  }
  return (
    <div className="rounded-b-lg border border-t-0 border-gray-200 overflow-hidden">
      <div className="bg-gray-700 text-white px-4 py-3 font-bold text-base">
        과목별세부능력및특기사항
      </div>
      <div className="border border-gray-200 overflow-x-auto">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50">
          <span className="text-sm font-semibold text-gray-700">학년</span>
          {([1, 2, 3] as const).map((g) => (
            <button key={g} type="button" onClick={() => onGradeChange(g)} className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${selectedGrade === g ? 'bg-blue-600 text-white' : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'}`}>
              {g}학년
            </button>
          ))}
        </div>
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="w-32 py-3 px-3 border-r border-gray-200 font-semibold text-gray-900">과목</th>
              <th className="py-3 px-3 font-semibold text-gray-900">세부능력 및 특기사항</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            {[0, 1, 2].map((i) => (
              <tr key={i} className="border-b border-gray-200 align-top">
                <td className="py-2 px-3 border-r border-gray-200 align-top">
                  <input type="text" placeholder="입력" value={data.subjects[i] ?? ''} onChange={(e) => setSubject(i, e.target.value)} className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 placeholder:text-gray-400" />
                </td>
                <td className="py-2 px-3">
                  <textarea placeholder="입력" value={data.notes[i] ?? ''} onChange={(e) => setNote(i, e.target.value)} className="w-full min-h-[100px] px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 placeholder:text-gray-400 resize-y" rows={4} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** 개인별 — 학년별 하나의 입력란 (행동특성과 동일 레이아웃) */
export type IndividualDevGrade = { content: string }
export type IndividualDevData = { showInputs: boolean; byGrade: Record<1 | 2 | 3, IndividualDevGrade> }

function IndividualDevForm({
  selectedGrade,
  onGradeChange,
  data,
  onChange,
}: {
  selectedGrade: 1 | 2 | 3
  onGradeChange: (g: 1 | 2 | 3) => void
  data: IndividualDevData
  onChange: (d: IndividualDevData) => void
}) {
  const byGrade = data?.byGrade ?? { 1: { content: '' }, 2: { content: '' }, 3: { content: '' } }
  const gradeData = byGrade[selectedGrade] ?? { content: '' }
  const setContent = (v: string) => {
    onChange({ ...data, byGrade: { ...byGrade, [selectedGrade]: { content: v } } })
  }
  return (
    <div className="rounded-b-lg border border-t-0 border-gray-200 overflow-hidden">
      <div className="bg-gray-700 text-white px-4 py-3 font-bold text-base">
        개인별세부능력및특기사항
      </div>
      <div className="border border-gray-200 overflow-x-auto">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50">
          <span className="text-sm font-semibold text-gray-700">학년</span>
          {([1, 2, 3] as const).map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => onGradeChange(g)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${selectedGrade === g ? 'bg-blue-600 text-white' : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'}`}
            >
              {g}학년
            </button>
          ))}
        </div>
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="w-28 py-3 px-3 border-r border-gray-200 font-semibold text-gray-900">영역</th>
              <th className="py-3 px-3 font-semibold text-gray-900">특기사항</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            <tr className="border-b border-gray-200 align-top">
              <td className="py-2 px-3 border-r border-gray-200 align-middle">개인별세부능력및특기사항</td>
              <td className="py-2 px-3">
                <textarea placeholder="입력" value={gradeData.content} onChange={(e) => setContent(e.target.value)} className="w-full min-h-[80px] px-3 py-2 border border-gray-300 rounded resize-y" rows={3} />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** 행동특성 — opinions[0]=1학년, [1]=2학년, [2]=3학년 */
export type BehaviorOpinionData = { showInputs: boolean; opinions: string[] }

const DEFAULT_CREATIVE: CreativeActivityData = {
  byGrade: { 1: { ...EMPTY_CREATIVE_GRADE }, 2: { ...EMPTY_CREATIVE_GRADE }, 3: { ...EMPTY_CREATIVE_GRADE } },
}
const DEFAULT_ACADEMIC: AcademicDevData = {
  byGrade: { 1: { subjects: ['', '', ''], notes: ['', '', ''] }, 2: { subjects: ['', '', ''], notes: ['', '', ''] }, 3: { subjects: ['', '', ''], notes: ['', '', ''] } },
}
const DEFAULT_INDIVIDUAL: IndividualDevData = {
  showInputs: false,
  byGrade: { 1: { content: '' }, 2: { content: '' }, 3: { content: '' } },
}
const DEFAULT_BEHAVIOR: BehaviorOpinionData = { showInputs: false, opinions: ['', '', ''] }

function BehaviorOpinionForm({
  selectedGrade,
  onGradeChange,
  data,
  onChange,
}: {
  selectedGrade: 1 | 2 | 3
  onGradeChange: (g: 1 | 2 | 3) => void
  data: BehaviorOpinionData
  onChange: (d: BehaviorOpinionData) => void
}) {
  const setOpinion = (gradeIndex: number, v: string) => {
    const next = [...data.opinions]
    next[gradeIndex] = v
    onChange({ ...data, opinions: next })
  }
  return (
    <div className="rounded-b-lg border border-t-0 border-gray-200 overflow-hidden">
      <div className="bg-gray-700 text-white px-4 py-3 font-bold text-base">
        행동특성 및 종합의견
      </div>
      <div className="border border-gray-200 overflow-x-auto">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50">
          <span className="text-sm font-semibold text-gray-700">학년</span>
          {([1, 2, 3] as const).map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => onGradeChange(g)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${selectedGrade === g ? 'bg-blue-600 text-white' : 'bg-white border border-gray-300 text-gray-700 hover:bg-gray-50'}`}
            >
              {g}학년
            </button>
          ))}
        </div>
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="w-28 py-3 px-3 border-r border-gray-200 font-semibold text-gray-900">영역</th>
              <th className="py-3 px-3 font-semibold text-gray-900">특기사항</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            <tr className="border-b border-gray-200 align-top">
              <td className="py-2 px-3 border-r border-gray-200 align-middle">행동특성 및 종합의견</td>
              <td className="py-2 px-3">
                <textarea placeholder="입력" value={data.opinions[selectedGrade - 1] ?? ''} onChange={(e) => setOpinion(selectedGrade - 1, e.target.value)} className="w-full min-h-[80px] px-3 py-2 border border-gray-300 rounded resize-y" rows={3} />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

interface SavedSchoolRecordItem {
  content?: string
  hope_major?: string
  result?: { feedback?: string; grade?: string; benchmark?: string; rewrite?: string }
  created_at?: string
}

/** 4단계 필승구조 기반 진단 결과 (간단한 카드 스타일 - 창의적체험활동 등에서 사용) */
function DiagnosisPanel({
  diagnosis,
  loading,
}: {
  diagnosis: DiagnosisResultV2 | null
  loading: boolean
}) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-6">
        <h3 className="text-base font-bold text-gray-900 mb-3">진단 결과</h3>
        <p className="text-sm text-gray-500">4단계 필승구조 기준으로 분석 중...</p>
      </div>
    )
  }
  if (diagnosis?.error) {
    return (
      <div className="rounded-xl border border-gray-200 bg-red-50 p-6">
        <h3 className="text-base font-bold text-gray-900 mb-3">진단 결과</h3>
        <p className="text-sm text-red-600">{diagnosis.error}</p>
      </div>
    )
  }
  
  const highlights = diagnosis?.highlights || []
  const goodHighlights = highlights.filter(h => h.type === 'good')
  const badHighlights = highlights.filter(h => h.type === 'bad')
  
  const hasAny = goodHighlights.length > 0 || badHighlights.length > 0
  if (!hasAny) return null
  
  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="px-4 py-3 bg-gray-100 border-b border-gray-200">
        <h3 className="text-base font-bold text-gray-900">진단 결과</h3>
        <p className="text-xs text-gray-500 mt-0.5">4단계 필승구조(계기→심화→역량→변화) 기준</p>
      </div>
      <div className="p-4 space-y-4">
        {goodHighlights.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-emerald-600" aria-hidden>👍</span>
              <h4 className="text-sm font-semibold text-gray-900">이런 점이 좋아요</h4>
            </div>
            <ul className="space-y-2 text-sm text-gray-700">
              {goodHighlights.map((h, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-emerald-400 mt-0.5">•</span>
                  <div>
                    {h.step && STEP_LABELS[h.step] && (
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-700 mr-1.5 mb-0.5">
                        {STEP_LABELS[h.step]}
                      </span>
                    )}
                    {h.label && (
                      <span className="text-xs font-medium text-emerald-600 mr-1.5">{h.label}</span>
                    )}
                    <span className="text-gray-800">{h.feedback}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
        {badHighlights.length > 0 && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-red-500" aria-hidden>💡</span>
              <h4 className="text-sm font-semibold text-gray-900">이렇게 보완해 보세요</h4>
            </div>
            <ul className="space-y-2 text-sm text-gray-700">
              {badHighlights.map((h, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span className="text-red-400 mt-0.5">•</span>
                  <div>
                    {h.step && STEP_LABELS[h.step] && (
                      <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-100 text-red-700 mr-1.5 mb-0.5">
                        {STEP_LABELS[h.step]}
                      </span>
                    )}
                    {h.label && (
                      <span className="text-xs font-medium text-red-600 mr-1.5">{h.label}</span>
                    )}
                    <span className="text-gray-800">{h.feedback}</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

export default function SchoolRecordEvalPage() {
  const navigate = useNavigate()
  const { user, accessToken, isAuthenticated } = useAuth()
  const resultRef = useRef<HTMLDivElement>(null)

  const [viewMode, setViewMode] = useState<ViewMode>('list')
  const [listTab, setListTab] = useState<ListTab>('all')
  const [hopeMajor, setHopeMajor] = useState('')
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<EvalResult | null>(null)
  const [error, setError] = useState('')
  const [tipsOpen, setTipsOpen] = useState(false)
  const [savedItems, setSavedItems] = useState<SavedSchoolRecordItem[]>([])
  const [savedItemsLoading, setSavedItemsLoading] = useState(false)

  const [creativeActivity, setCreativeActivity] = useState<CreativeActivityData>(DEFAULT_CREATIVE)
  const [academicDev, setAcademicDev] = useState<AcademicDevData>(DEFAULT_ACADEMIC)
  const [individualDev, setIndividualDev] = useState<IndividualDevData>(DEFAULT_INDIVIDUAL)
  const [behaviorOpinion, setBehaviorOpinion] = useState<BehaviorOpinionData>(DEFAULT_BEHAVIOR)
  const [creativeGrade, setCreativeGrade] = useState<1 | 2 | 3>(1)
  const [academicGrade, setAcademicGrade] = useState<1 | 2 | 3>(1)
  const [individualGrade, setIndividualGrade] = useState<1 | 2 | 3>(1)
  const [behaviorGrade, setBehaviorGrade] = useState<1 | 2 | 3>(1)
  const [formsLoading, setFormsLoading] = useState(false)
  const [formsSaveStatus, setFormsSaveStatus] = useState<'idle' | 'saving' | 'ok' | 'err'>('idle')
  
  // 탭별·학년별 진단 결과 저장 (예: "creative-1", "academicSubject-2" 등)
  // 새로운 API 응답 스키마 (highlights + indices 포함)
  const [diagnosisResults, setDiagnosisResults] = useState<Record<string, DiagnosisResultV2>>({})
  const [diagnosisLoading, setDiagnosisLoading] = useState(false)

  // 희망 전공 → 전공 계열 (S등급 표준 사례 카드용)
  const majorCategoryForPractice = getMajorCategoryFromHopeMajor(hopeMajor)

  const baseUrl = getApiBaseUrl()

  /** 현재 탭·학년의 진단 결과 키 */
  const getCurrentDiagnosisKey = (): string => {
    if (listTab === 'creative') return `creative-${creativeGrade}`
    if (listTab === 'academicSubject') return `academicSubject-${academicGrade}`
    if (listTab === 'academicIndividual') return `academicIndividual-${individualGrade}`
    if (listTab === 'behavior') return `behavior-${behaviorGrade}`
    return ''
  }

  /** 현재 탭·학년의 진단 결과 조회 */
  const currentDiagnosis = diagnosisResults[getCurrentDiagnosisKey()] ?? null

  /** 현재 탭·학년에 해당하는 세특 텍스트 추출 (진단 API용) */
  const getContentForDiagnosis = (): string => {
    if (listTab === 'creative') {
      const g = creativeActivity.byGrade[creativeGrade]
      return [g.autonomousNotes, g.clubNotes, g.careerNotes].filter(Boolean).join('\n\n')
    }
    if (listTab === 'academicSubject') {
      // 과목별은 개별 진단하므로 이 함수 사용 안 함
      return ''
    }
    if (listTab === 'academicIndividual') {
      return individualDev.byGrade[individualGrade]?.content ?? ''
    }
    if (listTab === 'behavior') {
      return behaviorOpinion.opinions[behaviorGrade - 1] ?? ''
    }
    return ''
  }

  /** API 응답을 DiagnosisResultV2로 변환 */
  const defaultStructure = (): Record<string, StructureStep> => ({
    계기: { status: 'warn', summary: '', detail: '' },
    심화: { status: 'warn', summary: '', detail: '' },
    역량: { status: 'warn', summary: '', detail: '' },
    변화: { status: 'warn', summary: '', detail: '' },
  })
  const defaultChecklist = (): ChecklistResult => ({
    actionVerbs: false,
    concreteData: false,
    curriculumLink: false,
    uniqueQuestion: false,
  })

  const parseApiResponse = (data: Record<string, unknown>, originalContent: string): DiagnosisResultV2 => {
    const highlights: Highlight[] = (data.highlights as Highlight[]) || []
    return {
      success: (data.success as boolean) ?? false,
      original_text: (data.original_text as string) || originalContent,
      highlights,
      goodPoints: (data.goodPoints as DiagnosisResultV2['goodPoints']) || [],
      reconsiderPoints: (data.reconsiderPoints as DiagnosisResultV2['reconsiderPoints']) || [],
      rewritten_version: (data.rewritten_version as string) || '',
      structure_analysis: (data.structure_analysis as Record<string, StructureStep>) || defaultStructure(),
      checklist: (data.checklist as ChecklistResult) || defaultChecklist(),
      admission_comment: (data.admission_comment as string) || '',
      error: data.error as string | null
    }
  }

  /** 과목별세부능력및특기사항 과목별 진단 */
  const runAcademicSubjectDiagnosis = async () => {
    const g = academicDev.byGrade[academicGrade]
    const subjectsWithContent: Array<{ idx: number; subject: string; content: string }> = []
    for (let i = 0; i < 3; i++) {
      const subj = (g.subjects[i] ?? '').trim()
      const note = (g.notes[i] ?? '').trim()
      if (subj || note) {
        // 과목명만 있고 내용이 없는 경우 경고 메시지
        if (subj && !note) {
          const diagnosisKey = `academicSubject-${academicGrade}-${i}`
          setDiagnosisResults((prev) => ({ 
            ...prev, 
            [diagnosisKey]: { 
              success: true,
              original_text: '',
              highlights: [{
                type: 'bad',
                step: '전체',
                label: '내용 부족',
                feedback: '과목의 세부능력 및 특기사항 내용을 입력해 주세요.',
                indices: [-1, -1],
                quote: ''
              }],
              goodPoints: [], 
              reconsiderPoints: [{ step: '전체', label: '내용 부족', feedback: '과목의 세부능력 및 특기사항 내용을 입력해 주세요.', quote: '' }], 
              rewritten_version: '',
              error: null 
            } 
          }))
          continue
        }
        // 과목명과 내용을 합쳐서 전송
        subjectsWithContent.push({ idx: i, subject: subj || `과목 ${i + 1}`, content: note || `${subj}\n${note}`.trim() })
      }
    }
    if (subjectsWithContent.length === 0) {
      return
    }
    setDiagnosisLoading(true)
    try {
      await Promise.all(
        subjectsWithContent.map(async ({ idx, content }) => {
          const diagnosisKey = `academicSubject-${academicGrade}-${idx}`
          try {
            const res = await fetch(`${baseUrl}/api/school-record/diagnose`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ content, hope_major: hopeMajor.trim() || undefined }),
            })
            let data: Record<string, unknown> = {}
            try {
              data = await res.json()
            } catch {
              data = { error: res.statusText || '서버 응답을 읽을 수 없습니다.' }
            }
            if (!res.ok) {
              setDiagnosisResults((prev) => ({ 
                ...prev, 
                [diagnosisKey]: { 
                  success: false,
                  original_text: content,
                  highlights: [],
                  goodPoints: [], 
                  reconsiderPoints: [], 
                  rewritten_version: '',
                  error: (data.detail || data.error || `진단 요청 실패 (${res.status})`) as string
                } 
              }))
              return
            }
            if (data.success) {
              setDiagnosisResults((prev) => ({ 
                ...prev, 
                [diagnosisKey]: parseApiResponse(data, content)
              }))
            } else {
              setDiagnosisResults((prev) => ({ 
                ...prev, 
                [diagnosisKey]: { 
                  success: false,
                  original_text: content,
                  highlights: [],
                  goodPoints: [], 
                  reconsiderPoints: [], 
                  rewritten_version: '',
                  error: (data.error || '진단 결과를 가져오지 못했습니다.') as string
                } 
              }))
            }
          } catch (e: unknown) {
            setDiagnosisResults((prev) => ({ 
              ...prev, 
              [diagnosisKey]: { 
                success: false,
                original_text: content,
                highlights: [],
                goodPoints: [], 
                reconsiderPoints: [], 
                rewritten_version: '',
                error: e instanceof Error ? e.message : '진단 중 오류가 발생했습니다.'
              } 
            }))
          }
        })
      )
    } finally {
      setDiagnosisLoading(false)
    }
  }

  const runDiagnosis = async () => {
    if (listTab === 'academicSubject') {
      await runAcademicSubjectDiagnosis()
      return
    }
    const content = getContentForDiagnosis().trim()
    const diagnosisKey = getCurrentDiagnosisKey()
    if (!diagnosisKey) return

    if (!content) {
      setDiagnosisResults((prev) => ({ 
        ...prev, 
        [diagnosisKey]: { 
          success: false,
          original_text: '',
          highlights: [],
          goodPoints: [], 
          reconsiderPoints: [], 
          rewritten_version: '',
          error: '진단할 내용을 먼저 입력해 주세요.'
        } 
      }))
      return
    }
    setDiagnosisLoading(true)
    try {
      const res = await fetch(`${baseUrl}/api/school-record/diagnose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, hope_major: hopeMajor.trim() || undefined }),
      })
      let data: Record<string, unknown> = {}
      try {
        data = await res.json()
      } catch {
        data = { error: res.statusText || '서버 응답을 읽을 수 없습니다.' }
      }
      if (!res.ok) {
        setDiagnosisResults((prev) => ({ 
          ...prev, 
          [diagnosisKey]: { 
            success: false,
            original_text: content,
            highlights: [],
            goodPoints: [], 
            reconsiderPoints: [], 
            rewritten_version: '',
            error: (data.detail || data.error || `진단 요청 실패 (${res.status})`) as string
          } 
        }))
        return
      }
      if (data.success) {
        setDiagnosisResults((prev) => ({ 
          ...prev, 
          [diagnosisKey]: parseApiResponse(data, content)
        }))
      } else {
        setDiagnosisResults((prev) => ({ 
          ...prev, 
          [diagnosisKey]: { 
            success: false,
            original_text: content,
            highlights: [],
            goodPoints: [], 
            reconsiderPoints: [], 
            rewritten_version: '',
            error: (data.error || '진단 결과를 가져오지 못했습니다.') as string
          } 
        }))
      }
    } catch (e: unknown) {
      setDiagnosisResults((prev) => ({ 
        ...prev, 
        [diagnosisKey]: { 
          success: false,
          original_text: content,
          highlights: [],
          goodPoints: [], 
          reconsiderPoints: [], 
          rewritten_version: '',
          error: e instanceof Error ? e.message : '진단 중 오류가 발생했습니다.'
        } 
      }))
    } finally {
      setDiagnosisLoading(false)
    }
  }

  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      setSavedItems([])
      return
    }
    setSavedItemsLoading(true)
    fetch(`${baseUrl}/api/school-record/list`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((res) => (res.ok ? res.json() : { items: [] }))
      .then((data) => setSavedItems(Array.isArray(data?.items) ? data.items : []))
      .catch(() => setSavedItems([]))
      .finally(() => setSavedItemsLoading(false))
  }, [isAuthenticated, accessToken, baseUrl])

  useEffect(() => {
    if (!isAuthenticated || !accessToken) return
    setFormsLoading(true)
    fetch(`${baseUrl}/api/school-record/forms`, { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((res) => (res.ok ? res.json() : { forms: {} }))
      .then((data) => {
        const f = data?.forms || {}
        if (f.creativeActivity) {
          if (f.creativeActivity.byGrade && typeof f.creativeActivity.byGrade === 'object') {
            const byGrade = f.creativeActivity.byGrade
            setCreativeActivity({
              byGrade: {
                1: { ...EMPTY_CREATIVE_GRADE, ...byGrade[1] },
                2: { ...EMPTY_CREATIVE_GRADE, ...byGrade[2] },
                3: { ...EMPTY_CREATIVE_GRADE, ...byGrade[3] },
              },
            })
          } else {
            const g = (f.creativeActivity.grade ?? 1) as 1 | 2 | 3
            const one = { autonomousNotes: f.creativeActivity.autonomousNotes ?? '', clubNotes: f.creativeActivity.clubNotes ?? '', careerNotes: f.creativeActivity.careerNotes ?? '' }
            setCreativeActivity({ ...DEFAULT_CREATIVE, byGrade: { ...DEFAULT_CREATIVE.byGrade, [g]: one } })
          }
        }
        if (f.academicDev) {
          if (f.academicDev.byGrade && typeof f.academicDev.byGrade === 'object') {
            const byGrade = f.academicDev.byGrade as Record<string, { subjects?: string[]; notes?: string[] }>
            const pad = (arr: string[] | undefined): string[] =>
              (arr || []).slice(0, 3).concat(Array(3).fill('')).slice(0, 3)
            setAcademicDev({ byGrade: { 1: { subjects: pad(byGrade['1']?.subjects), notes: pad(byGrade['1']?.notes) }, 2: { subjects: pad(byGrade['2']?.subjects), notes: pad(byGrade['2']?.notes) }, 3: { subjects: pad(byGrade['3']?.subjects), notes: pad(byGrade['3']?.notes) } } })
          } else {
            const g = (f.academicDev.grade ?? 1) as 1 | 2 | 3
            const subj = Array.isArray(f.academicDev.subjects) ? f.academicDev.subjects.slice(0, 3).concat(Array(3).fill('')).slice(0, 3) : Array(3).fill('')
            const notes = Array.isArray(f.academicDev.notes) ? f.academicDev.notes.slice(0, 3).concat(Array(3).fill('')).slice(0, 3) : Array(3).fill('')
            setAcademicDev({ ...DEFAULT_ACADEMIC, byGrade: { ...DEFAULT_ACADEMIC.byGrade, [g]: { subjects: subj, notes } } })
          }
        }
        if (f.individualDev) {
          const toContent = (g: Record<string, unknown> | undefined): string => {
            if (!g) return ''
            if (typeof (g as { content?: string }).content === 'string') return (g as { content: string }).content
            const notes = (g as { notes?: string[] }).notes
            if (Array.isArray(notes) && notes.some((n) => n && String(n).trim())) return notes.filter(Boolean).join('\n')
            return ''
          }
          const showInputs = f.individualDev.showInputs === true
          if (f.individualDev.byGrade && typeof f.individualDev.byGrade === 'object') {
            const byGrade = f.individualDev.byGrade as Record<string, Record<string, unknown>>
            setIndividualDev({ showInputs, byGrade: { 1: { content: toContent(byGrade['1']) }, 2: { content: toContent(byGrade['2']) }, 3: { content: toContent(byGrade['3']) } } })
          } else {
            const g = (f.individualDev.grade ?? 1) as 1 | 2 | 3
            const notes = (f.individualDev as { notes?: string[] }).notes
            const content = Array.isArray(notes) && notes.length ? notes.filter(Boolean).join('\n') : ''
            setIndividualDev({ showInputs: true, byGrade: { ...DEFAULT_INDIVIDUAL.byGrade, [g]: { content } } })
          }
        }
        if (f.behaviorOpinion) setBehaviorOpinion({ ...DEFAULT_BEHAVIOR, ...f.behaviorOpinion, opinions: Array.isArray(f.behaviorOpinion.opinions) ? f.behaviorOpinion.opinions.slice(0, 3).concat(Array(3).fill('')).slice(0, 3) : DEFAULT_BEHAVIOR.opinions })
      })
      .catch(() => {})
      .finally(() => setFormsLoading(false))
  }, [isAuthenticated, accessToken, baseUrl])

  const saveForms = async (payload: { creativeActivity?: CreativeActivityData; academicDev?: AcademicDevData; individualDev?: IndividualDevData; behaviorOpinion?: BehaviorOpinionData }) => {
    if (!accessToken) return
    setFormsSaveStatus('saving')
    try {
      const res = await fetch(`${baseUrl}/api/school-record/forms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('저장 실패')
      setFormsSaveStatus('ok')
      void captureBusinessEvent(TrackingEventNames.schoolRecordSaved, {
        category: 'engagement',
        source: 'school_record_eval_forms',
      })
      setTimeout(() => setFormsSaveStatus('idle'), 2000)
    } catch {
      setFormsSaveStatus('err')
      setTimeout(() => setFormsSaveStatus('idle'), 2000)
    }
  }

  const userName = user?.name || '회원'
  const completedCount = (result?.result && (result.result.grade || result.result.rewrite) ? 1 : 0) + savedItems.length
  const inProgressCount = loading ? 1 : 0
  const progressPercent = !content.trim() ? 0 : result ? 100 : loading ? 50 : 33

  const handleEvaluate = async () => {
    if (!content.trim()) {
      setError('세특 초안을 입력해 주세요.')
      return
    }
    setError('')
    setResult(null)
    setLoading(true)
    void captureBusinessEvent(TrackingEventNames.schoolRecordAnalysisRequested, {
      category: 'engagement',
      source: 'school_record_eval',
      has_hope_major: Boolean(hopeMajor.trim()),
    })
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (accessToken) headers['Authorization'] = `Bearer ${accessToken}`
      const res = await fetch(`${baseUrl}/api/school-record/evaluate`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          content: content.trim(),
          hope_major: hopeMajor.trim(),
          options: {},
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '평가 요청 실패')
      setResult(data)
      if (isAuthenticated && accessToken && data?.success && data?.result) {
        setSavedItems((prev) => {
          const next = [
            ...prev,
            {
              content: content.trim().slice(0, 30000),
              hope_major: hopeMajor.trim(),
              result: data.result,
              created_at: new Date().toISOString(),
            },
          ]
          return next.slice(-50)
        })
      }
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '평가 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const openSavedItem = (item: SavedSchoolRecordItem) => {
    setContent(item.content ?? '')
    setHopeMajor(item.hope_major ?? '')
    setResult(item.result ? { success: true, result: item.result } : null)
    setViewMode('detail')
  }

  const r = result?.result

  // ——— 목록 뷰 (이미지 1 스타일) ———
  if (viewMode === 'list') {
    return (
      <div className="min-h-screen bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
          {/* 헤더: 인사 + 요약 */}
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-6 mb-6">
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-gray-900">
                안녕하세요, {userName}님!
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                생기부를 평가하고 S등급 수준으로 다듬어 보세요
              </p>
            </div>
            <div className="flex gap-6 sm:gap-8">
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900">{completedCount}</p>
                <p className="text-xs text-gray-500 mt-0.5">평가 완료</p>
                <div className={`h-0.5 mt-1 ${completedCount ? 'bg-blue-600' : 'bg-gray-200'}`} />
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900">{inProgressCount}</p>
                <p className="text-xs text-gray-500 mt-0.5">평가 중</p>
                <div className={`h-0.5 mt-1 ${inProgressCount ? 'bg-blue-600' : 'bg-gray-200'}`} />
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900">0</p>
                <p className="text-xs text-gray-500 mt-0.5">활용 가능</p>
                <div className="h-0.5 mt-1 bg-gray-200" />
              </div>
            </div>
          </div>
          <p className="text-xs text-gray-400 mb-4">
            평가중 · 평가완료
          </p>

          {/* 탭 */}
          <nav className="flex flex-wrap gap-4 sm:gap-6 border-b border-gray-200 mb-6">
            <button
              type="button"
              onClick={() => setListTab('all')}
              className={`pb-3 text-sm font-medium -mb-px border-b-2 transition-colors ${listTab === 'all' ? 'text-gray-900 border-blue-600' : 'text-gray-500 border-transparent hover:text-gray-700'}`}
            >
              전체보기
            </button>
            <button
              type="button"
              onClick={() => setListTab('creative')}
              className={`pb-3 text-sm font-medium -mb-px border-b-2 transition-colors ${listTab === 'creative' ? 'text-gray-900 border-blue-600' : 'text-gray-500 border-transparent hover:text-gray-700'}`}
            >
              창의적체험활동상황
            </button>
            <button
              type="button"
              onClick={() => setListTab('academicSubject')}
              className={`pb-3 text-sm font-medium -mb-px border-b-2 transition-colors ${listTab === 'academicSubject' ? 'text-gray-900 border-blue-600' : 'text-blue-400 border-transparent hover:text-blue-600'}`}
            >
              과목별세부능력및특기사항
            </button>
            <button
              type="button"
              onClick={() => setListTab('academicIndividual')}
              className={`pb-3 text-sm font-medium -mb-px border-b-2 transition-colors ${listTab === 'academicIndividual' ? 'text-gray-900 border-blue-600' : 'text-blue-400 border-transparent hover:text-blue-600'}`}
            >
              개인별세부능력및특기사항
            </button>
            <button
              type="button"
              onClick={() => setListTab('behavior')}
              className={`pb-3 text-sm font-medium -mb-px border-b-2 transition-colors ${listTab === 'behavior' ? 'text-gray-900 border-blue-600' : 'text-gray-500 border-transparent hover:text-gray-700'}`}
            >
              행동특성 및 종합의견
            </button>
          </nav>

          {/* 탭별 콘텐츠 */}
          {listTab === 'creative' && (
            <div className="mb-6">
              {formsLoading ? (
                <div className="py-8 text-center text-gray-500 text-sm">폼 불러오는 중...</div>
              ) : (
                <>
                  <CreativeActivityForm
                    selectedGrade={creativeGrade}
                    onGradeChange={setCreativeGrade}
                    data={creativeActivity.byGrade[creativeGrade]}
                    onChange={(next) => setCreativeActivity((prev) => ({ ...prev, byGrade: { ...prev.byGrade, [creativeGrade]: next } }))}
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {isAuthenticated && (
                      <>
                        <button type="button" onClick={() => saveForms({ creativeActivity })} disabled={formsSaveStatus === 'saving'} className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                          {formsSaveStatus === 'saving' ? '저장 중...' : formsSaveStatus === 'ok' ? '저장됨' : '저장'}
                        </button>
                        {formsSaveStatus === 'err' && <span className="text-sm text-red-600">저장 실패</span>}
                      </>
                    )}
                    <button type="button" onClick={runDiagnosis} disabled={diagnosisLoading} className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50">
                      {diagnosisLoading ? '진단 중...' : '4단계 필승구조 진단 받기'}
                    </button>
                  </div>
                  <div className="mt-4">
                    <SubjectDiagnosisPanel
                      subject="창의적체험활동상황"
                      content={currentDiagnosis?.original_text || getContentForDiagnosis()}
                      diagnosis={currentDiagnosis ?? null}
                      loading={diagnosisLoading && !currentDiagnosis}
                      majorCategory={majorCategoryForPractice}
                    />
                  </div>
                </>
              )}
            </div>
          )}
          {listTab === 'academicSubject' && (
            <div className="mb-6">
              {formsLoading ? (
                <div className="py-8 text-center text-gray-500 text-sm">폼 불러오는 중...</div>
              ) : (
                <>
                  <AcademicDevForm
                    selectedGrade={academicGrade}
                    onGradeChange={setAcademicGrade}
                    data={academicDev.byGrade[academicGrade]}
                    onChange={(next) => setAcademicDev((prev) => ({ ...prev, byGrade: { ...prev.byGrade, [academicGrade]: next } }))}
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {isAuthenticated && (
                      <>
                        <button type="button" onClick={() => saveForms({ academicDev })} disabled={formsSaveStatus === 'saving'} className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                          {formsSaveStatus === 'saving' ? '저장 중...' : formsSaveStatus === 'ok' ? '저장됨' : '저장'}
                        </button>
                        {formsSaveStatus === 'err' && <span className="text-sm text-red-600">저장 실패</span>}
                      </>
                    )}
                    <button type="button" onClick={runDiagnosis} disabled={diagnosisLoading} className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50">
                      {diagnosisLoading ? '진단 중...' : '4단계 필승구조 진단 받기'}
                    </button>
                  </div>
                  {/* 과목별 진단 결과 */}
                  <div className="mt-4 space-y-4">
                    {[0, 1, 2].map((idx) => {
                      const g = academicDev.byGrade[academicGrade]
                      const subj = (g.subjects[idx] ?? '').trim()
                      const note = (g.notes[idx] ?? '').trim()
                      if (!subj && !note) return null
                      const diagKey = `academicSubject-${academicGrade}-${idx}`
                      const diag = diagnosisResults[diagKey]
                      // 진단 결과가 있으면 original_text 사용, 없으면 note 사용
                      const displayContent = diag?.original_text || note
                      return (
                        <SubjectDiagnosisPanel
                          key={idx}
                          subject={subj || `과목 ${idx + 1}`}
                          content={displayContent}
                          diagnosis={diag ?? null}
                          loading={diagnosisLoading && !diag}
                          majorCategory={majorCategoryForPractice}
                        />
                      )
                    })}
                  </div>
                </>
              )}
            </div>
          )}
          {listTab === 'academicIndividual' && (
            <div className="mb-6">
              {formsLoading ? (
                <div className="py-8 text-center text-gray-500 text-sm">폼 불러오는 중...</div>
              ) : (
                <>
                  <IndividualDevForm
                    selectedGrade={individualGrade}
                    onGradeChange={setIndividualGrade}
                    data={individualDev}
                    onChange={setIndividualDev}
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {isAuthenticated && (
                      <>
                        <button type="button" onClick={() => saveForms({ individualDev })} disabled={formsSaveStatus === 'saving'} className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                          {formsSaveStatus === 'saving' ? '저장 중...' : formsSaveStatus === 'ok' ? '저장됨' : '저장'}
                        </button>
                        {formsSaveStatus === 'err' && <span className="text-sm text-red-600">저장 실패</span>}
                      </>
                    )}
                    <button type="button" onClick={runDiagnosis} disabled={diagnosisLoading} className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50">
                      {diagnosisLoading ? '진단 중...' : '4단계 필승구조 진단 받기'}
                    </button>
                  </div>
                  <div className="mt-4">
                    <SubjectDiagnosisPanel
                      subject="개인별세부능력및특기사항"
                      content={currentDiagnosis?.original_text || getContentForDiagnosis()}
                      diagnosis={currentDiagnosis ?? null}
                      loading={diagnosisLoading && !currentDiagnosis}
                      majorCategory={majorCategoryForPractice}
                    />
                  </div>
                </>
              )}
            </div>
          )}
          {listTab === 'behavior' && (
            <div className="mb-6">
              {formsLoading ? (
                <div className="py-8 text-center text-gray-500 text-sm">폼 불러오는 중...</div>
              ) : (
                <>
                  <BehaviorOpinionForm
                    selectedGrade={behaviorGrade}
                    onGradeChange={setBehaviorGrade}
                    data={behaviorOpinion}
                    onChange={setBehaviorOpinion}
                  />
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    {isAuthenticated && (
                      <>
                        <button type="button" onClick={() => saveForms({ behaviorOpinion })} disabled={formsSaveStatus === 'saving'} className="px-4 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
                          {formsSaveStatus === 'saving' ? '저장 중...' : formsSaveStatus === 'ok' ? '저장됨' : '저장'}
                        </button>
                        {formsSaveStatus === 'err' && <span className="text-sm text-red-600">저장 실패</span>}
                      </>
                    )}
                    <button type="button" onClick={runDiagnosis} disabled={diagnosisLoading} className="px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 disabled:opacity-50">
                      {diagnosisLoading ? '진단 중...' : '4단계 필승구조 진단 받기'}
                    </button>
                  </div>
                  <div className="mt-4">
                    <SubjectDiagnosisPanel
                      subject="행동특성 및 종합의견"
                      content={currentDiagnosis?.original_text || getContentForDiagnosis()}
                      diagnosis={currentDiagnosis ?? null}
                      loading={diagnosisLoading && !currentDiagnosis}
                      majorCategory={majorCategoryForPractice}
                    />
                  </div>
                </>
              )}
            </div>
          )}
          {listTab === 'all' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {/* 생기부 세특 평가 추가 카드 */}
              <button
                type="button"
                onClick={() => setViewMode('detail')}
                className="flex flex-col items-center justify-center min-h-[180px] rounded-xl border-2 border-dashed border-gray-300 text-gray-500 hover:border-blue-400 hover:text-blue-600 hover:bg-blue-50/50 transition-colors"
              >
                <span className="text-4xl font-light text-inherit mb-2">+</span>
                <span className="text-sm font-medium">생기부 세특 평가 추가</span>
              </button>

              {/* 유저 연동 저장 목록 (user_profiles.metadata.school_record) */}
              {savedItemsLoading && savedItems.length === 0 ? (
                <div className="min-h-[180px] rounded-xl border border-gray-200 flex items-center justify-center text-sm text-gray-400">
                  저장 목록 불러오는 중...
                </div>
              ) : null}
              {[...savedItems].reverse().map((item, idx) => {
                const hasResult = item.result && (item.result.grade || item.result.rewrite)
                const dateStr = item.created_at
                  ? new Date(item.created_at).toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\. /g, '.').replace('.', '. ')
                  : ''
                return (
                  <button
                    key={`saved-${idx}-${item.created_at ?? idx}`}
                    type="button"
                    onClick={() => openSavedItem(item)}
                    className="flex flex-col items-start justify-between min-h-[180px] rounded-xl border border-gray-200 bg-white p-4 text-left shadow-sm hover:shadow-md transition-shadow"
                  >
                    <div className="flex items-start justify-between w-full">
                      <span className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 flex-shrink-0" />
                      <span className="text-xs text-gray-400">생기부 세특 평가</span>
                    </div>
                    <p className="text-base font-semibold text-gray-900 truncate w-full">
                      {item.hope_major || '희망 전공 미입력'}
                    </p>
                    <p className="text-sm text-gray-500">{hasResult ? '평가가 완료되었습니다.' : '평가 데이터'}</p>
                    <div className="flex items-center justify-between w-full mt-2">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                        평가완료
                      </span>
                      {dateStr && <span className="text-xs text-gray-400">{dateStr}</span>}
                    </div>
                  </button>
                )
              })}

              {/* 비로그인 시 현재 세션 평가 카드 (로그인 시에는 savedItems에 이미 반영됨) */}
              {result?.result && (r?.grade || r?.rewrite) && !isAuthenticated && (
                <button
                  type="button"
                  onClick={() => setViewMode('detail')}
                  className="flex flex-col items-start justify-between min-h-[180px] rounded-xl border border-gray-200 bg-white p-4 text-left shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between w-full">
                    <span className="w-2 h-2 rounded-full bg-blue-500 mt-1.5 flex-shrink-0" />
                    <span className="text-xs text-gray-400">생기부 세특 평가</span>
                  </div>
                  <p className="text-base font-semibold text-gray-900 truncate w-full">
                    {hopeMajor || '희망 전공 미입력'}
                  </p>
                  <p className="text-sm text-gray-500">평가가 완료되었습니다.</p>
                  <div className="flex items-center justify-between w-full mt-2">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
                      평가완료
                    </span>
                    <span className="text-xs text-gray-400">
                      {new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: '2-digit', day: '2-digit' }).replace(/\. /g, '.').replace('.', '. ')}
                    </span>
                  </div>
                </button>
              )}
            </div>
          )}

          {/* 하단 액션 */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 mt-8 pt-6 border-t border-gray-100">
            <button
              type="button"
              className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              PDF 다운로드 (0개)
            </button>
            <button
              type="button"
              onClick={() => navigate('/chat')}
              className="px-5 py-2.5 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 transition-colors flex items-center gap-1"
            >
              채팅으로 이동
              <span className="text-lg leading-none">→</span>
            </button>
          </div>
        </div>

        {/* 우측 플로팅 버튼 */}
        <div className="fixed right-4 top-1/2 -translate-y-1/2 flex flex-col gap-3 z-10">
          <button
            type="button"
            className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-gray-600 hover:bg-gray-200"
            aria-label="레이아웃"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6z" />
            </svg>
          </button>
          <button
            type="button"
            onClick={() => navigate('/chat')}
            className="w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center text-gray-600 hover:bg-gray-200"
            aria-label="채팅"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </button>
          <button
            type="button"
            className="w-12 h-12 rounded-full bg-blue-600 flex items-center justify-center text-white shadow-lg hover:bg-blue-700"
            aria-label="도움말"
          >
            <span className="text-lg font-bold">?</span>
          </button>
        </div>
      </div>
    )
  }

  // ——— 상세 뷰 (이미지 2 스타일): 좌측 사이드바 + 메인 ———
  return (
    <div className="min-h-screen bg-white flex">
      <style>{`
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in { animation: fade-in 0.4s ease-out; }
      `}</style>

      {/* 좌측 사이드바 */}
      <aside className="w-64 flex-shrink-0 border-r border-gray-200 bg-gray-50/50 p-4 flex flex-col">
        <button
          type="button"
          onClick={() => setViewMode('list')}
          className="text-sm text-gray-600 hover:text-gray-900 mb-6 flex items-center gap-1"
        >
          ‹ 목록으로
        </button>
        <p className="text-xs font-medium text-gray-500 mb-1">진행률</p>
        <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-6">
          <div
            className="h-full bg-blue-600 rounded-full transition-all duration-300"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        <ol className="space-y-2 text-sm mb-6">
          {['입력', '평가', '결과'].map((label, i) => {
            const step = !content.trim() ? 0 : result ? 2 : loading ? 1 : 0
            const active = step === i
            return (
              <li
                key={label}
                className={active ? 'text-blue-600 font-semibold' : 'text-gray-500'}
              >
                {i + 1}. {label}
              </li>
            )
          })}
        </ol>
        <div className="mt-auto">
          <button
            type="button"
            onClick={() => setTipsOpen((o) => !o)}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 w-full"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            생기부 세특 평가 Tip
          </button>
          {tipsOpen && (
            <ul className="mt-2 pl-6 space-y-1 text-xs text-gray-500">
              <li>· 세특만 있어도 평가받을 수 있어요</li>
              <li>· 희망 전공을 넣으면 더 정확해요</li>
              <li>· 평가 요청 후 잠시 기다려 주세요</li>
            </ul>
          )}
          <button
            type="button"
            onClick={handleEvaluate}
            disabled={loading || !content.trim()}
            className="mt-4 w-full py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            평가 요청
          </button>
        </div>
      </aside>

      {/* 메인 영역 */}
      <main className="flex-1 overflow-auto">
        <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8">
          <h2 className="text-lg font-bold text-gray-900">생기부 세특 평가</h2>
          <p className="text-sm text-gray-500 mt-0.5">세특·생활기록부 평가</p>

          <p className="text-sm text-gray-700 mt-6 leading-relaxed">
            안녕하세요, {userName}님.
          </p>
          <p className="text-sm text-gray-600 mt-2 leading-relaxed">
            입학사정관 기준 3대 역량(학업·진로·공동체)과 4단계 필승 구조로 생기부를 분석합니다.
            희망 전공과 세특 초안을 입력해 주시면, S등급 수준으로 다듬어 드립니다.
          </p>

          {!result ? (
            <>
              <p className="text-sm font-semibold text-gray-900 mt-8 mb-3">[첫 번째 단계] 입력</p>
              <ol className="list-decimal list-inside space-y-2 text-sm text-gray-700 mb-4">
                <li>희망 전공(계열)을 알려주세요.</li>
                <li>세특 또는 생기부 관련 원문을 붙여넣어 주세요.</li>
              </ol>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">희망 전공</label>
                  <input
                    type="text"
                    value={hopeMajor}
                    onChange={(e) => setHopeMajor(e.target.value)}
                    placeholder="예: 경영학과, 컴퓨터공학과"
                    className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                    disabled={loading}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">세특 초안</label>
                  <textarea
                    value={content}
                    onChange={(e) => setContent(e.target.value)}
                    placeholder="세특 원문을 붙여넣기 하세요."
                    className="w-full h-44 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-y text-sm"
                    disabled={loading}
                  />
                </div>
              </div>
              <p className="text-sm font-semibold text-gray-700 mt-6 mb-2">[예시]</p>
              <ul className="list-disc list-inside space-y-1 text-sm text-gray-500">
                <li>고등학교 2학년 때 경제 수업에서 배운 한계효용 체감을 바탕으로, 실생활 가격 결정에 관심을 갖고 『부의 시나리오』를 읽으며 데이터로 정리해 보았습니다.</li>
                <li>물리 실험에서 옴의 법칙을 적용해 전압 손실 원인을 찾고, 아두이노로 회로를 설계해 검증한 경험이 있습니다.</li>
              </ul>
              {error && <p className="text-sm text-red-600 mt-3">{error}</p>}
              <button
                type="button"
                onClick={handleEvaluate}
                disabled={loading || !content.trim()}
                className="mt-6 w-full sm:w-auto px-6 py-2.5 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    평가 중…
                  </>
                ) : (
                  <>메시지 보내기 ↑</>
                )}
              </button>
            </>
          ) : (
            <div ref={resultRef} className="mt-6 space-y-6">
              <p className="text-sm text-gray-700 leading-relaxed">
                입학사정관 AI가 제출하신 세특을 분석했습니다. 아래 결과를 확인해 주세요.
              </p>

              {r?.grade && (
                <section className="animate-fade-in rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                  <h3 className="flex items-center gap-2 text-sm font-bold text-amber-800 mb-3">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-100">📊 희망 전공·핵심 역량</span>
                  </h3>
                  <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{r.grade}</p>
                </section>
              )}

              {r?.benchmark && (
                <section className="animate-fade-in rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                  <h3 className="flex items-center gap-2 text-sm font-bold text-blue-800 mb-3">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-blue-100">🎯 평가요소 기반 진단</span>
                  </h3>
                  <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{r.benchmark}</p>
                </section>
              )}

              {r?.rewrite && (
                <section className="animate-fade-in rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
                  <h3 className="flex items-center gap-2 text-sm font-bold text-emerald-800 mb-3">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-100">✨ S등급 리라이팅</span>
                    {/<criteria\s+id=/.test(r.rewrite) && (
                      <span className="text-xs font-normal text-gray-500">· 색 구간에 커서를 올리면 4단계 필승 구조를 볼 수 있어요</span>
                    )}
                  </h3>
                  <div className="p-4 bg-emerald-50/50 rounded-lg border border-emerald-100">
                    {/<criteria\s+id=/.test(r.rewrite) ? (
                      <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap font-medium [&>span]:align-baseline">
                        {parseRewriteWithCriteria(r.rewrite)}
                      </p>
                    ) : (
                      <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap font-medium">
                        {r.rewrite}
                      </p>
                    )}
                  </div>
                  <p className="text-xs text-gray-500 mt-2">👆 이 문장을 그대로 사용하시면 됩니다!</p>
                  <CopyButton text={stripCriteriaTags(r.rewrite)} />
                </section>
              )}

              {r?.feedback && !r.grade && !r.benchmark && !r.rewrite && (
                <section className="rounded-xl border border-gray-200 bg-white p-5">
                  <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">{r.feedback}</p>
                </section>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => { setResult(null); setContent(''); setHopeMajor(''); }}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  다시 평가하기
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('list')}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  목록으로
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
