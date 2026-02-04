import { useState } from 'react'

// 카드 아이템 타입
interface SuggestionCard {
  title: string
  representative: string
  questions: string[]
  icon: JSX.Element
  iconBgColor: string
  isPremium?: boolean  // 프리미엄 기능 여부
  badge?: string  // 뱃지 텍스트
}

// 4개의 제안 카드
const suggestionList: SuggestionCard[] = [
  {
    title: '합격 예측',
    representative: '내 점수로 어디 갈 수 있을까?',
    questions: [
      '나 12232인데 고려대 기계공학부 합격 가능해?',
      '국수영탐 21111 어디 전자공학과 갈 수 있어?',
      '백분위 80, 98, 1등급, 95, 95인데 대학 추천해줘',
    ],
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    iconBgColor: 'bg-blue-100 text-blue-600',
  },
  {
    title: '환산 점수',
    representative: '내 성적으로 갈 수 있는 대학 찾기',
    questions: [
      '서울대 환산점수 계산해줘',
      '연세대 환산점수 계산해줘',
      '고려대 자연계 환산점수 어떻게 계산해?',
    ],
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
    iconBgColor: 'bg-gradient-to-br from-emerald-400 to-cyan-500 text-white',
    isPremium: true,
    badge: '맞춤',
  },
  {
    title: '모집요강',
    representative: '전형별 모집 정보를 알려줘',
    questions: [
      '경희대 빅데이터응용학과 학종으로 몇 명 뽑아?',
      '성균관대랑 한양대 모집요강 핵심만 요약해줘',
      '중앙대랑 이화여대 수능 최저 기준 어떻게 돼?',
      '부산대랑 경북대 지역인재 전형 조건 알려줘',
    ],
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
    iconBgColor: 'bg-purple-100 text-purple-600',
  },
  {
    title: '대학 정보',
    representative: '입결 및 대학 정보를 알려줘',
    questions: [
      '서울대학교 기계공학부 정시 입결 알려줘',
      '연세대학교 인재상 알려줘',
      '고려대학교 경영학과 작년 컷 알려줘',
    ],
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
    iconBgColor: 'bg-orange-100 text-orange-600',
  },
]

// 스타일 (파란색 통일)
const styles = {
  selected: 'ring-2 ring-blue-300 border-blue-200 bg-blue-50/70',
}

interface RollingPlaceholderProps {
  onQuestionClick?: (question: string) => void
  onCategorySelect?: (category: string | null) => void
  selectedCategory?: string | null
  isAuthenticated?: boolean
  hasProfile?: boolean  // 성적 입력 여부
  onLoginRequired?: (message: { title: string; description: string }) => void
  onProfileRequired?: () => void  // 성적 입력 유도
}

export default function RollingPlaceholder({ onQuestionClick, onCategorySelect, selectedCategory, isAuthenticated, hasProfile, onLoginRequired, onProfileRequired }: RollingPlaceholderProps) {
  const [selectedQuestionIndex, setSelectedQuestionIndex] = useState<number | null>(null)

  // 선택된 카테고리에 해당하는 인덱스 찾기
  const expandedIndex = selectedCategory 
    ? suggestionList.findIndex(item => item.title === selectedCategory)
    : null
  const actualExpandedIndex = expandedIndex === -1 ? null : expandedIndex

  const handleCardClick = (index: number) => {
    const card = suggestionList[index]
    
    // "환산 점수" 카드 처리
    if (card.title === '환산 점수') {
      if (!isAuthenticated) {
        // 비로그인 → 로그인 유도
        onLoginRequired?.({
          title: '로그인하여 고급 기능을 사용하세요',
          description: '학생의 성적 입력을 통해 학교별로 환산하여 대학을 추천해드립니다'
        })
        return
      } else if (!hasProfile) {
        // 로그인했지만 성적 미입력 → 성적 입력 유도
        onProfileRequired?.()
        return
      }
    }
    
    if (selectedCategory === card.title) {
      // 이미 선택된 카드 클릭 시 닫기
      onCategorySelect?.(null)
      setSelectedQuestionIndex(null)
    } else {
      // 새 카드 선택
      onCategorySelect?.(card.title)
      setSelectedQuestionIndex(null)
    }
  }

  const handleQuestionClick = (question: string, qIndex: number) => {
    setSelectedQuestionIndex(qIndex)
    if (onQuestionClick) {
      onQuestionClick(question)
    }
  }

  const selectedCard = actualExpandedIndex !== null ? suggestionList[actualExpandedIndex] : null

  // 카테고리가 선택되면 질문 목록만 표시
  if (selectedCategory && selectedCard) {
    return (
      <div className="w-full max-w-3xl animate-fade-in">
        {/* 질문 목록 */}
        <div className="space-y-4">
          {selectedCard.questions.map((question, qIndex) => (
            <div 
              key={qIndex}
              className="animate-fade-in-up"
              style={{ animationDelay: `${qIndex * 0.08}s`, animationFillMode: 'both' }}
            >
              <span
                onClick={() => handleQuestionClick(question, qIndex)}
                className={`
                  inline-block text-base font-semibold px-4 py-2.5 rounded-full cursor-pointer transition-all duration-200
                  ${selectedQuestionIndex === qIndex 
                    ? 'bg-gray-200 text-gray-800' 
                    : 'text-gray-700 hover:bg-gray-100'
                  }
                `}
              >
                {qIndex + 1}. {question}
              </span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // 카테고리 미선택 시 카드 그리드 표시
  return (
    <div className="w-full max-w-3xl mx-auto px-4">
      {/* 2x2 그리드 */}
      <div className="grid grid-cols-2 gap-4 sm:gap-5">
        {suggestionList.map((item, index) => {
          return (
            <div
              key={index}
              onClick={() => handleCardClick(index)}
              className={`
                relative
                bg-white 
                rounded-3xl 
                p-5 sm:p-6
                min-h-[140px] sm:min-h-[160px]
                flex flex-col
                cursor-pointer 
                transition-all 
                duration-300
                shadow-[0_2px_12px_rgba(0,0,0,0.06)]
                hover:shadow-[0_8px_30px_rgba(0,0,0,0.12)]
                hover:-translate-y-1
                active:scale-[0.98]
                ${item.isPremium ? 'ring-2 ring-emerald-200 bg-gradient-to-br from-white to-emerald-50/30' : ''}
                ${actualExpandedIndex === index ? styles.selected : ''}
                ${actualExpandedIndex !== null && actualExpandedIndex !== index ? 'opacity-50' : ''}
              `}
            >
              {/* 뱃지 */}
              {item.badge && (
                <div className="absolute top-3 right-3 px-2 py-0.5 bg-gradient-to-r from-emerald-500 to-cyan-500 text-white text-[10px] sm:text-xs font-bold rounded-full">
                  {item.badge}
                </div>
              )}
              
              {/* 아이콘 - 원형 */}
              <div className={`w-11 h-11 sm:w-12 sm:h-12 rounded-full ${item.iconBgColor} flex items-center justify-center mb-4 ${item.isPremium ? 'shadow-lg' : ''}`}>
                {item.icon}
              </div>
              
              {/* 제목 */}
              <h3 className={`text-base sm:text-lg font-bold mb-1.5 ${item.isPremium ? 'text-emerald-700' : 'text-gray-900'}`}>
                {item.title}
              </h3>
              
              {/* 설명 */}
              <p className="text-xs sm:text-sm text-gray-400 leading-relaxed">
                {item.representative}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
