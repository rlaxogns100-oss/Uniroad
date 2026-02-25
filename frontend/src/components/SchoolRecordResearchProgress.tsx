import { useMemo, useState, useEffect } from 'react'

interface SchoolRecordResearchProgressProps {
  logs: string[]
  query?: string
  onStop?: () => void
}

interface ParsedLog {
  message: string
  step: string
  detail?: Record<string, any>
}

interface ResearchStepItem {
  id: string
  label: string
}

const STEP_INDEX_BY_ID: Record<string, number> = {
  school_record_router: 0,
  school_record_retrieval_complete: 1,
  school_record_retrieval_skip: 1,
  school_record_retrieval_rounds: 1,
  school_record_report: 2,
  school_record_deep_dive: 3,
  school_record_follow_up: 4,
}

const parseLog = (rawLog: string): ParsedLog => {
  const [messagePart, metaPart] = String(rawLog || '').split('|||')
  if (!metaPart) {
    return {
      message: String(rawLog || '').trim(),
      step: '',
    }
  }

  try {
    const parsed = JSON.parse(metaPart)
    return {
      message: String(messagePart || '').trim(),
      step: String(parsed?.step || '').trim(),
      detail: parsed?.detail && typeof parsed.detail === 'object' ? parsed.detail : undefined,
    }
  } catch {
    return {
      message: String(rawLog || '').trim(),
      step: '',
    }
  }
}

const ExpandIcon = () => (
  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 3H3v5M16 3h5v5M8 21H3v-5M21 16v5h-5" />
  </svg>
)

const CloseIcon = () => (
  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
  </svg>
)

const StopIcon = () => (
  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden>
    <rect x="6" y="6" width="12" height="12" rx="1.5" />
  </svg>
)

const UNIVERSITY_ALIAS_MAP: Record<string, string[]> = {
  서울대학교: ['서울대학교', '서울대'],
  연세대학교: ['연세대학교', '연세대'],
  고려대학교: ['고려대학교', '고려대'],
  중앙대학교: ['중앙대학교', '중앙대'],
  성균관대학교: ['성균관대학교', '성균관대'],
  한양대학교: ['한양대학교', '한양대'],
  경희대학교: ['경희대학교', '경희대'],
  서강대학교: ['서강대학교', '서강대'],
  이화여자대학교: ['이화여자대학교', '이화여대'],
  한국외국어대학교: ['한국외국어대학교', '한국외대'],
  서울시립대학교: ['서울시립대학교', '서울시립대', '시립대'],
}

const dedupe = (items: string[]) => Array.from(new Set(items.filter((v) => String(v || '').trim())))

const detectUniversitiesFromQuery = (query: string) => {
  const normalized = String(query || '').trim()
  if (!normalized) return []
  const found: string[] = []
  for (const [university, aliases] of Object.entries(UNIVERSITY_ALIAS_MAP)) {
    if (aliases.some((alias) => normalized.includes(alias))) {
      found.push(university)
    }
  }
  return dedupe(found)
}

const buildDynamicResearchTitle = (query: string, universities: string[]) => {
  const q = String(query || '')
  const uniText = universities.length > 0 ? `${universities.join(', ')} 맞춤 ` : ''
  const hasRecommendation = /추천|제안|아이디어|주제/.test(q)
  const hasActivity = /탐구|활동|프로젝트|세특/.test(q)
  const hasInterview = /면접|질문|답변/.test(q)
  const hasHighSchool3 = /3학년|고3/.test(q)

  if (hasRecommendation && hasActivity) {
    const gradeText = hasHighSchool3 ? '3학년 ' : ''
    return `${uniText}${gradeText}탐구 활동 추천 리서치`
  }
  if (hasInterview) {
    return `${uniText}면접 대비 리서치`
  }
  return `${uniText}생기부 심층 분석 리서치`
}

const buildDynamicSteps = (query: string, universities: string[]): ResearchStepItem[] => {
  const q = String(query || '')
  const uniText = universities.length > 0 ? universities.join(', ') : ''
  const hasRecommendation = /추천|제안|아이디어|주제/.test(q)
  const hasActivity = /탐구|활동|프로젝트|세특/.test(q)
  const hasInterview = /면접|질문|답변/.test(q)
  const hasHighSchool3 = /3학년|고3/.test(q)

  const step1 = uniText
    ? `${uniText} 전형의 공식 평가 기준·인재상·가이드 근거를 수집합니다.`
    : '질문 주제와 연결되는 학생부 평가 기준·가이드 근거를 수집합니다.'

  const step2 = hasRecommendation && hasActivity
    ? `${hasHighSchool3 ? '3학년' : '현재'} 생기부 맥락에서 실행 가능한 탐구 활동 후보를 추출합니다.`
    : hasInterview
      ? '질문 의도에 맞는 면접 핵심 평가 포인트를 추출합니다.'
      : '생기부 항목별 근거와 질문 요구사항을 정밀 매칭합니다.'

  const step3 = hasRecommendation && hasActivity
    ? '후보 활동별 세특 반영 포인트와 기대 효과를 근거 기반으로 정리합니다.'
    : hasInterview
      ? '예상 질문과 답변 프레임을 생기부 원문 근거와 함께 구성합니다.'
      : '생기부 원문 근거를 매칭해 구조화된 리포트 초안을 작성합니다.'

  const step4 = hasRecommendation && hasActivity
    ? '활동 난이도·실행 가능성·대학 적합성을 교차 검증합니다.'
    : '학년·과목별 세특 분석을 확장하고 교차 검증합니다.'

  return [
    { id: 'school_record_router', label: step1 },
    { id: 'school_record_retrieval', label: step2 },
    { id: 'school_record_report', label: step3 },
    { id: 'school_record_deep_dive', label: step4 },
    { id: 'school_record_follow_up', label: '최종 리포트와 후속 실행 질문을 정리해 전달합니다.' },
  ]
}

