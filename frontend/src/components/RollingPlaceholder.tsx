import { useState } from 'react'
import { trackUserAction } from '../utils/tracking'

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
      '나 내신 2.5인데 교대 가고 싶어',
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
    title: '생활기록부',
    representative: '내 생활기록부 분석하기',
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
      '성균관대 특성화고 전형에 대해 알려줘',
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
      '연세대학교 농어촌 가능해?',
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
  /** 카드 확장 시 채팅창에 첫 번째 질문을 넣을 때 호출 */
  onCategoryExpand?: (firstQuestion: string) => void
  selectedCategory?: string | null
  isAuthenticated?: boolean
  hasProfile?: boolean  // 성적 입력 여부
  onLoginRequired?: (message: { title: string; description: string }) => void
  onProfileRequired?: () => void  // 성적 입력 유도
  onSchoolRecordClick?: () => void
}

export default function RollingPlaceholder({ onQuestionClick, onCategorySelect, onCategoryExpand, selectedCategory, onSchoolRecordClick }: RollingPlaceholderProps) {
  const [selectedQuestionIndex, setSelectedQuestionIndex] = useState<number | null>(null)

  // 선택된 카테고리에 해당하는 인덱스 찾기
  const expandedIndex = selectedCategory 
    ? suggestionList.findIndex(item => item.title === selectedCategory)
    : null
  const actualExpandedIndex = expandedIndex === -1 ? null : expandedIndex

  const handleCardClick = (index: number) => {
    const card = suggestionList[index]
    
    // 카테고리 카드 클릭 추적
    trackUserAction('category_card_click', card.title)
    
    // "생활기록부" 카드 클릭 시 사이드바의 생기부 세특 평가 이동 동작으로 연결
    if (card.title === '생활기록부') {
      onSchoolRecordClick?.()
      return
    }
    
    if (selectedCategory === card.title) {
      // 이미 선택된 카드 클릭 시 닫기
      onCategorySelect?.(null)
      setSelectedQuestionIndex(null)
    } else {
      // 새 카드 선택
      onCategorySelect?.(card.title)
      setSelectedQuestionIndex(null)
      // 해당 카드의 첫 번째 질문을 채팅창에 넣기
      if (card.questions.length > 0) {
        onCategoryExpand?.(card.questions[0])
      }
    }
  }

  const handleQuestionClick = (question: string, qIndex: number) => {
    setSelectedQuestionIndex(qIndex)
    if (onQuestionClick) {
      onQuestionClick(question)
    }
  }

  const selectedCard = actualExpandedIndex !== null ? suggestionList[actualExpandedIndex] : null

  // 하단 4개 버튼: 둥근 사각, 아이콘 왼쪽 + 텍스트 오른쪽 (이미지 레이아웃)
  const fourButtons = (
    <div className="flex flex-wrap justify-center gap-2 sm:gap-3">
      {suggestionList.map((item, index) => (
        <button
          key={index}
          type="button"
          onClick={() => handleCardClick(index)}
          className={`
            flex items-center gap-1.5 rounded-full border border-gray-200 bg-white px-2.5 py-1.5 sm:px-3 sm:py-2
            cursor-pointer transition-all duration-200
            hover:border-gray-300 hover:bg-gray-50
            active:scale-[0.98]
            ${actualExpandedIndex === index ? 'ring-2 ring-blue-300 border-blue-200 bg-blue-50/50' : ''}
            ${actualExpandedIndex !== null && actualExpandedIndex !== index ? 'opacity-50' : ''}
            ${item.isPremium ? 'border-emerald-200' : ''}
          `}
        >
          <span className={`w-2.5 h-2.5 sm:w-3 sm:h-3 rounded ${item.iconBgColor} flex items-center justify-center shrink-0 [&>svg]:w-1.5 [&>svg]:h-1.5 sm:[&>svg]:w-2 sm:[&>svg]:h-2`}>
            {item.icon}
          </span>
          <span className="text-xs font-medium text-gray-800 whitespace-nowrap">
            {item.title}
          </span>
        </button>
      ))}
    </div>
  )

  // 카테고리가 선택되면 버튼 + 질문 목록 표시
  if (selectedCategory && selectedCard) {
    return (
      <div className="w-full max-w-xl animate-fade-in">
        <div className="mb-3">{fourButtons}</div>
        <div className="space-y-1.5">
          {selectedCard.questions.map((question, qIndex) => (
            <div 
              key={qIndex}
              className="animate-fade-in-up"
              style={{ animationDelay: `${qIndex * 0.08}s`, animationFillMode: 'both' }}
            >
              <span
                onClick={() => handleQuestionClick(question, qIndex)}
                className={`
                  inline-block text-xs font-semibold px-2.5 py-1.5 rounded-full cursor-pointer transition-all duration-200
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

  // 카테고리 미선택 시 4개 버튼만 표시 (상위에서 제목·입력 카드와 함께 레이아웃)
  return (
    <div className="w-full max-w-3xl mx-auto">
      {fourButtons}
    </div>
  )
}
