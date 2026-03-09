import { useEffect, useRef, useState } from 'react'
import { Trophy, FileText, FileSearch, Building2, ArrowUpRight } from 'lucide-react'
import { trackUserAction } from '../utils/tracking'

// 카드 아이템 타입 (이미지 형식: 아이콘 위, 라벨 아래, 연한 배경)
interface SuggestionCard {
  title: string
  representative: string
  questions: string[]
  defaultExpandedQuestion?: string
  icon: JSX.Element
  iconColor: string
  iconHoverBg: string
  isPremium?: boolean
  badge?: string
}

const QUESTION_MENTION_SPLIT_REGEX = /(@생활기록부|@내신\s*성적|@내신성적|@모의고사성적|@모의고사|@[가-힣a-zA-Z0-9_]{1,20})/g
const QUESTION_MENTION_FULL_REGEX = /^(@생활기록부|@내신\s*성적|@내신성적|@모의고사성적|@모의고사|@[가-힣a-zA-Z0-9_]{1,20})$/

// 4개의 제안 카드 — 호버 시 아이콘에 맞는 배경색으로 변경
const suggestionList: SuggestionCard[] = [
  {
    title: '합격 예측',
    representative: '내 점수로 어디 갈 수 있을까?',
    questions: [
      '@내신성적으로 갈 수 있는 사범대 추천해줘',
      '나 내신 2.5인데 교대 가고 싶어',
      '국수영탐 21111 어디 전자공학과 갈 수 있어?',
      '백분위 80, 98, 1등급, 95, 95인데 대학 추천해줘',
    ],
    defaultExpandedQuestion: '나 내신 2.5인데 교대 가고 싶어',
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
      '수원대학교 수능최저학력기준 알려줘',
    ],
    icon: <Building2 className="w-6 h-6 sm:w-7 sm:h-7" strokeWidth={2} />,
    iconColor: 'text-rose-600',
    iconHoverBg: 'group-hover:bg-rose-100',
  },
]

const categoryPickRate: Record<string, string> = {
  '합격 예측': '68%가 선택!',
  '생활기록부': '27%가 선택!',
}

const categoryPickRateBadgeClass: Record<string, string> = {
  '합격 예측': 'bg-amber-100 text-amber-800 border border-amber-200',
  '생활기록부': 'bg-violet-100 text-violet-800 border border-violet-200',
}

const questionCardTitles: Record<string, string[]> = {
  '합격 예측': [
    '저장된 성적으로 질문',
    '교대 지원 가능성',
    '전자공학과 지원 전략',
    '성적 기반 대학 추천',
  ],
  '생활기록부': [
    '생기부 기반 대학 적합성 평가',
    '면접 예상 질문',
    '생기부 세특 평가',
    '지원 전략 수립',
  ],
  '모집요강': [
    '모집인원 확인',
    '전형 요건 정리',
    '수능 최저 기준',
    '지역인재 조건',
  ],
  '대학 정보': [
    '정시 입결 확인',
    '지원 가능 여부',
    '전년 컷 분석',
    '수능 최저 기준',
  ],
}

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
  schoolRecordLinked?: boolean | null
  naesinLinked?: boolean
  mockExamLinked?: boolean
  onSchoolRecordLinkClick?: () => void
  onNaesinLinkClick?: () => void
  onMockExamLinkClick?: () => void
  isAuthenticated?: boolean
  hasProfile?: boolean  // 성적 입력 여부
  onLoginRequired?: (message: { title: string; description: string }) => void
  onProfileRequired?: () => void  // 성적 입력 유도
}