export default function SchoolRecordResearchProgress({ logs, query, onStop }: SchoolRecordResearchProgressProps) {
  const [isFullscreen, setIsFullscreen] = useState(false)

  const parsedLogs = useMemo(() => logs.map(parseLog), [logs])

  const targetUniversities = useMemo(() => {
    const fromLogs: string[] = []
    for (const item of parsedLogs) {
      const candidates = item.detail?.target_universities
      if (Array.isArray(candidates)) {
        candidates.forEach((u) => {
          if (typeof u === 'string' && u.trim()) fromLogs.push(u.trim())
        })
      }
    }
    const fromQuery = detectUniversitiesFromQuery(String(query || ''))
    return dedupe([...fromLogs, ...fromQuery])
  }, [parsedLogs, query])

  const researchTitle = useMemo(
    () => buildDynamicResearchTitle(String(query || ''), targetUniversities),
    [query, targetUniversities]
  )

  const researchSteps = useMemo(
    () => buildDynamicSteps(String(query || ''), targetUniversities),
    [query, targetUniversities]
  )

  const activeStepIndex = useMemo(() => {
    let found = 0
    for (const item of parsedLogs) {
      const mapped = STEP_INDEX_BY_ID[item.step]
      if (typeof mapped === 'number') {
        found = Math.max(found, mapped)
      }
    }
    return found
  }, [parsedLogs])

  const progressPercent = useMemo(() => {
    const ratio = (activeStepIndex + 1) / researchSteps.length
    return Math.min(100, Math.max(8, Math.round(ratio * 100)))
  }, [activeStepIndex, researchSteps.length])

  const latestStatusText = useMemo(() => {
    for (let i = parsedLogs.length - 1; i >= 0; i -= 1) {
      const line = String(parsedLogs[i]?.message || '').trim()
      if (line) return line
    }
    return '리서치 중...'
  }, [parsedLogs])

  useEffect(() => {
    if (!isFullscreen) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prevOverflow
    }
  }, [isFullscreen])

  const renderStepIndicator = (state: 'done' | 'active' | 'pending') => {
    if (state === 'done') {
      return (
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[#0e6093] text-white">
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
        </span>
      )
    }

    if (state === 'active') {
      return <span className="inline-flex h-7 w-7 rounded-full border-[2.5px] border-slate-900 bg-white" />
    }

    return <span className="inline-flex h-7 w-7 rounded-full border-2 border-dashed border-slate-300 bg-white" />
  }

  const renderCard = (fullscreen: boolean) => (
    <div
      className={[
        'rounded-[26px] border border-slate-200 bg-white shadow-[0_1px_2px_rgba(16,24,40,0.05)]',
        fullscreen ? 'h-full overflow-y-auto px-8 py-8' : 'w-full max-w-[920px] px-5 py-6 sm:px-8 sm:py-8',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[13px] font-semibold tracking-wide text-[#0e6093]">리포트 리서치</p>
          <h3 className="mt-1 text-[22px] font-semibold leading-tight text-slate-900 sm:text-[30px]">
            {researchTitle}
          </h3>
          {query && (
            <p className="mt-2 line-clamp-2 max-w-[760px] text-sm text-slate-500">
              질문: {query}
            </p>
          )}
        </div>

        <button
          type="button"
          onClick={() => setIsFullscreen((prev) => !prev)}
          className="inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-slate-200 bg-white text-slate-700 transition hover:bg-slate-50"
          title={fullscreen ? '전체화면 닫기' : '전체화면으로 보기'}
          aria-label={fullscreen ? '전체화면 닫기' : '전체화면으로 보기'}
        >
          {fullscreen ? <CloseIcon /> : <ExpandIcon />}
        </button>
      </div>

      <div className="mt-8 space-y-5">
        {researchSteps.map((item, idx) => {
          let state: 'done' | 'active' | 'pending' = 'pending'
          if (idx < activeStepIndex) state = 'done'
          else if (idx === activeStepIndex) state = 'active'

          return (
            <div key={item.id} className="flex items-start gap-4">
              <div className="pt-0.5">{renderStepIndicator(state)}</div>
              <p
                className={[
                  'text-[19px] leading-[1.45] sm:text-[30px]',
                  state === 'pending' ? 'text-slate-500' : 'text-slate-900',
                ].join(' ')}
              >
                {item.label}
              </p>
            </div>
          )
        })}
      </div>

      <div className="mt-8">
        <p className="text-[22px] text-slate-500 sm:text-[34px]">리서치 중...</p>
        <div className="mt-4 flex items-center gap-3">
          <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
            <div
              className="relative h-full rounded-full bg-[#0e6093]"
              style={{ width: `${progressPercent}%` }}
            >
              <span className="absolute right-0 top-1/2 h-3.5 w-3.5 -translate-y-1/2 rounded-full bg-slate-900" />
            </div>
          </div>
          {onStop && (
            <button
              type="button"
              onClick={onStop}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-800 transition hover:bg-slate-200"
              title="생성 중지"
              aria-label="생성 중지"
            >
              <StopIcon />
            </button>
          )}
        </div>
        <p className="mt-2 text-sm text-slate-500">{latestStatusText}</p>
      </div>
    </div>
  )

  return (
    <>
      {renderCard(false)}

      {isFullscreen && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/50 p-4">
          <div className="h-[92vh] w-[min(1320px,96vw)]">{renderCard(true)}</div>
        </div>
      )}
    </>
  )
}
