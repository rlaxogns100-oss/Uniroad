import { forwardRef } from 'react'

/* ────────────────────────── 타입 ────────────────────────── */
interface SubjectGrade {
  name: string
  grades: (number | null)[]
  color: string
}

interface FlowNode {
  id: string
  label: string
  sub: string
  type: 'start' | 'activity' | 'milestone' | 'result' | 'warning' | 'missing'
}

interface StrengthWeakness {
  title: string
  subtitle: string
  type: 'heatmap' | 'text-analysis' | 'flowchart' | 'bar-chart'
  description?: string | null
  data: any
}

interface ComparisonCard {
  title: string
  subtitle: string
  accepted: { label: string; text: string }
  student: { text: string }
  highlight: string
}

export interface VisualReportData {
  studentName: string
  page1: {
    grades: {
      subjects: SubjectGrade[]
      semesters: string[]
      avgAll: number[]
      avgMain: number[]
    }
    radar: {
      values: number[]
      labels: string[]
      totalScore: number
    }
    studentType: string
    studentTypeHighlight: string
    hashtags: string[]
    summary: string
    growthSummary: string
    growthSteps: { title: string; desc: string; sub: string }[]
    keyPoints: { label: string; desc: string }[]
  }
  page2: { strengths: StrengthWeakness[] }
  page3: { weaknesses: StrengthWeakness[]; diagnosisSummary: string }
  page4: { targetMajor: string; comparisons: ComparisonCard[] }
}

/* ────────────────────────── 유틸 ────────────────────────── */
const BLUE = '#5B9BD5'
const DARK = '#2E5C8A'
const RED = '#C0392B'
const CHEVRON_PALETTE = ['#B8D4E8', '#96C3DE', '#7FB3D5', '#5B9BD5', '#3D7EBF', '#2E5C8A']
const clampText = (text: string, max: number) => {
  const value = String(text || '').trim()
  if (value.length <= max) return value
  return `${value.slice(0, Math.max(0, max - 1)).trim()}…`
}

const splitText = (text: string, maxCharsPerLine: number, maxLines: number) => {
  const raw = String(text || '').trim()
  if (!raw) return []
  const words = raw.split(/\s+/)
  const lines: string[] = []
  let current = ''
  for (const word of words) {
    const next = current ? `${current} ${word}` : word
    if (next.length <= maxCharsPerLine) {
      current = next
      continue
    }
    if (current) lines.push(current)
    current = word
    if (lines.length >= maxLines - 1) break
  }
  if (lines.length < maxLines && current) lines.push(current)
  if (lines.length > maxLines) return lines.slice(0, maxLines)
  if (lines.length === maxLines && words.join(' ').length > lines.join(' ').length) {
    lines[maxLines - 1] = clampText(lines[maxLines - 1], maxCharsPerLine)
  }
  return lines
}

const nodeColor = (type: FlowNode['type']) => {
  switch (type) {
    case 'start': return DARK
    case 'milestone': return BLUE
    case 'result': return DARK
    case 'warning': return RED
    case 'missing': return RED
    default: return '#EBF4FA'
  }
}
const nodeTextColor = (type: FlowNode['type']) => {
  switch (type) {
    case 'start': case 'milestone': case 'result': return 'white'
    case 'warning': case 'missing': return RED
    default: return DARK
  }
}
const nodeBorder = (type: FlowNode['type']) => {
  if (type === 'warning' || type === 'missing') return RED
  if (type === 'activity') return BLUE
  return 'none'
}

/* ────────────────────────── 서브 컴포넌트 ────────────────────────── */

function Watermark() {
  return (
    <div
      className="pointer-events-none absolute right-8 top-10 select-none"
      style={{ fontSize: '60px', fontWeight: 900, letterSpacing: '6px', color: 'rgba(0,0,0,0.04)' }}
    >
      UNIROAD
    </div>
  )
}

function PageFooter({ page }: { page: number }) {
  return (
    <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-10 py-4">
      <p className="text-xs leading-none text-gray-500">
        Written by <span className="font-extrabold" style={{ color: BLUE }}>UNIROAD</span>
      </p>
      <p className="text-xs leading-none text-gray-400">Page {page}</p>
    </div>
  )
}

function PageShell({ page, children }: { page: number; children: React.ReactNode }) {
  return (
    <div
      data-page={page}
      className="mx-auto max-w-[800px] border border-gray-200 bg-white shadow-md"
      style={{
        minHeight: '1130px',
        position: 'relative',
        overflow: 'hidden',
        marginTop: page > 1 ? '32px' : 0,
        breakAfter: page < 4 ? 'page' : 'auto',
        pageBreakAfter: page < 4 ? 'always' : 'auto',
      }}
    >
      <Watermark />
      <div className="px-10 pb-6 pt-8">{children}</div>
      <PageFooter page={page} />
    </div>
  )
}

function Badge({ text }: { text: string }) {
  return (
    <div className="mb-4">
      <span
        className="inline-flex items-center justify-center rounded-full px-4 text-xs font-bold text-white"
        style={{ backgroundColor: BLUE, height: '24px' }}
      >
        {text}
      </span>
    </div>
  )
}

