import React from 'react'

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
  sources?: string[]
  source_urls?: string[]
  used_chunks?: UsedChunk[]
}

export default function ChatMessage({ message, isUser, sources, source_urls, used_chunks }: ChatMessageProps) {
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
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className="flex flex-col max-w-[85%] sm:max-w-[75%]">
        <div
          className={`rounded-2xl px-4 py-3 text-sm sm:text-base ${
            isUser
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-white text-gray-900 shadow-sm'
          }`}
        >
          {renderMessage()}
        </div>
        
        {/* 팩트 체크 섹션 - 접을 수 있게 */}
        {!isUser && used_chunks && used_chunks.length > 0 && (
          <details className="mt-4 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden group">
            {/* 헤더 (summary) */}
            <summary className="bg-gray-50 px-4 py-3 border-b border-gray-200 cursor-pointer list-none">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 rounded border-2 border-gray-400 flex items-center justify-center flex-shrink-0 group-open:bg-blue-100 group-open:border-blue-500 transition-colors">
                    <svg className="w-3 h-3 text-gray-600 group-open:text-blue-600 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">팩트 체크</h3>
                    <p className="text-xs text-gray-500 mt-0.5">답변에 인용된 부분이에요</p>
                  </div>
                </div>
                <svg 
                  className="w-5 h-5 text-gray-400 group-open:rotate-180 transition-transform flex-shrink-0" 
                  fill="none" 
                  stroke="currentColor" 
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </summary>
            
            {/* 청크 목록 (접혔을 때는 보이지 않음) */}
            <div className="divide-y divide-gray-100">
              {used_chunks.map((chunk, index) => {
                const handleDownload = () => {
                  // 청크 내용을 텍스트 파일로 다운로드
                  const content = `제목: ${chunk.title || '문서 내용'}\n출처: ${chunk.source || ''}\n\n${chunk.content}`
                  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
                  const url = URL.createObjectURL(blob)
                  const link = document.createElement('a')
                  link.href = url
                  link.download = `${chunk.title || '문서'}_${index + 1}.txt`
                  document.body.appendChild(link)
                  link.click()
                  document.body.removeChild(link)
                  URL.revokeObjectURL(url)
                }

                return (
                  <div key={chunk.id || index} className="px-4 py-4">
                    {/* 출처 정보 */}
                    <div className="flex items-center gap-2 mb-3">
                      <div className="w-6 h-6 rounded-full bg-blue-100 flex items-center justify-center flex-shrink-0">
                        <span className="text-xs font-bold text-blue-700">
                          {chunk.source ? chunk.source.charAt(0) : chunk.title ? chunk.title.charAt(0) : '문'}
                        </span>
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-bold text-gray-900 truncate">
                          {chunk.title || '문서 내용'}
                        </p>
                        {chunk.source && (
                          <p className="text-xs text-gray-500 truncate">{chunk.source}</p>
                        )}
                      </div>
                    </div>
                    
                    {/* 청크 내용 */}
                    <div className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed mb-3">
                      {chunk.content}
                    </div>
                    
                    {/* 자료 다운 버튼 */}
                    <button
                      onClick={handleDownload}
                      className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium text-gray-700 bg-gray-50 hover:bg-gray-100 rounded-lg border border-gray-200 transition-colors"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      자료 다운
                    </button>
                  </div>
                )
              })}
            </div>
          </details>
        )}
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
          <div key={`title-${keyIndex++}`} className="font-bold text-gray-900 mt-3 mb-4 text-base sm:text-lg leading-tight">
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

        // 인용된 텍스트를 시각적으로 강조 (배경색, 아이콘)
        if (citedText) {
          const textNodes = renderTextWithBreaks(citedText, `cite-${keyIndex}`)
          if (textNodes.length > 0) {
            paragraphResult.push(
              <span 
                key={`cite-${keyIndex++}`}
                className="inline-flex items-center gap-1 bg-blue-50 text-blue-900 px-1.5 py-0.5 rounded border border-blue-200"
                title={`인용: ${sourceText}`}
              >
                <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {textNodes}
              </span>
            )
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

        // 인용된 텍스트를 시각적으로 강조 (배경색, 아이콘)
        if (citedText) {
          const textNodes = renderTextWithBreaks(citedText, `scite-${keyIndex}`)
          if (textNodes.length > 0) {
            paragraphResult.push(
              <span 
                key={`cite-${keyIndex++}`}
                className="inline-flex items-center gap-1 bg-blue-50 text-blue-900 px-1.5 py-0.5 rounded border border-blue-200"
                title={sourceText ? `인용: ${sourceText}` : '인용된 내용'}
              >
                <svg className="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                {textNodes}
              </span>
            )
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
        {/* 문단 끝에 출처 표시 - 깔끔하게 */}
        {paragraphSources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 items-center">
            {paragraphSources.map((source, idx) => {
              // 하드코딩 URL (수능 점수 변환 및 추정 방법 PDF)
              const SCORE_GUIDE_URL = "https://rnitmphvahpkosvxjshw.supabase.co/storage/v1/object/public/document/pdfs/efe55407-d51c-4cab-8c20-aabb2445ac2b.pdf"
              
              // "환산" 관련 출처는 모두 "수능 점수 변환 및 추정 방법"으로 통일
              let finalText = source.text
              let finalUrl = source.url
              
              if (source.text.includes("환산") || source.text.includes("추정") || source.text.includes("변환")) {
                finalText = "수능 점수 변환 및 추정 방법"
                finalUrl = SCORE_GUIDE_URL
              }
              
              // URL 없으면 클릭 불가능한 span
              if (!finalUrl) {
                return (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs font-medium text-gray-400 bg-gray-100 rounded"
                  >
                    <svg className="w-3 h-3 flex-shrink-0 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {finalText}
                  </span>
                )
              }
              
              // URL 있으면 클릭 가능 - 새 탭에서 열기 (가장 단순하고 확실한 방법)
              return (
                <a
                  key={idx}
                  href={finalUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs font-medium text-gray-500 bg-gray-100 hover:bg-gray-200 rounded transition-colors cursor-pointer group"
                  title={`출처: ${finalText} (클릭하여 열기)`}
                >
                  <svg className="w-3 h-3 flex-shrink-0 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <span className="group-hover:underline">{finalText}</span>
                </a>
              )
            })}
          </div>
        )}
      </div>
    )
  })

  return result
}
