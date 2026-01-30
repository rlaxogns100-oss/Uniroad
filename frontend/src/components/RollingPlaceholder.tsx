import { useState } from 'react'

// 카드 아이템 타입
interface SuggestionCard {
  title: string
  representative: string
  questions: string[]
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
  },
  {
    title: '환산 점수',
    representative: '대학별 환산점수를 계산해줘',
    questions: [
      '서울대 환산점수 계산해줘',
      '연세대 환산점수 계산해줘',
      '고려대 자연계 환산점수 어떻게 계산해?',
    ],
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
  },
  {
    title: '대학 정보',
    representative: '입결 및 대학 정보를 알려줘',
    questions: [
      '서울대학교 기계공학부 정시 입결 알려줘',
      '연세대학교 인재상 알려줘',
      '고려대학교 경영학과 작년 컷 알려줘',
    ],
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
}

export default function RollingPlaceholder({ onQuestionClick, onCategorySelect, selectedCategory }: RollingPlaceholderProps) {
  const [selectedQuestionIndex, setSelectedQuestionIndex] = useState<number | null>(null)

  // 선택된 카테고리에 해당하는 인덱스 찾기
  const expandedIndex = selectedCategory 
    ? suggestionList.findIndex(item => item.title === selectedCategory)
    : null
  const actualExpandedIndex = expandedIndex === -1 ? null : expandedIndex

  const handleCardClick = (index: number) => {
    const card = suggestionList[index]
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
    <div className="w-full max-w-5xl mx-auto px-4 -mt-4">
      {/* 4열 그리드 */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">
        {suggestionList.map((item, index) => {
          return (
            <div
              key={index}
              onClick={() => handleCardClick(index)}
              className={`
                bg-white 
                border border-gray-200 
                rounded-xl 
                px-5 py-3
                min-h-[70px]
                flex flex-col justify-center
                cursor-pointer 
                transition-all 
                duration-200
                shadow-sm
                hover:shadow-md
                hover:-translate-y-0.5
                active:scale-[0.98]
                ${actualExpandedIndex === index ? styles.selected : ''}
                ${actualExpandedIndex !== null && actualExpandedIndex !== index ? 'opacity-60' : ''}
              `}
            >
              <h3 className="text-sm font-semibold text-gray-800 mb-0.5">
                {item.title}
              </h3>
              <p className="text-xs text-gray-500 leading-relaxed">
                {item.representative}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
