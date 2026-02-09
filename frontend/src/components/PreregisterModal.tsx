import { useState, useEffect, useRef } from 'react'
import confetti from 'canvas-confetti'

interface PreregisterModalProps {
  isOpen: boolean
  onClose: () => void
  userId?: string
  userName?: string
}

type GradeOption = '예비 고3' | 'N수생' | '예비 고2' | '예비 고1' | '기타'
type EtcOption = '학부모' | '교사' | '중등' | '직접 입력'

interface DropdownItem {
  label: string
  description?: string
}

export default function PreregisterModal({ isOpen, onClose, userId, userName }: PreregisterModalProps) {
  const [step, setStep] = useState<'form' | 'success'>('form')
  const [grade, setGrade] = useState<GradeOption | null>(null)
  const [etcOption, setEtcOption] = useState<EtcOption | null>(null)
  const [customGrade, setCustomGrade] = useState('')
  const [phone, setPhone] = useState('')
  const [secretCode, setSecretCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showEtcDropdown, setShowEtcDropdown] = useState(false)
  const [codeCopied, setCodeCopied] = useState(false)
  const [openDropdown, setOpenDropdown] = useState<'info' | 'logic' | null>(null)
  const modalRef = useRef<HTMLDivElement>(null)

  const infoItems: DropdownItem[] = [
    { label: '26년도 입시 결과' },
    { label: '27년도 입시 요강' },
    { label: '28년도 입시 요강' },
    { label: '22년 개정 교육과정' },
    { label: '고교학점제' },
    { label: '5등급제' },
    { label: '수능 개편안' }
  ]

  const logicItems: DropdownItem[] = [
    { label: '생기부 기반 활동 추천' },
    { label: '공부 계획 및 주간 일정 설계' }
  ]

  // 모달 열릴 때 초기화
  useEffect(() => {
    if (isOpen) {
      setStep('form')
      setGrade(null)
      setEtcOption(null)
      setCustomGrade('')
      setPhone('')
      setSecretCode('')
      setError('')
      setCodeCopied(false)
      setOpenDropdown(null)
    }
  }, [isOpen])

  // 전화번호 포맷팅 (하이픈 자동 입력)
  const formatPhone = (value: string) => {
    const digits = value.replace(/\D/g, '')
    if (digits.length <= 3) return digits
    if (digits.length <= 7) return `${digits.slice(0, 3)}-${digits.slice(3)}`
    return `${digits.slice(0, 3)}-${digits.slice(3, 7)}-${digits.slice(7, 11)}`
  }

  const handlePhoneChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const formatted = formatPhone(e.target.value)
    setPhone(formatted)
  }

  // 학년 선택 값 가져오기
  const getGradeValue = () => {
    if (grade === '기타') {
      if (etcOption === '직접 입력') return customGrade || '기타'
      return etcOption ? `기타-${etcOption}` : '기타'
    }
    return grade || ''
  }

  // 폭죽 효과
  const fireConfetti = () => {
    const duration = 3000
    const end = Date.now() + duration

    const frame = () => {
      confetti({
        particleCount: 3,
        angle: 60,
        spread: 55,
        origin: { x: 0 },
        colors: ['#ff6b6b', '#feca57', '#48dbfb', '#ff9ff3', '#54a0ff']
      })
      confetti({
        particleCount: 3,
        angle: 120,
        spread: 55,
        origin: { x: 1 },
        colors: ['#ff6b6b', '#feca57', '#48dbfb', '#ff9ff3', '#54a0ff']
      })

      if (Date.now() < end) {
        requestAnimationFrame(frame)
      }
    }
    frame()
  }

  // 신청하기
  const handleSubmit = async () => {
    // 유효성 검사
    if (!grade) {
      setError('학년을 선택해주세요.')
      return
    }
    if (grade === '기타' && !etcOption) {
      setError('기타 옵션을 선택해주세요.')
      return
    }
    if (grade === '기타' && etcOption === '직접 입력' && !customGrade.trim()) {
      setError('학년을 직접 입력해주세요.')
      return
    }

    const phoneDigits = phone.replace(/\D/g, '')
    if (phoneDigits.length !== 11 || !phoneDigits.startsWith('010')) {
      setError('올바른 휴대폰 번호를 입력해주세요.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const response = await fetch('/api/preregister', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: phoneDigits,
          grade: getGradeValue(),
          user_id: userId,
          user_name: userName
        })
      })

      const data = await response.json()

      if (data.success) {
        setSecretCode(data.secret_code)
        setStep('success')
        fireConfetti()
      } else if (data.secret_code) {
        // 이미 신청한 경우
        setSecretCode(data.secret_code)
        setStep('success')
        setError('이미 신청하셨습니다. 기존 코드를 확인해주세요.')
      } else {
        setError(data.message || '신청 처리 중 오류가 발생했습니다.')
      }
    } catch (err) {
      console.error('사전신청 오류:', err)
      setError('네트워크 오류가 발생했습니다. 다시 시도해주세요.')
    } finally {
      setLoading(false)
    }
  }

  // 코드 복사
  const handleCopyCode = async () => {
    try {
      await navigator.clipboard.writeText(secretCode)
      setCodeCopied(true)
      setTimeout(() => setCodeCopied(false), 3000)
    } catch (err) {
      console.error('복사 실패:', err)
      // 폴백: 텍스트 선택
      const textArea = document.createElement('textarea')
      textArea.value = secretCode
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      setCodeCopied(true)
      setTimeout(() => setCodeCopied(false), 3000)
    }
  }

  // 닫기 시도 시 확인
  const handleClose = () => {
    if (step === 'success' && !codeCopied) {
      if (!confirm('잠시만요! 코드를 저장하지 않으면 혜택이 사라져요. 캡처하셨나요?')) {
        return
      }
    }
    onClose()
  }

  // 모달 바깥 클릭 시 닫기
  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      handleClose()
    }
  }

  if (!isOpen) return null

  return (
    <div 
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div 
        ref={modalRef}
        className="bg-white rounded-2xl max-w-md w-full max-h-[90vh] overflow-y-auto shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* 닫기 버튼 */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 p-2 text-gray-400 hover:text-gray-600 transition-colors z-10"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        {step === 'form' ? (
          /* 신청 폼 */
          <div className="p-6">
            {/* 헤더 메시지 */}
            <div className="text-center mb-6">
              <div className="text-4xl mb-3">🎁</div>
              <h2 className="text-xl font-bold text-gray-900 mb-4">PRO 2개월 무료 사전신청</h2>
              <div className="text-left bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl p-4 text-sm text-gray-700 leading-relaxed">
                <p className="font-medium text-gray-900 mb-2">안녕하세요 유니로드 팀입니다!</p>
                <p className="mb-2">
                  2월 말, 더 똑똑해진 유니로드가 <span className="font-semibold text-blue-600">모바일 앱</span>으로 돌아옵니다.
                </p>
                <p>
                  지금 사전신청하고 
                  <button
                    onClick={() => setOpenDropdown(openDropdown === 'info' ? null : 'info')}
                    className="border-b border-dashed border-gray-400 text-gray-700 hover:border-gray-600 transition-colors inline-flex items-center gap-0.5 mx-0.5"
                  >
                    최신 입시 정보
                    <svg className={`w-3 h-3 transition-transform ${openDropdown === 'info' ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  와 
                  <button
                    onClick={() => setOpenDropdown(openDropdown === 'logic' ? null : 'logic')}
                    className="border-b border-dashed border-gray-400 text-gray-700 hover:border-gray-600 transition-colors inline-flex items-center gap-0.5 mx-0.5"
                  >
                    더 똑똑한 대화 로직
                    <svg className={`w-3 h-3 transition-transform ${openDropdown === 'logic' ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  을 장착한 <span className="font-semibold text-purple-600">유니로드 PRO</span>를 무료로 이용하세요!
                </p>

                {/* 최신 입시 정보 드롭다운 */}
                {openDropdown === 'info' && (
                  <div className="mt-3 pt-3 border-t border-purple-200 space-y-1.5">
                    {infoItems.map((item, idx) => (
                      <div key={idx} className="text-xs text-gray-600 pl-2 py-1">
                        • {item.label}
                      </div>
                    ))}
                  </div>
                )}

                {/* 더 똑똑한 대화 로직 드롭다운 */}
                {openDropdown === 'logic' && (
                  <div className="mt-3 pt-3 border-t border-purple-200 space-y-1.5">
                    {logicItems.map((item, idx) => (
                      <div key={idx} className="text-xs text-gray-600 pl-2 py-1">
                        • {item.label}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* 학년 선택 */}
            <div className="mb-5">
              <label className="block text-sm font-medium text-gray-700 mb-3">
                현재 학년이 어떻게 되나요?
              </label>
              <div className="space-y-2">
                {/* 첫 번째 줄 */}
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => { setGrade('예비 고3'); setShowEtcDropdown(false) }}
                    className={`px-4 py-3 rounded-lg border-2 text-sm font-medium transition-all ${
                      grade === '예비 고3'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 hover:border-gray-300 text-gray-700'
                    }`}
                  >
                    예비 고3
                  </button>
                  <button
                    onClick={() => { setGrade('N수생'); setShowEtcDropdown(false) }}
                    className={`px-4 py-3 rounded-lg border-2 text-sm font-medium transition-all ${
                      grade === 'N수생'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 hover:border-gray-300 text-gray-700'
                    }`}
                  >
                    N수생
                  </button>
                </div>
                
                {/* 두 번째 줄 */}
                <div className="grid grid-cols-3 gap-2">
                  <button
                    onClick={() => { setGrade('예비 고2'); setShowEtcDropdown(false) }}
                    className={`px-4 py-3 rounded-lg border-2 text-sm font-medium transition-all ${
                      grade === '예비 고2'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 hover:border-gray-300 text-gray-700'
                    }`}
                  >
                    예비 고2
                  </button>
                  <button
                    onClick={() => { setGrade('예비 고1'); setShowEtcDropdown(false) }}
                    className={`px-4 py-3 rounded-lg border-2 text-sm font-medium transition-all ${
                      grade === '예비 고1'
                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                        : 'border-gray-200 hover:border-gray-300 text-gray-700'
                    }`}
                  >
                    예비 고1
                  </button>
                  <div className="relative">
                    <button
                      onClick={() => { 
                        setGrade('기타')
                        setShowEtcDropdown(!showEtcDropdown)
                      }}
                      className={`w-full px-4 py-3 rounded-lg border-2 text-sm font-medium transition-all flex items-center justify-between ${
                        grade === '기타'
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-200 hover:border-gray-300 text-gray-700'
                      }`}
                    >
                      <span>기타</span>
                      <svg className={`w-4 h-4 transition-transform ${showEtcDropdown ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    {/* 기타 드롭다운 */}
                    {showEtcDropdown && grade === '기타' && (
                      <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-10">
                        {(['학부모', '교사', '중등', '직접 입력'] as EtcOption[]).map((option) => (
                          <button
                            key={option}
                            onClick={() => {
                              setEtcOption(option)
                              if (option !== '직접 입력') {
                                setShowEtcDropdown(false)
                              }
                            }}
                            className={`w-full px-4 py-2.5 text-left text-sm hover:bg-gray-50 transition-colors ${
                              etcOption === option ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                            } ${option === '학부모' ? 'rounded-t-lg' : ''} ${option === '직접 입력' ? 'rounded-b-lg' : ''}`}
                          >
                            {option}
                          </button>
                        ))}
                        {etcOption === '직접 입력' && (
                          <div className="p-2 border-t">
                            <input
                              type="text"
                              value={customGrade}
                              onChange={(e) => setCustomGrade(e.target.value)}
                              placeholder="학년을 입력하세요"
                              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                              autoFocus
                            />
                            <button
                              onClick={() => setShowEtcDropdown(false)}
                              className="w-full mt-2 px-3 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors"
                            >
                              확인
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* 전화번호 입력 */}
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                전화번호
              </label>
              <input
                type="tel"
                value={phone}
                onChange={handlePhoneChange}
                placeholder="010-0000-0000"
                maxLength={13}
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              />
              <p className="mt-1.5 text-xs text-gray-500">
                앱 출시 시 알림 문자를 보내드립니다.
              </p>
            </div>

            {/* 에러 메시지 */}
            {error && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600">
                {error}
              </div>
            )}

            {/* 신청 버튼 */}
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="w-full py-3.5 bg-gradient-to-r from-blue-500 to-purple-500 text-white rounded-xl font-semibold text-base hover:from-blue-600 hover:to-purple-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-blue-500/25"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  신청 중...
                </span>
              ) : (
                '🎁 신청하기'
              )}
            </button>
          </div>
        ) : (
          /* 성공 화면 */
          <div className="p-6 text-center">
            <div className="text-5xl mb-4">🎉</div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">
              ✅ 신청이 완료되었습니다!
            </h2>
            <p className="text-sm text-gray-600 mb-6 leading-relaxed">
              앱 출시 후 아래 시크릿 코드를 입력해야만<br />
              <span className="font-semibold text-purple-600">25,000원 혜택</span>이 적용됩니다.<br />
              <span className="text-red-500 font-medium">(재발급이 불가능하니 지금 바로 캡처하세요!)</span>
            </p>

            {/* 시크릿 코드 박스 */}
            <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl p-5 mb-4">
              <p className="text-sm text-gray-600 mb-2">🎫 내 시크릿 코드</p>
              <div className="text-2xl font-bold text-gray-900 tracking-wider mb-4 font-mono">
                {secretCode}
              </div>
              <button
                onClick={handleCopyCode}
                className={`px-6 py-2.5 rounded-lg font-medium text-sm transition-all ${
                  codeCopied
                    ? 'bg-green-500 text-white'
                    : 'bg-white border-2 border-gray-200 text-gray-700 hover:border-blue-500 hover:text-blue-600'
                }`}
              >
                {codeCopied ? '✓ 복사 완료!' : '📋 복사하기'}
              </button>
            </div>

            {/* 토스트 메시지 */}
            {codeCopied && (
              <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
                코드가 복사되었습니다. 메모장에 붙여넣기 해두세요!
              </div>
            )}

            <p className="text-xs text-gray-500">
              앱 출시 알림 문자가 오면 이 코드를 입력해주세요.
            </p>

            {/* 닫기 버튼 */}
            <button
              onClick={handleClose}
              className="mt-6 w-full py-3 bg-gray-100 text-gray-700 rounded-xl font-medium hover:bg-gray-200 transition-colors"
            >
              닫기
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
