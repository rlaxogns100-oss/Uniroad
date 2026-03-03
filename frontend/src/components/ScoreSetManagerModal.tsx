import { useEffect, useMemo, useRef, useState } from 'react'
import {
  listScoreSets,
  createScoreSet,
  updateScoreSet,
  deleteScoreSet,
  type ScoreSetItem,
} from '../api/client'

interface ScoreSetManagerModalProps {
  isOpen: boolean
  onClose: () => void
  sessionId: string
  token?: string
  onUseScoreSet?: (scoreSetId: string, scoreSetName: string) => void
  embedded?: boolean
}

const subjects = ['한국사', '국어', '수학', '영어', '탐구1', '탐구2', '제2외국어/한문']

const electiveOptionsMap: Record<string, string[]> = {
  국어: ['미응시', '화법과작문', '언어와매체'],
  수학: ['미응시', '확률과통계', '기하', '미적분'],
  영어: ['미응시', '영어'],
  탐구1: ['미응시', '한국지리', '윤리와사상', '생활과윤리', '사회문화', '정치와법', '경제', '세계사', '동아시아사', '세계지리', '물리학1', '물리학2', '화학1', '화학2', '생명과학1', '생명과학2', '지구과학1', '지구과학2'],
  탐구2: ['미응시', '한국지리', '윤리와사상', '생활과윤리', '사회문화', '정치와법', '경제', '세계사', '동아시아사', '세계지리', '물리학1', '물리학2', '화학1', '화학2', '생명과학1', '생명과학2', '지구과학1', '지구과학2'],
  '제2외국어/한문': ['미응시', '독일어1', '프랑스어1', '스페인어1', '중국어1', '일본어1', '러시아어1', '아랍어1', '베트남어1', '한문1'],
}

const DEFAULT_SCORE_SET: Record<string, any> = {
  한국사: { 등급: 2 },
  국어: { 선택과목: '화법과작문', 표준점수: 129, 백분위: 92, 등급: 2 },
  수학: { 선택과목: '확률과통계', 표준점수: 121, 백분위: 83, 등급: 3 },
  영어: { 선택과목: '영어', 등급: 2 },
  탐구1: { 선택과목: '생활과윤리', 표준점수: 61, 백분위: 83, 등급: 3 },
  탐구2: { 선택과목: '사회문화', 표준점수: 63, 백분위: 92, 등급: 2 },
  '제2외국어/한문': { 선택과목: '미응시' },
}

const normalizeTitle = (name: string): string => (name || '').replace(/^@/, '').slice(0, 10)

const cloneScores = (value: Record<string, any>): Record<string, any> => {
  try {
    return JSON.parse(JSON.stringify(value || {}))
  } catch {
    return {}
  }
}

const getElectiveValue = (subject: string, row: Record<string, any>) => {
  if (subject === '한국사') return '-'
  return row?.['선택과목'] ?? row?.['과목명'] ?? '미응시'
}

const readNumber = (value: any): number | null => {
  if (value === null || value === undefined || value === '') return null
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return null
  return parsed
}

const calculateAverageGrade = (scores: Record<string, any>): number | null => {
  const grades: number[] = []

  for (const subject of subjects) {
    const row = scores?.[subject] || {}
    const elective = getElectiveValue(subject, row)
    const isNoExam = subject !== '한국사' && elective === '미응시'
    if (isNoExam) continue

    const grade = readNumber(row['등급'])
    if (grade !== null && grade >= 1 && grade <= 9) {
      grades.push(grade)
    }
  }

  if (grades.length === 0) return null
  const avg = grades.reduce((sum, curr) => sum + curr, 0) / grades.length
  return Number(avg.toFixed(1))
}

const formatAverageLabel = (scores: Record<string, any>): string => {
  const avg = calculateAverageGrade(scores)
  if (avg === null) return '미입력'
  return `${avg}등급`
}

const resolveNextScoreIndex = (items: ScoreSetItem[]): number => {
  const indices = items
    .map((item) => normalizeTitle(item.name).match(/^새성적_(\d+)$/)?.[1])
    .map((v) => (v ? Number(v) : null))
    .filter((v): v is number => v !== null && Number.isFinite(v))

  if (indices.length === 0) return 0
  return Math.max(...indices) + 1
}

