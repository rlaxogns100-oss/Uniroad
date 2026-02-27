import { useState, useEffect } from 'react'
import ShareModal from './ShareModal'

interface ScoreReviewCardData {
  pendingId: string
  titleAuto: string
  scores: Record<string, any>
}

interface UsedChunk {
  id: string
  content: string
  title: string
  source: string
  file_url: string
  metadata?: Record<string, any>
}

interface ChatMessageProps {
  message: string
  isUser: boolean
  scoreMentions?: string[]
  sources?: string[]
  source_urls?: string[]  // 다운로드 URL (기존 방식용)
  usedChunks?: UsedChunk[]
  userQuery?: string  // AI 답변일 때 연결된 사용자 질문
  isStreaming?: boolean  // 스트리밍 중인지 여부
  onRegenerate?: () => void  // 재생성 콜백
  imageUrl?: string  // 이미지 첨부 시 미리보기 URL
  onLoginClick?: () => void  // 로그인 버튼 클릭 콜백
  isMasked?: boolean  // 마스킹 여부 (비로그인 3회째 질문)
  agentData?: {
    routerOutput: any
    functionResults: any
    mainAgentOutput: string | null
    rawAnswer?: string | null
    logs: string[]
  } | null
  isAdmin?: boolean
  onAgentClick?: () => void
  scoreReview?: ScoreReviewCardData
  onScoreReviewApprove?: (pendingId: string, title: string, scores: Record<string, any>) => void
  onScoreReviewSkipSession?: (pendingId: string) => void
  onScoreTagClick?: (name: string) => void
  onFollowUpClick?: (question: string) => void
}

