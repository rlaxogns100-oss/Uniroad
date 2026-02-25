import { useEffect, useMemo, useState } from 'react'
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

export default function ScoreSetManagerModal({
  isOpen,
  onClose,
  sessionId,
  token,
  onUseScoreSet,
}: ScoreSetManagerModalProps) {
  const [items, setItems] = useState<ScoreSetItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [title, setTitle] = useState('내성적1')
  const [scores, setScores] = useState<Record<string, any>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')

  const selectedItem = useMemo(
    () => items.find((item) => item.id === selectedId) || null,
    [items, selectedId]
  )

  const load = async () => {
    setIsLoading(true)
    setError('')
    try {
      const rows = await listScoreSets(sessionId, token)
      setItems(rows)
      if (rows.length > 0) {
        const first = rows[0]
        setSelectedId(first.id)
        setTitle(normalizeTitle(first.name))
        setScores(first.scores || {})
      } else {
        setSelectedId(null)
        setTitle('내성적1')
        setScores({})
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail || '성적 목록을 불러오지 못했습니다.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    if (!isOpen) return
    void load()
  }, [isOpen, sessionId, token])

  const selectItem = (item: ScoreSetItem) => {
    setSelectedId(item.id)
    setTitle(normalizeTitle(item.name))
    setScores(item.scores || {})
    setError('')
  }

  const createNew = () => {
    setSelectedId(null)
    setTitle('내성적1')
    setScores({})
    setError('')
  }

  const setVal = (subject: string, key: string, value: any) => {
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

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-[80] bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white w-full max-w-6xl rounded-xl shadow-xl max-h-[88vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-5 py-4 border-b flex items-center justify-between">
          <h3 className="text-lg font-bold text-gray-900">모의고사 성적 관리</h3>
          <button className="text-gray-500 hover:text-gray-700 text-2xl" onClick={onClose}>×</button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[220px_1fr] min-h-[520px]">
          <div className="border-r bg-gray-50 p-3 overflow-y-auto">
            <div className="flex gap-2 mb-3">
              <button
                type="button"
                onClick={createNew}
                className="w-full px-3 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700"
              >
                새 성적
              </button>
            </div>
            {isLoading ? (
              <div className="text-sm text-gray-500 px-2 py-2">불러오는 중...</div>
            ) : items.length === 0 ? (
              <div className="text-sm text-gray-500 px-2 py-2">저장된 성적이 없습니다.</div>
            ) : (
              <div className="space-y-2">
                {items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => selectItem(item)}
                    className={`w-full text-left px-3 py-2 rounded-lg border ${
                      selectedId === item.id
                        ? 'bg-blue-50 border-blue-300 text-blue-800'
                        : 'bg-white border-gray-200 text-gray-800 hover:bg-gray-100'
                    }`}
                  >
                    {item.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="p-4 overflow-y-auto">
            <div className="bg-white border border-gray-200 rounded-xl p-4">
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="font-semibold text-gray-900 pt-1">성적 세트 편집</div>
                <div className="flex gap-2">
                  {selectedItem && onUseScoreSet && (
                    <button
                      type="button"
                      className="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-700"
                      onClick={() => onUseScoreSet(selectedItem.id, selectedItem.name)}
                    >
                      이 성적 사용
                    </button>
                  )}
                  <button
                    type="button"
                    className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-700 disabled:bg-gray-300"
                    disabled={isSaving}
                    onClick={onSave}
                  >
                    {isSaving ? '저장 중...' : '저장'}
                  </button>
                  <button
                    type="button"
                    className="px-3 py-1.5 rounded-lg bg-gray-800 text-white text-sm hover:bg-black disabled:bg-gray-300"
                    disabled={!selectedId || isSaving}
                    onClick={onDelete}
                  >
                    삭제
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-2 mb-3">
                <div className="text-sm text-gray-600 shrink-0">제목</div>
                <div className="flex-1 flex items-center rounded-lg border border-gray-300 bg-white">
                  <span className="px-3 text-sm text-gray-500">@</span>
                  <input
                    className="w-full py-2 pr-3 rounded-r-lg text-sm focus:outline-none"
                    value={title}
                    onChange={(e) => setTitle(e.target.value.slice(0, 10))}
                  />
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm border-collapse">
                  <thead>
                    <tr className="text-left">
                      <th className="py-1">과목</th>
                      <th className="py-1">선택과목</th>
                      <th className="py-1">표준점수</th>
                      <th className="py-1">백분위</th>
                      <th className="py-1">등급</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subjects.map((subject) => {
                      const row = scores?.[subject] || {}
                      const electiveValue = getElectiveValue(subject, row)
                      const isKoreanHistory = subject === '한국사'
                      const isNoExam = !isKoreanHistory && electiveValue === '미응시'
                      const disableStandardPercentile = isKoreanHistory || isNoExam
                      const disableGrade = isNoExam
                      return (
                        <tr key={subject} className="border-t border-gray-100">
                          <td className="py-1">{subject}</td>
                          <td className="py-1">
                            {subject === '한국사' ? (
                              <span>-</span>
                            ) : (
                              <select
                                className="w-full px-2 py-1 rounded border border-gray-200 bg-white"
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
                                  <option key={option} value={option}>
                                    {option}
                                  </option>
                                ))}
                              </select>
                            )}
                          </td>
                          <td className="py-1">
                            {disableStandardPercentile ? (
                              <span className="text-gray-400">-</span>
                            ) : (
                              <input
                                type="number"
                                min={0}
                                max={200}
                                className="w-full px-2 py-1 rounded border border-gray-200"
                                value={row['표준점수'] ?? ''}
                                onChange={(e) => setVal(subject, '표준점수', e.target.value === '' ? null : Number(e.target.value))}
                              />
                            )}
                          </td>
                          <td className="py-1">
                            {disableStandardPercentile ? (
                              <span className="text-gray-400">-</span>
                            ) : (
                              <input
                                type="number"
                                min={0}
                                max={100}
                                className="w-full px-2 py-1 rounded border border-gray-200"
                                value={row['백분위'] ?? ''}
                                onChange={(e) => setVal(subject, '백분위', e.target.value === '' ? null : Number(e.target.value))}
                              />
                            )}
                          </td>
                          <td className="py-1">
                            {disableGrade ? (
                              <span className="text-gray-400">-</span>
                            ) : (
                              <input
                                type="number"
                                min={1}
                                max={9}
                                className="w-full px-2 py-1 rounded border border-gray-200"
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
              {!!error && <p className="mt-3 text-sm text-red-600">{error}</p>}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
