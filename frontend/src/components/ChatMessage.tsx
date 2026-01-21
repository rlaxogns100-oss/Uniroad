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
      <div className="leading-relaxed">
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
 * 마크다운 표 파싱 및 렌더링
 * 텍스트에서 표를 찾아 위치와 함께 반환
 */
function findAndParseTable(text: string, keyPrefix: string): { 
  found: boolean
  beforeTable: string
  table?: JSX.Element
  afterTable: string 
} {
  const lines = text.split('\n')
  
  // 표 시작 위치 찾기
  let tableStartIdx = -1
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim().match(/^\|.+\|$/)) {
      // 다음 줄이 구분선인지 확인
      if (i + 1 < lines.length && lines[i + 1].trim().match(/^\|[-:\s|]+\|$/)) {
        tableStartIdx = i
        break
      }
    }
  }
  
  if (tableStartIdx === -1) {
    return { found: false, beforeTable: text, afterTable: '' }
  }
  
  // 표 줄들 수집
  const tableLines: string[] = []
  let tableEndIdx = tableStartIdx
  
  for (let i = tableStartIdx; i < lines.length; i++) {
    if (lines[i].trim().match(/^\|.+\|$/) || lines[i].trim().match(/^\|[-:\s|]+\|$/)) {
      tableLines.push(lines[i])
      tableEndIdx = i
    } else {
      break
    }
  }
  
  if (tableLines.length < 3) {  // 헤더 + 구분선 + 최소 1개 데이터
    return { found: false, beforeTable: text, afterTable: '' }
  }
  
  // 헤더 파싱
  const headerLine = tableLines[0]
  const headers = headerLine.split('|').filter(h => h.trim()).map(h => h.trim())
  
  // 데이터 행 파싱 (구분선 제외)
  const rows = tableLines.slice(2).map(line => 
    line.split('|').filter(c => c.trim() !== '' || c.includes(' ')).map(cell => cell.trim())
  ).filter(row => row.length > 0)
  
  // HTML 테이블 생성
  const table = (
    <table key={keyPrefix} className="w-full my-2 border-collapse border border-gray-300 text-sm">
      <thead className="bg-gray-100">
        <tr>
          {headers.map((header, idx) => (
            <th key={idx} className="border border-gray-300 px-2 py-1.5 text-left font-semibold text-gray-800 whitespace-nowrap">
              {header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, rowIdx) => (
          <tr key={rowIdx} className={rowIdx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
            {row.map((cell, cellIdx) => (
              <td key={cellIdx} className="border border-gray-300 px-2 py-1.5 text-gray-700">
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
  
  const beforeTable = lines.slice(0, tableStartIdx).join('\n')
  const afterTable = lines.slice(tableEndIdx + 1).join('\n')
  
  return { found: true, beforeTable, table, afterTable }
}

/**
 * 메시지 파싱 및 렌더링
 * - 【타이틀】 → 볼드 타이틀
 * - <cite data-source="..." data-url="...">...</cite> → 밑줄 (출처는 문단 끝에 모음)
 * - <cite>...</cite> (기존 형식) → 밑줄 (출처는 문단 끝에 모음)
 * - | ... | 표 형식 → HTML 테이블
 */
// 텍스트를 줄바꿈 포함하여 렌더링
// • 로 시작하는 소분류 항목은 위아래 마진(mb-4) 적용
function renderTextWithBreaks(text: string, keyPrefix: string): React.ReactNode[] {
  // 연속 줄바꿈을 하나로 정리
  const cleanedText = text.replace(/\n\s*\n/g, '\n').trim()
  if (!cleanedText) return []
  
  const lines = cleanedText.split('\n')
  return lines.map((line, idx) => {
    const trimmedLine = line.trim()
    const isBulletPoint = trimmedLine.startsWith('•') || trimmedLine.startsWith('-')
    
    if (isBulletPoint) {
      // 소분류 항목: 위아래 마진 적용
      return (
        <div key={`${keyPrefix}-${idx}`} className="my-4">
          {line}
        </div>
      )
    }
    
    // 일반 텍스트
    return (
      <React.Fragment key={`${keyPrefix}-${idx}`}>
        {line}
        {idx < lines.length - 1 && <br />}
      </React.Fragment>
    )
  })
}

function parseAndRenderMessage(
  message: string,
  sources?: string[],
  source_urls?: string[]
): React.ReactNode[] {
  const result: React.ReactNode[] = []
  
  // 메시지를 섹션 단위로 분리 (빈 줄 2개 기준)
  const paragraphs = message.split(/\n\n+/).filter(p => p.trim())
  
  paragraphs.forEach((paragraph, paragraphIndex) => {
    const paragraphResult: React.ReactNode[] = []
    const paragraphSources: Array<{ text: string; url: string }> = []
    let remaining = paragraph
    let keyIndex = 0
    let simpleCiteIndex = 0

    while (remaining.length > 0) {
      // 표 패턴 먼저 체크
      const tableResult = findAndParseTable(remaining, `table-${paragraphIndex}-${keyIndex}`)
      if (tableResult.found && tableResult.table) {
        // 표 이전 텍스트가 있으면 먼저 처리
        if (tableResult.beforeTable.trim()) {
          const textNodes = renderTextWithBreaks(tableResult.beforeTable.trim(), `tbl-before-${keyIndex}`)
          if (textNodes.length > 0) {
            paragraphResult.push(<span key={`text-${keyIndex++}`}>{textNodes}</span>)
          }
        }
        paragraphResult.push(tableResult.table)
        keyIndex++
        remaining = tableResult.afterTable
        continue
      }

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
        // 더 이상 패턴 없음 - 나머지 텍스트 추가 (줄바꿈 처리)
        const textNodes = renderTextWithBreaks(remaining, `text-${keyIndex}`)
        if (textNodes.length > 0) {
          paragraphResult.push(<span key={`text-${keyIndex++}`}>{textNodes}</span>)
        }
        break
      }

      const firstMatch = matches[0]
      const matchIndex = firstMatch.index

      // 패턴 이전 텍스트 추가 (타이틀 앞 텍스트는 trim)
      if (matchIndex > 0) {
        const beforeText = remaining.substring(0, matchIndex)
        const trimmedText = firstMatch.type === 'title' ? beforeText.trim() : beforeText.trim()
        if (trimmedText) {
          const textNodes = renderTextWithBreaks(trimmedText, `before-${keyIndex}`)
          if (textNodes.length > 0) {
            paragraphResult.push(<span key={`text-${keyIndex++}`}>{textNodes}</span>)
          }
        }
      }

      // 패턴 처리
      if (firstMatch.type === 'title' && titleMatch) {
        // 【타이틀】 → 볼드 타이틀 (하단 여백 mb-4)
        paragraphResult.push(
          <div key={`title-${keyIndex++}`} className="font-bold text-gray-900 mt-3 mb-4 text-lg leading-tight">
            {titleMatch[1]}
          </div>
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
        const citedText = dataCiteMatch[3].trim()

        // 텍스트만 추가 (빈 텍스트가 아닌 경우만)
        if (citedText) {
          const textNodes = renderTextWithBreaks(citedText, `cite-${keyIndex}`)
          if (textNodes.length > 0) {
            paragraphResult.push(<span key={`cite-${keyIndex++}`}>{textNodes}</span>)
          }
        }

        // 출처 정보 저장 (중복 제거)
        if (sourceText && !paragraphSources.some(s => s.text === sourceText && s.url === sourceUrl)) {
          paragraphSources.push({ text: sourceText, url: sourceUrl })
        }

        remaining = remaining.substring(matchIndex + dataCiteMatch[0].length)
      }
      else if (firstMatch.type === 'simpleCite' && simpleCiteMatch) {
        // <cite>...</cite> (기존 형식)
        const citedText = simpleCiteMatch[1].trim()
        const sourceText = sources && simpleCiteIndex < sources.length ? sources[simpleCiteIndex] : null
        const sourceUrl = source_urls && simpleCiteIndex < source_urls.length ? source_urls[simpleCiteIndex] : null

        // 텍스트만 추가 (빈 텍스트가 아닌 경우만)
        if (citedText) {
          const textNodes = renderTextWithBreaks(citedText, `scite-${keyIndex}`)
          if (textNodes.length > 0) {
            paragraphResult.push(<span key={`cite-${keyIndex++}`}>{textNodes}</span>)
          }
        }

        // 출처 정보 저장 (중복 제거)
        if (sourceText && !paragraphSources.some(s => s.text === sourceText && s.url === sourceUrl)) {
          paragraphSources.push({ text: sourceText || '', url: sourceUrl || '' })
        }

        simpleCiteIndex++
        remaining = remaining.substring(matchIndex + simpleCiteMatch[0].length)
      }
    }

    // 문단 결과 추가 (섹션 간 여백 충분히, 마지막 섹션 제외)
    result.push(
      <div key={`para-${paragraphIndex}`} className="mb-6 last:mb-0">
        {paragraphResult}
        {/* 문단 끝에 출처 표시 - 바로 붙임 */}
        {paragraphSources.length > 0 && (
          <div className="border-t border-gray-200 mt-1 pt-1 flex flex-wrap gap-1.5 items-center">
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