export default function RollingPlaceholder({
  onQuestionClick,
  onCategorySelect,
  onCategoryExpand,
  selectedCategory,
  schoolRecordLinked,
  naesinLinked = false,
  mockExamLinked = false,
  onSchoolRecordLinkClick,
  onNaesinLinkClick,
  onMockExamLinkClick,
}: RollingPlaceholderProps) {
  const [selectedQuestionIndex, setSelectedQuestionIndex] = useState<number | null>(null)
  const [floatingNoticeMessage, setFloatingNoticeMessage] = useState<string | null>(null)
  const [isFloatingNoticeFading, setIsFloatingNoticeFading] = useState(false)
  const noticeFadeTimeoutRef = useRef<number | null>(null)
  const noticeHideTimeoutRef = useRef<number | null>(null)

  // 선택된 카테고리에 해당하는 인덱스 찾기
  const expandedIndex = selectedCategory 
    ? suggestionList.findIndex(item => item.title === selectedCategory)
    : null
  const actualExpandedIndex = expandedIndex === -1 ? null : expandedIndex

  const handleCardClick = (index: number) => {
    const card = suggestionList[index]
    trackUserAction('category_card_click', card.title)

    // 카테고리 클릭 시 질문 목록 펼침 (채팅 전송 X)
    if (selectedCategory === card.title) {
      onCategorySelect?.(null)
      setSelectedQuestionIndex(null)
    } else {
      onCategorySelect?.(card.title)
      setSelectedQuestionIndex(null)
      const defaultExpandedQuestion = card.defaultExpandedQuestion ?? card.questions[0]
      if (defaultExpandedQuestion) {
        onCategoryExpand?.(defaultExpandedQuestion)
      }
    }
  }

  const clearSchoolRecordNoticeTimers = () => {
    if (noticeFadeTimeoutRef.current) {
      window.clearTimeout(noticeFadeTimeoutRef.current)
      noticeFadeTimeoutRef.current = null
    }
    if (noticeHideTimeoutRef.current) {
      window.clearTimeout(noticeHideTimeoutRef.current)
      noticeHideTimeoutRef.current = null
    }
  }

  const triggerFloatingNotice = (message: string) => {
    clearSchoolRecordNoticeTimers()
    setFloatingNoticeMessage(message)
    setIsFloatingNoticeFading(false)
    noticeFadeTimeoutRef.current = window.setTimeout(() => {
      setIsFloatingNoticeFading(true)
    }, 900)
    noticeHideTimeoutRef.current = window.setTimeout(() => {
      setFloatingNoticeMessage(null)
      setIsFloatingNoticeFading(false)
    }, 1500)
  }

  const handleQuestionClick = (question: string, qIndex: number) => {
    if (selectedCard?.title === '생활기록부' && schoolRecordLinked !== true) {
      triggerFloatingNotice('먼저 생활기록부를 연동해 주세요')
      return
    }
    if (selectedCard?.title === '합격 예측' && qIndex === 0 && !naesinLinked && !mockExamLinked) {
      triggerFloatingNotice('먼저 성적을 연동해 주세요')
      return
    }
    setSelectedQuestionIndex(qIndex)
    if (onQuestionClick) {
      onQuestionClick(question)
    }
  }

  const selectedCard = actualExpandedIndex !== null ? suggestionList[actualExpandedIndex] : null
  const selectedQuestionTitles = selectedCard ? (questionCardTitles[selectedCard.title] || []) : []

  const renderQuestionPreview = (question: string) => {
    const parts = question.split(QUESTION_MENTION_SPLIT_REGEX)
    if (parts.length <= 1) return question

    return parts.map((part, idx) => {
      if (!part) return null
      if (QUESTION_MENTION_FULL_REGEX.test(part)) {
        return (
          <span
            key={`${part}-${idx}`}
            className="inline rounded-md bg-[#eaf2ff] text-[#2563eb]"
          >
            {part}
          </span>
        )
      }
      return <span key={`${idx}`}>{part}</span>
    })
  }

  useEffect(() => {
    return () => {
      clearSchoolRecordNoticeTimers()
    }
  }, [])

  // 4개 카드: 아이콘 위(연한 회색 원형), 라벨 아래(검정), 한 줄 균등 배치
  const fourButtons = (
    <div className="flex flex-wrap justify-center gap-3 sm:gap-5 items-start">
      {suggestionList.map((item, index) => (
        <button
          key={index}
          type="button"
          onClick={() => handleCardClick(index)}
          className={`
            group relative flex flex-col items-center gap-2 py-1 min-w-[72px] sm:min-w-[80px] max-w-[90px] sm:max-w-[100px]
            cursor-pointer transition-all duration-200
            hover:opacity-90
            active:scale-[0.98]
            ${actualExpandedIndex === index ? 'ring-2 ring-blue-300 rounded-2xl ring-offset-2 ring-offset-transparent' : ''}
            ${actualExpandedIndex !== null && actualExpandedIndex !== index ? 'opacity-50' : ''}
          `}
        >
          {categoryPickRate[item.title] && (
            <span className={`absolute -top-2 -right-5 sm:-right-6 rounded-full text-[10px] sm:text-[11px] font-semibold px-2 py-0.5 whitespace-nowrap shadow-sm ${categoryPickRateBadgeClass[item.title] || 'bg-gray-100 text-gray-800 border border-gray-200'}`}>
              {categoryPickRate[item.title]}
            </span>
          )}
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

  const shouldShowSchoolRecordLinkButton =
    selectedCard?.title === '생활기록부' && schoolRecordLinked !== true
  const shouldShowScoreLinkButtons = selectedCard?.title === '합격 예측'

  // 카테고리가 선택되면 버튼 + 질문 목록 표시
  if (selectedCategory && selectedCard) {
    return (
      <div className="w-full max-w-[760px] animate-fade-in">
        <div className="mb-3">{fourButtons}</div>
        <p className="text-center text-[13px] text-gray-400 mb-2 sm:mb-2.5">
          이런 질문은 어때요? (클릭)
        </p>
        {floatingNoticeMessage && (
          <div className={`fixed top-20 left-1/2 -translate-x-1/2 z-[80] pointer-events-none transition-opacity duration-500 ${isFloatingNoticeFading ? 'opacity-0' : 'opacity-100'}`}>
            <p className="rounded-2xl bg-gray-900/90 px-7 py-4 text-base sm:text-lg font-semibold text-white backdrop-blur-sm shadow-xl whitespace-nowrap">
              {floatingNoticeMessage}
            </p>
          </div>
        )}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {selectedCard.questions.map((question, qIndex) => (
            <button
              key={qIndex}
              type="button"
              onClick={() => handleQuestionClick(question, qIndex)}
              className={`
                animate-fade-in-up w-full text-left rounded-xl border border-gray-200 bg-white p-4 transition-all group
                ${selectedQuestionIndex === qIndex
                  ? 'border-blue-300 bg-blue-50/30'
                  : 'hover:border-blue-300 hover:bg-blue-50/30'}
              `}
              style={{ animationDelay: `${qIndex * 0.08}s`, animationFillMode: 'both' }}
            >
              <div className="flex items-start gap-3">
                <span className="inline-flex items-center justify-center w-5 h-5 mt-0.5 text-gray-400 group-hover:text-blue-500 transition-colors">
                  <ArrowUpRight className="w-4 h-4" />
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-gray-900 mb-1">
                    {selectedQuestionTitles[qIndex] || `${selectedCard.title} 추천 질문 ${qIndex + 1}`}
                  </p>
                  <p className="text-xs text-gray-500 leading-relaxed line-clamp-2">
                    {renderQuestionPreview(question)}
                  </p>
                </div>
              </div>
            </button>
          ))}
        </div>
        {shouldShowSchoolRecordLinkButton && (
          <div className="mt-3 flex justify-center">
            <button
              type="button"
              onClick={onSchoolRecordLinkClick}
              className="inline-flex items-center justify-center rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white hover:bg-violet-700 active:bg-violet-800 transition-colors"
            >
              생활기록부 연동하기
            </button>
          </div>
        )}
        {shouldShowScoreLinkButtons && (
          <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
            <button
              type="button"
              onClick={onNaesinLinkClick}
              className="inline-flex items-center justify-center rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-amber-200/70 hover:bg-amber-600 active:bg-amber-700 transition-colors"
            >
              내신성적 연동하기
            </button>
            <button
              type="button"
              onClick={onMockExamLinkClick}
              className="inline-flex items-center justify-center rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-white shadow-sm shadow-amber-200/70 hover:bg-amber-600 active:bg-amber-700 transition-colors"
            >
              모의고사 성적 연동하기
            </button>
          </div>
        )}
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
