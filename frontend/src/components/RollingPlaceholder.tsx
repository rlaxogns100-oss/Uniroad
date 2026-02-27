import { useState } from 'react'
import { Trophy, FileText, FileSearch, Building2 } from 'lucide-react'
import { trackUserAction } from '../utils/tracking'

// 카드 아이템 타입 (이미지 형식: 아이콘 위, 라벨 아래, 연한 배경)
interface SuggestionCard {
  title: string
  representative: string
  questions: string[]
  icon: JSX.Element
  iconColor: string
  iconHoverBg: string
  isPremium?: boolean
  badge?: string
}

// 4개의 제안 카드 — 호버 시 아이콘에 맞는 배경색으로 변경
const suggestionList: SuggestionCard[] = [
  {
    title: '합격 예측',
    representative: '내 점수로 어디 갈 수 있을까?',
    questions: [
      '나 내신 2.5인데 교대 가고 싶어',
      '국수영탐 21111 어디 전자공학과 갈 수 있어?',
      '백분위 80, 98, 1등급, 95, 95인데 대학 추천해줘',
    ],
    icon: <Trophy className="w-6 h-6 sm:w-7 sm:h-7" strokeWidth={2} />,
    iconColor: 'text-yellow-500',
    iconHoverBg: 'group-hover:bg-yellow-100',
  },
  {
    title: '생활기록부',
    representative: '내 생활기록부 분석하기',
    questions: [
      '내 생활기록부 바탕으로 가장 적합한 학교 어디야?',
      '덕성여대 기준으로 생기부 면접 질문 10개 만들어줘',
      '최근 합격자 생기부랑 내 생기부 비교해줘',
      '세특 내용을 3학년때 어떻게 보완하는게 좋을까?',
    ],
    icon: <FileText className="w-6 h-6 sm:w-7 sm:h-7" strokeWidth={2} />,
    iconColor: 'text-purple-600',
    iconHoverBg: 'group-hover:bg-purple-100',
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
    icon: <FileSearch className="w-6 h-6 sm:w-7 sm:h-7" strokeWidth={2} />,
    iconColor: 'text-emerald-600',
    iconHoverBg: 'group-hover:bg-emerald-100',
  },
  {
    title: '대학 정보',
    representative: '입결 및 대학 정보를 알려줘',
    questions: [
      '서울대학교 기계공학부 정시 입결 알려줘',
      '연세대학교 농어촌 가능해?',
      '고려대학교 경영학과 작년 컷 알려줘',
    ],
    icon: <Building2 className="w-6 h-6 sm:w-7 sm:h-7" strokeWidth={2} />,
    iconColor: 'text-rose-600',
    iconHoverBg: 'group-hover:bg-rose-100',
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
    trackUserAction('category_card_click', card.title)

    // "생활기록부" 카드 클릭 시 사이드바의 생기부 세특 평가 이동
    if (card.title === '생활기록부') {
      onSchoolRecordClick?.()
      return
    }

    // 합격 예측 / 모집요강 / 대학 정보: 이전처럼 질문 목록 펼침 (채팅 전송 X)
    if (selectedCategory === card.title) {
      onCategorySelect?.(null)
      setSelectedQuestionIndex(null)
    } else {
      onCategorySelect?.(card.title)
      setSelectedQuestionIndex(null)
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

  // 4개 카드: 아이콘 위(연한 회색 원형), 라벨 아래(검정), 한 줄 균등 배치
  const fourButtons = (
    <div className="flex flex-wrap justify-center gap-3 sm:gap-5 items-start">
      {suggestionList.map((item, index) => (
        <button
          key={index}
          type="button"
          onClick={() => handleCardClick(index)}
          className={`
            group flex flex-col items-center gap-2 py-1 min-w-[72px] sm:min-w-[80px] max-w-[90px] sm:max-w-[100px]
            cursor-pointer transition-all duration-200
            hover:opacity-90
            active:scale-[0.98]
            ${actualExpandedIndex === index ? 'ring-2 ring-blue-300 rounded-2xl ring-offset-2 ring-offset-transparent' : ''}
            ${actualExpandedIndex !== null && actualExpandedIndex !== index ? 'opacity-50' : ''}
          `}
        >
          <span className={`w-12 h-12 sm:w-14 sm:h-14 rounded-full bg-gray-100 flex items-center justify-center shrink-0 transition-colors duration-200 ${item.iconColor} ${item.iconHoverBg}`}>
            {item.icon}
          </span>
          <span className="text-sm font-medium text-black text-center whitespace-nowrap">
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
