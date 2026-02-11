import { useState, useEffect } from 'react'
import ShareModal from './ShareModal'

interface ChatMessageProps {
  message: string
  isUser: boolean
  sources?: string[]
  source_urls?: string[]  // 다운로드 URL (기존 방식용)
  userQuery?: string  // AI 답변일 때 연결된 사용자 질문
  isStreaming?: boolean  // 스트리밍 중인지 여부
  onRegenerate?: () => void  // 재생성 콜백
  imageUrl?: string  // 이미지 첨부 시 미리보기 URL
  showLoginPrompt?: boolean  // 로그인 유도 메시지 표시 여부
  onLoginClick?: () => void  // 로그인 버튼 클릭 콜백
  isMasked?: boolean  // 마스킹 여부 (비로그인 3회째 질문)
}

export default function ChatMessage({ message, isUser, sources, source_urls, userQuery, isStreaming, onRegenerate, imageUrl, showLoginPrompt, onLoginClick, isMasked }: ChatMessageProps) {
  const [showFactCheck, setShowFactCheck] = useState(false)
  const [showGlow, setShowGlow] = useState(false)
  const [showShareModal, setShowShareModal] = useState(false)  // 공유 모달 상태
  
  // AI 답변 스트리밍이 완료되면 글로우 효과 트리거
  useEffect(() => {
    if (!isUser && !isStreaming && message) {
      // 스트리밍 완료 후 짧은 딜레이 후 글로우 시작
      const timer = setTimeout(() => {
        setShowGlow(true)
        // 3초 후 글로우 효과 제거 (1.5초 × 2회 반복)
        setTimeout(() => setShowGlow(false), 3000)
      }, 200)
      
      return () => clearTimeout(timer)
    }
  }, [isUser, isStreaming, message])
  
  // ChatGPT에서 같은 질문하기
  const openChatGPT = () => {
    if (userQuery) {
      const encodedQuery = encodeURIComponent(userQuery)
      window.open(`https://chatgpt.com/?q=${encodedQuery}`, '_blank')
    }
  }
  
  // 후처리된 메시지 생성 (섹션 마크, 마크다운, 대괄호 제거)
  const getCleanedMessage = () => {
    return message
      .replace(/===SECTION_START(?::\w+)?===\s*/g, '')  // 섹션 마크 제거
      .replace(/===SECTION_END===\s*/g, '')
      .replace(/<cite[^>]*>([\s\S]*?)<\/cite>/g, '$1')  // cite 태그 제거
      .replace(/\*\*([^*]+)\*\*/g, '$1')  // **볼드** → 볼드
      .replace(/【([^】]+)】/g, '$1')  // 【타이틀】 → 타이틀
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')  // [텍스트](링크) → 텍스트
      .replace(/\n{3,}/g, '\n\n')
      .trim()
  }
  
  // 복사하기
  const handleCopy = () => {
    navigator.clipboard.writeText(getCleanedMessage())
    alert('답변이 복사되었습니다.')
  }
  
  // 공유하기 - 모달 열기
  const handleShare = () => {
    if (!userQuery) {
      alert('공유할 질문이 없습니다.')
      return
    }
    setShowShareModal(true)
  }
  
  // 재생성
  const handleRegenerate = () => {
    if (onRegenerate) {
      onRegenerate()
    }
  }
  // **텍스트** 형식을 볼드체로 파싱하는 헬퍼 함수
  const parseBold = (text: string | React.ReactNode): React.ReactNode => {
    if (typeof text !== 'string') return text

    const parts: React.ReactNode[] = []
    const boldRegex = /\*\*([^*]+)\*\*/g
    let lastIndex = 0
    let match
    let keyIndex = 0

    while ((match = boldRegex.exec(text)) !== null) {
      // 볼드 이전 텍스트
      if (match.index > lastIndex) {
        parts.push(
          <span key={`text-${keyIndex++}`}>
            {text.substring(lastIndex, match.index)}
          </span>
        )
      }

      // 볼드 부분
      parts.push(
        <strong key={`bold-${keyIndex++}`} className="font-semibold">
          {match[1]}
        </strong>
      )

      lastIndex = boldRegex.lastIndex
    }

    // 마지막 남은 텍스트
    if (lastIndex < text.length) {
      parts.push(
        <span key={`text-${keyIndex++}`}>
          {text.substring(lastIndex)}
        </span>
      )
    }

    return parts.length > 0 ? parts : text
  }

  // 【】로 감싸진 타이틀을 파싱하는 헬퍼 함수
  const parseTitles = (text: string) => {
    const parts: React.ReactNode[] = []
    // 타이틀 내부의 ** 볼드 마크다운도 함께 처리
    // 【**제목**】 또는 **【제목】** 형태 모두 처리
    const titleRegex = /(?:\*\*)?【(?:\*\*)?([^】]+?)(?:\*\*)?】(?:\*\*)?/g
    let lastIndex = 0
    let match
    let keyIndex = 0

    while ((match = titleRegex.exec(text)) !== null) {
      // 타이틀 이전 텍스트 (볼드 파싱 적용)
      if (match.index > lastIndex) {
        parts.push(
          <span key={`text-${keyIndex++}`}>
            {parseBold(text.substring(lastIndex, match.index))}
          </span>
        )
      }

      // 타이틀 부분 (18.5px, 볼드, 대괄호 및 ** 제거)
      // match[1]에서 추가로 ** 제거
      const titleContent = match[1].replace(/\*\*/g, '')
      parts.push(
        <span key={`title-${keyIndex++}`} className="text-[18.5px] font-bold">
          {titleContent}
        </span>
      )

      lastIndex = titleRegex.lastIndex
    }

    // 마지막 남은 텍스트 (볼드 파싱 적용)
    if (lastIndex < text.length) {
      parts.push(
        <span key={`text-${keyIndex++}`}>
          {parseBold(text.substring(lastIndex))}
        </span>
      )
    }

    return parts.length > 0 ? parts : parseBold(text)
  }

  // 불릿 포인트 라인을 감지해서 들여쓰기 스타일 적용
  const wrapBulletLines = (content: React.ReactNode): React.ReactNode => {
    if (typeof content === 'string') {
      const lines = content.split('\n')
      return lines.map((line, idx) => {
        const isBullet = /^[\s]*[•\-\*]\s/.test(line)
        if (isBullet) {
          return (
            <span key={idx} className="bullet-line">
              {line}
              {idx < lines.length - 1 && '\n'}
            </span>
          )
        }
        return idx < lines.length - 1 ? line + '\n' : line
      })
    }

    // React 노드 배열인 경우
    if (Array.isArray(content)) {
      return content.map((node, idx) => {
        if (typeof node === 'string') {
          return wrapBulletLines(node)
        }
        return node
      })
    }

    return content
  }

  // ___DIVIDER___ 마커를 <hr> 구분선으로 변환
  const addSectionDividers = (content: React.ReactNode): React.ReactNode => {
    if (typeof content === 'string') {
      if (!content.includes('___DIVIDER___')) return content

      const parts = content.split('___DIVIDER___')
      const result: React.ReactNode[] = []

      parts.forEach((part, idx) => {
        if (idx > 0) {
          result.push(
            <hr
              key={`divider-${idx}`}
              className="hidden sm:block"
              style={{
                border: 'none',
                borderTop: '1.2px solid #dddddd',
                marginTop: '2.0em',
                marginBottom: '0.1em'
              }}
            />
          )
        }
        if (part) {
          result.push(<span key={`section-${idx}`}>{part}</span>)
        }
      })

      return result
    }

    // 배열인 경우 각 요소 재귀 처리
    if (Array.isArray(content)) {
      const result: React.ReactNode[] = []
      content.forEach((node, idx) => {
        const processed = addSectionDividers(node)
        if (Array.isArray(processed)) {
          result.push(...processed)
        } else {
          result.push(processed)
        }
      })
      return result
    }

    // React 요소의 children 처리
    if (content && typeof content === 'object' && 'props' in content) {
      const element = content as React.ReactElement
      if (element.props && element.props.children) {
        const processedChildren = addSectionDividers(element.props.children)
        // children이 변경된 경우 새 요소 반환
        if (processedChildren !== element.props.children) {
          return { ...element, props: { ...element.props, children: processedChildren } }
        }
      }
    }

    return content
  }

  // cite 태그 개수 세기
  const countCiteTags = () => {
    const newCiteRegex = /<cite\s+data-source="([^"]*)"(?:\s+data-url="([^"]*)")?\s*>([\s\S]*?)<\/cite>/g
    const oldCiteRegex = /<cite>(.*?)<\/cite>/g
    
    const newMatches = message.match(newCiteRegex)
    const oldMatches = message.match(oldCiteRegex)
    
    return (newMatches?.length || 0) + (oldMatches?.length || 0)
  }

  // <cite> 태그를 파싱해서 희미한 밑줄 + 출처 표시
  const renderMessage = () => {
    if (isUser) {
      return <div className="whitespace-pre-wrap">{message}</div>
    }

    // 1. 섹션 경계를 구분선 마커로 변환 (===SECTION_END=== ... ===SECTION_START=== → ___DIVIDER___)
    let cleanedMessage = message.replace(/===SECTION_END===\s*===SECTION_START(?::\w+)?===/g, '___DIVIDER___')

    // 남은 섹션 마커 제거 (맨 처음/끝에 있는 것들)
    cleanedMessage = cleanedMessage.replace(/===SECTION_(START|END)(:\w+)?===/g, '')
    
    // --- 구분선을 ___DIVIDER___ 마커로 변환 (백엔드에서 보내는 형식)
    // 줄바꿈은 유지하면서 ---만 마커로 변환 (모바일에서 빈 줄 1개만 표시되도록)
    cleanedMessage = cleanedMessage.replace(/\n*---\n*/g, '\n___DIVIDER___\n')

    // 연속 줄바꿈 정리
    cleanedMessage = cleanedMessage.replace(/\n{3,}/g, '\n\n').trim()

    // JSON 형식인지 확인 ({ 로 시작하고 } 로 끝남)
    const trimmed = cleanedMessage.trim()
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        // JSON 파싱 가능한지 확인
        const parsed = JSON.parse(trimmed)
        // 파싱 성공하면 보기 좋게 표시
        const formatted = JSON.stringify(parsed, null, 2)
        return (
          <pre className="whitespace-pre-wrap font-mono text-sm bg-gray-50 p-3 rounded-lg overflow-x-auto">
            {formatted}
          </pre>
        )
      } catch {
        // JSON 아니면 일반 처리
      }
    }

    // 2. 새로운 cite 형식 파싱: <cite data-source="..." data-url="...">...</cite>
    const parts: React.ReactNode[] = []
    let lastIndex = 0
    
    // 새로운 형식: <cite data-source="..." data-url="...">...</cite>
    const newCiteRegex = /<cite\s+data-source="([^"]*)"(?:\s+data-url="([^"]*)")?\s*>([\s\S]*?)<\/cite>/g
    // 기존 형식: <cite>...</cite>
    const oldCiteRegex = /<cite>(.*?)<\/cite>/g
    
    // 새 형식이 있는지 먼저 확인
    const hasNewFormat = newCiteRegex.test(cleanedMessage)
    newCiteRegex.lastIndex = 0 // reset regex
    
    if (hasNewFormat) {
      // 새로운 형식으로 파싱
      let match
      while ((match = newCiteRegex.exec(cleanedMessage)) !== null) {
        // cite 이전 텍스트
        if (match.index > lastIndex) {
          const textBefore = cleanedMessage.substring(lastIndex, match.index)
          parts.push(
            <span key={`text-${lastIndex}`}>
              {parseTitles(textBefore)}
            </span>
          )
        }

        const sourceText = match[1]  // data-source 값 (문서명 + 페이지)
        const sourceUrl = match[2]   // data-url 값 (PDF URL)
        const citedContent = match[3] // 인용 내용

        parts.push(
          <span key={`cite-${match.index}`}>
            <span className={showFactCheck ? "bg-yellow-200/60 px-0.5" : ""}>
              {parseBold(citedContent)}
            </span>
            {showFactCheck && (sourceUrl && sourceUrl.length > 0 ? (
              <a
                href={sourceUrl}
                download
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-600 rounded-md whitespace-nowrap hover:bg-blue-100 cursor-pointer transition-colors ml-1"
                title="클릭하면 원본 PDF를 다운로드합니다"
              >
                📄 {sourceText}
              </a>
            ) : sourceText ? (
              <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-600 rounded-md whitespace-nowrap ml-1">
                📄 {sourceText}
              </span>
            ) : null)}
          </span>
        )

        lastIndex = newCiteRegex.lastIndex
      }

      // 마지막 남은 텍스트
      if (lastIndex < cleanedMessage.length) {
        const remainingText = cleanedMessage.substring(lastIndex)
        parts.push(
          <span key={`text-${lastIndex}`}>
            {parseTitles(remainingText)}
          </span>
        )
      }

      const content = wrapBulletLines(parts.length > 0 ? parts : parseTitles(cleanedMessage))
      return <div className="whitespace-pre-wrap">{addSectionDividers(content)}</div>
    }

    // 기존 형식 처리 (하위 호환성)
    const citeMatches = cleanedMessage.match(oldCiteRegex)
    const citeCount = citeMatches ? citeMatches.length : 0
    const sourcesCount = sources ? sources.length : 0

    // cite 태그와 sources가 매칭되지 않으면 cite 무시하고 일반 텍스트로 표시
    if (citeCount > 0 && sourcesCount === 0) {
      // cite 태그 제거하고 일반 텍스트로
      const finalClean = cleanedMessage.replace(/<\/?cite>/g, '')
      const content = wrapBulletLines(parseTitles(finalClean))
      return <div className="whitespace-pre-wrap">{addSectionDividers(content)}</div>
    }

    // 기존 <cite>...</cite> 패턴 찾기
    let match
    let citeIndex = 0

    while ((match = oldCiteRegex.exec(cleanedMessage)) !== null) {
      // <cite> 이전 텍스트
      if (match.index > lastIndex) {
        const textBefore = cleanedMessage.substring(lastIndex, match.index)
        parts.push(
          <span key={`text-${lastIndex}`}>
            {parseTitles(textBefore)}
          </span>
        )
      }

      // 출처가 있는지 확인
      const sourceText = sources && citeIndex < sources.length ? sources[citeIndex] : null
      const sourceUrl = source_urls && citeIndex < source_urls.length ? source_urls[citeIndex] : null
      
      if (sourceText) {
        // 출처가 있으면 형광펜 + 다운로드 가능한 출처 버블
        parts.push(
          <span key={`cite-${match.index}`}>
            <span className={showFactCheck ? "bg-yellow-200/60 px-0.5" : ""}>
              {parseBold(match[1])}
            </span>
            {showFactCheck && (sourceUrl ? (
              <a
                href={sourceUrl}
                download
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-600 rounded-md whitespace-nowrap hover:bg-blue-100 cursor-pointer transition-colors ml-1"
                title="클릭하면 원본 PDF를 다운로드합니다"
              >
                {sourceText}
              </a>
            ) : (
              <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-600 rounded-md whitespace-nowrap ml-1">
                {sourceText}
              </span>
            ))}
          </span>
        )
      } else {
        // 출처가 없으면 일반 텍스트로
        parts.push(
          <span key={`cite-${match.index}`}>
            {parseTitles(match[1])}
          </span>
        )
      }

      citeIndex++
      lastIndex = oldCiteRegex.lastIndex
    }

    // 마지막 남은 텍스트
    if (lastIndex < cleanedMessage.length) {
      const remainingText = cleanedMessage.substring(lastIndex)
      parts.push(
        <span key={`text-${lastIndex}`}>
          {parseTitles(remainingText)}
        </span>
      )
    }

    const content = wrapBulletLines(parts.length > 0 ? parts : parseTitles(cleanedMessage))
    return <div className="whitespace-pre-wrap">{addSectionDividers(content)}</div>
  }

  // 메시지에서 [이미지 첨부] 태그 제거
  const getDisplayMessage = () => {
    return message.replace(/^\[이미지 첨부\]\s*/, '')
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      {isUser ? (
        // 사용자 메시지: 말풍선 스타일 유지
        <div className="max-w-[70%]">
          {/* 이미지가 있으면 이미지 먼저 표시 */}
          {imageUrl && (
            <div className="mb-2 flex justify-end">
              <img 
                src={imageUrl} 
                alt="첨부된 이미지" 
                className="max-w-full max-h-64 rounded-lg border border-gray-200 shadow-sm"
              />
            </div>
          )}
          <div className="rounded-2xl px-4 py-3 text-gray-800" style={{ backgroundColor: '#F1F5FB' }}>
            <div className="whitespace-pre-wrap">{getDisplayMessage()}</div>
          </div>
        </div>
      ) : (
        // AI 답변: Gemini 스타일 (말풍선 없이, 폰트/간격 조정)
        <div className="w-full relative">
          {/* 마스킹 오버레이 - 비로그인 3회째 질문 시 */}
          {isMasked && (
            <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-white/80 backdrop-blur-md rounded-lg">
              <div className="text-center p-6">
                <div className="text-4xl mb-4">🔒</div>
                <h3 className="text-lg font-bold text-gray-900 mb-2">
                  로그인하고 답변을 확인하세요
                </h3>
                <p className="text-sm text-gray-600 mb-4">
                  더 많은 입시 정보와 개인별로 갈 수 있는 대학을 확인해보세요!
                </p>
                <button
                  onClick={onLoginClick}
                  className="px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-medium rounded-lg transition-all shadow-lg hover:shadow-xl flex items-center gap-2 mx-auto"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
                  </svg>
                  로그인하기
                </button>
              </div>
            </div>
          )}
          
          <div className={`text-gray-900 ai-response mb-4 ${isMasked ? 'blur-sm select-none' : ''}`}>
            {renderMessage()}
          </div>
          
          {/* 로그인 유도 버튼 - Rate Limit 초과 시 */}
          {showLoginPrompt && (
            <button
              onClick={onLoginClick}
              className="mt-4 px-6 py-3 bg-blue-500 hover:bg-blue-600 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
              </svg>
              로그인하기
            </button>
          )}
          
          {/* 버튼 영역 - 스트리밍 완료 후에만 표시, 로그인 유도 시 숨김 */}
          {!isStreaming && !showLoginPrompt && (
          <div className="flex gap-1 mt-3 items-center">
            {/* 복사 */}
            <button
              onClick={handleCopy}
              className="custom-tooltip p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
              data-tooltip="복사"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </button>
            
            {/* 공유 */}
            <button
              onClick={handleShare}
              disabled={!userQuery}
              className="custom-tooltip p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              data-tooltip="공유"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
              </svg>
            </button>
            
            {/* 재생성 */}
            <button
              onClick={handleRegenerate}
              className="custom-tooltip p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
              data-tooltip="재생성"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
            
            {/* GPT (아이콘만) */}
            <button
              onClick={openChatGPT}
              disabled={!userQuery}
              className="custom-tooltip p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              data-tooltip="ChatGPT 답변 비교하기"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z"/>
              </svg>
            </button>
            
            {/* 출처 확인하기 (맨 오른쪽) */}
            <button
              onClick={() => setShowFactCheck(!showFactCheck)}
              className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                showFactCheck
                  ? 'bg-green-100 text-green-700 hover:bg-green-200'
                  : 'text-gray-500 hover:bg-gray-50'
              } ${showGlow ? 'animate-pulse-glow' : ''}`}
            >
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              출처 확인하기{countCiteTags() > 0 && `(${countCiteTags()})`}
            </button>
          </div>
          )}
        </div>
      )}
      
      {/* 공유 모달 */}
      <ShareModal
        isOpen={showShareModal}
        onClose={() => setShowShareModal(false)}
        userQuery={userQuery || ''}
        assistantResponse={message}
        sources={sources}
        sourceUrls={source_urls}
      />
    </div>
  )
}

