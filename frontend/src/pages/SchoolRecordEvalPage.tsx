import React, { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

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
      className="mt-3 px-4 py-2 text-xs font-medium rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white shadow-sm transition-colors"
    >
      {copied ? '✓ 복사 완료!' : '📋 리라이팅 복사하기'}
    </button>
  )
}

type ViewMode = 'list' | 'detail'
type ListTab = 'all' | 'creative' | 'academicSubject' | 'academicIndividual' | 'behavior'

/** 창의적체험활동상황 테이블 폼 (첨부 이미지 스타일) */
function CreativeActivityForm() {
  const [grade, setGrade] = useState(1)
  const [autonomousNotes, setAutonomousNotes] = useState('')
  const [clubNotes, setClubNotes] = useState('')
  const [careerNotes, setCareerNotes] = useState('')

  return (
    <div className="rounded-b-lg border border-t-0 border-gray-200 overflow-hidden">
      <div className="bg-gray-700 text-white px-4 py-3 font-bold text-base">
        창의적체험활동상황
      </div>
      <div className="border border-gray-200 overflow-x-auto">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50">
          <span className="text-sm font-semibold text-gray-700">학년</span>
          <select
            value={grade}
            onChange={(e) => setGrade(Number(e.target.value) || 1)}
            className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm"
          >
            <option value={1}>1학년</option>
            <option value={2}>2학년</option>
            <option value={3}>3학년</option>
          </select>
        </div>
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="w-28 py-3 px-3 border-r border-gray-200 font-semibold text-gray-900">영역</th>
              <th className="py-3 px-3 font-semibold text-gray-900">특기사항</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            {/* 자율활동 */}
            <tr className="border-b border-gray-200 align-top">
              <td className="py-2 px-3 border-r border-gray-200 align-middle">자율활동</td>
              <td className="py-2 px-3">
                <textarea
                  placeholder="입력"
                  value={autonomousNotes}
                  onChange={(e) => setAutonomousNotes(e.target.value)}
                  className="w-full min-h-[80px] px-3 py-2 border border-gray-300 rounded resize-y"
                  rows={3}
                />
              </td>
            </tr>
            {/* 동아리활동 */}
            <tr className="border-b border-gray-200 align-top">
              <td className="py-2 px-3 border-r border-gray-200 align-middle">동아리활동</td>
              <td className="py-2 px-3">
                <textarea
                  placeholder="입력"
                  value={clubNotes}
                  onChange={(e) => setClubNotes(e.target.value)}
                  className="w-full min-h-[80px] px-3 py-2 border border-gray-300 rounded resize-y"
                  rows={3}
                />
              </td>
            </tr>
            {/* 진로활동 */}
            <tr className="border-b border-gray-200 align-top">
              <td className="py-2 px-3 border-r border-gray-200 align-middle">진로활동</td>
              <td className="py-2 px-3">
                <textarea
                  placeholder="입력"
                  value={careerNotes}
                  onChange={(e) => setCareerNotes(e.target.value)}
                  className="w-full min-h-[80px] px-3 py-2 border border-gray-300 rounded resize-y"
                  rows={3}
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** 교과 학습 발달 상황 테이블 폼 (과목 + 세부능력 및 특기사항) */
function AcademicDevForm() {
  const [grade, setGrade] = useState(1)
  const [subjects, setSubjects] = useState(['', '', ''])
  const [notes, setNotes] = useState(['', '', ''])

  const setSubject = (i: number, v: string) => {
    const next = [...subjects]
    next[i] = v
    setSubjects(next)
  }
  const setNote = (i: number, v: string) => {
    const next = [...notes]
    next[i] = v
    setNotes(next)
  }

  return (
    <div className="rounded-b-lg border border-t-0 border-gray-200 overflow-hidden">
      <div className="bg-gray-700 text-white px-4 py-3 font-bold text-base">
        과목별세부능력및특기사항
      </div>
      <div className="border border-gray-200 overflow-x-auto">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50">
          <span className="text-sm font-semibold text-gray-700">학년</span>
          <select
            value={grade}
            onChange={(e) => setGrade(Number(e.target.value) || 1)}
            className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm"
          >
            <option value={1}>1학년</option>
            <option value={2}>2학년</option>
            <option value={3}>3학년</option>
          </select>
        </div>
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-300 bg-white">
              <th className="w-32 py-3 px-3 border-r border-gray-200 font-bold text-gray-900">과목</th>
              <th className="py-3 px-3 font-bold text-gray-900">세부능력 및 특기사항</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            {[0, 1, 2].map((i) => (
              <tr key={i} className="border-b border-gray-200 align-top">
                <td className="py-2 px-3 border-r border-gray-200 align-top">
                  <input
                    type="text"
                    placeholder="입력"
                    value={subjects[i]}
                    onChange={(e) => setSubject(i, e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 placeholder:text-gray-400"
                  />
                </td>
                <td className="py-2 px-3">
                  <textarea
                    placeholder="입력"
                    value={notes[i]}
                    onChange={(e) => setNote(i, e.target.value)}
                    className="w-full min-h-[100px] px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 placeholder:text-gray-400 resize-y"
                    rows={4}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** 개인별세부능력및특기사항 폼 */
function IndividualDevForm() {
  const [grade, setGrade] = useState(1)
  const [items, setItems] = useState(['', '', ''])
  const [notes, setNotes] = useState(['', '', ''])

  const setItem = (i: number, v: string) => {
    const next = [...items]
    next[i] = v
    setItems(next)
  }
  const setNote = (i: number, v: string) => {
    const next = [...notes]
    next[i] = v
    setNotes(next)
  }

  return (
    <div className="rounded-b-lg border border-t-0 border-gray-200 overflow-hidden">
      <div className="bg-gray-700 text-white px-4 py-3 font-bold text-base">
        개인별세부능력및특기사항
      </div>
      <div className="border border-gray-200 overflow-x-auto">
        <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50">
          <span className="text-sm font-semibold text-gray-700">학년</span>
          <select
            value={grade}
            onChange={(e) => setGrade(Number(e.target.value) || 1)}
            className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm"
          >
            <option value={1}>1학년</option>
            <option value={2}>2학년</option>
            <option value={3}>3학년</option>
          </select>
        </div>
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-300 bg-white">
              <th className="w-32 py-3 px-3 border-r border-gray-200 font-bold text-gray-900">구분</th>
              <th className="py-3 px-3 font-bold text-gray-900">세부능력 및 특기사항</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            {[0, 1, 2].map((i) => (
              <tr key={i} className="border-b border-gray-200 align-top">
                <td className="py-2 px-3 border-r border-gray-200 align-top">
                  <input
                    type="text"
                    placeholder="입력"
                    value={items[i]}
                    onChange={(e) => setItem(i, e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 placeholder:text-gray-400"
                  />
                </td>
                <td className="py-2 px-3">
                  <textarea
                    placeholder="입력"
                    value={notes[i]}
                    onChange={(e) => setNote(i, e.target.value)}
                    className="w-full min-h-[100px] px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 placeholder:text-gray-400 resize-y"
                    rows={4}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/** 행동특성 및 종합의견 폼 (학년 + 행동특성 및 종합의견 테이블) */
function BehaviorOpinionForm() {
  const [showInputs, setShowInputs] = useState(false)
  const [grade, setGrade] = useState(1)
  const [opinions, setOpinions] = useState(['', '', ''])

  const setOpinion = (i: number, v: string) => {
    const next = [...opinions]
    next[i] = v
    setOpinions(next)
  }

  return (
    <div className="rounded-b-lg border border-t-0 border-gray-200 overflow-hidden">
      <div className="bg-gray-700 text-white px-4 py-3 font-bold text-base">
        행동특성 및 종합의견
      </div>
      <div className="border border-gray-200 overflow-x-auto">
        {showInputs && (
          <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-200 bg-gray-50">
            <span className="text-sm font-semibold text-gray-700">학년</span>
            <select
              value={grade}
              onChange={(e) => setGrade(Number(e.target.value) || 1)}
              className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm"
            >
              <option value={1}>1학년</option>
              <option value={2}>2학년</option>
              <option value={3}>3학년</option>
            </select>
          </div>
        )}
        <table className="w-full text-sm text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-300 bg-gray-100">
              <th className="py-3 px-3 font-bold text-gray-900">행동특성 및 종합의견</th>
            </tr>
          </thead>
          <tbody className="bg-white">
            {!showInputs ? (
              <tr className="border-b border-gray-200">
                <td className="py-12 px-3 text-center text-gray-400">
                  해당 사항 없음
                </td>
              </tr>
            ) : (
              <tr className="border-b border-gray-200 align-top">
                <td className="py-2 px-3">
                  <textarea
                    placeholder="입력"
                    value={opinions[grade - 1]}
                    onChange={(e) => setOpinion(grade - 1, e.target.value)}
                    className="w-full min-h-[100px] px-3 py-2 border border-gray-300 rounded-lg resize-y"
                    rows={4}
                  />
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {!showInputs && (
        <div className="border-t border-gray-200 bg-white py-4 px-3">
          <button
            type="button"
            className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            onClick={() => setShowInputs(true)}
          >
            + 내용 입력하기
          </button>
        </div>
      )}
    </div>
  )
}

export default function SchoolRecordEvalPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const resultRef = useRef<HTMLDivElement>(null)

  const [viewMode, setViewMode] = useState<ViewMode>('list')
  const [listTab, setListTab] = useState<ListTab>('all')
  const [hopeMajor, setHopeMajor] = useState('')
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<EvalResult | null>(null)
  const [error, setError] = useState('')
  const [tipsOpen, setTipsOpen] = useState(false)

  const userName = user?.name || '회원'
  const completedCount = result?.result && (result.result.grade || result.result.rewrite) ? 1 : 0
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
    try {
      const res = await fetch('/api/school-record/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content: content.trim(),
          hope_major: hopeMajor.trim(),
          options: {},
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '평가 요청 실패')
      setResult(data)
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : '평가 중 오류가 발생했습니다.')
    } finally {
      setLoading(false)
    }
  }

  const r = result?.result

  // ——— 목록 뷰 (이미지 1 스타일) ———
  if (viewMode === 'list') {
    return (
      <div className="min-h-screen bg-white">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-6">
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
              <CreativeActivityForm />
            </div>
          )}
          {listTab === 'academicSubject' && (
            <div className="mb-6">
              <AcademicDevForm />
            </div>
          )}
          {listTab === 'academicIndividual' && (
            <div className="mb-6">
              <IndividualDevForm />
            </div>
          )}
          {listTab === 'behavior' && (
            <div className="mb-6">
              <BehaviorOpinionForm />
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

              {/* 최근 평가 카드 */}
              {result?.result && (r?.grade || r?.rewrite) && (
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
