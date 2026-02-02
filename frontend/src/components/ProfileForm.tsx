import { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { getProfile, saveProfile, ScoreEntry } from '../api/client'

interface ProfileFormProps {
  isOpen: boolean
  onClose: () => void
  showGuide?: boolean  // 성적 입력 가이드 표시 여부
}

const subjects = [
  { key: '국어', label: '국어', hasChoice: true, choices: ['화법과작문', '언어와매체'] },
  { key: '수학', label: '수학', hasChoice: true, choices: ['확률과통계', '미적분', '기하'] },
  { key: '영어', label: '영어', hasChoice: false },
  { key: '탐구1', label: '탐구1', hasChoice: true, isInquiry: true },
  { key: '탐구2', label: '탐구2', hasChoice: true, isInquiry: true },
  { key: '한국사', label: '한국사', hasChoice: false },
]

const inquirySubjects = [
  '물리학Ⅰ', '물리학Ⅱ', '화학Ⅰ', '화학Ⅱ', '생명과학Ⅰ', '생명과학Ⅱ', '지구과학Ⅰ', '지구과학Ⅱ',
  '생활과윤리', '윤리와사상', '한국지리', '세계지리', '동아시아사', '세계사', '경제', '정치와법', '사회·문화'
]

export default function ProfileForm({ isOpen, onClose, showGuide }: ProfileFormProps) {
  const { accessToken } = useAuth()
  const [scores, setScores] = useState<Record<string, ScoreEntry>>({})
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)

  // 프로필 불러오기
  useEffect(() => {
    if (isOpen && accessToken) {
      loadProfile()
    }
  }, [isOpen, accessToken])

  const loadProfile = async () => {
    if (!accessToken) return
    
    try {
      const profile = await getProfile(accessToken)
      setScores(profile.scores || {})
    } catch (error: any) {
      // 404는 프로필이 없는 것이므로 무시
      if (error.response?.status !== 404) {
        console.error('프로필 로드 오류:', error)
      }
    }
  }

  const handleScoreChange = (subject: string, field: keyof ScoreEntry, value: any) => {
    setScores(prev => ({
      ...prev,
      [subject]: {
        ...prev[subject],
        [field]: value
      }
    }))
  }

  const handleSave = async () => {
    if (!accessToken) {
      setMessage({ type: 'error', text: '로그인이 필요합니다.' })
      return
    }

    // 유효성 검사: 최소 1개 과목은 입력되어야 함
    const filledScores = Object.entries(scores).filter(([_, score]) => 
      score && (score.등급 !== undefined || score.표준점수 !== undefined || score.백분위 !== undefined)
    )

    if (filledScores.length === 0) {
      setMessage({ type: 'error', text: '최소 1개 과목의 점수를 입력해주세요.' })
      return
    }

    setIsLoading(true)
    setMessage(null)

    try {
      // 빈 값 제거
      const cleanedScores: Record<string, ScoreEntry> = {}
      filledScores.forEach(([subject, score]) => {
        cleanedScores[subject] = score
      })

      await saveProfile(accessToken, cleanedScores)
      setMessage({ type: 'success', text: '성적이 저장되었습니다!' })
      
      // 2초 후 모달 닫기
      setTimeout(() => {
        onClose()
        setMessage(null)
      }, 2000)
    } catch (error: any) {
      console.error('프로필 저장 오류:', error)
      setMessage({ 
        type: 'error', 
        text: error.response?.data?.detail || '저장 중 오류가 발생했습니다.' 
      })
    } finally {
      setIsLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-white border-b p-4 flex justify-between items-center">
          <h2 className="text-xl font-bold text-gray-800">내 모의고사 성적</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl font-bold"
          >
            ×
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* 성적 입력 가이드 */}
          {showGuide && (
            <div className="bg-gradient-to-r from-emerald-50 to-cyan-50 border border-emerald-200 rounded-xl p-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 bg-gradient-to-br from-emerald-400 to-cyan-500 rounded-full flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-bold text-emerald-800 mb-1">성적을 입력하면 더 정확해요!</h3>
                  <p className="text-sm text-emerald-700">
                    모의고사 성적을 입력하면 대학별 환산점수를 자동으로 계산하고, 
                    <strong> 합격 가능성이 높은 대학</strong>을 추천해드립니다.
                  </p>
                </div>
              </div>
            </div>
          )}

          {message && (
            <div className={`p-4 rounded ${
              message.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
            }`}>
              {message.text}
            </div>
          )}

          {subjects.map((subject) => {
            const score = scores[subject.key] || {}
            
            return (
              <div key={subject.key} className="border rounded-lg p-4 space-y-3">
                <h3 className="font-semibold text-gray-700">{subject.label}</h3>
                
                <div className="grid grid-cols-3 gap-3">
                  {/* 등급 */}
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">등급</label>
                    <input
                      type="number"
                      value={score.등급 || ''}
                      onChange={(e) => handleScoreChange(subject.key, '등급', e.target.value ? parseInt(e.target.value) : undefined)}
                      placeholder="1-9"
                      className="w-full border rounded px-3 py-2 text-sm"
                      min={1}
                      max={9}
                      step={1}
                    />
                  </div>

                  {/* 표준점수 */}
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">표준점수</label>
                    <input
                      type="number"
                      value={score.표준점수 || ''}
                      onChange={(e) => handleScoreChange(subject.key, '표준점수', e.target.value ? parseFloat(e.target.value) : undefined)}
                      placeholder="점수"
                      className="w-full border rounded px-3 py-2 text-sm"
                      min={0}
                      max={200}
                      step={0.1}
                    />
                  </div>

                  {/* 백분위 */}
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">백분위</label>
                    <input
                      type="number"
                      value={score.백분위 || ''}
                      onChange={(e) => handleScoreChange(subject.key, '백분위', e.target.value ? parseFloat(e.target.value) : undefined)}
                      placeholder="0-100"
                      className="w-full border rounded px-3 py-2 text-sm"
                      min={0}
                      max={100}
                      step={0.1}
                    />
                  </div>
                </div>

                {/* 선택과목 (국어, 수학, 탐구) */}
                {subject.hasChoice && (
                  <div>
                    <label className="block text-sm text-gray-600 mb-1">
                      {subject.isInquiry ? '탐구 과목' : '선택과목'}
                    </label>
                    <select
                      value={score.선택과목 || ''}
                      onChange={(e) => handleScoreChange(subject.key, '선택과목', e.target.value)}
                      className="w-full border rounded px-3 py-2 text-sm"
                    >
                      <option value="">선택</option>
                      {subject.isInquiry ? (
                        inquirySubjects.map(subj => (
                          <option key={subj} value={subj}>{subj}</option>
                        ))
                      ) : (
                        subject.choices?.map(choice => (
                          <option key={choice} value={choice}>{choice}</option>
                        ))
                      )}
                    </select>
                  </div>
                )}
              </div>
            )
          })}

          <div className="flex gap-3 pt-4 border-t">
            <button
              onClick={onClose}
              className="flex-1 px-4 py-2 border rounded-lg text-gray-700 hover:bg-gray-50"
              disabled={isLoading}
            >
              취소
            </button>
            <button
              onClick={handleSave}
              disabled={isLoading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300"
            >
              {isLoading ? '저장 중...' : '저장하기'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
