import React from 'react'

interface ChatMessageProps {
  message: string
  isUser: boolean
  sources?: string[]
  source_urls?: string[]
}

export default function ChatMessage({ message, isUser, sources, source_urls }: ChatMessageProps) {
  const renderMessage = () => {
    if (isUser) {
      return <div className="whitespace-pre-wrap">{message}</div>
    }

    // 메시지 파싱 및 렌더링
    return (
      <div className="whitespace-pre-wrap leading-relaxed">
        {parseAndRenderMessage(message, sources, source_urls)}
      </div>
    )
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[70%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-gray-100 text-gray-900'
        }`}
      >
        {renderMessage()}
      </div>
    </div>
  )
}

/**
 * 메시지 파싱 및 렌더링
 * - 【타이틀】 → 볼드 타이틀
 * - <cite data-source="..." data-url="...">...</cite> → 밑줄 (출처는 문단 끝에 모음)
 * - <cite>...</cite> (기존 형식) → 밑줄 (출처는 문단 끝에 모음)
 */
function parseAndRenderMessage(
  message: string,
  sources?: string[],
  source_urls?: string[]
): React.ReactNode[] {
  const result: React.ReactNode[] = []
  
  // 문단 단위로 분리 (【타이틀】 기준)
  const paragraphs = message.split(/(?=【)/g).filter(p => p.trim())
  
  paragraphs.forEach((paragraph, paragraphIndex) => {
    const paragraphResult: React.ReactNode[] = []
    const paragraphSources: Array<{ text: string; url: string }> = []
    let remaining = paragraph
    let keyIndex = 0
    let simpleCiteIndex = 0

    while (remaining.length > 0) {
      // 【타이틀】 패턴 찾기
      const titleMatch = remaining.match(/【([^】]+)】/)
      
      // <cite data-source="..." data-url="...">...</cite> 패턴 찾기
      const dataCiteMatch = remaining.match(/<cite\s+data-source="([^"]*?)"\s+data-url="([^"]*?)">([\s\S]*?)<\/cite>/)
      
      // <cite>...</cite> (기존 형식) 패턴 찾기
      const simpleCiteMatch = remaining.match(/<cite>([\s\S]*?)<\/cite>/)

      // 어떤 패턴이 먼저 나오는지 확인
      const matches = [
        { type: 'title', match: titleMatch, index: titleMatch?.index ?? Infinity },
        { type: 'dataCite', match: dataCiteMatch, index: dataCiteMatch?.index ?? Infinity },
        { type: 'simpleCite', match: simpleCiteMatch, index: simpleCiteMatch?.index ?? Infinity },
      ].filter(m => m.match !== null)
        .sort((a, b) => a.index - b.index)

      if (matches.length === 0) {
        // 더 이상 패턴 없음 - 나머지 텍스트 추가
        paragraphResult.push(<span key={`text-${keyIndex++}`}>{remaining}</span>)
        break
      }

      const firstMatch = matches[0]
      const matchIndex = firstMatch.index

      // 패턴 이전 텍스트 추가 (타이틀 앞 텍스트는 trim)
      if (matchIndex > 0) {
        const beforeText = remaining.substring(0, matchIndex)
        const trimmedText = firstMatch.type === 'title' ? beforeText.trim() : beforeText
        if (trimmedText) {
          paragraphResult.push(<span key={`text-${keyIndex++}`}>{trimmedText}</span>)
        }
      }

      // 패턴 처리
      if (firstMatch.type === 'title' && titleMatch) {
        // 【타이틀】 → 볼드 타이틀
        paragraphResult.push(
          <span key={`title-${keyIndex++}`} className="block font-bold text-gray-800 mt-2 text-[1.125rem]">
            {titleMatch[1]}
          </span>
        )
        // 타이틀 뒤 줄바꿈과 공백 모두 제거
        let afterTitle = remaining.substring(matchIndex + titleMatch[0].length)
        afterTitle = afterTitle.replace(/^[\s\n]+/, '')
        remaining = afterTitle
      } 
      else if (firstMatch.type === 'dataCite' && dataCiteMatch) {
        // <cite data-source="..." data-url="...">...</cite>
        const sourceText = dataCiteMatch[1]
        const sourceUrl = dataCiteMatch[2]
        const citedText = dataCiteMatch[3]

        // 텍스트만 추가 (밑줄 없이)
        paragraphResult.push(
          <span key={`cite-${keyIndex++}`}>
            {citedText}
          </span>
        )

        // 출처 정보 저장 (중복 제거)
        if (sourceText && !paragraphSources.some(s => s.text === sourceText && s.url === sourceUrl)) {
          paragraphSources.push({ text: sourceText, url: sourceUrl })
        }

        remaining = remaining.substring(matchIndex + dataCiteMatch[0].length)
      }
      else if (firstMatch.type === 'simpleCite' && simpleCiteMatch) {
        // <cite>...</cite> (기존 형식)
        const citedText = simpleCiteMatch[1]
        const sourceText = sources && simpleCiteIndex < sources.length ? sources[simpleCiteIndex] : null
        const sourceUrl = source_urls && simpleCiteIndex < source_urls.length ? source_urls[simpleCiteIndex] : null

        // 텍스트만 추가 (밑줄 없이)
        paragraphResult.push(
          <span key={`cite-${keyIndex++}`}>
            {citedText}
          </span>
        )

        // 출처 정보 저장 (중복 제거)
        if (sourceText && !paragraphSources.some(s => s.text === sourceText && s.url === sourceUrl)) {
          paragraphSources.push({ text: sourceText || '', url: sourceUrl || '' })
        }

        simpleCiteIndex++
        remaining = remaining.substring(matchIndex + simpleCiteMatch[0].length)
      }
    }

    // 문단 결과 추가
    result.push(
      <div key={`para-${paragraphIndex}`} className="mb-3">
        {paragraphResult}
        
        {/* 문단 끝에 출처 표시 */}
        {paragraphSources.length > 0 && (
          <div className="border-t border-gray-200 flex flex-wrap gap-1.5 items-center">
            <span className="text-[10px] text-gray-500 font-medium">출처:</span>
            {paragraphSources.map((source, idx) => (
              source.url ? (
                <a
                  key={idx}
                  href={source.url}
                  download
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-700 rounded hover:bg-blue-100 cursor-pointer transition-colors"
                  title={`출처: ${source.text} (클릭하면 원본 파일 다운로드)`}
                >
                  {source.text}
                </a>
              ) : (
                <span
                  key={idx}
                  className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-700 rounded"
                >
                  {source.text}
                </span>
              )
            ))}
          </div>
        )}
      </div>
    )
  })

  return result
}