export default function ChatMessage({ message, isUser, scoreMentions, sources, source_urls, usedChunks, userQuery, isStreaming, onRegenerate, imageUrl, onLoginClick, isMasked, agentData, isAdmin, onAgentClick, scoreReview, onScoreReviewApprove, onScoreReviewSkipSession, onScoreTagClick, onFollowUpClick }: ChatMessageProps) {
  const [showFactCheck, setShowFactCheck] = useState(false)
  const [activeChunk, setActiveChunk] = useState<UsedChunk | null>(null)
  const [showGlow, setShowGlow] = useState(false)
  const [showShareModal, setShowShareModal] = useState(false)  // 공유 모달 상태
  const [isReportFullscreen, setIsReportFullscreen] = useState(false)
  const [isEditScoreReview, setIsEditScoreReview] = useState(false)
  const [scoreReviewTitle, setScoreReviewTitle] = useState((scoreReview?.titleAuto || '@내성적1').replace(/^@/, ''))
  const [scoreReviewScores, setScoreReviewScores] = useState<Record<string, any>>(scoreReview?.scores || {})

  useEffect(() => {
    if (scoreReview) {
      setScoreReviewTitle((scoreReview.titleAuto || '@내성적1').replace(/^@/, '').slice(0, 10))
      setScoreReviewScores(scoreReview.scores)
    }
  }, [scoreReview])

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

  useEffect(() => {
    if (!isReportFullscreen) return
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prevOverflow
    }
  }, [isReportFullscreen])
  
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

  const isSchoolRecordReport = !isUser && (
    message.includes('# 0. 평가기준 설명') ||
    message.includes('# 0. 학교별 평가기준 설명') ||
    message.includes('# 1. 기준별 적용 평가') ||
    message.includes('# 1. 대학별 기준 적용 평가') ||
    message.includes('부록 A. 학년별 과목 세특 확장 평가') ||
    message.includes('## 답변 후 꼬리 질문')
  )

  const findChunkBySource = (dataSource: string): UsedChunk | null => {
    if (!usedChunks || usedChunks.length === 0) return null
    const srcLower = dataSource.toLowerCase()
    return usedChunks.find(c => {
      const s = (c.source || '').toLowerCase()
      const t = (c.title || '').toLowerCase()
      return srcLower.includes(t) || s.includes(srcLower) || srcLower.includes(s)
    }) || usedChunks.find(c => {
      const keywords = dataSource.split(/[|/]/).filter(k => k.trim().length > 2)
      return keywords.some(kw => (c.content || '').toLowerCase().includes(kw.trim().toLowerCase()))
    }) || null
  }

  const countRetrievedChunksFromAgent = () => {
    if (!agentData?.functionResults || typeof agentData.functionResults !== 'object') return 0
    let total = 0
    for (const value of Object.values(agentData.functionResults)) {
      if (value && typeof value === 'object' && Array.isArray((value as any).chunks)) {
        total += (value as any).chunks.length
      }
    }
    return total
  }

  const extractFollowUpSection = (text: string) => {
    if (!text) return { bodyText: text, questions: [] as string[] }

    const headingRegex = /(?:^|\n)(?:##\s*답변 후 꼬리 질문|##\s*다음 질문 제안|【답변 후 꼬리 질문】|【다음 질문 제안】)\s*(?:\n|$)/m
    const match = headingRegex.exec(text)
    if (!match || match.index == null) {
      return { bodyText: text, questions: [] as string[] }
    }

    const headingStart = match.index
    const sectionStart = headingStart + match[0].length
    const bodyText = text.slice(0, headingStart).trim()
    const tail = text.slice(sectionStart).trim()
    if (!tail) return { bodyText, questions: [] as string[] }

    const questions: string[] = []
    const seen = new Set<string>()
    for (const rawLine of tail.split('\n')) {
      const line = String(rawLine || '').trim()
      if (!line) continue
      if (/^[【《].+[】》]$/.test(line)) break

      let q = line.replace(/^\s*[-*•]\s*/, '').replace(/^\s*\d+\.\s*/, '').trim()
      q = q.replace(/^["']+|["']+$/g, '').trim()
      if (!q) continue
      if (!q.endsWith('?')) q = `${q.replace(/[.]+$/, '')}?`
      if (q.length < 5 || seen.has(q)) continue
      seen.add(q)
      questions.push(q)
      if (questions.length >= 4) break
    }

    return { bodyText, questions }
  }

  const renderFollowUpBlock = (questions: string[]) => {
    if (!questions.length) return null
    return (
      <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50/70 px-4 py-4">
        <p className="mb-3 text-[14px] font-semibold text-slate-700">다음에 물어보면 좋은 질문</p>
        <div className="flex flex-wrap gap-2">
          {questions.map((q, idx) => (
            <button
              key={`follow-up-${idx}`}
              type="button"
              onClick={() => onFollowUpClick?.(q)}
              className="max-w-full rounded-full border border-slate-300 bg-white px-3 py-1.5 text-left text-[13px] text-slate-700 transition-colors hover:border-[#0e6093]/45 hover:bg-[#0e6093]/5"
              title={onFollowUpClick ? '클릭하면 바로 질문합니다' : q}
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    )
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
  // **텍스트** 또는 *텍스트* 형식을 볼드체로 파싱하는 헬퍼 함수
  const parseBold = (text: string | React.ReactNode): React.ReactNode => {
    if (typeof text !== 'string') return text

    const parts: React.ReactNode[] = []
    // **bold** 우선, 그 다음 *bold* (단, ** 안의 *는 제외되도록 ** 먼저 매칭)
    const boldRegex = /\*\*([^*]+)\*\*|\*([^*]+)\*/g
    let lastIndex = 0
    let match
    let keyIndex = 0

    while ((match = boldRegex.exec(text)) !== null) {
      const boldContent = match[1] ?? match[2] ?? ''
      if (match.index > lastIndex) {
        parts.push(
          <span key={`text-${keyIndex++}`}>
            {text.substring(lastIndex, match.index)}
          </span>
        )
      }
      parts.push(
        <strong key={`bold-${keyIndex++}`} className="font-semibold">
          {boldContent}
        </strong>
      )
      lastIndex = boldRegex.lastIndex
    }

    if (lastIndex < text.length) {
      parts.push(
        <span key={`text-${keyIndex++}`}>
          {text.substring(lastIndex)}
        </span>
      )
    }

    return parts.length > 0 ? parts : text
  }

  // 【】 타이틀 + 마크다운 ## ### #### 헤딩 파싱
  const parseTitles = (text: string) => {
    const lines = text.split('\n')
    const lineNodes: React.ReactNode[] = []
    let keyIndex = 0

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i]
      const headingMatch = line.match(/^(#{1,4})\s+(.*)$/)
      if (headingMatch) {
        const level = headingMatch[1].length
        const content = headingMatch[2]
        const headingClass =
          level === 1
            ? 'text-2xl font-bold block mt-4 mb-1'
            : level === 2
              ? 'text-xl font-bold block mt-3 mb-1'
              : level === 3
                ? 'text-lg font-bold block mt-2 mb-0.5'
                : 'text-base font-bold block mt-2 mb-0.5'
        lineNodes.push(
          <span key={`md-h-${keyIndex++}`} className={headingClass}>
            {parseBold(content)}
          </span>
        )
      } else {
        lineNodes.push(
          <span key={`line-${keyIndex++}`}>
            {parseTitlesLine(line)}
          </span>
        )
      }
      if (i < lines.length - 1) lineNodes.push('\n')
    }

    return lineNodes.length > 0 ? lineNodes : parseBold(text)
  }

  // 한 줄 안에서만 【】 타이틀 + 볼드 처리 (parseTitles에서 라인별로 호출)
  const parseTitlesLine = (line: string) => {
    const parts: React.ReactNode[] = []
    const titleRegex = /(?:\*\*)?【(?:\*\*)?([^】]+?)(?:\*\*)?】(?:\*\*)?/g
    let lastIndex = 0
    let match
    let keyIndex = 0

    while ((match = titleRegex.exec(line)) !== null) {
      if (match.index > lastIndex) {
        parts.push(
          <span key={`t-${keyIndex++}`}>
            {parseBold(line.substring(lastIndex, match.index))}
          </span>
        )
      }
      const titleContent = match[1].replace(/\*\*/g, '')
      parts.push(
        <span key={`t-${keyIndex++}`} className="text-[18.5px] font-bold">
          {titleContent}
        </span>
      )
      lastIndex = titleRegex.lastIndex
    }
    if (lastIndex < line.length) {
      parts.push(
        <span key={`t-${keyIndex++}`}>
          {parseBold(line.substring(lastIndex))}
        </span>
      )
    }
    return parts.length > 0 ? parts : parseBold(line)
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

  // cite 태그 개수 세기 (기존 <cite> + 생기부 리포트의 (외부근거: ...) 포함)
  const countCiteTags = () => {
    const newCiteRegex = /<cite\s+data-source="([^"]*)"(?:\s+data-url="([^"]*)")?\s*>([\s\S]*?)<\/cite>/g
    const oldCiteRegex = /<cite>(.*?)<\/cite>/g
    const externalCiteRegex = /\(외부근거:\s*[^)]+\)/g

    const newMatches = message.match(newCiteRegex)
    const oldMatches = message.match(oldCiteRegex)
    const externalMatches = message.match(externalCiteRegex)

    return (newMatches?.length || 0) + (oldMatches?.length || 0) + (externalMatches?.length || 0)
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
    const { bodyText, questions: followUpQuestions } = extractFollowUpSection(cleanedMessage)
    cleanedMessage = bodyText

    // 화면에 그대로 노출되면 안 되는 raw 태그/마크다운 제거 (모든 <cite ...> 제거, 절대 raw 노출 방지)
    const stripRawCiteAndHeadingSyntax = (raw: string) => {
      let s = raw
        .replace(/<cite\s+[^>]*>/g, '')  // 속성 순서 무관하게 여는 태그 제거
        .replace(/<\/cite>/g, '')
      return s
    }

    // (외부근거: 문서명/페이지) → <cite data-source="문서명/페이지">앞 문장</cite> 로 변환 (생기부 리포트 출처 표시)
    const externalCiteRegex = /\s*\((외부근거:\s*[^)]+)\)/g
    if (externalCiteRegex.test(cleanedMessage)) {
      externalCiteRegex.lastIndex = 0
      let built = ''
      let prevEnd = 0
      let m: RegExpExecArray | null
      while ((m = externalCiteRegex.exec(cleanedMessage)) !== null) {
        const cited = cleanedMessage.slice(prevEnd, m.index).trim()
        const sourceRaw = m[1].replace(/^외부근거:\s*/, '').trim()
        const sourceAttr = sourceRaw.replace(/"/g, '&quot;')
        built += `<cite data-source="${sourceAttr}">${cited}</cite>`
        prevEnd = m.index + m[0].length
      }
      built += cleanedMessage.slice(prevEnd)
      cleanedMessage = built
    }

    // JSON 형식인지 확인 ({ 로 시작하고 } 로 끝남)
    const trimmed = cleanedMessage.trim()
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        // JSON 파싱 가능한지 확인
        const parsed = JSON.parse(trimmed)
        // 파싱 성공하면 보기 좋게 표시
        const formatted = JSON.stringify(parsed, null, 2)
        return (
          <div className="whitespace-pre-wrap">
            <pre className="whitespace-pre-wrap font-mono text-sm bg-gray-50 p-3 rounded-lg overflow-x-auto">
              {formatted}
            </pre>
            {renderFollowUpBlock(followUpQuestions)}
          </div>
        )
      } catch {
        // JSON 아니면 일반 처리
      }
    }

    // 2. 새로운 cite 형식 파싱: <cite data-source="..." data-url="...">...</cite> (속성 순서 무관)
    const parts: React.ReactNode[] = []
    let lastIndex = 0

    // data-source/data-url 순서 무관, 속성 사이 공백/줄바꿈 허용
    const newCiteRegex = /<cite\s+[^>]*data-source="([^"]*)"[^>]*(?:data-url="([^"]*)")?[^>]*>([\s\S]*?)<\/cite>/g
    const newCiteRegexAlt = /<cite\s+[^>]*data-url="([^"]*)"[^>]*data-source="([^"]*)"[^>]*>([\s\S]*?)<\/cite>/g
    // 기존 형식: <cite>...</cite>
    const oldCiteRegex = /<cite>(.*?)<\/cite>/g

    const tryMatchNewCite = (str: string, startIndex: number): { match: RegExpExecArray; source: string; url: string; content: string } | null => {
      let best: { match: RegExpExecArray; source: string; url: string; content: string } | null = null
      newCiteRegex.lastIndex = startIndex
      let m = newCiteRegex.exec(str)
      if (m && m.index >= startIndex) best = { match: m, source: m[1], url: (m[2] || '').trim(), content: (m[3] || '').trim() }
      newCiteRegexAlt.lastIndex = startIndex
      m = newCiteRegexAlt.exec(str)
      if (m && m.index >= startIndex) {
        const cur = { match: m, source: m[2], url: (m[1] || '').trim(), content: (m[3] || '').trim() }
        if (!best || m.index < best.match.index) best = cur
      }
      return best
    }

    // 새 형식이 있는지 먼저 확인 (두 패턴 모두)
    const hasNewFormat = newCiteRegex.test(cleanedMessage) || newCiteRegexAlt.test(cleanedMessage)
    newCiteRegex.lastIndex = 0
    newCiteRegexAlt.lastIndex = 0
    
    if (hasNewFormat) {
      // 새로운 형식으로 파싱 (data-source/data-url 순서 무관)
      let parsed: ReturnType<typeof tryMatchNewCite>
      while ((parsed = tryMatchNewCite(cleanedMessage, lastIndex)) !== null) {
        const { match, source: sourceText, url: sourceUrl, content: citedContentRaw } = parsed
        // cite 이전 텍스트 (raw cite 태그 제거 후 파싱)
        if (match.index > lastIndex) {
          const textBefore = stripRawCiteAndHeadingSyntax(cleanedMessage.substring(lastIndex, match.index))
          if (textBefore) {
            parts.push(
              <span key={`text-${lastIndex}`}>
                {parseTitles(textBefore)}
              </span>
            )
          }
        }

        let citedContent = citedContentRaw.replace(/^#+\s*/, '').trim() || citedContentRaw

        const matchedChunk = isSchoolRecordReport ? findChunkBySource(sourceText) : null

        parts.push(
          <span key={`cite-${match.index}`}>
            <span className={showFactCheck ? "bg-yellow-200/60 px-0.5" : ""}>
              {parseBold(citedContent)}
            </span>
            {showFactCheck && (isSchoolRecordReport && matchedChunk ? (
              <button
                onClick={() => setActiveChunk(matchedChunk)}
                className="inline-flex items-center px-1.5 py-0.5 text-[10px] bg-blue-50 text-blue-600 rounded-md whitespace-nowrap hover:bg-blue-100 cursor-pointer transition-colors ml-1"
                title="출처 근거 보기"
              >
                📄 {sourceText}
              </button>
            ) : sourceUrl && sourceUrl.length > 0 ? (
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

        lastIndex = match.index + match[0].length
      }

      // 마지막 남은 텍스트 (raw cite 태그 제거 후 파싱)
      if (lastIndex < cleanedMessage.length) {
        const remainingText = stripRawCiteAndHeadingSyntax(cleanedMessage.substring(lastIndex))
        if (remainingText) {
          parts.push(
            <span key={`text-${lastIndex}`}>
              {parseTitles(remainingText)}
            </span>
          )
        }
      }

      const content = wrapBulletLines(parts.length > 0 ? parts : parseTitles(stripRawCiteAndHeadingSyntax(cleanedMessage)))
      return (
        <div className="whitespace-pre-wrap">
          {addSectionDividers(content)}
          {renderFollowUpBlock(followUpQuestions)}
        </div>
      )
    }

    // 기존 형식 처리 (하위 호환성)
    const citeMatches = cleanedMessage.match(oldCiteRegex)
    const citeCount = citeMatches ? citeMatches.length : 0
    const sourcesCount = sources ? sources.length : 0

    // cite 태그와 sources가 매칭되지 않으면 cite 무시하고 일반 텍스트로 표시
    if (citeCount > 0 && sourcesCount === 0) {
      const finalClean = stripRawCiteAndHeadingSyntax(cleanedMessage.replace(/<\/?cite>/g, ''))
      const content = wrapBulletLines(parseTitles(finalClean))
      return (
        <div className="whitespace-pre-wrap">
          {addSectionDividers(content)}
          {renderFollowUpBlock(followUpQuestions)}
        </div>
      )
    }

    // 기존 <cite>...</cite> 패턴 찾기
    let match
    let citeIndex = 0

    while ((match = oldCiteRegex.exec(cleanedMessage)) !== null) {
      if (match.index > lastIndex) {
        const textBefore = stripRawCiteAndHeadingSyntax(cleanedMessage.substring(lastIndex, match.index))
        if (textBefore) {
          parts.push(
            <span key={`text-${lastIndex}`}>
              {parseTitles(textBefore)}
            </span>
          )
        }
      }

      const sourceText = sources && citeIndex < sources.length ? sources[citeIndex] : null
      const sourceUrl = source_urls && citeIndex < source_urls.length ? source_urls[citeIndex] : null
      const citedContent = (match[1] || '').replace(/^#+\s*/, '').trim() || match[1]

      if (sourceText) {
        parts.push(
          <span key={`cite-${match.index}`}>
            <span className={showFactCheck ? "bg-yellow-200/60 px-0.5" : ""}>
              {parseBold(citedContent)}
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
        parts.push(
          <span key={`cite-${match.index}`}>
            {parseTitles(citedContent)}
          </span>
        )
      }

      citeIndex++
      lastIndex = oldCiteRegex.lastIndex
    }

    if (lastIndex < cleanedMessage.length) {
      const remainingText = stripRawCiteAndHeadingSyntax(cleanedMessage.substring(lastIndex))
      if (remainingText) {
        parts.push(
          <span key={`text-${lastIndex}`}>
            {parseTitles(remainingText)}
          </span>
        )
      }
    }

    const content = wrapBulletLines(parts.length > 0 ? parts : parseTitles(stripRawCiteAndHeadingSyntax(cleanedMessage)))
    return (
      <div className="whitespace-pre-wrap">
        {addSectionDividers(content)}
        {renderFollowUpBlock(followUpQuestions)}
      </div>
    )
  }

  // 메시지에서 [이미지 첨부] 태그 제거
  const getDisplayMessage = () => {
    return message.replace(/^\[이미지 첨부\]\s*/, '')
  }
  const reportCitationCount = countCiteTags()
  const reportRetrievedChunks = countRetrievedChunksFromAgent()

  const renderInlineScoreMentions = (content: React.ReactNode): React.ReactNode => {
    if (typeof content === 'string') {
      const mentionRegex = /(@[가-힣a-zA-Z0-9_]{1,10})/g
      const parts = content.split(mentionRegex)
      if (parts.length <= 1) return content

      return parts.map((part, idx) => {
        if (mentionRegex.test(part)) {
          mentionRegex.lastIndex = 0
          return (
            <button
              key={`inline-score-${idx}-${part}`}
              className="inline-flex items-center align-baseline bg-indigo-50 text-indigo-700 border border-indigo-100 rounded-full px-2 py-0.5 text-xs hover:bg-indigo-100 transition-colors mx-0.5"
              onClick={() => onScoreTagClick?.(part)}
            >
              {part}
            </button>
          )
        }
        return part
      })
    }

    if (Array.isArray(content)) {
      return content.map((node) => renderInlineScoreMentions(node))
    }

    if (content && typeof content === 'object' && 'props' in content) {
      const element = content as React.ReactElement
      if (element.props && element.props.children) {
        const processedChildren = renderInlineScoreMentions(element.props.children)
        if (processedChildren !== element.props.children) {
          return { ...element, props: { ...element.props, children: processedChildren } }
        }
      }
    }

    return content
  }

  if (!isUser && scoreReview) {
    const subjects = ['한국사', '국어', '수학', '영어', '탐구1', '탐구2', '제2외국어/한문']
    const electiveOptionsMap: Record<string, string[]> = {
      국어: ['미응시', '화법과작문', '언어와매체'],
      수학: ['미응시', '확률과통계', '기하', '미적분'],
      영어: ['미응시', '영어'],
      탐구1: ['미응시', '한국지리', '윤리와사상', '생활과윤리', '사회문화', '정치와법', '경제', '세계사', '동아시아사', '세계지리', '물리학1', '물리학2', '화학1', '화학2', '생명과학1', '생명과학2', '지구과학1', '지구과학2'],
      탐구2: ['미응시', '한국지리', '윤리와사상', '생활과윤리', '사회문화', '정치와법', '경제', '세계사', '동아시아사', '세계지리', '물리학1', '물리학2', '화학1', '화학2', '생명과학1', '생명과학2', '지구과학1', '지구과학2'],
      '제2외국어/한문': ['미응시', '독일어1', '프랑스어1', '스페인어1', '중국어1', '일본어1', '러시아어1', '아랍어1', '베트남어1', '한문1'],
    }
    return (
      <div className="flex justify-start mb-4 w-full">
        <div className="w-full bg-white border border-gray-200 rounded-xl p-4">
          <div className="flex items-start justify-between gap-2 mb-3">
            <div className="font-semibold text-gray-900 pt-1">다음 성적을 기반으로 답변할까요?</div>
            <div className="flex gap-2">
              <button className="px-3 py-1.5 rounded-lg bg-gray-100 text-sm" onClick={() => setIsEditScoreReview((v) => !v)}>
                {isEditScoreReview ? '수정 완료' : '수정'}
              </button>
              <button
                className="px-3 py-1.5 rounded-lg bg-blue-600 text-white text-sm"
                onClick={() =>
                  onScoreReviewApprove?.(
                    scoreReview.pendingId,
                    `@${(scoreReviewTitle || '내성적1').slice(0, 10)}`,
                    scoreReviewScores
                  )
                }
              >
                확인
              </button>
              <button
                className="px-3 py-1.5 rounded-lg bg-gray-800 text-white text-sm"
                onClick={() => onScoreReviewSkipSession?.(scoreReview.pendingId)}
              >
                다시 묻지 않기
              </button>
            </div>
          </div>
          <div className="flex items-center gap-2 mb-3">
            <div className="text-sm text-gray-600 shrink-0">제목</div>
            <div className="flex-1 flex items-center rounded-lg border border-gray-300 bg-white">
              <span className="px-3 text-sm text-gray-500">@</span>
              <input
                className="w-full py-2 pr-3 rounded-r-lg text-sm focus:outline-none"
                value={scoreReviewTitle}
                disabled={!isEditScoreReview}
                onChange={(e) => setScoreReviewTitle(e.target.value.slice(0, 10))}
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="text-left">
                  <th className="py-1">과목</th>
                  <th className="py-1">선택과목</th>
                  <th className="py-1">표준점수</th>
                  <th className="py-1">백분위</th>
                  <th className="py-1">등급</th>
                </tr>
              </thead>
              <tbody>
                {subjects.map((subject) => {
                  const row = scoreReviewScores?.[subject] || {}
                  const electiveValue =
                    subject === '한국사' ? '-' : row['선택과목'] ?? row['과목명'] ?? '미응시'
                  const isKoreanHistory = subject === '한국사'
                  const isNoExam = !isKoreanHistory && electiveValue === '미응시'
                  const disableStandardPercentile = isKoreanHistory || isNoExam
                  const disableGrade = isNoExam
                  const setVal = (key: string, value: any) =>
                    setScoreReviewScores((prev) => ({
                      ...prev,
                      [subject]: { ...(prev?.[subject] || {}), [key]: value },
                    }))
                  return (
                    <tr key={subject} className="border-t border-gray-100">
                      <td className="py-1">{subject}</td>
                      <td className="py-1">
                        {subject === '한국사' ? (
                          <span>-</span>
                        ) : (
                          <select
                            className="w-full px-2 py-1 rounded border border-gray-200 bg-white"
                            disabled={!isEditScoreReview}
                            value={electiveValue}
                            onChange={(e) => {
                              const nextValue = e.target.value
                              setVal('선택과목', nextValue)
                              if (nextValue === '미응시') {
                                setVal('표준점수', null)
                                setVal('백분위', null)
                                setVal('등급', null)
                              }
                            }}
                          >
                            {(electiveOptionsMap[subject] || ['미응시']).map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                          </select>
                        )}
                      </td>
                      <td className="py-1">
                        {disableStandardPercentile ? (
                          <span className="text-gray-400">-</span>
                        ) : (
                          <input
                            type="number"
                            min={0}
                            max={200}
                            className="w-full px-2 py-1 rounded border border-gray-200"
                            disabled={!isEditScoreReview}
                            value={row['표준점수'] ?? ''}
                            onChange={(e) => setVal('표준점수', e.target.value === '' ? null : Number(e.target.value))}
                          />
                        )}
                      </td>
                      <td className="py-1">
                        {disableStandardPercentile ? (
                          <span className="text-gray-400">-</span>
                        ) : (
                          <input
                            type="number"
                            min={0}
                            max={100}
                            className="w-full px-2 py-1 rounded border border-gray-200"
                            disabled={!isEditScoreReview}
                            value={row['백분위'] ?? ''}
                            onChange={(e) => setVal('백분위', e.target.value === '' ? null : Number(e.target.value))}
                          />
                        )}
                      </td>
                      <td className="py-1">
                        {disableGrade ? (
                          <span className="text-gray-400">-</span>
                        ) : (
                          <input
                            type="number"
                            min={1}
                            max={9}
                            className="w-full px-2 py-1 rounded border border-gray-200"
                            disabled={!isEditScoreReview}
                            value={row['등급'] ?? ''}
                            onChange={(e) => setVal('등급', e.target.value === '' ? null : Number(e.target.value))}
                          />
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    )
  }

  const renderMaskedLoginCta = (compact: boolean = false) => (
    <div className={`text-center ${compact ? 'p-4' : 'p-6'}`}>
      <div className={`${compact ? 'text-3xl mb-3' : 'text-4xl mb-4'}`}>🔒</div>
      <h3 className={`${compact ? 'text-base' : 'text-lg'} font-bold text-gray-900 mb-2`}>
        로그인하고 답변을 확인하세요
      </h3>
      <p className={`${compact ? 'text-xs' : 'text-sm'} text-gray-600 mb-4`}>
        더 많은 입시 정보와 개인별로 갈 수 있는 대학을 확인해보세요!
      </p>
      <button
        onClick={onLoginClick}
        className={`${compact ? 'px-5 py-2.5 text-sm' : 'px-6 py-3'} bg-gradient-to-r from-blue-500 to-purple-500 hover:from-blue-600 hover:to-purple-600 text-white font-medium rounded-lg transition-all shadow-lg hover:shadow-xl flex items-center gap-2 mx-auto`}
      >
        <svg className={`${compact ? 'w-4 h-4' : 'w-5 h-5'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
        </svg>
        로그인하기
      </button>
    </div>
  )

  const getMobileCtaSlots = (): Array<'top' | 'center' | 'bottom'> => {
    const lineBreakCount = (message.match(/\n/g) || []).length
    const estimatedLength = message.replace(/\s+/g, ' ').length + lineBreakCount * 40

    if (estimatedLength < 520) {
      return ['center'] // 짧은 답변
    }
    if (estimatedLength < 1400) {
      return ['top', 'bottom'] // 중간 길이 답변
    }
    return ['top', 'center', 'bottom'] // 긴 답변
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
            <div className="absolute inset-0 z-10 bg-white/80 backdrop-blur-md rounded-lg overflow-hidden">
              {/* 데스크톱: 중앙 1회 */}
              <div className="hidden sm:flex h-full items-center justify-center">
                {renderMaskedLoginCta(false)}
              </div>

              {/* 모바일: 답변 길이에 따라 1/2/3개 CTA를 유동 배치 */}
              <div className="sm:hidden absolute inset-0 pointer-events-none">
                {getMobileCtaSlots().map((slot, index) => {
                  const positionClass =
                    slot === 'top'
                      ? 'top-5 left-1/2 -translate-x-1/2'
                      : slot === 'center'
                        ? 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2'
                        : 'bottom-5 left-1/2 -translate-x-1/2'

                  return (
                    <div
                      key={`${slot}-${index}`}
                      className={`absolute ${positionClass} w-[88%] max-w-sm pointer-events-auto`}
                    >
                      <div className="rounded-xl bg-white/90 shadow-md border border-gray-100">
                        {renderMaskedLoginCta(true)}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
          
          <div
            className={`text-gray-900 ai-response mb-4 ${isMasked ? 'blur-sm select-none' : ''} ${
              isSchoolRecordReport
                ? 'rounded-2xl border border-gray-200 bg-white px-5 py-5 sm:px-7 sm:py-6'
                : ''
            }`}
          >
            {isSchoolRecordReport && (
              <div className="mb-4 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-[16px] font-semibold text-gray-900">
                    <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-[#0e6093]/10 text-[#0e6093]">
                      📄
                    </span>
                    <span>생활기록부 심층 분석 보고서</span>
                  </div>
                  <p className="mt-1 text-[12px] text-gray-500">
                    리포트 · 인용 {reportCitationCount}개
                    {reportRetrievedChunks > 0 ? ` · 검색 ${reportRetrievedChunks}건` : ''}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsReportFullscreen(true)}
                  className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-gray-200 bg-white text-gray-700 transition hover:bg-gray-50"
                  title="전체화면으로 보기"
                  aria-label="전체화면으로 보기"
                >
                  <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 3H3v5M16 3h5v5M8 21H3v-5M21 16v5h-5" />
                  </svg>
                </button>
              </div>
            )}
            {renderMessage()}
          </div>
          
          {/* 버튼 영역 - 스트리밍 완료 후에만 표시, 마스킹 시 숨김 */}
          {!isStreaming && !isMasked && (
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
            
            {/* Agent 디버그 버튼 (관리자 전용) */}
            {isAdmin && (
              <button
                onClick={onAgentClick}
                className={`flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                  agentData ? 'text-purple-600 hover:bg-purple-50' : 'text-gray-400 cursor-not-allowed'
                }`}
                disabled={!agentData}
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                </svg>
                Agent
              </button>
            )}
          </div>
          )}
        </div>
      )}

      {isSchoolRecordReport && isReportFullscreen && (
        <div className="fixed inset-0 z-[80] bg-black/55 p-3 sm:p-6">
          <div className="mx-auto flex h-full w-full max-w-[1320px] flex-col overflow-hidden rounded-3xl border border-gray-200 bg-white">
            <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4 sm:px-7">
              <div className="flex items-center gap-2 text-[16px] font-semibold text-gray-900 sm:text-[18px]">
                <span className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-[#0e6093]/10 text-[#0e6093]">
                  📄
                </span>
                <span>생활기록부 심층 분석 보고서</span>
              </div>
              <button
                type="button"
                onClick={() => setIsReportFullscreen(false)}
                className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-gray-200 bg-white text-gray-700 transition hover:bg-gray-50"
                title="전체화면 닫기"
                aria-label="전체화면 닫기"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex flex-1 overflow-hidden">
              <div className={`ai-response flex-1 overflow-y-auto px-5 py-5 sm:px-8 sm:py-7 transition-all duration-300 ${activeChunk ? 'w-3/5' : 'w-full'}`}>
                {renderMessage()}
              </div>
              {activeChunk && (
                <div className="w-2/5 border-l border-gray-200 bg-gray-50 flex flex-col overflow-hidden animate-slideIn">
                  <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200 bg-white">
                    <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                      <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-blue-50 text-blue-600 text-xs">📄</span>
                      출처 근거
                    </h3>
                    <button
                      onClick={() => setActiveChunk(null)}
                      className="p-1.5 hover:bg-gray-100 rounded-lg transition-colors text-gray-500"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto p-5 space-y-4">
                    <div className="rounded-xl bg-white border border-gray-200 p-4 shadow-sm">
                      <div className="flex items-center gap-2 mb-3">
                        <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-[10px] font-semibold rounded-full">문서</span>
                        <span className="text-xs font-medium text-gray-700 truncate">{activeChunk.title}</span>
                      </div>
                      <p className="text-xs text-gray-500 mb-3">{activeChunk.source}</p>
                      <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap max-h-[60vh] overflow-y-auto">
                        {activeChunk.content}
                      </div>
                    </div>
                    {activeChunk.file_url && (
                      <a
                        href={activeChunk.file_url}
                        download
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center justify-center gap-2 w-full py-2.5 bg-blue-50 text-blue-600 text-xs font-medium rounded-lg hover:bg-blue-100 transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        원본 문서 다운로드
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 인라인(비전체화면) 출처 패널 */}
      {activeChunk && !isReportFullscreen && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 p-4" onClick={() => setActiveChunk(null)}>
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-gray-200 overflow-hidden animate-slideIn" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-gray-50">
              <h3 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-blue-50 text-blue-600 text-xs">📄</span>
                출처 근거
              </h3>
              <button
                onClick={() => setActiveChunk(null)}
                className="p-1.5 hover:bg-gray-200 rounded-lg transition-colors text-gray-500"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-5 space-y-4">
              <div className="rounded-xl bg-gray-50 border border-gray-200 p-4">
                <div className="flex items-center gap-2 mb-3">
                  <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-[10px] font-semibold rounded-full">문서</span>
                  <span className="text-xs font-medium text-gray-700 truncate">{activeChunk.title}</span>
                </div>
                <p className="text-xs text-gray-500 mb-3">{activeChunk.source}</p>
                <div className="bg-white rounded-lg p-4 text-sm text-gray-800 leading-relaxed whitespace-pre-wrap max-h-[50vh] overflow-y-auto border border-gray-100">
                  {activeChunk.content}
                </div>
              </div>
              {activeChunk.file_url && (
                <a
                  href={activeChunk.file_url}
                  download
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-center gap-2 w-full py-2.5 bg-blue-50 text-blue-600 text-xs font-medium rounded-lg hover:bg-blue-100 transition-colors"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  원본 문서 다운로드
                </a>
              )}
            </div>
          </div>
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

