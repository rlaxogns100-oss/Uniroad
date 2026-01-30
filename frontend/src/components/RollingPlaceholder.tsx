import { useEffect, useState } from 'react'

const questions = [
  '나 12232인데 고려대 기계공학부 합격 가능해?',
  '표준점수 언매 115 미적 120 영어 2등급, 물1 52, 화1 55인데 서울대 환산점수 알려줘',
  '국수영탐 21111 어디 전자공학과 갈 수 있어?',
  '백분위 80, 98, 1등급, 95, 95인데 대학 추천해줘',
  '경희대 빅데이터응용학과 학종으로 몇 명 뽑아?',
  '성균관대랑 한양대 모집요강 핵심만 요약해줘',
  '중앙대랑 이화여대 수능 최저 기준 어떻게 돼?',
  '부산대랑 경북대 지역인재 전형 조건 알려줘',
  '서울대학교 기계공학부 정시 입결 알려줘',
  '2028 경희대 모집 계획 알려줘',
  '연세대학교 인재상 알려줘',
]

interface RollingPlaceholderProps {
  onQuestionClick?: (question: string) => void
}

export default function RollingPlaceholder({ onQuestionClick }: RollingPlaceholderProps) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const itemHeight = 32 // 각 검색창 높이 (px) - 절반으로 축소
  const itemGap = 8 // 검색창 사이 간격 (px) - 절반으로 축소
  const totalItemHeight = itemHeight + itemGap
  const visibleItems = 5 // 보이는 항목 수
  const containerHeight = totalItemHeight * visibleItems
  
  // 무한 루프를 위해 리스트를 3번 반복
  const extendedQuestions = [...questions, ...questions, ...questions]
  
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentIndex((prev) => {
        // 한 세트가 끝나면 리셋
        if (prev >= questions.length - 1) {
          return 0
        }
        return prev + 1
      })
    }, 5000) // 5초마다 이동
    
    return () => clearInterval(interval)
  }, [])
  
  const handleClick = (question: string) => {
    if (onQuestionClick) {
      onQuestionClick(question)
    }
  }
  
  return (
    <div
      className="relative w-1/2 mx-auto overflow-hidden"
      style={{ height: `${containerHeight}px` }}
    >
      {/* 그라데이션 마스크 */}
      <div
        className="absolute inset-0"
        style={{
          maskImage: 'linear-gradient(to bottom, transparent 0%, black 25%, black 75%, transparent 100%)',
          WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 25%, black 75%, transparent 100%)',
        }}
      >
        {/* 롤링 컨테이너 */}
        <div
          className="will-change-transform transition-transform duration-500 ease-out"
          style={{
            transform: `translateY(-${currentIndex * totalItemHeight}px)`,
          }}
        >
          {extendedQuestions.map((question, index) => (
            <div
              key={index}
              style={{ 
                height: `${itemHeight}px`,
                marginBottom: `${itemGap}px`,
              }}
            >
              {/* 개별 검색창 */}
              <div
                onClick={() => handleClick(question)}
                className="h-full w-full bg-white rounded-full border border-blue-200 cursor-pointer hover:border-blue-400 hover:shadow-md transition-all shadow-sm flex items-center px-3 pr-10 relative"
              >
                <span className="text-sm text-gray-500 truncate">
                  "{question}"
                </span>
                
                {/* 전송 아이콘 */}
                <div className="absolute right-1.5 top-1/2 -translate-y-1/2">
                  <div className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center shadow-sm">
                    <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
