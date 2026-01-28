interface ChatMessageProps {
  message: string
  isUser: boolean
  sources?: string[]
  source_urls?: string[]  // 다운로드 URL
}

export default function ChatMessage({ message, isUser, sources, source_urls }: ChatMessageProps) {
  // <cite> 태그를 파싱해서 희미한 밑줄 + 출처 표시
  const renderMessage = () => {
    if (isUser) {
      return <div className="whitespace-pre-wrap">{message}</div>
    }

    // JSON 형식인지 확인 ({ 로 시작하고 } 로 끝남)
    const trimmed = message.trim()
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

    // <cite> 태그 개수 세기
    const citeMatches = message.match(/<cite>(.*?)<\/cite>/g)
    const citeCount = citeMatches ? citeMatches.length : 0
    const sourcesCount = sources ? sources.length : 0

    // cite 태그와 sources가 매칭되지 않으면 cite 무시하고 일반 텍스트로 표시
    if (citeCount > 0 && sourcesCount === 0) {
      // cite 태그 제거하고 일반 텍스트로
      const cleanedMessage = message.replace(/<\/?cite>/g, '')
      return <div className="whitespace-pre-wrap leading-relaxed">{cleanedMessage}</div>
    }

    // <cite>...</cite> 패턴 찾기
    const parts = []
    let lastIndex = 0
    const regex = /<cite>(.*?)<\/cite>/g
    let match
    let citeIndex = 0

    while ((match = regex.exec(message)) !== null) {
      // <cite> 이전 텍스트
      if (match.index > lastIndex) {
        parts.push(
          <span key={`text-${lastIndex}`}>
            {message.substring(lastIndex, match.index)}
          </span>
        )
      }

      // 출처가 있는지 확인
      const sourceText = sources && citeIndex < sources.length ? sources[citeIndex] : null
      const sourceUrl = source_urls && citeIndex < source_urls.length ? source_urls[citeIndex] : null
      
      if (sourceText) {
        // 출처가 있으면 밑줄 + 다운로드 가능한 출처 버블
        parts.push(
          <span key={`cite-${match.index}`} className="inline-flex items-baseline gap-1">
            <span className="underline decoration-blue-300/40 decoration-1 underline-offset-2">
              {match[1]}
            </span>
            {sourceUrl ? (
              <a
                href={sourceUrl}
                download
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-600 rounded-md whitespace-nowrap hover:bg-blue-100 cursor-pointer transition-colors"
                title="클릭하면 원본 PDF를 다운로드합니다"
              >
                {sourceText}
              </a>
            ) : (
              <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-600 rounded-md whitespace-nowrap">
                {sourceText}
              </span>
            )}
          </span>
        )
      } else {
        // 출처가 없으면 일반 텍스트로
        parts.push(
          <span key={`cite-${match.index}`}>
            {match[1]}
          </span>
        )
      }

      citeIndex++
      lastIndex = regex.lastIndex
    }

    // 마지막 남은 텍스트
    if (lastIndex < message.length) {
      parts.push(
        <span key={`text-${lastIndex}`}>
          {message.substring(lastIndex)}
        </span>
      )
    }

    return <div className="whitespace-pre-wrap leading-relaxed">{parts.length > 0 ? parts : message}</div>
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