/* ─── 히트맵 ─── */
function HeatmapViz({ data }: { data: any }) {
  const subjects: string[] = data?.subjects ?? []
  const semesters: string[] = data?.semesters ?? []
  const values: (number | null)[][] = data?.values ?? []
  const bgColor = (g: number | null) => {
    if (g === null) return '#F9FAFB'
    if (g === 1) return '#DBEAFE'
    if (g === 2) return '#EFF6FF'
    return 'transparent'
  }
  return (
    <div className="flex justify-center px-5 pb-3">
      <table className="text-center" style={{ borderCollapse: 'collapse', width: '420px' }}>
        <thead>
          <tr>
            <th style={{ width: '48px', padding: '2px 0' }} />
            {semesters.map(s => (
              <th key={s} style={{ padding: '2px 0', fontSize: '11px', fontWeight: 600, color: '#94A3B8' }}>{s}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {subjects.map((subj, row) => (
            <tr key={subj} style={{ borderTop: '1px solid #F1F5F9' }}>
              <td style={{ padding: '3px 6px 3px 0', fontSize: '12px', fontWeight: 600, color: '#374151', textAlign: 'left' }}>{subj}</td>
              {semesters.map((_, col) => {
                const v = values[row]?.[col] ?? null
                return (
                  <td key={col} style={{ padding: '3px 0', fontSize: '13px', fontWeight: 700, color: v === null ? '#D1D5DB' : '#374151', backgroundColor: bgColor(v) }}>
                    {v === null ? '-' : v}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/* ─── 좌측 인용 / 우측 분석 ─── */
function TextAnalysisViz({ data }: { data: any }) {
  return (
    <div className="flex">
      <div className="flex-1 border-r border-gray-100 px-5 pb-4">
        <p className="text-[11px] leading-5 text-gray-600" style={{ fontStyle: 'italic' }}>"{data?.quote}"</p>
      </div>
      <div className="flex-1 px-5 pb-4">
        <p className="text-[11px] leading-5 text-gray-500">{data?.analysis}</p>
      </div>
    </div>
  )
}

/* ─── 플로우차트 (간소화) ─── */
function FlowchartViz({ data, isWeakness }: { data: any; isWeakness?: boolean }) {
  const nodes: FlowNode[] = data?.nodes ?? []
  if (nodes.length === 0) return null
  const accentColor = isWeakness ? RED : BLUE
  const startNode = nodes[0]
  const resultNode = nodes[nodes.length - 1]
  const middleNodes = nodes.slice(1, -1)
  const splitIndex = Math.ceil(middleNodes.length / 2)
  const topNodes = middleNodes.slice(0, splitIndex)
  const bottomNodes = middleNodes.slice(splitIndex)
  const columnCount = Math.max(topNodes.length, bottomNodes.length, 1)
  const svgW = Math.max(960, 340 + columnCount * 195 + 240)
  const svgH = 310
  const startX = 20
  const startY = 125
  const nodeW = 140
  const nodeH = 48
  const branchCenterX = 210
  const topY = 40
  const bottomY = 212
  const firstColX = 295
  const colGap = 190
  const mergeCenterX = firstColX + (columnCount - 1) * colGap + 150
  const resultX = mergeCenterX + 95
  const branchLabel = String(data?.branchLabel || (isWeakness ? '전환 지점' : '전문 확장')).trim()
  const mergeLabel = String(data?.mergeLabel || (isWeakness ? '보완 필요' : '역량 통합')).trim()
  const branchLines = splitText(branchLabel, 6, 2)
  const mergeLines = splitText(mergeLabel, 6, 2)
  const diamondLineSpacing = 10

  const renderNodeText = (
    x: number,
    y: number,
    width: number,
    label: string,
    sub: string,
    color: string
  ) => {
    const labelLines = splitText(label, 10, 2)
    const subLines = splitText(sub, 13, 2)
    const centerX = x + width / 2
    const centerY = y + nodeH / 2
    const labelLineSpacing = 14
    const subLineSpacing = 11

    if (subLines.length === 0) {
      const labelStartY = centerY - ((labelLines.length - 1) * labelLineSpacing) / 2
      return (
        <text
          x={centerX}
          y={labelStartY}
          textAnchor="middle"
          fontSize="12"
          fill={color}
          fontWeight="700"
          dominantBaseline="central"
        >
          {labelLines.map((line, idx) => (
            <tspan key={idx} x={centerX} dy={idx === 0 ? 0 : labelLineSpacing}>{line}</tspan>
          ))}
        </text>
      )
    }

    const labelBlockH = (labelLines.length - 1) * labelLineSpacing
    const subBlockH = (subLines.length - 1) * subLineSpacing
    const gap = 12
    const totalH = labelBlockH + gap + subBlockH
    const labelStartY = centerY - totalH / 2
    const subStartY = labelStartY + labelBlockH + gap

    return (
      <>
        <text
          x={centerX}
          y={labelStartY}
          textAnchor="middle"
          fontSize="12"
          fill={color}
          fontWeight="700"
          dominantBaseline="central"
        >
          {labelLines.map((line, idx) => (
            <tspan key={idx} x={centerX} dy={idx === 0 ? 0 : labelLineSpacing}>{line}</tspan>
          ))}
        </text>
        <text
          x={centerX}
          y={subStartY}
          textAnchor="middle"
          fontSize="9.5"
          fill={color}
          opacity={0.82}
          dominantBaseline="central"
        >
          {subLines.map((line, idx) => (
            <tspan key={idx} x={centerX} dy={idx === 0 ? 0 : subLineSpacing}>{line}</tspan>
          ))}
        </text>
      </>
    )
  }

  const renderRectNode = (node: FlowNode, x: number, y: number) => {
    const fill = nodeColor(node.type)
    const textFill = nodeTextColor(node.type)
    const border = nodeBorder(node.type)
    const isDashed = node.type === 'missing'
    return (
      <g key={node.id}>
        <rect
          x={x}
          y={y}
          width={nodeW}
          height={nodeH}
          rx={node.type === 'start' || node.type === 'result' || node.type === 'milestone' ? 20 : 5}
          fill={fill === RED ? 'none' : fill}
          stroke={border !== 'none' ? border : fill}
          strokeWidth={1.4}
          strokeDasharray={isDashed ? '5 3' : undefined}
        />
        {renderNodeText(x, y, nodeW, node.label, node.sub, textFill)}
      </g>
    )
  }

  return (
    <div className="px-5 pb-4">
      <svg viewBox={`0 0 ${svgW} ${svgH}`} className="w-full" style={{ height: isWeakness ? '200px' : '220px' }}>
        <defs>
          <marker id={`fc-arrow-${isWeakness ? 'w' : 's'}`} markerWidth="7" markerHeight="5" refX="7" refY="2.5" orient="auto">
            <path d="M0,0 L7,2.5 L0,5" fill="none" stroke="#94A3B8" strokeWidth="1" />
          </marker>
        </defs>
        <text x={firstColX + 20} y={18} fontSize="8" fill="#94A3B8" fontWeight="600" dominantBaseline="central">1학년</text>
        <text x={firstColX + colGap + 20} y={18} fontSize="8" fill="#94A3B8" fontWeight="600" dominantBaseline="central">2학년</text>
        <text x={mergeCenterX - 20} y={18} fontSize="8" fill="#94A3B8" fontWeight="600" dominantBaseline="central">3학년</text>

        <line x1={firstColX - 35} y1="10" x2={firstColX - 35} y2="228" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />
        <line x1={firstColX + colGap - 35} y1="10" x2={firstColX + colGap - 35} y2="228" stroke="#E5E7EB" strokeWidth="0.8" strokeDasharray="4 3" />

        {renderRectNode(startNode, startX, startY + 30 - nodeH / 2)}

        <line x1={startX + nodeW} y1={startY + 30} x2={branchCenterX - 38} y2={startY + 30} stroke="#94A3B8" strokeWidth="1.2" markerEnd={`url(#fc-arrow-${isWeakness ? 'w' : 's'})`} />
        <text x={startX + nodeW + 5} y={startY + 14} textAnchor="start" fontSize="9" fill={BLUE} fontWeight="600" dominantBaseline="central">
          {isWeakness ? '연결 부족' : '탐구 심화'}
        </text>

        <polygon points={`${branchCenterX},${startY + 6} ${branchCenterX + 36},${startY + 30} ${branchCenterX},${startY + 54} ${branchCenterX - 36},${startY + 30}`} fill="none" stroke={accentColor} strokeWidth="1.5" />
        <text x={branchCenterX} y={startY + 30 - ((branchLines.length - 1) * diamondLineSpacing) / 2} textAnchor="middle" fontSize="10" fill={accentColor} fontWeight="700" dominantBaseline="central">
          {branchLines.map((line, idx) => (
            <tspan key={idx} x={branchCenterX} dy={idx === 0 ? 0 : diamondLineSpacing}>{line}</tspan>
          ))}
        </text>

        <line x1={branchCenterX} y1={startY + 6} x2={branchCenterX} y2={topY + nodeH / 2} stroke="#94A3B8" strokeWidth="1.2" />
        <line x1={branchCenterX} y1={topY + nodeH / 2} x2={firstColX} y2={topY + nodeH / 2} stroke="#94A3B8" strokeWidth="1.2" markerEnd={`url(#fc-arrow-${isWeakness ? 'w' : 's'})`} />
        <text x={branchCenterX + 28} y={topY + nodeH / 2 - 10} fontSize="9" fill={BLUE} fontWeight="600" dominantBaseline="central">상위 확장</text>

        <line x1={branchCenterX} y1={startY + 54} x2={branchCenterX} y2={bottomY + nodeH / 2} stroke="#94A3B8" strokeWidth="1.2" />
        <line x1={branchCenterX} y1={bottomY + nodeH / 2} x2={firstColX} y2={bottomY + nodeH / 2} stroke="#94A3B8" strokeWidth="1.2" markerEnd={`url(#fc-arrow-${isWeakness ? 'w' : 's'})`} />
        <text x={branchCenterX + 28} y={bottomY + nodeH / 2 - 10} fontSize="9" fill={BLUE} fontWeight="600" dominantBaseline="central">보조 전개</text>

        {topNodes.map((node, idx) => {
          const x = firstColX + idx * colGap
          return (
            <g key={node.id}>
              {renderRectNode(node, x, topY)}
              {idx < topNodes.length - 1 && (
                <>
                  <line x1={x + nodeW} y1={topY + nodeH / 2} x2={x + colGap} y2={topY + nodeH / 2} stroke="#94A3B8" strokeWidth="1.2" markerEnd={`url(#fc-arrow-${isWeakness ? 'w' : 's'})`} />
                  <text x={x + nodeW + colGap / 2 - 8} y={topY + nodeH / 2 - 12} textAnchor="middle" fontSize="9" fill={BLUE} fontWeight="600" dominantBaseline="central">심화</text>
                </>
              )}
            </g>
          )
        })}

        {bottomNodes.map((node, idx) => {
          const x = firstColX + idx * colGap
          return (
            <g key={node.id}>
              {renderRectNode(node, x, bottomY)}
              {idx < bottomNodes.length - 1 && (
                <>
                  <line x1={x + nodeW} y1={bottomY + nodeH / 2} x2={x + colGap} y2={bottomY + nodeH / 2} stroke="#94A3B8" strokeWidth="1.2" markerEnd={`url(#fc-arrow-${isWeakness ? 'w' : 's'})`} />
                  <text x={x + nodeW + colGap / 2 - 8} y={bottomY + nodeH / 2 - 12} textAnchor="middle" fontSize="9" fill={BLUE} fontWeight="600" dominantBaseline="central">확장</text>
                </>
              )}
            </g>
          )
        })}

        {topNodes.length > 0 && (
          <>
            <line x1={firstColX + (topNodes.length - 1) * colGap + nodeW} y1={topY + nodeH / 2} x2={mergeCenterX - 36} y2={topY + nodeH / 2} stroke="#94A3B8" strokeWidth="1.2" />
            <line x1={mergeCenterX - 36} y1={topY + nodeH / 2} x2={mergeCenterX - 36} y2={startY + 30} stroke="#94A3B8" strokeWidth="1.2" markerEnd={`url(#fc-arrow-${isWeakness ? 'w' : 's'})`} />
          </>
        )}
        {bottomNodes.length > 0 && (
          <>
            <line x1={firstColX + (bottomNodes.length - 1) * colGap + nodeW} y1={bottomY + nodeH / 2} x2={mergeCenterX - 36} y2={bottomY + nodeH / 2} stroke="#94A3B8" strokeWidth="1.2" />
            <line x1={mergeCenterX - 36} y1={bottomY + nodeH / 2} x2={mergeCenterX - 36} y2={startY + 30} stroke="#94A3B8" strokeWidth="1.2" markerEnd={`url(#fc-arrow-${isWeakness ? 'w' : 's'})`} />
          </>
        )}

        <polygon points={`${mergeCenterX},${startY + 6} ${mergeCenterX + 36},${startY + 30} ${mergeCenterX},${startY + 54} ${mergeCenterX - 36},${startY + 30}`} fill="none" stroke={accentColor} strokeWidth="1.5" />
        <text x={mergeCenterX} y={startY + 30 - ((mergeLines.length - 1) * diamondLineSpacing) / 2} textAnchor="middle" fontSize="10" fill={accentColor} fontWeight="700" dominantBaseline="central">
          {mergeLines.map((line, idx) => (
            <tspan key={idx} x={mergeCenterX} dy={idx === 0 ? 0 : diamondLineSpacing}>{line}</tspan>
          ))}
        </text>

        <line x1={mergeCenterX + 36} y1={startY + 30} x2={resultX} y2={startY + 30} stroke="#94A3B8" strokeWidth="1.2" markerEnd={`url(#fc-arrow-${isWeakness ? 'w' : 's'})`} />
        <text x={mergeCenterX + 58} y={startY + 30 - 12} fontSize="9" fill={BLUE} fontWeight="600" dominantBaseline="central">
          {isWeakness ? '공백 발생' : '핵심 연결'}
        </text>

        {renderRectNode(resultNode, resultX, startY + 30 - nodeH / 2)}

        <rect x="10" y="284" width="10" height="10" rx="2" fill="#EBF4FA" stroke={BLUE} strokeWidth="1" />
        <text x="24" y="289" fontSize="8" fill="#6B7280" dominantBaseline="central">활동/세특 노드</text>
        <polygon points="130,289 136,284 142,289 136,294" fill="none" stroke={accentColor} strokeWidth="1" />
        <text x="148" y="289" fontSize="8" fill="#6B7280" dominantBaseline="central">분기/전환 지점</text>
        <rect x="240" y="284" width="10" height="10" rx="5" fill={BLUE} />
        <text x="254" y="289" fontSize="8" fill="#6B7280" dominantBaseline="central">핵심 성과</text>
        <line x1="310" y1="289" x2="330" y2="289" stroke="#94A3B8" strokeWidth="1.2" markerEnd={`url(#fc-arrow-${isWeakness ? 'w' : 's'})`} />
        <text x="334" y="289" fontSize="8" fill="#6B7280" dominantBaseline="central">이어지는 맥락</text>
      </svg>
    </div>
  )
}

/* ─── 가로 바 차트 ─── */
function BarChartViz({ data }: { data: any }) {
  const rows: { label: string; values: number[]; labels: string[] }[] = data?.rows ?? []
  const barW = 420
  const barH = 24
  const labelW = 55
  const rowGap = 14
  const startY = 10
  const svgH = startY + rows.length * (barH + rowGap) + 40

  return (
    <div className="flex justify-center px-5 pb-4">
      <svg viewBox={`0 0 600 ${svgH}`} style={{ width: '480px', height: '130px' }}>
        {rows.map((row, i) => {
          const y = startY + i * (barH + rowGap)
          const total = row.values.reduce((a, b) => a + b, 0) || 100
          const w1 = barW * (row.values[0] / total)
          const w2 = barW * ((row.values[1] ?? 0) / total)
          return (
            <g key={i}>
              <text x={labelW - 8} y={y + barH / 2} textAnchor="end" fontSize="10" fill="#374151" fontWeight="600" dominantBaseline="central">{row.label}</text>
              <rect x={labelW} y={y} width={w1} height={barH} rx="4" fill="#E8A0A0" />
              <text x={labelW + w1 / 2} y={y + barH / 2} textAnchor="middle" fontSize="8" fill="#991B1B" fontWeight="700" dominantBaseline="central">{row.values[0]}%</text>
              <rect x={labelW + w1} y={y} width={w2} height={barH} rx="4" fill={BLUE} />
              <text x={labelW + w1 + w2 / 2} y={y + barH / 2} textAnchor="middle" fontSize="8" fill="white" fontWeight="700" dominantBaseline="central">{row.values[1] ?? 0}%</text>
            </g>
          )
        })}
        <rect x={labelW} y={svgH - 22} width={12} height={12} rx="2" fill="#E8A0A0" />
        <text x={labelW + 16} y={svgH - 16} fontSize="8" fill="#6B7280" dominantBaseline="central">{rows[0]?.labels?.[0] ?? '항목1'}</text>
        <rect x={labelW + 180} y={svgH - 22} width={12} height={12} rx="2" fill={BLUE} />
        <text x={labelW + 196} y={svgH - 16} fontSize="8" fill="#6B7280" dominantBaseline="central">{rows[0]?.labels?.[1] ?? '항목2'}</text>
      </svg>
    </div>
  )
}

/* ─── 강점/약점 카드 ─── */
function StrengthWeaknessCard({ item, index, isWeakness }: { item: StrengthWeakness; index: number; isWeakness?: boolean }) {
  const accent = isWeakness ? RED : BLUE
  return (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <div className="flex items-center gap-2 px-5 pt-4 pb-2">
        <span
          className="inline-flex items-center justify-center rounded-full text-[10px] font-bold text-white"
          style={{ backgroundColor: accent, width: '20px', height: '20px', flexShrink: 0 }}
        >
          {index + 1}
        </span>
        <span className="inline-flex items-center text-sm font-bold text-gray-900" style={{ height: '20px' }}>{item.title}</span>
        <span className="inline-flex items-center text-[10px] text-gray-400" style={{ height: '20px' }}>— {item.subtitle}</span>
      </div>
      {item.description && (
        <p className="px-5 pb-2 text-[11px] leading-5 text-gray-500">{item.description}</p>
      )}
      {item.type === 'heatmap' && <HeatmapViz data={item.data} />}
      {item.type === 'text-analysis' && <TextAnalysisViz data={item.data} />}
      {item.type === 'flowchart' && <FlowchartViz data={item.data} isWeakness={isWeakness} />}
      {item.type === 'bar-chart' && <BarChartViz data={item.data} />}
    </div>
  )
}

/* ────────────────────────── 메인 컴포넌트 ────────────────────────── */

const SchoolRecordVisualReport = forwardRef<HTMLDivElement, { data: VisualReportData }>(
  function SchoolRecordVisualReport({ data }, ref) {
    const p1 = data.page1
    const p2 = data.page2
    const p3 = data.page3
    const p4 = data.page4
    const semesters = p1.grades.semesters
    const semCount = semesters.length
    const now = new Date()
    const genTime = `${now.getFullYear()}. ${now.getMonth() + 1}. ${now.getDate()}. ${now.getHours() >= 12 ? '오후' : '오전'} ${now.getHours() % 12 || 12}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`

    const xs = Array.from({ length: semCount }, (_, i) => {
      const pad = 60
      const end = 410
      return semCount === 1 ? (pad + end) / 2 : pad + ((end - pad) / (semCount - 1)) * i
    })
    const chartTop = 48
    const chartBottom = 243
    const allGradeValues = [
      ...p1.grades.subjects.flatMap((sub) => sub.grades.filter((g): g is number => typeof g === 'number')),
      ...p1.grades.avgAll,
      ...p1.grades.avgMain,
    ].filter((g) => Number.isFinite(g))
    const bestGrade = allGradeValues.length > 0 ? Math.max(1, Math.floor(Math.min(...allGradeValues))) : 1
    const worstGrade = allGradeValues.length > 0 ? Math.max(bestGrade + 1, Math.ceil(Math.max(...allGradeValues))) : 4
    const axisGrades = Array.from({ length: Math.max(2, worstGrade - bestGrade + 1) }, (_, i) => bestGrade + i)
    const gy = (g: number) => {
      if (worstGrade === bestGrade) return (chartTop + chartBottom) / 2
      return chartTop + ((g - bestGrade) / (worstGrade - bestGrade)) * (chartBottom - chartTop)
    }

    return (
      <div
        ref={ref}
        className="bg-gray-100 py-6"
        style={{ width: '800px' }}
      >
        {/* ═══════ 1페이지 ═══════ */}
        <PageShell page={1}>
          <Badge text="Part 01 학생 유형 요약" />
          <h1 className="mb-1 text-xl font-extrabold text-gray-900" style={{ letterSpacing: '-0.02em' }}>
            {data.studentName}학생의 학교생활기록부 심층 분석
          </h1>
          <p className="mb-6 text-xs text-gray-400">생성 시각: {genTime}</p>
          <hr className="border-gray-200" style={{ marginBottom: '20px' }} />
          <h3 className="mb-3 text-base font-extrabold text-gray-900">교과 성적 흐름과 6대 핵심 지표</h3>

          <div className="flex items-center" style={{ height: '265px', marginBottom: '14px', gap: '12px' }}>
            {/* 라인 차트 */}
            <div className="h-full" style={{ flex: '1 1 0' }}>
              <svg viewBox="0 0 440 282" preserveAspectRatio="none" className="h-full w-full">
                <rect x="30" y="20" width="400" height="270" fill="#F7F9FB" rx="4" />
                {axisGrades.map((grade) => (
                  <line key={grade} x1="30" y1={gy(grade)} x2="430" y2={gy(grade)} stroke="#E5E8EB" strokeWidth="0.6" strokeDasharray="3 3" />
                ))}
                {axisGrades.map((grade) => (
                  <text key={grade} x="22" y={gy(grade)} textAnchor="end" fontSize="10" fill="#B0B8C1" dominantBaseline="central">{grade}</text>
                ))}
                {p1.grades.subjects.map(sub => {
                  const valid = sub.grades.map((g, i) => g !== null ? [xs[i], gy(g)] : null).filter(Boolean) as number[][]
                  if (valid.length < 2) return null
                  const lastX = valid[valid.length - 1][0]
                  const lastY = valid[valid.length - 1][1]
                  const labelOnRight = lastX <= 394
                  return (
                    <g key={sub.name}>
                      <polyline fill="none" stroke={sub.color} strokeWidth="0.8" strokeLinejoin="round" strokeLinecap="round" opacity="0.25"
                        points={valid.map(p => p.join(',')).join(' ')} />
                      {valid.map(([cx, cy], i) => (
                        <circle key={i} cx={cx} cy={cy} r="1.5" fill={sub.color} opacity="0.3" />
                      ))}
                      <text
                        x={labelOnRight ? lastX + 5 : lastX - 5}
                        y={lastY}
                        textAnchor={labelOnRight ? 'start' : 'end'}
                        dominantBaseline="central"
                        fontSize="7"
                        fill={sub.color}
                        fontWeight="600"
                        opacity="0.4"
                      >
                        {sub.name}
                      </text>
                    </g>
                  )
                })}
                <polyline fill="none" stroke={DARK} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"
                  points={p1.grades.avgAll.map((g, i) => `${xs[i]},${gy(g)}`).join(' ')} />
                <polyline fill="none" stroke="#A8D0E0" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round"
                  points={p1.grades.avgMain.map((g, i) => `${xs[i]},${gy(g)}`).join(' ')} />
                {p1.grades.avgAll.map((g, i) => <circle key={`a${i}`} cx={xs[i]} cy={gy(g)} r="3" fill={DARK} />)}
                {p1.grades.avgMain.map((g, i) => <circle key={`b${i}`} cx={xs[i]} cy={gy(g)} r="3" fill="#A8D0E0" />)}
                <line x1="310" y1="35" x2="320" y2="35" stroke={DARK} strokeWidth="2.5" />
                <text x="324" y="35" fontSize="8" fill="#6B7280" dominantBaseline="central">전교과</text>
                <line x1="358" y1="35" x2="368" y2="35" stroke="#A8D0E0" strokeWidth="2.5" />
                <text x="372" y="35" fontSize="8" fill="#6B7280" dominantBaseline="central">국영수사과</text>
                {xs.map((x, i) => (
                  <g key={`vl${i}`}>
                    <line x1={x} y1={48} x2={x} y2={243} stroke="#E5E8EB" strokeWidth="0.6" strokeDasharray="3 3" />
                    <text x={x} y="268" textAnchor="middle" fontSize="9" fill="#B0B8C1" dominantBaseline="central">{semesters[i]}</text>
                  </g>
                ))}
              </svg>
            </div>

            {/* 레이더 차트 */}
            <div className="h-full" style={{ width: '200px', flexShrink: 0, overflow: 'hidden' }}>
              <svg viewBox="5 20 290 265" preserveAspectRatio="xMidYMid meet" className="h-full w-full">
                {[1, 0.75, 0.5, 0.25].map((s, idx) => {
                  const cx = 150; const cy = 142; const r = 100 * s
                  const pts = Array.from({ length: 6 }, (_, i) => {
                    const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                    return `${cx + r * Math.cos(angle)},${cy - r * Math.sin(angle)}`
                  }).join(' ')
                  return <polygon key={idx} points={pts} fill={idx === 0 ? '#F7F9FB' : 'none'} stroke="#DDE2E8" strokeWidth="0.8" />
                })}
                {Array.from({ length: 6 }, (_, i) => {
                  const cx = 150; const cy = 142
                  const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                  return <line key={i} x1={cx} y1={cy} x2={cx + 100 * Math.cos(angle)} y2={cy - 100 * Math.sin(angle)} stroke="#DDE2E8" strokeWidth="0.8" />
                })}
                {(() => {
                  const cx = 150; const cy = 142
                  const vals = p1.radar.values
                  const pts = vals.map((v, i) => {
                    const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                    return `${cx + 100 * v * Math.cos(angle)},${cy - 100 * v * Math.sin(angle)}`
                  }).join(' ')
                  return (
                    <>
                      <polygon points={pts} fill="rgba(91,155,213,0.15)" stroke={BLUE} strokeWidth="2.5" />
                      {vals.map((v, i) => {
                        const angle = (Math.PI / 2) + (i * Math.PI * 2) / 6
                        return <circle key={i} cx={cx + 100 * v * Math.cos(angle)} cy={cy - 100 * v * Math.sin(angle)} r="4.5" fill={BLUE} />
                      })}
                    </>
                  )
                })()}
                <text x="150" y="142" textAnchor="middle" fontSize="32" fill={DARK} fontWeight="900" dominantBaseline="central">{p1.radar.totalScore}점</text>
                {[
                  { x: 150, y: 26 }, { x: 262, y: 82 }, { x: 262, y: 210 },
                  { x: 150, y: 268 }, { x: 36, y: 210 }, { x: 36, y: 82 },
                ].map((pos, i) => (
                  <text key={i} x={pos.x} y={pos.y} textAnchor="middle" fontSize="11" fill="#8B95A1" fontWeight="500" dominantBaseline="central">{p1.radar.labels[i]}</text>
                ))}
              </svg>
            </div>
          </div>

          <hr className="border-gray-200" style={{ marginBottom: '20px' }} />

          <h3 className="mb-3 text-base font-extrabold text-gray-900">
            {p1.studentType} <span className="underline decoration-2 underline-offset-4">{p1.studentTypeHighlight}</span>
          </h3>
          <div className="mb-3 flex flex-wrap gap-2">
            {p1.hashtags.map(tag => (
              <span key={tag} className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-600">{tag}</span>
            ))}
          </div>
          <p className="mb-6 text-xs leading-6 text-gray-600">{p1.summary}</p>

          <h3 className="mb-1 text-sm font-extrabold text-gray-900">성장 흐름 요약</h3>
          <p className="mb-4 text-xs leading-5 text-gray-500">
            <span className="font-extrabold" style={{ color: BLUE }}>UNIROAD</span>: {p1.growthSummary}
          </p>

          <div className="mb-6 flex" style={{ height: '90px' }}>
            {p1.growthSteps.map((step, i, arr) => {
              const color = CHEVRON_PALETTE[Math.min(i, CHEVRON_PALETTE.length - 1)]
              const zIndex = arr.length - i
              return (
                <div key={i} className="relative flex-1" style={{ marginRight: i < arr.length - 1 ? '-12px' : 0, zIndex }}>
                  <svg viewBox="0 0 140 90" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
                    {i === 0
                      ? <polygon points="0,0 124,0 140,45 124,90 0,90" fill={color} />
                      : i === arr.length - 1
                        ? <polygon points="0,0 140,0 140,90 0,90 16,45" fill={color} />
                        : <polygon points="0,0 124,0 140,45 124,90 0,90 16,45" fill={color} />}
                  </svg>
                  <div
                    className="relative z-10 flex h-full flex-col justify-center"
                    style={{
                      paddingLeft: i === 0 ? '10px' : '22px',
                      paddingRight: '6px',
                    }}
                  >
                    <div className="flex items-center gap-1">
                      <span
                        className="inline-flex items-center justify-center rounded-full bg-white/25 text-[8px] font-bold text-white"
                        style={{ width: '16px', height: '16px', flexShrink: 0 }}
                      >{i + 1}</span>
                      <span className="inline-flex items-center text-[11px] font-extrabold text-white" style={{ height: '16px' }}>{step.title}</span>
                    </div>
                    <p className="mt-1 text-[11.5px] font-extrabold leading-[1.1] text-white">{step.desc}</p>
                    <p className="mt-0.5 text-[8px] leading-[1.2] text-white/80">{step.sub}</p>
                  </div>
                </div>
              )
            })}
          </div>

          <hr className="mb-5 border-gray-200" />
          <h3 className="mb-4 text-sm font-extrabold text-gray-900">성장 흐름의 핵심 포인트</h3>
          <div className="mb-6 grid grid-cols-3 gap-4">
            {p1.keyPoints.map((item, i) => (
              <div key={i} className="rounded-lg border border-gray-200 p-4">
                <div className="mb-2 flex items-center gap-1.5">
                  <span
                    className="inline-flex items-center justify-center rounded-full text-[10px] font-bold text-white"
                    style={{ backgroundColor: BLUE, width: '20px', height: '20px', flexShrink: 0 }}
                  >{i + 1}</span>
                  <span className="inline-flex items-center text-xs font-bold text-gray-900" style={{ height: '20px' }}>{item.label}</span>
                </div>
                <p className="text-[11px] leading-5 text-gray-500">{item.desc}</p>
              </div>
            ))}
          </div>
        </PageShell>

        {/* ═══════ 2페이지: 강점 ═══════ */}
        <PageShell page={2}>
          <Badge text="Part 02 진단과 보완" />
          <h2 className="mb-4 text-sm font-extrabold text-gray-900">학교생활기록부 핵심 강점</h2>
          <div className="mb-6 flex flex-col gap-3">
            {p2.strengths.map((item, i) => (
              <StrengthWeaknessCard key={i} item={item} index={i} />
            ))}
          </div>
        </PageShell>

        {/* ═══════ 3페이지: 약점 ═══════ */}
        <PageShell page={3}>
          <Badge text="Part 02 진단과 보완" />
          <h2 className="mb-4 text-sm font-extrabold text-gray-900">학교생활기록부 핵심 약점</h2>
          <div className="mb-4 flex flex-col gap-3">
            {p3.weaknesses.map((item, i) => (
              <StrengthWeaknessCard key={i} item={item} index={i} isWeakness />
            ))}
          </div>
          <hr className="border-gray-200" style={{ marginBottom: '10px' }} />
          <h2 className="mb-1 text-sm font-extrabold text-gray-900">생기부 핵심 진단</h2>
          <p className="text-xs leading-5 text-gray-600">{p3.diagnosisSummary}</p>
        </PageShell>

        {/* ═══════ 4페이지: 비교 ═══════ */}
        <PageShell page={4}>
          <Badge text="Part 03 합격자 비교 분석" />
          <h2 className="mb-1 text-sm font-extrabold text-gray-900">합격자 생기부와의 비교</h2>
          <p className="mb-4 text-xs leading-5 text-gray-500">동일 전공({p4.targetMajor}) 합격자의 세특과 나란히 비교하여 보완 포인트를 찾습니다.</p>

          {p4.comparisons.map((card, i) => (
            <div key={i} className="mb-4 overflow-hidden rounded-lg border border-gray-200">
              <div className="flex items-center gap-3 px-5 pt-3 pb-2" style={{ borderLeft: `3px solid ${BLUE}` }}>
                <span className="inline-flex items-center text-lg font-black" style={{ color: BLUE, height: '24px' }}>{String(i + 1).padStart(2, '0')}</span>
                <div className="flex items-center">
                  <span className="text-sm font-bold text-gray-900">{card.title}</span>
                  <span className="ml-2 text-[10px] text-gray-400">{card.subtitle}</span>
                </div>
              </div>
              <div className="flex" style={{ borderTop: '1px solid #F1F5F9' }}>
                <div className="flex-1 border-r border-gray-100 px-5 py-3">
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <span className="inline-flex items-center justify-center rounded px-2 text-[9px] font-bold text-white" style={{ backgroundColor: DARK, height: '18px' }}>합격자</span>
                    <span className="inline-flex items-center text-[10px] text-gray-400" style={{ height: '18px' }}>{card.accepted.label}</span>
                  </div>
                  <p className="text-[11px] leading-5 text-gray-600">{card.accepted.text}</p>
                </div>
                <div className="flex-1 px-5 py-3">
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <span className="inline-flex items-center justify-center rounded px-2 text-[9px] font-bold text-white" style={{ backgroundColor: '#6B7280', height: '18px' }}>{data.studentName}</span>
                    <span className="inline-flex items-center text-[10px] text-gray-400" style={{ height: '18px' }}>{card.subtitle}</span>
                  </div>
                  <p className="text-[11px] leading-5 text-gray-600">{card.student.text}</p>
                </div>
              </div>
              <div className="px-5 py-2.5" style={{ backgroundColor: '#F8FAFC', borderTop: '1px solid #F1F5F9' }}>
                <p className="text-[11px] leading-5 text-gray-600">{card.highlight}</p>
              </div>
            </div>
          ))}

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1">
              <span className="inline-block rounded-sm px-1.5 py-0.5 text-[9px]" style={{ backgroundColor: '#BDE0FE' }}>파랑</span>
              <span className="text-[10px] text-gray-400">합격자 핵심 표현</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="inline-block rounded-sm px-1.5 py-0.5 text-[9px]" style={{ backgroundColor: '#FECACA' }}>빨강</span>
              <span className="text-[10px] text-gray-400">학생 보완 필요 표현</span>
            </div>
          </div>

          <div className="mt-8 rounded-lg border border-blue-200 px-6 py-5 text-center" style={{ backgroundColor: '#F0F7FF' }}>
            <p className="mb-1 text-[15px] font-extrabold text-gray-900">다음 학기에 뭘 해야 할지 궁금하다면? | 대학별 생기부 적합성이 궁금하다면?</p>
            <p className="text-[12px]" style={{ color: BLUE }}>유니로드와 상담해 보세요!</p>
          </div>
        </PageShell>
      </div>
    )
  }
)

export default SchoolRecordVisualReport
