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
  /** true면 모달이 아닌 패널 내부에 임베드되어 렌더 (오버레이 없음) */
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

const normalizeTitle = (name: string) => (name || '').replace(/^@/, '').slice(0, 10)
const getElectiveValue = (subject: string, row: Record<string, any>) => {
  if (subject === '한국사') return '-'
  return row['선택과목'] ?? row['과목명'] ?? '미응시'
}

/** 과목별 요약 값 표시 (등급 우선, 없으면 표준점수/백분위) */
const getSubjectDisplay = (scores: Record<string, any>, subject: string): string => {
  const row = scores?.[subject] || {}
  const 등급 = row['등급']
  const 표준점수 = row['표준점수']
  const 백분위 = row['백분위']
  if (등급 !== null && 등급 !== undefined && 등급 !== '') return `${등급}등`
  if (표준점수 !== null && 표준점수 !== undefined && 표준점수 !== '') return `${표준점수}`
  if (백분위 !== null && 백분위 !== undefined && 백분위 !== '') return `${백분위}%`
  return '-'
}

/** 기본 성적 데이터 (@내성적2) - 성적 없을 때 보여줄 기본값 */
const DEFAULT_SCORE_SET: Record<string, any> = {
  '한국사': { '등급': 2 },
  '국어': { '선택과목': '화법과작문', '표준점수': 129, '백분위': 92, '등급': 2 },
  '수학': { '선택과목': '확률과통계', '표준점수': 121, '백분위': 83, '등급': 3 },
  '영어': { '선택과목': '영어', '등급': 2 },
  '탐구1': { '선택과목': '생활과윤리', '표준점수': 61, '백분위': 83, '등급': 3 },
  '탐구2': { '선택과목': '사회문화', '표준점수': 63, '백분위': 92, '등급': 2 },
  '제2외국어/한문': { '선택과목': '미응시' },
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
  const [title, setTitle] = useState('내성적1')
  const [scores, setScores] = useState<Record<string, any>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  /** 여러 개 선택 후 일괄 삭제용 체크된 id 목록 */
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set())
  /** 왼쪽 사이드바 검색/필터 */
  const [sidebarFilter, setSidebarFilter] = useState('')
  /** 테이블 뷰 모드 (grid | list) */
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')
  /** 새 성적 클릭 시 제목용 인덱스 (새성적_0, 새성적_1, ...) */
  const newScoreIndexRef = useRef(0)
  /** 사이드바 행 메뉴(⋮) 열린 id */
  const [sidebarMenuOpenId, setSidebarMenuOpenId] = useState<string | null>(null)
  /** 사용자가 지정한 대표 성적 id (localStorage에 저장, 세션별) */
  const [representativeId, setRepresentativeId] = useState<string | null>(null)
  /** 편집 후 자동 저장용 dirty 플래그 */
  const [dirty, setDirty] = useState(false)
  const titleRef = useRef(title)
  const scoresRef = useRef(scores)
  titleRef.current = title
  scoresRef.current = scores

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId) || null,
    [items, selectedId]
  )

  /** 대표 성적: 사용자 지정 > 없으면 가장 먼저 만든 성적(updated_at 기준) */
  const firstCreatedItem = useMemo(() => {
    if (items.length === 0) return null
    const byId = items.find((i) => i.id === representativeId)
    if (byId) return byId
    return [...items].sort((a, b) => new Date(a.updated_at || 0).getTime() - new Date(b.updated_at || 0).getTime())[0]
  }, [items, representativeId])

  const filteredSidebarItems = useMemo(() => {
    let list = [...items]
    if (sidebarFilter.trim()) {
      const ft = sidebarFilter.toLowerCase()
      list = list.filter((i) => i.name.toLowerCase().includes(ft))
    }
    // 최근 생성순 정렬
    list.sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())
    return list
  }, [items, sidebarFilter])

  const load = async () => {
    setIsLoading(true)
    setError('')
    try {
      const rows = await listScoreSets(sessionId, token)
      setItems(rows)
      setCheckedIds(new Set())
      if (rows.length > 0) {
        const first = rows[0]
        setSelectedId(first.id)
        setTitle(normalizeTitle(first.name))
        setScores(first.scores || {})
        newScoreIndexRef.current = 0
      } else {
        // 성적 없을 때 기본값 + 새성적_0
        setSelectedId(null)
        setTitle('새성적_0')
        setScores(DEFAULT_SCORE_SET)
        newScoreIndexRef.current = 1
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || '성적 목록을 불러오지 못했습니다.')
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

  /** 편집 시 디바운스 자동 저장 */
  useEffect(() => {
    if (!selectedId || !dirty) return
    const timer = setTimeout(async () => {
      const name = `@${normalizeTitle(titleRef.current)}`.trim()
      if (!name || name === '@') return
      setIsSaving(true)
      setError('')
      try {
        await updateScoreSet(selectedId, sessionId, name, scoresRef.current, token)
        setDirty(false)
      } catch (e: any) {
        setError(e?.response?.data?.detail || '자동 저장 중 오류가 발생했습니다.')
      } finally {
        setIsSaving(false)
      }
    }, 800)
    return () => clearTimeout(timer)
  }, [selectedId, dirty, sessionId, token])

  const setRepresentativeScore = (scoreSetId: string) => {
    const key = `uniroad_representative_score_${sessionId}`
    try {
      localStorage.setItem(key, scoreSetId)
      setRepresentativeId(scoreSetId)
    } catch {
      // ignore
    }
  }

  const selectItem = (item: ScoreSetItem) => {
    setSelectedId(item.id)
    setTitle(normalizeTitle(item.name))
    setScores(item.scores || {})
    setDirty(false)
    setError('')
  }

  /** 새 성적 클릭 시 즉시 생성·저장 후 해당 항목 선택 */
  const createNew = async () => {
    const newTitle = `새성적_${newScoreIndexRef.current}`
    newScoreIndexRef.current += 1
    const newScores = JSON.parse(JSON.stringify(DEFAULT_SCORE_SET))
    const payloadName = `@${newTitle}`
    setIsSaving(true)
    setError('')
    try {
      const saved = await createScoreSet(sessionId, payloadName, newScores, token)
      await load()
      setSelectedId(saved.id)
      setTitle(normalizeTitle(saved.name))
      setScores(saved.scores || {})
      setDirty(false)
    } catch (e: any) {
      setError(e?.response?.data?.detail || '성적 생성 중 오류가 발생했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const setVal = (subject: string, key: string, value: any) => {
    setDirty(true)
    setScores((prev) => ({
      ...prev,
      [subject]: { ...(prev?.[subject] || {}), [key]: value },
    }))
  }

  const hasAnyScore = Object.values(scores || {}).some((row: any) => {
    if (!row || typeof row !== 'object') return false
    return row['표준점수'] !== null && row['표준점수'] !== undefined && row['표준점수'] !== '' ||
      row['백분위'] !== null && row['백분위'] !== undefined && row['백분위'] !== '' ||
      row['등급'] !== null && row['등급'] !== undefined && row['등급'] !== ''
  })

  const onSave = async () => {
    const safeTitle = normalizeTitle(title)
    if (!safeTitle) {
      setError('성적 이름을 입력해 주세요.')
      return
    }
    if (!hasAnyScore) {
      setError('최소 1개 과목 점수를 입력해 주세요.')
      return
    }

    setIsSaving(true)
    setError('')
    try {
      const payloadName = `@${safeTitle}`
      const saved = selectedId
        ? await updateScoreSet(selectedId, sessionId, payloadName, scores, token)
        : await createScoreSet(sessionId, payloadName, scores, token)
      await load()
      setSelectedId(saved.id)
      setTitle(normalizeTitle(saved.name))
      setScores(saved.scores || {})
    } catch (e: any) {
      setError(e?.response?.data?.detail || '성적 저장 중 오류가 발생했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const onDelete = async () => {
    if (!selectedId) return
    if (!confirm('선택한 성적을 삭제할까요?')) return
    setIsSaving(true)
    setError('')
    try {
      await deleteScoreSet(selectedId, sessionId, token)
      await load()
    } catch (e: any) {
      setError(e?.response?.data?.detail || '성적 삭제 중 오류가 발생했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  const toggleChecked = (id: string) => {
    setCheckedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const onDeleteChecked = async () => {
    if (checkedIds.size === 0) return
    if (!confirm(`선택한 ${checkedIds.size}개 성적을 삭제할까요?`)) return
    setIsSaving(true)
    setError('')
    try {
      await Promise.all(
        Array.from(checkedIds).map((id) => deleteScoreSet(id, sessionId, token))
      )
      setCheckedIds(new Set())
      await load()
    } catch (e: any) {
      setError(e?.response?.data?.detail || '성적 삭제 중 오류가 발생했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  /** 사이드바에서 해당 성적 한 건 삭제 */
  const deleteItemById = async (id: string) => {
    setSidebarMenuOpenId(null)
    if (!confirm('이 성적을 삭제할까요?')) return
    setIsSaving(true)
    setError('')
    try {
      await deleteScoreSet(id, sessionId, token)
      await load()
    } catch (e: any) {
      setError(e?.response?.data?.detail || '성적 삭제 중 오류가 발생했습니다.')
    } finally {
      setIsSaving(false)
    }
  }

  if (!isOpen && !embedded) return null

  return (
    <div
      className={embedded ? 'bg-white w-full h-full flex flex-col min-h-0 rounded-xl overflow-hidden' : 'fixed inset-0 z-[80] bg-black/40 flex items-center justify-center p-4'}
      onClick={embedded ? undefined : onClose}
    >
      <div
        className={embedded ? 'bg-white w-full h-full flex flex-col min-h-0 rounded-xl overflow-hidden' : 'bg-white w-full max-w-6xl rounded-xl shadow-xl max-h-[90vh] overflow-hidden flex flex-col'}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b flex items-center justify-between bg-white shrink-0">
          <h3 className="text-lg font-bold text-gray-900">모의고사 성적 관리</h3>
          <button className="text-gray-500 hover:text-gray-700 text-2xl leading-none" onClick={onClose}>×</button>
        </div>

        {/* Main 2-Panel Layout */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Sidebar - Table List (Supabase style) */}
          <div className="w-64 border-r bg-gray-50 flex flex-col">
            {/* 새 성적 버튼 (성적 검색 상단) */}
            <div className="px-3 pt-3 pb-1 bg-white">
              <button
                type="button"
                onClick={createNew}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-md bg-emerald-600 text-white text-sm hover:bg-emerald-700 font-medium"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                새 성적
              </button>
            </div>
            {/* Sidebar Search */}
            <div className="px-3 pt-1 pb-3 bg-white">
              <div className="relative">
                <input
                  type="text"
                  placeholder="성적 검색..."
                  value={sidebarFilter}
                  onChange={(e) => setSidebarFilter(e.target.value)}
                  className="w-full px-3 py-2 pl-9 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-emerald-500"
                />
                <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
            </div>

            {/* Table List */}
            <div className="flex-1 overflow-y-auto">
              <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                성적 목록
              </div>
              {isLoading ? (
                <div className="px-3 py-2 text-sm text-gray-500">불러오는 중...</div>
              ) : filteredSidebarItems.length === 0 ? (
                <div className="px-3 py-2">
                  {sidebarFilter ? (
                    <div className="text-sm text-gray-500">검색 결과 없음</div>
                  ) : (
                    <div className="text-sm text-gray-400">저장된 성적 없음</div>
                  )}
                </div>
              ) : (
                <div className="space-y-0.5 px-2 pb-2">
                  {filteredSidebarItems.map((item) => {
                    const isSelected = selectedId === item.id
                    const isMenuOpen = sidebarMenuOpenId === item.id
                    return (
                      <div
                        key={item.id}
                        className={`group flex items-center gap-2 px-3 py-2 rounded-md transition-colors ${
                          isSelected
                            ? 'bg-emerald-100 text-emerald-900'
                            : 'hover:bg-gray-100 text-gray-700'
                        }`}
                      >
                        <div
                          onClick={() => selectItem(item)}
                          className="flex-1 min-w-0 truncate text-sm font-medium cursor-pointer"
                        >
                          {item.name}
                        </div>
                        <div className="relative shrink-0">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              setSidebarMenuOpenId(isMenuOpen ? null : item.id)
                            }}
                            className="p-1 rounded hover:bg-gray-200/80 text-gray-600 flex items-center justify-center"
                            aria-label="메뉴"
                          >
                            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
                              <circle cx="12" cy="5" r="1.5" />
                              <circle cx="12" cy="12" r="1.5" />
                              <circle cx="12" cy="19" r="1.5" />
                            </svg>
                          </button>
                          {isMenuOpen && (
                            <>
                              <div
                                className="fixed inset-0 z-10"
                                aria-hidden
                                onClick={() => setSidebarMenuOpenId(null)}
                              />
                              <div className="absolute right-0 top-full mt-1 py-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 min-w-[120px]">
                                <button
                                  type="button"
                                  onClick={() => {
                                    setRepresentativeScore(item.id)
                                    setSidebarMenuOpenId(null)
                                  }}
                                  className="w-full px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100"
                                >
                                  대표 성적 설정
                                </button>
                                {onUseScoreSet && (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      onUseScoreSet(item.id, item.name)
                                      setSidebarMenuOpenId(null)
                                    }}
                                    className="w-full px-3 py-1.5 text-left text-sm text-gray-700 hover:bg-gray-100"
                                  >
                                    이 성적 사용
                                  </button>
                                )}
                                <button
                                  type="button"
                                  onClick={() => deleteItemById(item.id)}
                                  className="w-full px-3 py-1.5 text-left text-sm text-red-600 hover:bg-red-50"
                                >
                                  삭제
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Right Panel - Data View */}
          <div className="flex-1 flex flex-col bg-white overflow-hidden">
            {/* Table Header / Tabs */}
            <div className="border-b bg-white flex items-center gap-1 px-4 py-2">
              <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-md text-sm font-medium text-gray-700 min-w-0">
                <svg className="w-4 h-4 text-gray-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7-4h14M4 6h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V8a2 2 0 012-2z" />
                </svg>
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="text-gray-500 shrink-0">@</span>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => {
                      setDirty(true)
                      setTitle(e.target.value.replace(/^@/, '').slice(0, 10))
                    }}
                    className="bg-transparent border-none outline-none text-gray-700 font-medium min-w-[4rem] w-28 max-w-[8rem] focus:ring-0 p-0 placeholder:text-gray-400"
                    placeholder="성적이름"
                  />
                </div>
                {selectedId && firstCreatedItem?.id === selectedId && (
                  <span className="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded ml-1 shrink-0">대표 성적</span>
                )}
              </div>
              <div className="flex-1" />
              {selectedItem && onUseScoreSet && (
                <button
                  type="button"
                  onClick={() => onUseScoreSet(selectedItem.id, selectedItem.name)}
                  className="px-3 py-1.5 rounded-md bg-indigo-600 text-white text-sm hover:bg-indigo-700 font-medium"
                >
                  이 성적 사용
                </button>
              )}
              {!selectedId && (
                <button
                  type="button"
                  disabled
                  className="px-3 py-1.5 rounded-md bg-gray-300 text-white text-sm font-medium cursor-not-allowed"
                  title="저장 후 사용 가능합니다"
                >
                  저장 후 사용
                </button>
              )}
            </div>

            {/* Toolbar */}
            <div className="px-4 py-2 border-b bg-gray-50 flex items-center gap-3">
              <div className="flex items-center gap-2">
                <button className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200 rounded-md flex items-center gap-1">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                  </svg>
                  필터
                </button>
                <button className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-200 rounded-md flex items-center gap-1">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                  정렬
                </button>
              </div>
              <div className="flex-1" />
              <div className="flex items-center gap-1 bg-gray-200 rounded-md p-0.5">
                <button
                  onClick={() => setViewMode('grid')}
                  className={`px-2 py-1 rounded text-sm ${viewMode === 'grid' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600'}`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                  </svg>
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className={`px-2 py-1 rounded text-sm ${viewMode === 'list' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-600'}`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Data Table */}
            <div className="flex-1 overflow-auto">
              {/* 성적이 없을 때는 기본 데이터(@내성적2)를 편집 가능하게 보여줌 */}
              <table className="w-full text-sm">
                <thead className="bg-gray-100 sticky top-0">
                  <tr>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">과목</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">선택과목</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">표준점수</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">백분위</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wider">등급</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {subjects.map((subject) => {
                    const row = scores?.[subject] || {}
                    const electiveValue = getElectiveValue(subject, row)
                    const isKoreanHistory = subject === '한국사'
                    const isNoExam = !isKoreanHistory && electiveValue === '미응시'
                    return (
                      <tr key={subject} className="hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{subject}</td>
                        <td className="px-4 py-3">
                          {subject === '한국사' ? (
                            <span className="text-gray-400">-</span>
                          ) : (
                            <select
                              className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-emerald-500"
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
                            >
                              {(electiveOptionsMap[subject] || ['미응시']).map((option) => (
                                <option key={option} value={option}>{option}</option>
                              ))}
                            </select>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {isKoreanHistory || isNoExam ? (
                            <span className="text-gray-400">-</span>
                          ) : (
                            <input
                              type="number"
                              min={0}
                              max={200}
                              className="w-24 px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-emerald-500"
                              value={row['표준점수'] ?? ''}
                              onChange={(e) => setVal(subject, '표준점수', e.target.value === '' ? null : Number(e.target.value))}
                            />
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {isKoreanHistory || isNoExam ? (
                            <span className="text-gray-400">-</span>
                          ) : (
                            <input
                              type="number"
                              min={0}
                              max={100}
                              className="w-24 px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-emerald-500"
                              value={row['백분위'] ?? ''}
                              onChange={(e) => setVal(subject, '백분위', e.target.value === '' ? null : Number(e.target.value))}
                            />
                          )}
                        </td>
                        <td className="px-4 py-3">
                          {isNoExam ? (
                            <span className="text-gray-400">-</span>
                          ) : (
                            <input
                              type="number"
                              min={1}
                              max={9}
                              className="w-20 px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-emerald-500"
                              value={row['등급'] ?? ''}
                              onChange={(e) => setVal(subject, '등급', e.target.value === '' ? null : Number(e.target.value))}
                            />
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Footer: 자동 저장 안내 및 에러만 표시 */}
            <div className="px-4 py-3 border-t bg-gray-50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {selectedId && (
                  <span className="text-sm text-gray-500">
                    수정 시 자동 저장됩니다
                  </span>
                )}
                {!!error && <span className="text-sm text-red-600">{error}</span>}
              </div>
              {isSaving && (
                <span className="text-sm text-emerald-600">저장 중...</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