export default function ScoreSetManagerModal({
  isOpen,
  onClose,
  sessionId,
  token,
  onUseScoreSet,
  embedded = false,
}: ScoreSetManagerModalProps) {
  const [items, setItems] = useState<ScoreSetItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [title, setTitle] = useState('새성적_0')
  const [scores, setScores] = useState<Record<string, any>>(cloneScores(DEFAULT_SCORE_SET))
  const [view, setView] = useState<'dashboard' | 'input'>('dashboard')
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [dirty, setDirty] = useState(false)
  const [representativeId, setRepresentativeId] = useState<string | null>(null)

  const titleRef = useRef(title)
  const scoresRef = useRef(scores)
  const newScoreIndexRef = useRef(0)
  const editorRef = useRef<HTMLDivElement>(null)
  const blurSaveTimerRef = useRef<number | null>(null)

  titleRef.current = title
  scoresRef.current = scores

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId) || null,
    [items, selectedId]
  )

  const dashboardItems = useMemo(() => {
    return [...items].sort(
      (a, b) => new Date(b.updated_at || b.created_at || 0).getTime() - new Date(a.updated_at || a.created_at || 0).getTime()
    )
  }, [items])

  const fallbackRepresentativeId = useMemo(() => {
    if (items.length === 0) return null
    return [...items].sort(
      (a, b) => new Date(a.created_at || a.updated_at || 0).getTime() - new Date(b.created_at || b.updated_at || 0).getTime()
    )[0]?.id || null
  }, [items])

  const resolvedRepresentativeId = useMemo(() => {
    if (representativeId && items.some((item) => item.id === representativeId)) return representativeId
    return fallbackRepresentativeId
  }, [representativeId, fallbackRepresentativeId, items])

  const selectedAverageLabel = useMemo(() => formatAverageLabel(scores), [scores])

  const load = async () => {
    setIsLoading(true)
    setError('')
    try {
      const rows = await listScoreSets(sessionId, token)
      setItems(rows)
      newScoreIndexRef.current = resolveNextScoreIndex(rows)

      if (rows.length === 0) {
        setSelectedId(null)
        setTitle(`새성적_${newScoreIndexRef.current}`)
        setScores(cloneScores(DEFAULT_SCORE_SET))
        setView('dashboard')
        return
      }

      const keepId = selectedId && rows.some((item) => item.id === selectedId) ? selectedId : rows[0].id
      const keepItem = rows.find((item) => item.id === keepId) || rows[0]

      setSelectedId(keepItem.id)
      setTitle(normalizeTitle(keepItem.name))
      setScores(cloneScores(keepItem.scores || {}))
    } catch (e: any) {
      const msg = e?.response?.data?.detail
      const isNotFound = e?.response?.status === 404 || (typeof msg === 'string' && msg.toLowerCase().includes('not found'))
      if (isNotFound) {
        setItems([])
        setError('')
        setSelectedId(null)
        newScoreIndexRef.current = 0
        setTitle('새성적_0')
        setScores(cloneScores(DEFAULT_SCORE_SET))
        setView('dashboard')
      } else {
        setError(msg || '성적 목록을 불러오지 못했습니다.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!isOpen && !embedded) return
    void load()
  }, [isOpen, embedded, sessionId, token])

  useEffect(() => {
    const key = `uniroad_representative_score_${sessionId}`
    try {
      setRepresentativeId(localStorage.getItem(key))
    } catch {
      setRepresentativeId(null)
    }
  }, [sessionId])

  useEffect(() => {
    if (!selectedId || !dirty) return

    const timer = setTimeout(async () => {
      const safeTitle = normalizeTitle(titleRef.current)
      const payloadName = `@${safeTitle}`.trim()
      if (!payloadName || payloadName === '@') return

      setIsSaving(true)
      setError('')
      try {
        await updateScoreSet(selectedId, sessionId, payloadName, scoresRef.current, token)
        setItems((prev) =>
          prev.map((item) =>
            item.id === selectedId
              ? { ...item, name: payloadName, scores: cloneScores(scoresRef.current) }
              : item
          )
        )
        setDirty(false)
      } catch (e: any) {
        setError(e?.response?.data?.detail || '자동 저장 중 오류가 발생했습니다.')
      } finally {
        setIsSaving(false)
      }
    }, 700)

    return () => clearTimeout(timer)
  }, [selectedId, dirty, sessionId, token])

  const setRepresentativeScore = (scoreSetId: string) => {
    const key = `uniroad_representative_score_${sessionId}`
    try {
      localStorage.setItem(key, scoreSetId)
    } catch {
      // ignore
    }
    setRepresentativeId(scoreSetId)
  }

  const selectItemForInput = (item: ScoreSetItem) => {
    setSelectedId(item.id)
    setTitle(normalizeTitle(item.name))
    setScores(cloneScores(item.scores || {}))
    setDirty(false)
    setError('')
    setView('input')
  }

  const createNew = async () => {
    if (isSaving) return

    const existing = new Set(items.map((item) => normalizeTitle(item.name)))
    let index = newScoreIndexRef.current
    while (existing.has(`새성적_${index}`)) index += 1
    newScoreIndexRef.current = index + 1

    const newTitle = `새성적_${index}`
    const newScores = cloneScores(DEFAULT_SCORE_SET)

    setIsSaving(true)
    setError('')
    try {
      const saved = await createScoreSet(sessionId, `@${newTitle}`, newScores, token)
      await load()
      setSelectedId(saved.id)
      setTitle(normalizeTitle(saved.name))
      setScores(cloneScores(saved.scores || {}))
      setDirty(false)
      setView('input')
    } catch (e: any) {
      setError(e?.response?.data?.detail || '새 성적 추가 중 오류가 발생했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const deleteById = async (id: string) => {
    if (!confirm('이 성적을 삭제할까요?')) return

    setIsSaving(true)
    setError('')
    try {
      await deleteScoreSet(id, sessionId, token)
      if (selectedId === id) {
        setView('dashboard')
        setSelectedId(null)
      }
      await load()
    } catch (e: any) {
      setError(e?.response?.data?.detail || '성적 삭제 중 오류가 발생했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const saveNow = async () => {
    if (!selectedId) return
    if (!dirty) return

    const safeTitle = normalizeTitle(title)
    if (!safeTitle) {
      setError('성적 이름을 입력해 주세요.')
      return
    }

    setIsSaving(true)
    setError('')
    try {
      const payloadName = `@${safeTitle}`
      await updateScoreSet(selectedId, sessionId, payloadName, scores, token)
      setItems((prev) =>
        prev.map((item) =>
          item.id === selectedId
            ? { ...item, name: payloadName, scores: cloneScores(scores) }
            : item
        )
      )
      setDirty(false)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '성적 저장 중 오류가 발생했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const scheduleSaveOnBlur = () => {
    if (!selectedId || !dirty) return
    if (blurSaveTimerRef.current) {
      window.clearTimeout(blurSaveTimerRef.current)
    }
    blurSaveTimerRef.current = window.setTimeout(() => {
      const activeEl = document.activeElement as HTMLElement | null
      if (editorRef.current && activeEl && editorRef.current.contains(activeEl)) {
        return
      }
      void saveNow()
    }, 80)
  }

  const setVal = (subject: string, key: string, value: any) => {
    setDirty(true)
    setScores((prev) => ({
      ...prev,
      [subject]: { ...(prev?.[subject] || {}), [key]: value },
    }))
  }

  useEffect(() => {
    return () => {
      if (blurSaveTimerRef.current) {
        window.clearTimeout(blurSaveTimerRef.current)
      }
    }
  }, [])

  if (!isOpen && !embedded) return null

  return (
    <div
      className={embedded ? 'w-full h-full min-h-0 flex flex-col bg-[#F5F6F8]' : 'fixed inset-0 z-[80] bg-black/30 flex items-center justify-center p-4'}
      onClick={embedded ? undefined : onClose}
    >
      <div
        className={embedded ? 'w-full h-full min-h-0 flex flex-col bg-[#F5F6F8]' : 'w-full max-w-6xl h-[88vh] rounded-3xl overflow-hidden bg-[#F5F6F8] shadow-2xl flex flex-col'}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-4 sm:px-7 py-3.5 sm:py-5 bg-[#F5F6F8] border-b border-[#E9EBEF] shrink-0 flex items-center justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-base sm:text-[20px] font-bold text-gray-900">모의고사 성적 관리</h3>
            <p className="text-xs sm:text-sm text-gray-500 mt-0.5 truncate">필요한 성적만 간단하게 저장하고 바로 활용하세요</p>
          </div>
          <button
            type="button"
            className="shrink-0 w-10 h-10 min-h-[44px] min-w-[44px] rounded-full bg-white text-gray-500 hover:text-gray-700 active:bg-gray-100 transition-colors flex items-center justify-center touch-manipulation"
            onClick={onClose}
            aria-label="닫기"
          >
            ×
          </button>
        </div>

        {error && (
          <div className="mx-5 sm:mx-7 mt-3 rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600">
            {error}
          </div>
        )}

        {view === 'dashboard' ? (
          <div className="flex-1 min-h-0 overflow-y-auto px-5 sm:px-7 py-5 sm:py-6">
            <div className="mb-4 sm:mb-5 flex items-end justify-between">
              <div>
                <p className="text-[20px] sm:text-[24px] font-bold text-gray-900">내 점수로 어디 갈 수 있을까?</p>
                <p className="text-sm text-gray-500 mt-1">성적 카드를 눌러서 수정하거나 바로 대학 추천을 받아보세요.</p>
              </div>
              {isSaving && <span className="text-xs text-[#0050FF] font-medium">저장 중...</span>}
            </div>

            {isLoading ? (
              <div className="rounded-3xl bg-white px-5 py-10 text-sm text-gray-500">성적 목록을 불러오는 중이에요...</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4">
                <button
                  type="button"
                  onClick={createNew}
                  disabled={isSaving}
                  className="group min-h-[180px] rounded-3xl border-2 border-dashed border-[#C9D7FF] bg-white transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_10px_28px_rgba(0,80,255,0.12)]"
                >
                  <div className="h-full flex flex-col items-center justify-center">
                    <div className="w-12 h-12 rounded-full bg-[#EAF1FF] text-[#0050FF] text-3xl leading-none flex items-center justify-center group-hover:scale-105 transition-transform">+</div>
                    <p className="mt-3 text-[15px] font-semibold text-gray-900">새 성적 추가</p>
                    <p className="text-xs text-gray-500 mt-1">기본값으로 빠르게 시작해요</p>
                  </div>
                </button>

                {dashboardItems.map((item) => {
                  const avgLabel = formatAverageLabel(item.scores || {})
                  const isRepresentative = resolvedRepresentativeId === item.id
                  const isSelected = selectedId === item.id

                  return (
                    <div
                      key={item.id}
                      onClick={() => selectItemForInput(item)}
                      className={`min-h-[180px] rounded-3xl bg-white p-4 sm:p-5 cursor-pointer transition-all duration-200 hover:-translate-y-0.5 hover:shadow-[0_10px_28px_rgba(17,24,39,0.08)] ${
                        isSelected ? 'ring-2 ring-[#0050FF]/40 shadow-[0_8px_24px_rgba(0,80,255,0.16)]' : ''
                      }`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-[15px] font-semibold text-gray-900 truncate">{item.name}</p>
                          <p className="text-xs text-gray-500 mt-1">최근 업데이트 {new Date(item.updated_at || item.created_at || Date.now()).toLocaleDateString('ko-KR')}</p>
                        </div>
                        {isRepresentative && (
                          <span className="shrink-0 rounded-full bg-[#EAF1FF] px-2.5 py-1 text-[11px] font-semibold text-[#0050FF]">대표</span>
                        )}
                      </div>

                      <div className="mt-5">
                        <p className="text-xs text-gray-500">평균 등급</p>
                        <p className="text-[32px] leading-[1.1] font-bold text-gray-900 mt-1">{avgLabel}</p>
                      </div>

                      <div className="mt-5 grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            setRepresentativeScore(item.id)
                          }}
                          className={`h-10 rounded-xl text-sm font-semibold transition-colors ${
                            isRepresentative
                              ? 'bg-[#EAF1FF] text-[#0050FF]'
                              : 'bg-[#F5F6F8] text-gray-700 hover:bg-[#EDEFF3]'
                          }`}
                        >
                          {isRepresentative ? '대표 성적' : '대표로 설정'}
                        </button>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            onUseScoreSet?.(item.id, item.name)
                          }}
                          className="h-10 rounded-xl bg-[#0050FF] text-white text-sm font-semibold hover:bg-[#0043D6] transition-colors"
                        >
                          대학 보기
                        </button>
                      </div>

                      <div className="mt-2">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            void deleteById(item.id)
                          }}
                          className="text-xs text-gray-400 hover:text-red-500 transition-colors"
                        >
                          삭제
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        ) : (
          <div className="flex-1 min-h-0 overflow-y-auto px-5 sm:px-7 py-5 sm:py-6">
            <div className="rounded-3xl bg-white p-4 sm:p-5 mb-4 sm:mb-5 transition-all duration-200">
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setView('dashboard')}
                  className="h-9 px-3 rounded-full bg-[#F5F6F8] text-sm font-semibold text-gray-700 hover:bg-[#ECEFF4] transition-colors"
                >
                  ← 목록으로
                </button>
                <div className="flex items-center gap-2">
                  {selectedId && (
                    <button
                      type="button"
                      onClick={() => setRepresentativeScore(selectedId)}
                      className={`h-9 px-3 rounded-full text-sm font-semibold transition-colors ${
                        resolvedRepresentativeId === selectedId
                          ? 'bg-[#EAF1FF] text-[#0050FF]'
                          : 'bg-[#F5F6F8] text-gray-700 hover:bg-[#ECEFF4]'
                      }`}
                    >
                      {resolvedRepresentativeId === selectedId ? '대표 성적' : '대표로 설정'}
                    </button>
                  )}
                  {selectedItem && onUseScoreSet && (
                    <button
                      type="button"
                      onClick={() => onUseScoreSet(selectedItem.id, selectedItem.name)}
                      className="h-9 px-4 rounded-full bg-[#0050FF] text-white text-sm font-semibold hover:bg-[#0043D6] transition-colors"
                    >
                      대학 보기
                    </button>
                  )}
                </div>
              </div>

              <div className="mt-4">
                <p className="text-xs text-gray-500">성적 이름</p>
                <div className="mt-1 flex items-center gap-2">
                  <span className="text-[20px] font-semibold text-[#0050FF]">@</span>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => {
                      setDirty(true)
                      setTitle(e.target.value.replace(/^@/, '').slice(0, 10))
                    }}
                    className="w-full text-[20px] font-semibold text-gray-900 bg-transparent outline-none placeholder:text-gray-300"
                    placeholder="성적 이름"
                  />
                </div>
              </div>

              <div className="mt-4 rounded-2xl bg-[#F5F6F8] px-4 py-3">
                <p className="text-xs text-gray-500">현재 평균 등급</p>
                <p className="mt-1 text-[28px] leading-none font-bold text-gray-900">{selectedAverageLabel}</p>
              </div>
            </div>

            <div ref={editorRef} className="rounded-3xl bg-[#FFFFFF] p-4 sm:p-5 transition-all duration-200">
              <div className="mb-4">
                <p className="text-[16px] font-bold text-[#000000]">과목별 성적을 한 번에 입력해 주세요</p>
                <p className="text-sm text-[#6B7684] mt-1">셀을 클릭해 바로 수정하고, 포커스를 벗어나면 자동 저장돼요.</p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] border-separate [border-spacing:0_10px]">
                  <thead>
                    <tr>
                      <th className="px-4 pb-1 text-left text-xs font-semibold text-[#6B7684]">과목</th>
                      <th className="px-3 pb-1 text-left text-xs font-semibold text-[#6B7684]">선택과목</th>
                      <th className="px-3 pb-1 text-left text-xs font-semibold text-[#6B7684]">표준점수</th>
                      <th className="px-3 pb-1 text-left text-xs font-semibold text-[#6B7684]">백분위</th>
                      <th className="px-3 pb-1 text-left text-xs font-semibold text-[#6B7684]">등급</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subjects.map((subject) => {
                      const row = scores?.[subject] || {}
                      const electiveValue = getElectiveValue(subject, row)
                      const isHistory = subject === '한국사'
                      const isNoExamRow = !isHistory && electiveValue === '미응시'

                      return (
                        <tr key={subject} className="bg-[#F8FAFD]">
                          <td className="px-4 py-3 rounded-l-2xl">
                            <p className="text-[14px] font-semibold text-[#000000]">{subject}</p>
                          </td>
                          <td className="px-3 py-3">
                            {isHistory ? (
                              <span className="text-sm text-[#6B7684]">-</span>
                            ) : (
                              <select
                                value={electiveValue}
                                onChange={(e) => {
                                  const nextValue = e.target.value
                                  setVal(subject, '선택과목', nextValue)
                                  if (nextValue === '미응시') {
                                    setVal(subject, '표준점수', null)
                                    setVal(subject, '백분위', null)
                                    setVal(subject, '등급', null)
                                  }
                                }}
                                onBlur={scheduleSaveOnBlur}
                                className="h-11 w-full rounded-xl border border-transparent bg-[#FFFFFF] px-3 text-[14px] font-medium text-[#000000] focus:outline-none focus:border-[#0050FF] focus:ring-2 focus:ring-[#0050FF]/15"
                              >
                                {(electiveOptionsMap[subject] || ['미응시']).map((option) => (
                                  <option key={option} value={option}>
                                    {option}
                                  </option>
                                ))}
                              </select>
                            )}
                          </td>
                          <td className="px-3 py-3">
                            {isHistory || isNoExamRow ? (
                              <span className="text-sm text-[#6B7684]">-</span>
                            ) : (
                              <input
                                type="number"
                                min={0}
                                max={200}
                                value={row['표준점수'] ?? ''}
                                onChange={(e) => setVal(subject, '표준점수', e.target.value === '' ? null : Number(e.target.value))}
                                onBlur={scheduleSaveOnBlur}
                                className="h-11 w-full rounded-xl border border-transparent bg-[#FFFFFF] px-3 text-[14px] font-semibold text-[#000000] focus:outline-none focus:border-[#0050FF] focus:ring-2 focus:ring-[#0050FF]/15"
                                placeholder="-"
                              />
                            )}
                          </td>
                          <td className="px-3 py-3">
                            {isHistory || isNoExamRow ? (
                              <span className="text-sm text-[#6B7684]">-</span>
                            ) : (
                              <input
                                type="number"
                                min={0}
                                max={100}
                                value={row['백분위'] ?? ''}
                                onChange={(e) => setVal(subject, '백분위', e.target.value === '' ? null : Number(e.target.value))}
                                onBlur={scheduleSaveOnBlur}
                                className="h-11 w-full rounded-xl border border-transparent bg-[#FFFFFF] px-3 text-[14px] font-semibold text-[#000000] focus:outline-none focus:border-[#0050FF] focus:ring-2 focus:ring-[#0050FF]/15"
                                placeholder="-"
                              />
                            )}
                          </td>
                          <td className="px-3 py-3 rounded-r-2xl">
                            {isNoExamRow ? (
                              <span className="text-sm text-[#6B7684]">-</span>
                            ) : (
                              <input
                                type="number"
                                min={1}
                                max={9}
                                value={row['등급'] ?? ''}
                                onChange={(e) => setVal(subject, '등급', e.target.value === '' ? null : Number(e.target.value))}
                                onBlur={scheduleSaveOnBlur}
                                className="h-11 w-full rounded-xl border border-transparent bg-[#FFFFFF] px-3 text-[14px] font-semibold text-[#000000] focus:outline-none focus:border-[#0050FF] focus:ring-2 focus:ring-[#0050FF]/15"
                                placeholder="-"
                              />
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <div className="mt-4 flex items-center justify-between gap-2">
                <p className="text-xs text-[#6B7684]">
                  {dirty ? '변경사항이 있어요. 포커스를 벗어나면 자동 저장됩니다.' : '최신 상태로 저장되어 있어요.'}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void saveNow()}
                    className="h-9 px-3 rounded-full bg-white border border-[#E6E8EC] text-sm font-semibold text-[#000000] hover:bg-[#F8FAFC]"
                  >
                    지금 저장
                  </button>
                  {selectedId && (
                    <button
                      type="button"
                      onClick={() => void deleteById(selectedId)}
                      className="h-9 px-3 rounded-full bg-white border border-red-100 text-sm font-semibold text-red-500 hover:bg-red-50"
                    >
                      삭제
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
