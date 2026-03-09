import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getApiBaseUrl } from '../config'
import SchoolRecordPdfDownloadRunner from '../components/SchoolRecordPdfDownloadRunner'
import {
  ArrowLeft,
  Send,
  Loader2,
  BookOpen,
  Sparkles,
  PanelRightOpen,
  PanelRightClose,
  Upload,
  Trash2,
  FileText,
  Download,
  CheckCircle2,
  AlertCircle,
  X,
} from 'lucide-react'

interface SourceMeta {
  document_id?: string
  source_title: string
  chapter: string
  part: string
  sub_section?: string
  chunk_index: number
  similarity: number
  rerank_score?: number
  chunk_title?: string
  chunk_summary?: string
  chunk_role?: string
  chunk_keywords?: string[]
  heading_path?: string[]
  document_summary?: string
  raw_content?: string
}

interface ReportEvidence {
  evidence_id: string
  evidence_type?: 'evaluation_criteria' | 'school_record'
  source_id?: string
  source_type?: string
  source_title?: string
  source_path?: string
  chunk_title?: string
  chunk_index?: number
  chunk_role?: string
  chunk_summary?: string
  document_summary?: string
  label?: string
  used_excerpt?: string
  display_excerpt?: string
  why_used?: string
}

interface EvaluationCriterion {
  criterion_id: string
  text: string
  evidence_refs: string[]
}

interface StudentAssessment {
  assessment_id: string
  text: string
  school_record_refs: string[]
}

interface AcceptedCaseExcerptPair {
  pair_id: string
  user_excerpt_label?: string
  user_excerpt: string
  accepted_excerpt_label?: string
  accepted_excerpt: string
  pair_comment?: string
}

interface AcceptedCaseComparisonCard {
  card_id: string
  case_id?: string
  label: string
  match_reason?: string
  comparison_axis?: string
  excerpt_pairs?: AcceptedCaseExcerptPair[]
  good_points?: string[]
  gaps?: string[]
  action_tips?: string[]
}

interface ReportSection {
  section_id: string
  title: string
  evaluation_criteria: EvaluationCriterion[]
  student_assessment: StudentAssessment[]
  answer: string
  /** 평가기준·학생 적용·답변을 하나의 매끄러운 문단으로 통합한 본문 (있으면 우선 표시) */
  section_narrative?: string
  comparison_focus?: string
  comparison_cards?: AcceptedCaseComparisonCard[]
  criteria_evidence_refs: string[]
  school_record_evidence_refs: string[]
}

interface DirectAnswerBlock {
  title?: string
  answer_mode?: string
  intro?: string
  items?: string[]
  closing?: string
}

interface StudentProfileAxisScore {
  axis: string
  score: number
  summary: string
  evidence_quotes?: string[]
}

interface StudentProfileSummary {
  headline?: string
  dominant_track?: string
  immediate_priority?: string
  strengths?: string[]
  risks?: string[]
  axis_scores?: StudentProfileAxisScore[]
}

interface ThreePageChartSemester {
  key: string
  label: string
}

interface ThreePageChartSeries {
  key: string
  label: string
  color?: string
  values: Array<number | null>
}

interface ThreePageGradeChart {
  title?: string
  summary?: string
  semesters: ThreePageChartSemester[]
  series: ThreePageChartSeries[]
}

interface ThreePageScoreSlice {
  axis: string
  score: number
  ratio?: number
  summary?: string
  color?: string
  evidence_quotes?: string[]
}

interface ThreePageScoreChart {
  title?: string
  total_score?: number
  summary?: string
  slices: ThreePageScoreSlice[]
}

interface ThreePageAxisItem {
  axis: string
  score: number
  title?: string
  description?: string
  color?: string
  evidence_quotes?: string[]
}

interface ThreePageStrengthBlock {
  headline?: string
  items: ThreePageAxisItem[]
}

interface ThreePageFlowNode {
  node_id: string
  grade: string
  title?: string
  summary: string
  evidence_quotes?: string[]
}

interface ThreePageFlowLink {
  from_node_id: string
  to_node_id: string
  label: string
}

interface ThreePageFlowchart {
  headline?: string
  nodes: ThreePageFlowNode[]
  links?: ThreePageFlowLink[]
}

interface ThreePageActionCard {
  axis: string
  priority?: string
  current_score?: number
  title: string
  why?: string
  actions?: string[]
  expected_effect?: string
}

interface ThreePageNextSemesterPlan {
  headline?: string
  action_cards: ThreePageActionCard[]
}

interface ThreePageComparisonCard {
  card_id: string
  label: string
  match_reason?: string
  comparison_axis?: string
  excerpt_pairs?: AcceptedCaseExcerptPair[]
  good_points?: string[]
  gaps?: string[]
  action_tips?: string[]
}

interface ThreePageReport {
  page1?: {
    grade_chart?: ThreePageGradeChart
    score_chart?: ThreePageScoreChart
    strength_block?: ThreePageStrengthBlock
    flowchart?: ThreePageFlowchart
  }
  page2?: {
    weakness_block?: ThreePageStrengthBlock
    next_semester_plan?: ThreePageNextSemesterPlan
  }
  page3?: {
    headline?: string
    cards?: ThreePageComparisonCard[]
  }
}

interface GradeSupport {
  label: string
  user_grade?: number
  cutoff_grade?: number
  department?: string
  admission_type?: string
  source_url?: string
}

interface AcceptedCaseHint {
  label?: string
  match_reason?: string
  similarity_score?: number
}

interface UniversityProfile {
  school_name: string
  evaluation_keywords?: string[]
  talent_summary?: string
  evaluation_summary?: string
  interview_policy?: string
  evidence_excerpt?: string
  source_title?: string
}

interface UniversityRecommendationCard {
  card_id: string
  school_name: string
  admission_label?: string
  fit_level?: string
  fit_summary: string
  matching_points?: string[]
  caution_points?: string[]
  interview_note?: string
  talent_keywords?: string[]
  evidence_excerpt?: string
  evidence_source?: string
  fit_score?: number
  grade_support?: GradeSupport
}

interface UniversityRecommendationSummary {
  summary?: string
  cards: UniversityRecommendationCard[]
  accepted_case_hints?: AcceptedCaseHint[]
}

export interface StructuredReport {
  report_title?: string
  summary?: string
  plain_text?: string
  direct_answer?: DirectAnswerBlock
  three_page_report?: ThreePageReport
  student_profile?: StudentProfileSummary
  university_profiles?: UniversityProfile[]
  university_recommendations?: UniversityRecommendationSummary
  sections: ReportSection[]
  evidence_catalog: Record<string, ReportEvidence>
}

interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
  sources?: SourceMeta[]
  report?: StructuredReport
  messageKind?: 'chat' | 'report'
}

interface SourceItem {
  source_title: string
  chunk_count: number
}

interface GenerateReportResponse {
  question?: string
  report?: StructuredReport
  sources?: SourceMeta[]
}

interface EvidenceDisplayExcerptRequestItem {
  evidence_id: string
  evidence_type?: 'evaluation_criteria' | 'school_record'
  source_id?: string
  source_type?: string
  source_title?: string
  chunk_title?: string
  chunk_summary?: string
  why_used?: string
  used_excerpt?: string
}

const QUICK_ACTIONS = [
  '내 생기부의 전체적인 강점과 약점을 분석해 줘',
  '학년별 성장 흐름을 분석해 줘',
  '교과 세특 전공적합성을 평가해 줘',
  '창의적 체험활동을 분석하고 개선점을 알려줘',
  '학생부종합전형 전략을 수립해 줘',
  '행동특성 및 종합의견 분석해 줘',
]

const normalizeTextForCompare = (text: string) =>
  text.replace(/[^0-9A-Za-z가-힣]+/g, '').toLowerCase()

const createMessageId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`

const buildSectionDescription = (section: ReportSection) => {
  const narrative = section.section_narrative?.trim()
  if (narrative) return narrative

  const answerText = section.answer.trim()
  if (answerText) return answerText

  const parts = [
    ...section.evaluation_criteria.map((item) => item.text),
    ...section.student_assessment.map((item) => item.text),
  ]
    .map((text) => text.trim())
    .filter(Boolean)

  const merged: string[] = []
  const mergedNormalized: string[] = []

  for (const part of parts) {
    const normalizedPart = normalizeTextForCompare(part)
    if (!normalizedPart) continue
    const isDuplicate = mergedNormalized.some(
      (existing) => existing.includes(normalizedPart) || normalizedPart.includes(existing)
    )
    if (isDuplicate) continue
    merged.push(part)
    mergedNormalized.push(normalizedPart)
  }

  return merged.join(' ')
}

const getSectionEvidenceIds = (section: ReportSection) =>
  Array.from(new Set([...section.criteria_evidence_refs, ...section.school_record_evidence_refs]))

const splitIntoReadableParagraphs = (text: string) => {
  const normalized = text.replace(/\r/g, '').trim()
  if (!normalized) return []

  const rawParagraphs = normalized
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean)

  const paragraphs = rawParagraphs.length > 0 ? rawParagraphs : [normalized]

  return paragraphs.flatMap((paragraph) => {
    if (paragraph.length <= 220) return [paragraph]

    const sentences = paragraph
      .split(/(?<=[.!?])\s+|(?<=다\.)\s+|(?<=요\.)\s+/)
      .map((sentence) => sentence.trim())
      .filter(Boolean)

    if (sentences.length <= 1) return [paragraph]

    const chunks: string[] = []
    let current = ''

    for (const sentence of sentences) {
      const next = current ? `${current} ${sentence}` : sentence
      if (next.length > 220 && current) {
        chunks.push(current)
        current = sentence
      } else {
        current = next
      }
    }

    if (current) chunks.push(current)
    return chunks
  })
}

const splitLeadSentence = (text: string) => {
  const trimmed = text.trim()
  if (!trimmed) return { lead: '', rest: '' }

  const match = trimmed.match(/^(.+?[.!?]|.+?다\.|.+?요\.)(\s+|$)/)
  if (match) {
    const lead = match[1].trim()
    const rest = trimmed.slice(match[0].length).trim()
    return { lead, rest }
  }

  if (trimmed.length <= 70) {
    return { lead: trimmed, rest: '' }
  }

  return {
    lead: `${trimmed.slice(0, 70).trim()}...`,
    rest: trimmed.slice(70).trim(),
  }
}

const escapeHtml = (text: string) =>
  text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

const chapterPathSegmentPattern =
  /^(?:제\s*\d+\s*장(?:\s*[:.])?|chapter\s*\d+(?:\s*[:.])?|ch\.?\s*\d+(?:\s*[:.])?)/i

const formatEvidenceSourcePath = (sourcePath?: string) => {
  if (!sourcePath) return ''

  const parts = sourcePath
    .split('>')
    .map((part) => part.trim())
    .filter(Boolean)

  if (parts.length === 0) return ''

  const visibleParts = chapterPathSegmentPattern.test(parts[0]) ? parts.slice(1) : parts
  return visibleParts.join(' > ')
}

const isAcademicEvidenceDisplayTarget = (evidence?: ReportEvidence) =>
  Boolean(
    evidence &&
      evidence.evidence_type === 'evaluation_criteria' &&
      (evidence.source_type || 'academic_contents') === 'academic_contents'
  )

const chunkSummaryShow = (text?: string) =>
  splitIntoReadableParagraphs(text || '')
    .join('\n\n')
    .trim()

const getEvidenceExcerptForRender = (evidence: ReportEvidence) => {
  if (isAcademicEvidenceDisplayTarget(evidence)) {
    return chunkSummaryShow(evidence.chunk_summary) || evidence.display_excerpt?.trim() || ''
  }
  return evidence.used_excerpt?.trim() || ''
}

const getEvidenceExcerptForExport = (evidence: ReportEvidence) =>
  isAcademicEvidenceDisplayTarget(evidence)
    ? chunkSummaryShow(evidence.chunk_summary) ||
      evidence.display_excerpt?.trim() ||
      evidence.used_excerpt?.trim() ||
      ''
    : evidence.display_excerpt?.trim() || evidence.used_excerpt?.trim() || ''

const isEvidenceExcerptPending = (evidence: ReportEvidence) =>
  isAcademicEvidenceDisplayTarget(evidence) &&
  !Boolean(chunkSummaryShow(evidence.chunk_summary) || evidence.display_excerpt?.trim())

const buildHtmlParagraphs = (text: string) =>
  splitIntoReadableParagraphs(text)
    .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
    .join('')

const buildHtmlList = (items: string[], ordered = false) => {
  const validItems = items.map((item) => item.trim()).filter(Boolean)
  if (validItems.length === 0) return ''
  const tag = ordered ? 'ol' : 'ul'
  return `<${tag}>${validItems
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join('')}</${tag}>`
}

const buildEvidenceHtml = (report: StructuredReport, evidenceIds: string[]) => {
  const cards = evidenceIds
    .map((evidenceId) => report.evidence_catalog?.[evidenceId])
    .filter((evidence): evidence is ReportEvidence => Boolean(evidence))
    .map((evidence) => {
      const title =
        evidence.source_title || evidence.chunk_title || evidence.label || '근거 자료'
      const formattedSourcePath = formatEvidenceSourcePath(evidence.source_path)
      const sourcePath = formattedSourcePath
        ? `<p class="evidence-path">${escapeHtml(formattedSourcePath)}</p>`
        : ''
      const visibleExcerpt = getEvidenceExcerptForExport(evidence)
      const excerpt = visibleExcerpt
        ? `<div class="evidence-excerpt"><p class="evidence-label">발췌</p><blockquote>${escapeHtml(
            visibleExcerpt
          )}</blockquote></div>`
        : ''
      const whyUsed = evidence.why_used
        ? `<div class="evidence-why"><p class="evidence-label">해석</p>${buildHtmlParagraphs(
            evidence.why_used
          )}</div>`
        : ''
      return `
        <article class="evidence-card">
          <h4>${escapeHtml(title)}</h4>
          ${sourcePath}
          ${excerpt}
          ${whyUsed}
        </article>
      `
    })
  if (cards.length === 0) return ''
  return `<div class="evidence-grid">${cards.join('')}</div>`
}

const buildComparisonSectionHtml = (section: ReportSection) => {
  const cards = (section.comparison_cards || []).map((card, cardIdx) => {
    const excerptPairs = (card.excerpt_pairs || [])
      .map((pair, pairIdx) => `
        <div class="comparison-pair">
          <p class="comparison-pair-title">원문 비교 ${(pairIdx + 1).toString().padStart(2, '0')}</p>
          ${
            pair.pair_comment
              ? `<div class="comparison-comment">${buildHtmlParagraphs(pair.pair_comment)}</div>`
              : ''
          }
          <div class="comparison-columns">
            <div>
              <p class="comparison-label">${escapeHtml(
                pair.user_excerpt_label || '내 생기부 원문'
              )}</p>
              <blockquote>${escapeHtml(pair.user_excerpt)}</blockquote>
            </div>
            <div>
              <p class="comparison-label">${escapeHtml(
                pair.accepted_excerpt_label || '합격자 생기부 원문'
              )}</p>
              <blockquote>${escapeHtml(pair.accepted_excerpt)}</blockquote>
            </div>
          </div>
        </div>
      `)
      .join('')

    return `
      <article class="comparison-card">
        <p class="section-kicker">Case ${(cardIdx + 1).toString().padStart(2, '0')}</p>
        <h3>${escapeHtml(card.label)}</h3>
        ${card.match_reason ? buildHtmlParagraphs(card.match_reason) : ''}
        ${
          card.comparison_axis
            ? `<div class="comparison-axis"><p class="comparison-label">세부 비교 관점</p>${buildHtmlParagraphs(
                card.comparison_axis
              )}</div>`
            : ''
        }
        ${excerptPairs}
        <div class="comparison-summary-grid">
          <div>
            <p class="comparison-label">강점</p>
            ${buildHtmlList(card.good_points || [])}
          </div>
          <div>
            <p class="comparison-label">보완이 필요한 점</p>
            ${buildHtmlList(card.gaps || [])}
          </div>
          <div>
            <p class="comparison-label">다음 행동</p>
            ${buildHtmlList(card.action_tips || [], true)}
          </div>
        </div>
      </article>
    `
  })

  return `
    <section class="report-section">
      <p class="section-kicker">${escapeHtml(section.section_id)}</p>
      <h2>${escapeHtml(section.title)}</h2>
      ${
        section.comparison_focus
          ? `<div class="section-focus"><p class="comparison-label">비교 관점</p>${buildHtmlParagraphs(
              section.comparison_focus
            )}</div>`
          : ''
      }
      ${cards.join('')}
    </section>
  `
}

const buildStudentProfileHtml = (profile?: StudentProfileSummary) => {
  if (!profile) return ''

  const axisCards = (profile.axis_scores || [])
    .filter((item) => item.axis && (item.summary || item.score))
    .map(
      (item) => `
        <article class="evidence-card">
          <p class="evidence-label">${escapeHtml(item.axis)}</p>
          <h4>${escapeHtml(`${item.score || 0}/5`)}</h4>
          ${item.summary ? buildHtmlParagraphs(item.summary) : ''}
          ${
            item.evidence_quotes && item.evidence_quotes.length > 0
              ? `<div class="sub-block"><h3>근거</h3>${buildHtmlList(item.evidence_quotes)}</div>`
              : ''
          }
        </article>
      `
    )
    .join('')

  return `
    <section class="report-section">
      <p class="section-kicker">Student Profile</p>
      <h2>학생 평가 프로필</h2>
      ${profile.headline ? `<div class="section-body">${buildHtmlParagraphs(profile.headline)}</div>` : ''}
      ${
        profile.dominant_track
          ? `<div class="sub-block"><h3>현재 서사</h3>${buildHtmlParagraphs(profile.dominant_track)}</div>`
          : ''
      }
      ${
        profile.immediate_priority
          ? `<div class="sub-block"><h3>가장 먼저 보완할 점</h3>${buildHtmlParagraphs(profile.immediate_priority)}</div>`
          : ''
      }
      ${axisCards ? `<div class="evidence-grid">${axisCards}</div>` : ''}
      ${
        profile.strengths && profile.strengths.length > 0
          ? `<div class="sub-block"><h3>핵심 강점</h3>${buildHtmlList(profile.strengths)}</div>`
          : ''
      }
      ${
        profile.risks && profile.risks.length > 0
          ? `<div class="sub-block"><h3>핵심 리스크</h3>${buildHtmlList(profile.risks)}</div>`
          : ''
      }
    </section>
  `
}

const buildUniversityProfilesHtml = (profiles?: UniversityProfile[]) => {
  if (!profiles || profiles.length === 0) return ''

  const cards = profiles
    .map(
      (profile) => `
        <article class="comparison-card">
          <p class="comparison-label">${escapeHtml(profile.school_name)}</p>
          <h3>${escapeHtml(profile.school_name)}</h3>
          ${profile.talent_summary ? buildHtmlParagraphs(profile.talent_summary) : ''}
          ${
            profile.evaluation_keywords && profile.evaluation_keywords.length > 0
              ? `<div class="sub-block"><h3>핵심 평가요소</h3>${buildHtmlList(
                  profile.evaluation_keywords
                )}</div>`
              : ''
          }
          ${
            profile.evaluation_summary
              ? `<div class="sub-block"><h3>평가 요약</h3>${buildHtmlParagraphs(profile.evaluation_summary)}</div>`
              : ''
          }
          ${
            profile.interview_policy
              ? `<div class="sub-block"><h3>면접 여부/포인트</h3>${buildHtmlParagraphs(profile.interview_policy)}</div>`
              : ''
          }
          ${
            profile.evidence_excerpt
              ? `<div class="sub-block"><h3>${escapeHtml(profile.source_title || '문서 근거')}</h3>${buildHtmlParagraphs(
                  profile.evidence_excerpt
                )}</div>`
              : ''
          }
        </article>
      `
    )
    .join('')

  return `
    <section class="report-section">
      <p class="section-kicker">University Profile</p>
      <h2>대학 평가 프로필</h2>
      <div class="comparison-summary-grid">${cards}</div>
    </section>
  `
}

const buildUniversityRecommendationsHtml = (summary?: UniversityRecommendationSummary) => {
  if (!summary || !summary.cards || summary.cards.length === 0) return ''

  const cards = summary.cards
    .map(
      (card) => `
        <article class="comparison-card">
          <p class="comparison-label">${escapeHtml(card.fit_level || '적합도')}</p>
          <h3>${escapeHtml(card.school_name)}</h3>
          ${card.admission_label ? `<p class="evidence-path">${escapeHtml(card.admission_label)}</p>` : ''}
          ${buildHtmlParagraphs(card.fit_summary)}
          ${
            card.matching_points && card.matching_points.length > 0
              ? `<div class="sub-block"><h3>맞는 이유</h3>${buildHtmlList(card.matching_points)}</div>`
              : ''
          }
          ${
            card.caution_points && card.caution_points.length > 0
              ? `<div class="sub-block"><h3>주의할 점</h3>${buildHtmlList(card.caution_points)}</div>`
              : ''
          }
          ${
            card.talent_keywords && card.talent_keywords.length > 0
              ? `<div class="sub-block"><h3>핵심 평가축</h3>${buildHtmlList(card.talent_keywords)}</div>`
              : ''
          }
          ${
            card.interview_note
              ? `<div class="sub-block"><h3>면접 포인트</h3>${buildHtmlParagraphs(card.interview_note)}</div>`
              : ''
          }
          ${
            card.grade_support
              ? `<div class="sub-block"><h3>교과 보조 판정</h3>${buildHtmlParagraphs(
                  `${card.grade_support.label} / ${
                    card.grade_support.department || '모집단위 미상'
                  } ${card.grade_support.admission_type || ''} / 내신 ${
                    card.grade_support.user_grade ?? '-'
                  } vs 컷 ${card.grade_support.cutoff_grade ?? '-'}`
                )}</div>`
              : ''
          }
          ${
            card.evidence_excerpt
              ? `<div class="sub-block"><h3>${escapeHtml(card.evidence_source || '문서 근거')}</h3>${buildHtmlParagraphs(
                  card.evidence_excerpt
                )}</div>`
              : ''
          }
        </article>
      `
    )
    .join('')

  return `
    <section class="report-section">
      <p class="section-kicker">University Fit</p>
      <h2>추천 대학 카드</h2>
      ${summary.summary ? `<div class="section-body">${buildHtmlParagraphs(summary.summary)}</div>` : ''}
      <div class="comparison-summary-grid">${cards}</div>
      ${
        summary.accepted_case_hints && summary.accepted_case_hints.length > 0
          ? `<div class="sub-block"><h3>합격 사례 유사도</h3>${buildHtmlList(
              summary.accepted_case_hints.map((hint) =>
                `${hint.label || '유사 사례'}${hint.similarity_score ? ` (유사도 ${hint.similarity_score})` : ''} ${hint.match_reason || ''}`.trim()
              )
            )}</div>`
          : ''
      }
    </section>
  `
}

const formatDisplayScore = (value?: number | null) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  const rounded = Math.round(value * 100) / 100
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(2).replace(/\.?0+$/, '')
}

const polarToCartesian = (cx: number, cy: number, radius: number, angleInDegrees: number) => {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0
  return {
    x: cx + radius * Math.cos(angleInRadians),
    y: cy + radius * Math.sin(angleInRadians),
  }
}

const describeArc = (
  cx: number,
  cy: number,
  radius: number,
  startAngle: number,
  endAngle: number
) => {
  const start = polarToCartesian(cx, cy, radius, endAngle)
  const end = polarToCartesian(cx, cy, radius, startAngle)
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1'
  return `M ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y}`
}

const buildThreePageTrendChartSvg = (chart?: ThreePageGradeChart) => {
  if (!chart || !chart.semesters?.length || !chart.series?.length) {
    return '<div class="chart-empty">연동된 학기별 내신 데이터가 없습니다.</div>'
  }

  const activeSeries = chart.series.filter((series) =>
    (series.values || []).some((value) => typeof value === 'number')
  )
  if (activeSeries.length === 0) {
    return '<div class="chart-empty">연동된 학기별 내신 데이터가 없습니다.</div>'
  }

  const width = 520
  const height = 260
  const padding = { top: 20, right: 18, bottom: 54, left: 44 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom
  const yMin = 1
  const yMax = 9
  const xStep = chart.semesters.length > 1 ? plotWidth / (chart.semesters.length - 1) : 0
  const yTicks = [1, 3, 5, 7, 9]

  const buildPath = (values: Array<number | null>) => {
    const pathParts: string[] = []
    values.forEach((value, index) => {
      if (typeof value !== 'number') return
      const x = padding.left + xStep * index
      const clamped = Math.min(yMax, Math.max(yMin, value))
      const y = padding.top + ((clamped - yMin) / (yMax - yMin)) * plotHeight
      pathParts.push(`${pathParts.length === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`)
    })
    return pathParts.join(' ')
  }

  const circles = activeSeries
    .map((series) =>
      (series.values || [])
        .map((value, index) => {
          if (typeof value !== 'number') return ''
          const x = padding.left + xStep * index
          const clamped = Math.min(yMax, Math.max(yMin, value))
          const y = padding.top + ((clamped - yMin) / (yMax - yMin)) * plotHeight
          return `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="4.5" fill="${escapeHtml(
            series.color || '#111827'
          )}" stroke="#fff" stroke-width="2" />`
        })
        .join('')
    )
    .join('')

  const paths = activeSeries
    .map((series) => {
      const path = buildPath(series.values || [])
      if (!path) return ''
      return `<path d="${path}" fill="none" stroke="${escapeHtml(
        series.color || '#111827'
      )}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round" />`
    })
    .join('')

  const grid = yTicks
    .map((tick) => {
      const y = padding.top + ((tick - yMin) / (yMax - yMin)) * plotHeight
      return `
        <line x1="${padding.left}" y1="${y.toFixed(1)}" x2="${width - padding.right}" y2="${y.toFixed(
          1
        )}" stroke="#e5e7eb" stroke-width="1" />
        <text x="${padding.left - 10}" y="${(y + 4).toFixed(1)}" text-anchor="end" font-size="11" fill="#9ca3af">${tick}</text>
      `
    })
    .join('')

  const xLabels = chart.semesters
    .map((semester, index) => {
      const x = padding.left + xStep * index
      return `<text x="${x.toFixed(1)}" y="${height - 18}" text-anchor="middle" font-size="11" fill="#6b7280">${escapeHtml(
        semester.key
      )}</text>`
    })
    .join('')

  return `
    <div class="chart-shell">
      <div class="chart-legend chart-legend-top">
        ${activeSeries
          .map(
            (series) => `
              <span class="legend-item legend-item-pill">
                <span class="legend-swatch" style="background:${escapeHtml(series.color || '#111827')}"></span>
                ${escapeHtml(series.label)}
              </span>
            `
          )
          .join('')}
      </div>
      <svg viewBox="0 0 ${width} ${height}" class="chart-svg" role="img" aria-label="${escapeHtml(
        chart.title || '학기별 내신 추이'
      )}">
        ${grid}
        <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${(
          height - padding.bottom
        ).toFixed(1)}" stroke="#d1d5db" stroke-width="1.2" />
        <line x1="${padding.left}" y1="${(height - padding.bottom).toFixed(1)}" x2="${(
          width - padding.right
        ).toFixed(1)}" y2="${(height - padding.bottom).toFixed(1)}" stroke="#d1d5db" stroke-width="1.2" />
        ${paths}
        ${circles}
        ${xLabels}
      </svg>
      ${chart.summary ? `<div class="chart-summary-box"><p class="chart-summary">${escapeHtml(chart.summary)}</p></div>` : ''}
    </div>
  `
}

const buildThreePageScoreChartSvg = (chart?: ThreePageScoreChart) => {
  if (!chart || !chart.slices?.length) {
    return '<div class="chart-empty">6요소 점수 데이터가 없습니다.</div>'
  }

  const width = 340
  const height = 340
  const cx = width / 2
  const cy = height / 2
  const radius = 118
  const levels = [0.25, 0.5, 0.75, 1]
  const axisCount = chart.slices.length
  const polygonPoints = (level: number) =>
    chart.slices
      .map((_, index) => {
        const angle = -Math.PI / 2 + (Math.PI * 2 * index) / axisCount
        const x = cx + Math.cos(angle) * radius * level
        const y = cy + Math.sin(angle) * radius * level
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  const dataPolygon = chart.slices
    .map((slice, index) => {
      const angle = -Math.PI / 2 + (Math.PI * 2 * index) / axisCount
      const ratio = Math.max(0, Math.min(1, (slice.score || 0) / 5))
      const x = cx + Math.cos(angle) * radius * ratio
      const y = cy + Math.sin(angle) * radius * ratio
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  return `
    <div class="score-chart-shell">
      <svg viewBox="0 0 ${width} ${height}" class="score-chart-svg" role="img" aria-label="${escapeHtml(
        chart.title || '6요소 진단 점수'
      )}">
        ${levels
          .map(
            (level) => `
              <polygon points="${polygonPoints(level)}" fill="none" stroke="#d4d4d8" stroke-width="1" />
            `
          )
          .join('')}
        ${chart.slices
          .map((slice, index) => {
            const angle = -Math.PI / 2 + (Math.PI * 2 * index) / axisCount
            const axisX = cx + Math.cos(angle) * radius
            const axisY = cy + Math.sin(angle) * radius
            const labelX = cx + Math.cos(angle) * (radius + 26)
            const labelY = cy + Math.sin(angle) * (radius + 26)
            const pointRatio = Math.max(0, Math.min(1, (slice.score || 0) / 5))
            const pointX = cx + Math.cos(angle) * radius * pointRatio
            const pointY = cy + Math.sin(angle) * radius * pointRatio
            const anchor = Math.abs(labelX - cx) < 12 ? 'middle' : labelX < cx ? 'end' : 'start'
            return `
              <line x1="${cx}" y1="${cy}" x2="${axisX.toFixed(1)}" y2="${axisY.toFixed(1)}" stroke="#d4d4d8" stroke-width="1" />
              <circle cx="${pointX.toFixed(1)}" cy="${pointY.toFixed(1)}" r="4" fill="#c4b5fd" stroke="#ffffff" stroke-width="2" />
              <text x="${labelX.toFixed(1)}" y="${labelY.toFixed(1)}" text-anchor="${anchor}" font-size="13" fill="#6b7280">${escapeHtml(
                slice.axis
              )}</text>
            `
          })
          .join('')}
        <polygon
          points="${dataPolygon}"
          fill="rgba(196,181,253,0.35)"
          stroke="#c4b5fd"
          stroke-width="2.5"
        />
      </svg>
      <div class="score-legend">
        ${chart.slices
          .map(
            (slice) => `
              <div class="score-legend-item">
                <span class="legend-dot" style="background:${escapeHtml(slice.color || '#6b7280')}"></span>
                <span>${escapeHtml(slice.axis)}</span>
                <strong>${escapeHtml(formatDisplayScore(slice.score))}/5</strong>
              </div>
            `
          )
          .join('')}
      </div>
      ${chart.summary ? `<p class="chart-summary">${escapeHtml(chart.summary)}</p>` : ''}
    </div>
  `
}

const buildThreePageAxisCardsHtml = (
  block: ThreePageStrengthBlock | undefined,
  emptyText: string,
  tone: 'strength' | 'weakness'
) => {
  if (!block || !block.items?.length) {
    return `<p class="chart-empty">${escapeHtml(emptyText)}</p>`
  }
  return `
    ${block.headline ? `<div class="narrative-box"><p>${escapeHtml(block.headline)}</p></div>` : ''}
    <div class="axis-card-grid">
      ${block.items
        .map(
          (item) => `
            <article class="axis-card axis-card-${tone}">
              <div class="axis-card-head">
                <span class="axis-badge" style="background:${escapeHtml(item.color || '#6b7280')}"></span>
                <p>${escapeHtml(item.axis)}</p>
                <strong>${escapeHtml(formatDisplayScore(item.score))}/5</strong>
              </div>
              ${item.title ? `<h4>${escapeHtml(item.title)}</h4>` : ''}
              ${item.description ? `<p>${escapeHtml(item.description)}</p>` : ''}
              ${
                item.evidence_quotes && item.evidence_quotes.length > 0
                  ? `<div class="axis-evidence">${buildHtmlList(item.evidence_quotes)}</div>`
                  : ''
              }
            </article>
          `
        )
        .join('')}
    </div>
  `
}

const buildThreePageFlowchartHtml = (flowchart?: ThreePageFlowchart) => {
  if (!flowchart || !flowchart.nodes?.length) {
    return '<p class="chart-empty">학년별 연결 흐름을 구성할 데이터가 없습니다.</p>'
  }

  return `
    ${flowchart.headline ? `<div class="narrative-box"><p>${escapeHtml(flowchart.headline)}</p></div>` : ''}
    <div class="flowchart-grid">
      ${flowchart.nodes
        .map((node, index) => {
          const link = flowchart.links?.[index]
          return `
            <div class="flow-step-wrap">
              <article class="flow-step">
                <p class="flow-grade">${escapeHtml(node.grade)}</p>
                <h4>${escapeHtml(node.title || node.grade)}</h4>
                <p>${escapeHtml(node.summary)}</p>
                ${
                  node.evidence_quotes && node.evidence_quotes.length > 0
                    ? `<div class="flow-evidence">${buildHtmlList(node.evidence_quotes)}</div>`
                    : ''
                }
              </article>
              ${
                link
                  ? `<div class="flow-link"><span>${escapeHtml(link.label)}</span></div>`
                  : ''
              }
            </div>
          `
        })
        .join('')}
    </div>
  `
}

const buildThreePagePlanHtml = (plan?: ThreePageNextSemesterPlan) => {
  if (!plan || !plan.action_cards?.length) {
    return '<p class="chart-empty">다음 학기 제안 데이터가 없습니다.</p>'
  }
  return `
    ${plan.headline ? `<div class="narrative-box"><p>${escapeHtml(plan.headline)}</p></div>` : ''}
    <div class="plan-card-grid">
      ${plan.action_cards
        .map(
          (card) => `
            <article class="plan-card">
              <div class="plan-card-head">
                <span class="plan-priority">${escapeHtml(card.priority || '보완')}</span>
                <p>${escapeHtml(card.axis)}</p>
                <strong>${escapeHtml(formatDisplayScore(card.current_score))}/5</strong>
              </div>
              <h4>${escapeHtml(card.title)}</h4>
              ${card.why ? `<p>${escapeHtml(card.why)}</p>` : ''}
              ${card.actions && card.actions.length > 0 ? buildHtmlList(card.actions, true) : ''}
              ${
                card.expected_effect
                  ? `<div class="plan-effect"><p class="plan-effect-label">기대 효과</p><p>${escapeHtml(
                      card.expected_effect
                    )}</p></div>`
                  : ''
              }
            </article>
          `
        )
        .join('')}
    </div>
  `
}

const buildThreePageComparisonHtml = (page3?: ThreePageReport['page3']) => {
  if (!page3 || !page3.cards?.length) {
    return '<p class="chart-empty">비교 가능한 합격 사례 데이터가 없습니다.</p>'
  }
  return `
    ${page3.headline ? `<div class="narrative-box"><p>${escapeHtml(page3.headline)}</p></div>` : ''}
    <div class="comparison-page-grid">
      ${page3.cards
        .map(
          (card, index) => `
            <article class="comparison-page-card">
              <p class="page-kicker">Case ${(index + 1).toString().padStart(2, '0')}</p>
              <h3>${escapeHtml(card.label)}</h3>
              ${card.match_reason ? `<p>${escapeHtml(card.match_reason)}</p>` : ''}
              ${
                card.comparison_axis
                  ? `<div class="comparison-axis-line"><span>비교 축</span><p>${escapeHtml(
                      card.comparison_axis
                    )}</p></div>`
                  : ''
              }
              ${
                card.excerpt_pairs && card.excerpt_pairs.length > 0
                  ? `<div class="excerpt-pairs">
                      ${card.excerpt_pairs
                        .map(
                          (pair) => `
                            <div class="excerpt-pair">
                              <div>
                                <p class="comparison-label">${escapeHtml(
                                  pair.user_excerpt_label || '내 생기부'
                                )}</p>
                                <blockquote>${escapeHtml(pair.user_excerpt)}</blockquote>
                              </div>
                              <div>
                                <p class="comparison-label">${escapeHtml(
                                  pair.accepted_excerpt_label || '합격자 생기부'
                                )}</p>
                                <blockquote>${escapeHtml(pair.accepted_excerpt)}</blockquote>
                              </div>
                              ${
                                pair.pair_comment
                                  ? `<div class="pair-comment">${buildHtmlParagraphs(pair.pair_comment)}</div>`
                                  : ''
                              }
                            </div>
                          `
                        )
                        .join('')}
                    </div>`
                  : ''
              }
              <div class="comparison-summary-grid comparison-summary-grid-3">
                <div>
                  <p class="comparison-label">닮은 점</p>
                  ${buildHtmlList(card.good_points || [])}
                </div>
                <div>
                  <p class="comparison-label">부족한 점</p>
                  ${buildHtmlList(card.gaps || [])}
                </div>
                <div>
                  <p class="comparison-label">보완 포인트</p>
                  ${buildHtmlList(card.action_tips || [], true)}
                </div>
              </div>
            </article>
          `
        )
        .join('')}
    </div>
  `
}

const buildIntegratedTypeSectionHtml = (
  report: StructuredReport,
  page1?: ThreePageReport['page1']
) => {
  const profile = report.student_profile
  const headline = profile?.headline || page1?.strength_block?.headline || '학교생활기록부 심층 분석'
  const dominantTrack = profile?.dominant_track || ''
  const strengths = profile?.strengths || []
  const topAxisItems = page1?.strength_block?.items?.slice(0, 3) || []

  const tagsHtml = strengths.length > 0
    ? `<div class="type-tags">${strengths.map(tag => `<span class="type-tag">#${escapeHtml(tag)}</span>`).join('')}</div>`
    : ''

  const topCardsHtml = topAxisItems.length > 0
    ? `<div class="top-axis-cards">
        ${topAxisItems.map((item, idx) => `
          <article class="top-axis-card">
            <div class="top-axis-card-head">
              <span class="top-axis-number">${idx + 1}</span>
              <span class="axis-badge" style="background:${escapeHtml(item.color || '#6b7280')}"></span>
              <span class="top-axis-name">${escapeHtml(item.axis)}</span>
              <span class="top-axis-score">${escapeHtml(item.score?.toString() || '0')}/5</span>
            </div>
            ${item.title ? `<h4>${escapeHtml(item.title)}</h4>` : ''}
            ${item.description ? `<p>${escapeHtml(item.description)}</p>` : ''}
          </article>
        `).join('')}
       </div>`
    : ''

  return `
    <section class="type-hero-section">
      <div class="type-hero-main">
        <div class="type-content">
          <p class="section-kicker">학교생활기록부 유형</p>
          <h2 class="type-title">${escapeHtml(headline)}</h2>
          ${tagsHtml}
          ${dominantTrack ? `<div class="type-description"><p>${escapeHtml(dominantTrack)}</p></div>` : ''}
        </div>
        <div class="type-radar">
          <div class="type-radar-chart">
            ${buildThreePageScoreChartSvg(page1?.score_chart)}
          </div>
        </div>
      </div>
      ${topCardsHtml ? `<div class="type-cards-section">${topCardsHtml}</div>` : ''}
    </section>
  `
}

const getThreePageSummaryMetricRows = (report: StructuredReport) =>
  getThreePageSummaryMetrics(report)
    .map(
      (item) => `
        <article class="summary-metric">
          <p class="summary-metric-label">${escapeHtml(item.label)}</p>
          <p class="summary-metric-value">${escapeHtml(item.value)}</p>
          <p class="summary-metric-description">${escapeHtml(item.description)}</p>
        </article>
      `
    )
    .join('')

const buildThreePageReportDownloadHtml = (report: StructuredReport, questionText = '') => {
  const generatedAt = new Date().toLocaleString('ko-KR')
  const threePage = report.three_page_report
  const page1 = threePage?.page1
  const page2 = threePage?.page2
  const page3 = threePage?.page3

  return `<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(report.report_title || '학교생활기록부 종합 분석 리포트')}</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #fafafa;
        --paper: #ffffff;
        --line: #e5e5e5;
        --text: #1a1a1a;
        --muted: #666666;
        --accent: #1e3a5f;
        --accent-light: #2d5a87;
        --border: #d1d1d1;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
        line-height: 1.6;
        -webkit-font-smoothing: antialiased;
      }
      .report-wrap {
        max-width: 210mm;
        margin: 0 auto;
        padding: 20px;
      }
      .report-page {
        min-height: 297mm;
        margin: 0 auto 20px;
        padding: 40px 48px;
        background: var(--paper);
        border: 1px solid var(--line);
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        page-break-after: always;
      }
      .report-page:last-child { page-break-after: auto; }
      .page-header {
        display: flex;
        justify-content: space-between;
        gap: 24px;
        align-items: flex-start;
        padding-bottom: 24px;
        border-bottom: 2px solid var(--accent);
        margin-bottom: 32px;
      }
      .part-label {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 4px;
        background: var(--accent);
        color: #ffffff;
        font-size: 12px;
        font-weight: 600;
        letter-spacing: 0.5px;
      }
      .page-kicker {
        margin: 0 0 8px;
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: var(--muted);
      }
      .page-header h1, .page-header h2 {
        margin: 12px 0 0;
        line-height: 1.2;
        font-weight: 700;
        color: var(--text);
      }
      .page-header h1 { font-size: 32px; }
      .page-header h2 { font-size: 26px; }
      .page-meta {
        margin-top: 12px;
        color: var(--muted);
        font-size: 13px;
        line-height: 1.5;
      }
      .page-number {
        min-width: 80px;
        padding: 16px 20px;
        border: 1px solid var(--line);
        text-align: center;
        background: #fafafa;
      }
      .page-number strong {
        display: block;
        margin-top: 4px;
        font-size: 28px;
        font-weight: 700;
        color: var(--accent);
      }
      .page-number .page-kicker {
        margin: 0;
        font-size: 10px;
      }
      .page-grid-top {
        display: grid;
        gap: 24px;
        grid-template-columns: 1.2fr 0.8fr;
        margin-top: 28px;
      }
      /* 통합 유형 섹션 스타일 */
      .type-hero-section {
        margin-top: 24px;
        border: 1px solid var(--line);
        background: var(--paper);
        padding: 32px;
      }
      .type-hero-main {
        display: grid;
        grid-template-columns: 1.2fr 0.8fr;
        gap: 32px;
        align-items: start;
      }
      .type-content {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .type-content .section-kicker {
        margin: 0;
        color: var(--accent);
        font-weight: 600;
      }
      .type-title {
        margin: 0;
        font-size: 28px;
        font-weight: 700;
        line-height: 1.3;
        color: var(--text);
      }
      .type-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 8px;
      }
      .type-tag {
        display: inline-flex;
        align-items: center;
        padding: 4px 10px;
        background: #f3f4f6;
        border-radius: 4px;
        font-size: 12px;
        font-weight: 600;
        color: var(--accent);
      }
      .type-description {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--line);
      }
      .type-description p {
        margin: 0;
        font-size: 14px;
        line-height: 1.7;
        color: var(--text);
        white-space: pre-wrap;
      }
      .type-radar {
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .type-radar-chart {
        width: 100%;
        max-width: 280px;
      }
      .type-cards-section {
        margin-top: 28px;
        padding-top: 28px;
        border-top: 1px solid var(--line);
      }
      .top-axis-cards {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
      }
      .top-axis-card {
        border: 1px solid var(--line);
        padding: 20px;
        background: #fafafa;
        border-left: 3px solid #22c55e;
      }
      .top-axis-card-head {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--line);
      }
      .top-axis-number {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px;
        height: 24px;
        background: var(--accent);
        color: #fff;
        font-size: 12px;
        font-weight: 700;
        border-radius: 50%;
      }
      .top-axis-name {
        flex: 1;
        font-size: 13px;
        font-weight: 600;
        color: var(--text);
      }
      .top-axis-score {
        font-size: 16px;
        font-weight: 700;
        color: var(--accent);
      }
      .top-axis-card h4 {
        margin: 0 0 8px;
        font-size: 15px;
        font-weight: 600;
        color: var(--text);
      }
      .top-axis-card p {
        margin: 0;
        font-size: 13px;
        line-height: 1.6;
        color: var(--muted);
        white-space: pre-wrap;
      }
      .summary-strip {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 16px;
        margin-top: 24px;
        padding: 20px 0;
        border-top: 1px solid var(--line);
        border-bottom: 1px solid var(--line);
      }
      .summary-metric {
        padding: 16px;
        border-left: 3px solid var(--accent);
        background: #fafafa;
      }
      .summary-metric-label {
        margin: 0;
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--muted);
      }
      .summary-metric-value {
        margin: 8px 0 0;
        font-size: 20px;
        font-weight: 700;
        color: var(--text);
      }
      .summary-metric-description {
        margin: 6px 0 0;
        font-size: 12px;
        line-height: 1.5;
        color: var(--muted);
      }
      .panel {
        border: 1px solid var(--line);
        padding: 24px;
        background: var(--paper);
      }
      .panel h3 {
        margin: 0 0 16px;
        font-size: 18px;
        font-weight: 600;
        color: var(--text);
      }
      .chart-shell, .score-chart-shell { display: flex; flex-direction: column; gap: 16px; position: relative; z-index: 1; }
      .chart-svg, .score-chart-svg { width: 100%; height: auto; display: block; }
      .chart-legend, .score-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 12px 16px;
      }
      .chart-legend-top { justify-content: flex-end; }
      .legend-item, .score-legend-item {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        color: var(--muted);
      }
      .legend-item-pill {
        padding: 6px 12px;
        border: 1px solid var(--line);
        background: #fafafa;
      }
      .legend-swatch {
        width: 12px;
        height: 12px;
        display: inline-block;
      }
      .score-legend-item {
        width: calc(50% - 8px);
        justify-content: space-between;
      }
      .legend-dot, .axis-badge {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        display: inline-block;
      }
      .chart-summary, .narrative-box p, .axis-card p, .flow-step p, .plan-card p, .comparison-page-card p {
        margin: 0;
        white-space: pre-wrap;
      }
      .chart-summary, .narrative-box p {
        font-size: 14px;
        color: var(--muted);
        line-height: 1.6;
      }
      .chart-empty {
        margin: 0;
        color: var(--muted);
        font-size: 14px;
        font-style: italic;
      }
      .chart-summary-box {
        border-left: 3px solid var(--accent);
        background: #f5f5f5;
        padding: 16px 20px;
      }
      .narrative-box {
        margin-top: 20px;
        padding: 20px 24px;
        border-left: 3px solid var(--accent);
        background: #f5f5f5;
      }
      .section-block { margin-top: 32px; }
      .section-block:first-of-type { margin-top: 24px; }
      .compact-section-head {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 16px;
        margin-bottom: 20px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--line);
      }
      .compact-section-head p {
        margin: 0;
        font-size: 13px;
        color: var(--muted);
      }
      .axis-card-grid, .plan-card-grid {
        display: grid;
        gap: 16px;
        margin-top: 20px;
      }
      .axis-card-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .plan-card-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .axis-card, .flow-step, .plan-card, .comparison-page-card {
        border: 1px solid var(--line);
        padding: 20px;
        background: var(--paper);
      }
      .axis-card h4, .flow-step h4, .plan-card h4, .comparison-page-card h3 {
        margin: 12px 0 12px;
        font-size: 17px;
        font-weight: 600;
        line-height: 1.4;
        color: var(--text);
      }
      .axis-card-head, .plan-card-head {
        display: flex;
        align-items: center;
        gap: 12px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--line);
        margin-bottom: 12px;
      }
      .axis-card-head p, .plan-card-head p {
        flex: 1;
        font-size: 12px;
        font-weight: 500;
        color: var(--muted);
        margin: 0;
        text-transform: uppercase;
        letter-spacing: 0.1em;
      }
      .axis-card-head strong, .plan-card-head strong {
        font-size: 18px;
        font-weight: 700;
        color: var(--text);
      }
      .axis-card-strength { background: #fafafa; border-left: 3px solid #22c55e; }
      .axis-card-weakness { background: #fafafa; border-left: 3px solid #ef4444; }
      .axis-evidence, .flow-evidence {
        margin-top: 14px;
        padding-top: 14px;
        border-top: 1px solid var(--line);
      }
      ul, ol {
        margin: 0;
        padding-left: 20px;
      }
      li + li { margin-top: 8px; }
      .flowchart-grid {
        display: grid;
        gap: 0;
        margin-top: 20px;
      }
      .flow-step-wrap {
        display: grid;
        gap: 0;
        grid-template-columns: minmax(0, 1fr);
      }
      .flow-step { position: relative; }
      .flow-step + .flow-step-wrap .flow-step::before {
        content: "";
        position: absolute;
        left: 24px;
        top: -20px;
        width: 2px;
        height: 20px;
        background: var(--line);
      }
      .flow-link {
        position: relative;
        padding-left: 24px;
        color: var(--muted);
        font-size: 13px;
        margin: 8px 0;
      }
      .flow-link span {
        display: inline-block;
        padding: 8px 14px;
        background: #f5f5f5;
        border: 1px solid var(--line);
        font-size: 12px;
      }
      .page-section-title {
        margin: 0;
        font-size: 20px;
        font-weight: 600;
        color: var(--text);
      }
      .plan-priority {
        display: inline-flex;
        align-items: center;
        height: 24px;
        padding: 0 10px;
        background: var(--accent);
        color: #ffffff;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
      }
      .plan-effect {
        margin-top: 16px;
        padding-top: 14px;
        border-top: 1px solid var(--line);
      }
      .plan-effect-label {
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--accent);
        margin: 0 0 6px;
      }
      .comparison-page-grid {
        display: grid;
        gap: 20px;
        margin-top: 20px;
      }
      .comparison-axis-line {
        margin-top: 14px;
        padding: 14px 18px;
        background: #f5f5f5;
        border-left: 2px solid var(--accent);
      }
      .comparison-axis-line span {
        display: block;
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 6px;
      }
      .excerpt-pairs {
        display: grid;
        gap: 16px;
        margin-top: 18px;
      }
      .excerpt-pair {
        border-top: 1px solid var(--line);
        padding-top: 16px;
      }
      .excerpt-pair > div:first-child,
      .excerpt-pair > div:nth-child(2) {
        margin-top: 12px;
      }
      blockquote {
        margin: 8px 0 0;
        padding: 14px 18px;
        border-left: 3px solid var(--accent);
        background: #f8f8f8;
        white-space: pre-wrap;
        font-size: 14px;
        line-height: 1.6;
        color: var(--text);
      }
      .pair-comment p { color: var(--muted); line-height: 1.6; }
      .comparison-summary-grid {
        display: grid;
        gap: 16px;
        margin-top: 18px;
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }
      .comparison-summary-grid-3 > div {
        padding: 16px;
        background: #f5f5f5;
        border-left: 3px solid var(--accent);
      }
      .grade-hero-panel::before {
        content: "학교생활기록부 분석 리포트";
        position: absolute;
        inset: 58px 12px auto 14px;
        font-size: 72px;
        font-weight: 800;
        letter-spacing: -0.04em;
        color: rgba(30, 58, 95, 0.04);
        white-space: nowrap;
        pointer-events: none;
      }
      .comparison-label {
        margin: 0 0 8px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--accent);
      }
      .flow-grade {
        margin: 0;
        font-size: 12px;
        font-weight: 600;
        color: var(--accent);
        text-transform: uppercase;
        letter-spacing: 0.1em;
      }
      @media print {
        body { background: #fff; }
        .report-wrap { padding: 0; max-width: none; }
        .report-page { margin: 0; border: 1px solid #ddd; box-shadow: none; }
      }
      @media (max-width: 960px) {
        .page-grid-top, .axis-card-grid, .plan-card-grid, .comparison-summary-grid, .summary-strip, .top-axis-cards {
          grid-template-columns: 1fr;
        }
        .type-hero-main { grid-template-columns: 1fr; }
        .type-radar-chart { max-width: 240px; }
        .score-legend-item { width: 100%; }
        .grade-hero-panel::before { font-size: 42px; inset: 76px 12px auto 14px; }
      }
    </style>
  </head>
  <body>
    <main class="report-wrap">
      <section class="report-page">
        <header class="page-header">
          <div>
            <div class="part-label">Part 1 학교생활기록부 진단</div>
            <p class="page-kicker">Page 01</p>
            <h1>${escapeHtml(report.report_title || '학교생활기록부 종합 분석 리포트')}</h1>
            <p class="page-meta">생성 시각: ${escapeHtml(generatedAt)}</p>
            ${questionText ? `<p class="page-meta">질문: ${escapeHtml(questionText)}</p>` : ''}
            ${report.summary ? `<p class="page-meta">${escapeHtml(report.summary)}</p>` : ''}
          </div>
          <div class="page-number">
            <p class="page-kicker">REPORT</p>
            <strong>01</strong>
          </div>
        </header>
        ${buildIntegratedTypeSectionHtml(report, page1)}
        <section class="section-block">
          <div class="compact-section-head">
            <div>
              <p class="page-kicker">Story Flow</p>
              <h2 class="page-section-title">1학년부터 3학년까지의 연결 흐름</h2>
            </div>
            <p>학년별 기록이 어떻게 이어지는지 압축 정리</p>
          </div>
          ${buildThreePageFlowchartHtml(page1?.flowchart)}
        </section>
        <section class="section-block">
          <div class="compact-section-head">
            <div>
              <p class="page-kicker">Story Flow</p>
              <h2 class="page-section-title">1학년부터 3학년까지의 연결 흐름</h2>
            </div>
            <p>학년별 기록이 어떻게 이어지는지 압축 정리</p>
          </div>
          ${buildThreePageFlowchartHtml(page1?.flowchart)}
        </section>
      </section>

      <section class="report-page">
        <header class="page-header">
          <div>
            <div class="part-label">Part 2 맞춤형 보완점</div>
            <p class="page-kicker">Page 02</p>
            <h2>약점 진단과 다음 학기 제안</h2>
            <p class="page-meta">1페이지의 6요소 점수를 기준으로 강점과 약점을 같은 축에서 해석합니다.</p>
          </div>
          <div class="page-number">
            <p class="page-kicker">REPORT</p>
            <strong>02</strong>
          </div>
        </header>
        <section class="section-block">
          <div class="compact-section-head">
            <div>
              <p class="page-kicker">Weakness</p>
              <h2 class="page-section-title">학생 생기부의 핵심 약점</h2>
            </div>
            <p>낮게 읽히는 축과 그 이유</p>
          </div>
          ${buildThreePageAxisCardsHtml(page2?.weakness_block, '약점 분석 데이터가 없습니다.', 'weakness')}
        </section>
        <section class="section-block">
          <div class="compact-section-head">
            <div>
              <p class="page-kicker">Next Semester</p>
              <h2 class="page-section-title">다음 학기 제안</h2>
            </div>
            <p>바로 실행할 수 있는 보완 액션</p>
          </div>
          ${buildThreePagePlanHtml(page2?.next_semester_plan)}
        </section>
      </section>

      <section class="report-page">
        <header class="page-header">
          <div>
            <div class="part-label">Part 3 합격자 비교</div>
            <p class="page-kicker">Page 03</p>
            <h2>합격자 생기부와의 비교</h2>
            <p class="page-meta">원문 발췌를 기준으로 닮은 점과 부족한 점을 함께 봅니다.</p>
          </div>
          <div class="page-number">
            <p class="page-kicker">REPORT</p>
            <strong>03</strong>
          </div>
        </header>
        ${buildThreePageComparisonHtml(page3)}
      </section>
    </main>
  </body>
</html>`
}

const buildLegacyStructuredReportDownloadHtml = (
  report: StructuredReport,
  questionText = ''
) => {
  const generatedAt = new Date().toLocaleString('ko-KR')
  const studentProfileHtml = buildStudentProfileHtml(report.student_profile)
  const universityProfilesHtml = buildUniversityProfilesHtml(report.university_profiles)
  const universityRecommendationsHtml = buildUniversityRecommendationsHtml(
    report.university_recommendations
  )
  const sectionsHtml = report.sections
    .map((section) => {
      if (section.comparison_cards && section.comparison_cards.length > 0) {
        return buildComparisonSectionHtml(section)
      }

      const sectionDescription = buildSectionDescription(section)
      const evidenceHtml = buildEvidenceHtml(report, getSectionEvidenceIds(section))
      return `
        <section class="report-section">
          <p class="section-kicker">${escapeHtml(section.section_id)}</p>
          <h2>${escapeHtml(section.title)}</h2>
          ${sectionDescription ? `<div class="section-body">${buildHtmlParagraphs(sectionDescription)}</div>` : ''}
          ${
            section.evaluation_criteria.length > 0
              ? `<div class="sub-block"><h3>평가기준</h3>${buildHtmlList(
                  section.evaluation_criteria.map((item) => item.text)
                )}</div>`
              : ''
          }
          ${
            section.student_assessment.length > 0
              ? `<div class="sub-block"><h3>학생 적용 판단</h3>${buildHtmlList(
                  section.student_assessment.map((item) => item.text)
                )}</div>`
              : ''
          }
          ${evidenceHtml}
        </section>
      `
    })
    .join('')

  const directAnswer = report.direct_answer
  const directAnswerHtml = directAnswer
    ? `
      <section class="hero-card">
        <p class="section-kicker">Executive Summary</p>
        <h2>${escapeHtml(directAnswer.title || 'Executive Summary')}</h2>
        ${directAnswer.intro ? buildHtmlParagraphs(directAnswer.intro) : ''}
        ${directAnswer.items?.length ? buildHtmlList(directAnswer.items, true) : ''}
        ${directAnswer.closing ? buildHtmlParagraphs(directAnswer.closing) : ''}
      </section>
    `
    : ''

  return `<!doctype html>
<html lang="ko">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>${escapeHtml(report.report_title || '학교생활기록부 종합 분석 리포트')}</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #fafafa;
        --paper: #ffffff;
        --line: #e5e5e5;
        --text: #1a1a1a;
        --muted: #666666;
        --accent: #1e3a5f;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: var(--bg);
        color: var(--text);
        font-family: "Pretendard", "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif;
        line-height: 1.6;
        -webkit-font-smoothing: antialiased;
      }
      .page {
        max-width: 210mm;
        margin: 0 auto;
        padding: 40px;
      }
      .cover, .hero-card, .report-section, .comparison-card, .evidence-card {
        background: var(--paper);
        border: 1px solid var(--line);
      }
      .cover {
        padding: 48px;
        border-top: 4px solid var(--accent);
        margin-bottom: 32px;
      }
      .hero-card, .report-section {
        margin-top: 24px;
        padding: 32px;
      }
      .section-kicker {
        margin: 0 0 12px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: var(--accent);
      }
      h1 {
        margin: 0;
        font-size: 32px;
        font-weight: 700;
        line-height: 1.2;
        color: var(--text);
      }
      h2 {
        margin: 0;
        font-size: 24px;
        font-weight: 600;
        line-height: 1.3;
        color: var(--text);
      }
      h3 {
        margin: 0 0 12px;
        font-size: 17px;
        font-weight: 600;
        color: var(--text);
      }
      h4 {
        margin: 0 0 8px;
        font-size: 15px;
        font-weight: 600;
        color: var(--text);
      }
      p {
        margin: 0 0 14px;
        white-space: pre-wrap;
        line-height: 1.7;
      }
      .meta {
        margin-top: 16px;
        color: var(--muted);
        font-size: 13px;
      }
      .summary {
        margin-top: 24px;
        font-size: 16px;
        color: var(--text);
        line-height: 1.7;
        padding: 20px;
        background: #f5f5f5;
        border-left: 3px solid var(--accent);
      }
      .section-body, .sub-block, .section-focus, .comparison-axis {
        margin-top: 20px;
      }
      .sub-block {
        padding-top: 18px;
        border-top: 1px solid var(--line);
      }
      ul, ol {
        margin: 0;
        padding-left: 20px;
      }
      li + li {
        margin-top: 8px;
      }
      .evidence-grid, .comparison-summary-grid {
        display: grid;
        gap: 16px;
        margin-top: 24px;
      }
      .evidence-grid {
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      }
      .comparison-summary-grid {
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }
      .evidence-card, .comparison-card {
        padding: 20px;
        border: 1px solid var(--line);
      }
      .evidence-card {
        border-left: 3px solid var(--accent);
      }
      .evidence-card h4 {
        margin: 0 0 10px;
        font-size: 15px;
        font-weight: 600;
      }
      .evidence-path, .comparison-label, .evidence-label {
        margin: 0 0 10px;
        color: var(--accent);
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.1em;
        text-transform: uppercase;
      }
      blockquote {
        margin: 0;
        padding: 14px 18px;
        border-left: 3px solid var(--accent);
        background: #f8f8f8;
        white-space: pre-wrap;
        font-size: 14px;
        line-height: 1.6;
      }
      .comparison-card + .comparison-card {
        margin-top: 20px;
      }
      .comparison-pair + .comparison-pair {
        margin-top: 18px;
        padding-top: 18px;
        border-top: 1px solid var(--line);
      }
      .comparison-pair-title {
        margin: 0 0 12px;
        font-size: 13px;
        font-weight: 600;
        color: var(--text);
      }
      .comparison-columns {
        display: grid;
        gap: 20px;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      }
      .comparison-comment {
        margin-bottom: 14px;
        padding: 14px 18px;
        background: #f5f5f5;
        border-left: 2px solid var(--accent);
      }
      @media print {
        body { background: #fff; }
        .page { padding: 0; max-width: none; }
        .cover, .hero-card, .report-section, .comparison-card, .evidence-card {
          break-inside: avoid;
          box-shadow: none;
        }
        .cover { border-top: 4px solid var(--accent); }
      }
    </style>
  </head>
  <body>
    <main class="page">
      <section class="cover">
        <p class="section-kicker">School Record Analysis Report</p>
        <h1>${escapeHtml(report.report_title || '학교생활기록부 종합 분석 리포트')}</h1>
        <p class="meta">생성 시각: ${escapeHtml(generatedAt)}</p>
        ${questionText ? `<p class="meta">분석 기준: ${escapeHtml(questionText)}</p>` : ''}
        ${
          report.summary
            ? `<div class="summary">${buildHtmlParagraphs(report.summary)}</div>`
            : ''
        }
      </section>
      ${directAnswerHtml}
      ${studentProfileHtml}
      ${universityProfilesHtml}
      ${universityRecommendationsHtml}
      ${sectionsHtml}
    </main>
  </body>
</html>`
}

const buildStructuredReportDownloadHtml = (report: StructuredReport, questionText = '') => {
  if (report.three_page_report) {
    return buildThreePageReportDownloadHtml(report, questionText)
  }
  return buildLegacyStructuredReportDownloadHtml(report, questionText)
}

const downloadStructuredReport = (report: StructuredReport, questionText = '') => {
  const html = buildStructuredReportDownloadHtml(report, questionText)
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  const rawTitle = report.report_title || '학교생활기록부_종합_분석_리포트'
  const safeTitle = rawTitle.replace(/[\\/:*?"<>|]+/g, ' ').trim().replace(/\s+/g, '_')
  a.href = url
  a.download = `${safeTitle || 'school_record_report'}_${new Date()
    .toISOString()
    .slice(0, 10)}.html`
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

const renderEmphasizedParagraph = (
  text: string,
  className = 'whitespace-pre-wrap break-words text-[16px] leading-8 text-[#1f2937]'
) => {
  const { lead, rest } = splitLeadSentence(text)
  return (
    <p className={className}>
      {lead && <span className="font-semibold text-[#111827]">{lead}</span>}
      {rest ? ` ${rest}` : ''}
    </p>
  )
}

const splitStructuredCellLead = (text: string) => {
  const trimmed = text.trim()
  if (!trimmed) return { lead: '', rest: '' }

  const colonIndex = trimmed.indexOf(':')
  if (colonIndex > 0 && colonIndex <= 42) {
    return {
      lead: trimmed.slice(0, colonIndex + 1).trim(),
      rest: trimmed.slice(colonIndex + 1).trim(),
    }
  }

  return splitLeadSentence(trimmed)
}

const renderStructuredCellText = (
  text: string,
  className = 'whitespace-pre-wrap break-words text-[15px] leading-[1.85] text-[#374151]',
  options?: { noHighlight?: boolean }
) => {
  const paragraphs = splitIntoReadableParagraphs(text)
  if (paragraphs.length === 0) {
    return <span className="text-[#9ca3af]">-</span>
  }

  const noHighlight = options?.noHighlight ?? false

  return (
    <div className="space-y-3">
      {paragraphs.map((paragraph, index) => {
        if (noHighlight) {
          return (
            <p key={`${paragraph}-${index}`} className={className}>
              {paragraph}
            </p>
          )
        }
        const { lead, rest } = splitStructuredCellLead(paragraph)
        return (
          <p key={`${paragraph}-${index}`} className={className}>
            {lead && <span className="font-semibold text-[#111827]">{lead}</span>}
            {rest ? ` ${rest}` : ''}
          </p>
        )
      })}
    </div>
  )
}

const renderTableListCell = (items: string[], ordered = false) => {
  const validItems = items.map((item) => item.trim()).filter(Boolean)
  if (validItems.length === 0) {
    return <span className="text-[#9ca3af]">-</span>
  }

  return (
    <div className="space-y-2">
      {validItems.map((item, index) => (
        <div key={`${item}-${index}`}>
          {renderStructuredCellText(ordered ? `${index + 1}. ${item}` : item)}
        </div>
      ))}
    </div>
  )
}

const extractKeywordSentences = (texts: string[], keywords: string[]) => {
  const sentences = texts
    .flatMap((text) => splitIntoReadableParagraphs(text))
    .flatMap((paragraph) =>
      paragraph
        .split(/(?<=[.!?])\s+|(?<=다\.)\s+|(?<=요\.)\s+/)
        .map((sentence) => sentence.trim())
        .filter(Boolean)
    )

  const matched = sentences.filter((sentence) => keywords.some((keyword) => sentence.includes(keyword)))
  return Array.from(new Set(matched))
}

const getComparisonSummaryItems = (
  card: AcceptedCaseComparisonCard,
  type: 'good' | 'gap' | 'action'
) => {
  const explicit =
    type === 'good' ? card.good_points || [] : type === 'gap' ? card.gaps || [] : card.action_tips || []
  const validExplicit = explicit.map((item) => item.trim()).filter(Boolean)
  if (validExplicit.length > 0) return validExplicit

  const pairComments = (card.excerpt_pairs || []).map((pair) => pair.pair_comment || '').filter(Boolean)
  const sourceTexts = [card.match_reason || '', card.comparison_axis || '', ...pairComments].filter(Boolean)

  if (type === 'good') {
    const matched = extractKeywordSentences(sourceTexts, ['우수', '강점', '돋보', '강하', '좋', '탄탄', '설득력'])
    if (matched.length > 0) return matched.slice(0, 3)
    return card.match_reason ? [card.match_reason] : ['비교 해설 기준 강점이 추가로 제공되지 않았습니다.']
  }

  if (type === 'gap') {
    const matched = extractKeywordSentences(sourceTexts, ['보완', '부족', '약점', '아쉬', '개선', '한계', '필요'])
    if (matched.length > 0) return matched.slice(0, 3)
    return pairComments.length > 0 ? [pairComments[0]] : ['비교 해설 기준 보완점이 추가로 제공되지 않았습니다.']
  }

  const matched = extractKeywordSentences(sourceTexts, [
    '확장',
    '강화',
    '연결',
    '구체화',
    '보완',
    '프로젝트',
    '다음',
    '필요',
    '제안',
  ])
  if (matched.length > 0) return matched.slice(0, 3)
  return card.comparison_axis
    ? [`다음 활동은 ${card.comparison_axis} 관점을 중심으로 구체화해 보세요.`]
    : ['다음 활동 제안이 추가로 제공되지 않았습니다.']
}

const buildSectionTableRows = (section: ReportSection): Array<Array<React.ReactNode>> => {
  const rowCount = Math.max(section.evaluation_criteria.length, section.student_assessment.length)
  return Array.from({ length: rowCount }, (_, index) => {
    const criteria = section.evaluation_criteria[index]
    const assessment = section.student_assessment[index]
    return [
      criteria?.text ? renderStructuredCellText(criteria.text) : '-',
      assessment?.text ? renderStructuredCellText(assessment.text) : '-',
    ]
  })
}

const buildEvidenceTableRows = (
  report: StructuredReport,
  evidenceIds: string[]
): Array<Array<React.ReactNode>> =>
  evidenceIds
    .map((evidenceId) => report.evidence_catalog?.[evidenceId])
    .filter((evidence): evidence is ReportEvidence => Boolean(evidence))
    .map((evidence, index) => {
      const sourceLabel =
        evidence.source_title || evidence.chunk_title || evidence.label || `출처 ${index + 1}`
      const formattedSourcePath = formatEvidenceSourcePath(evidence.source_path)
      const visibleExcerpt = getEvidenceExcerptForRender(evidence)
      return [
        sourceLabel,
        formattedSourcePath || '-',
        <div key={`${sourceLabel}-${index}`} className="space-y-2">
          {visibleExcerpt ? (
            renderStructuredCellText(visibleExcerpt, undefined, { noHighlight: true })
          ) : isEvidenceExcerptPending(evidence) ? (
            <span className="text-[#9ca3af]">근거 문장을 정리하는 중입니다.</span>
          ) : (
            <span className="text-[#9ca3af]">발췌 없음</span>
          )}
          {evidence.why_used && (
            renderStructuredCellText(`해석: ${evidence.why_used}`, 'whitespace-pre-wrap break-words text-[14px] leading-[1.8] text-[#6b7280]', { noHighlight: true })
          )}
        </div>,
      ]
    })

const getEvidenceEntries = (report: StructuredReport, evidenceIds: string[]) =>
  evidenceIds
    .map((evidenceId) => ({
      evidenceId,
      evidence: report.evidence_catalog?.[evidenceId],
    }))
    .filter((entry): entry is { evidenceId: string; evidence: ReportEvidence } => Boolean(entry.evidence))

const DeepResearchTable = ({
  columns,
  rows,
  className = '',
}: {
  columns: string[]
  rows: Array<Array<React.ReactNode>>
  className?: string
}) => {
  const validRows = rows.filter((row) =>
    row.some((cell) => {
      if (cell === null || cell === undefined) return false
      if (typeof cell === 'string') return cell.trim().length > 0
      return true
    })
  )

  if (validRows.length === 0) return null

  return (
    <div className={`border-y border-[#e5e7eb] bg-white ${className}`}>
      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse">
          <thead className="bg-[#f7f7f8]">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  className="border-b border-[#e5e7eb] px-5 py-4 text-left text-[12px] font-semibold tracking-[0.16em] text-[#6b7280]"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {validRows.map((row, rowIndex) => (
              <tr key={`table-row-${rowIndex}`} className="align-top">
                {row.map((cell, cellIndex) => (
                  <td
                    key={`table-cell-${rowIndex}-${cellIndex}`}
                    className="border-t border-[#eef0f3] px-5 py-4 text-[14px] leading-7 text-[#374151]"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

const EvidenceDisclosure = ({
  sourceLabel,
  visibleExcerpt,
  isExcerptPending,
  whyUsed,
}: {
  sourceLabel: string
  visibleExcerpt?: string
  isExcerptPending: boolean
  whyUsed?: string
}) => {
  const [isOpen, setIsOpen] = useState(false)

  return (
    <div className="space-y-2">
      <button
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className="inline-flex max-w-full items-center gap-1.5 rounded-[12px] bg-[#eef4ff] px-3 py-2 text-left text-[#2563eb] transition hover:bg-[#e5efff]"
      >
        <FileText className="h-3.5 w-3.5 shrink-0 text-[#94a3b8]" />
        <span className="truncate text-[13px] font-medium leading-5">{sourceLabel}</span>
      </button>

      {isOpen && (
        <div className="border-l-2 border-[#e5e7eb] pl-4">
          {(visibleExcerpt || isExcerptPending) && (
            <div className="mt-3">
              <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                발췌
              </p>
              <div className="mt-2">
                {visibleExcerpt ? (
                  renderStructuredCellText(visibleExcerpt, undefined, { noHighlight: true })
                ) : (
                  <p className="text-[14px] leading-[1.8] text-[#9ca3af]">
                    근거 문장을 정리하는 중입니다.
                  </p>
                )}
              </div>
            </div>
          )}

          {whyUsed && (
            <div className="mt-4 border-t border-[#eef0f3] pt-4">
              <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                해석
              </p>
              <div className="mt-2">
                {renderStructuredCellText(
                  whyUsed,
                  'whitespace-pre-wrap break-words text-[14px] leading-[1.8] text-[#4b5563]',
                  { noHighlight: true }
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const ThreePageTrendChartPreview = ({ chart }: { chart?: ThreePageGradeChart }) => {
  if (!chart || !chart.semesters?.length || !chart.series?.length) {
    return <p className="text-[14px] leading-7 text-[#8c867d]">연동된 학기별 내신 데이터가 없습니다.</p>
  }

  const activeSeries = chart.series.filter((series) =>
    (series.values || []).some((value) => typeof value === 'number')
  )
  if (activeSeries.length === 0) {
    return <p className="text-[14px] leading-7 text-[#8c867d]">연동된 학기별 내신 데이터가 없습니다.</p>
  }

  const width = 520
  const height = 250
  const padding = { top: 16, right: 18, bottom: 42, left: 36 }
  const plotWidth = width - padding.left - padding.right
  const plotHeight = height - padding.top - padding.bottom
  const yMin = 1
  const yMax = 9
  const xStep = chart.semesters.length > 1 ? plotWidth / (chart.semesters.length - 1) : 0
  const ticks = [1, 3, 5, 7, 9]
  const pointFor = (value: number, index: number) => {
    const x = padding.left + xStep * index
    const y = padding.top + ((Math.min(yMax, Math.max(yMin, value)) - yMin) / (yMax - yMin)) * plotHeight
    return { x, y }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap justify-end gap-3">
        {activeSeries.map((series) => (
          <div
            key={`legend-${series.key}`}
            className="inline-flex items-center gap-2 rounded-full bg-white/90 px-3 py-1.5 text-[12px] font-medium text-[#374151] shadow-sm"
          >
            <span className="h-3 w-3 rounded-[3px]" style={{ backgroundColor: series.color || '#111827' }} />
            <span>{series.label}</span>
          </div>
        ))}
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="w-full">
        {ticks.map((tick) => {
          const y = padding.top + ((tick - yMin) / (yMax - yMin)) * plotHeight
          return (
            <g key={`trend-tick-${tick}`}>
              <line
                x1={padding.left}
                y1={y}
                x2={width - padding.right}
                y2={y}
                stroke="#e5e7eb"
                strokeWidth="1"
              />
              <text x={padding.left - 10} y={y + 4} textAnchor="end" fontSize="11" fill="#9ca3af">
                {tick}
              </text>
            </g>
          )
        })}

        <line
          x1={padding.left}
          y1={padding.top}
          x2={padding.left}
          y2={height - padding.bottom}
          stroke="#cbd5e1"
          strokeWidth="1.2"
        />
        <line
          x1={padding.left}
          y1={height - padding.bottom}
          x2={width - padding.right}
          y2={height - padding.bottom}
          stroke="#cbd5e1"
          strokeWidth="1.2"
        />

        {activeSeries.map((series) => {
          const validPoints = (series.values || [])
            .map((value, index) =>
              typeof value === 'number' ? pointFor(value, index) : null
            )
            .filter((point): point is { x: number; y: number } => Boolean(point))
          if (validPoints.length === 0) return null
          const path = validPoints
            .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`)
            .join(' ')
          return (
            <g key={series.key}>
              <path
                d={path}
                fill="none"
                stroke={series.color || '#111827'}
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {(series.values || []).map((value, index) => {
                if (typeof value !== 'number') return null
                const point = pointFor(value, index)
                return (
                  <circle
                    key={`${series.key}-${chart.semesters[index]?.key || index}`}
                    cx={point.x}
                    cy={point.y}
                    r="4.2"
                    fill={series.color || '#111827'}
                    stroke="#fff"
                    strokeWidth="2"
                  />
                )
              })}
            </g>
          )
        })}

        {chart.semesters.map((semester, index) => (
          <text
            key={semester.key}
            x={padding.left + xStep * index}
            y={height - 16}
            textAnchor="middle"
            fontSize="11"
            fill="#6b7280"
          >
            {semester.key}
          </text>
        ))}
      </svg>

      {chart.summary && (
        <div className="rounded-[20px] bg-[#e9e1fb] px-5 py-4">
          <p className="whitespace-pre-wrap break-words text-[14px] leading-7 text-[#4f4b45]">
            {chart.summary}
          </p>
        </div>
      )}
    </div>
  )
}

const ThreePageScoreChartPreview = ({ chart }: { chart?: ThreePageScoreChart }) => {
  if (!chart || !chart.slices?.length) {
    return <p className="text-[14px] leading-7 text-[#8c867d]">6요소 점수 데이터가 없습니다.</p>
  }

  const width = 340
  const height = 340
  const cx = width / 2
  const cy = height / 2
  const radius = 120
  const levels = [0.25, 0.5, 0.75, 1]
  const axisCount = chart.slices.length
  const polygonPoints = (level: number) =>
    chart.slices
      .map((_, index) => {
        const angle = -Math.PI / 2 + (Math.PI * 2 * index) / axisCount
        const x = cx + Math.cos(angle) * radius * level
        const y = cy + Math.sin(angle) * radius * level
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  const dataPolygon = chart.slices
    .map((slice, index) => {
      const angle = -Math.PI / 2 + (Math.PI * 2 * index) / axisCount
      const ratio = Math.max(0, Math.min(1, (slice.score || 0) / 5))
      const x = cx + Math.cos(angle) * radius * ratio
      const y = cy + Math.sin(angle) * radius * ratio
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')

  return (
    <div className="space-y-4">
      <svg viewBox={`0 0 ${width} ${height}`} className="mx-auto w-full max-w-[340px]">
        {levels.map((level) => (
          <polygon
            key={`radar-grid-${level}`}
            points={polygonPoints(level)}
            fill="none"
            stroke="#d4d4d8"
            strokeWidth="1"
          />
        ))}
        {chart.slices.map((slice, index) => {
          const angle = -Math.PI / 2 + (Math.PI * 2 * index) / axisCount
          const axisX = cx + Math.cos(angle) * radius
          const axisY = cy + Math.sin(angle) * radius
          const labelX = cx + Math.cos(angle) * (radius + 28)
          const labelY = cy + Math.sin(angle) * (radius + 28)
          const pointRatio = Math.max(0, Math.min(1, (slice.score || 0) / 5))
          const pointX = cx + Math.cos(angle) * radius * pointRatio
          const pointY = cy + Math.sin(angle) * radius * pointRatio
          const anchor = Math.abs(labelX - cx) < 12 ? 'middle' : labelX < cx ? 'end' : 'start'
          return (
            <g key={`radar-axis-${slice.axis}`}>
              <line x1={cx} y1={cy} x2={axisX} y2={axisY} stroke="#d4d4d8" strokeWidth="1" />
              <circle cx={pointX} cy={pointY} r="4" fill="#c4b5fd" stroke="#ffffff" strokeWidth="2" />
              <text x={labelX} y={labelY} textAnchor={anchor} fontSize="13" fill="#6b7280">
                {slice.axis}
              </text>
            </g>
          )
        })}
        <polygon
          points={dataPolygon}
          fill="rgba(196,181,253,0.35)"
          stroke="#c4b5fd"
          strokeWidth="2.5"
        />
      </svg>

      <div className="grid gap-2 sm:grid-cols-2">
        {chart.slices.map((slice) => (
          <div
            key={`slice-${slice.axis}`}
            className="flex items-center justify-between rounded-2xl bg-white px-3 py-2 text-[12px] text-[#4b5563]"
          >
            <div className="inline-flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: slice.color || '#6b7280' }}
              />
              <span>{slice.axis}</span>
            </div>
            <strong className="text-[#111827]">{formatDisplayScore(slice.score)}/5</strong>
          </div>
        ))}
      </div>

      {chart.summary && (
        <p className="whitespace-pre-wrap break-words text-[14px] leading-7 text-[#6e685f]">
          {chart.summary}
        </p>
      )}
    </div>
  )
}

const ThreePageAxisBlockPreview = ({
  block,
  tone,
  emptyText,
}: {
  block?: ThreePageStrengthBlock
  tone: 'strength' | 'weakness'
  emptyText: string
}) => {
  if (!block || !block.items?.length) {
    return <p className="text-[14px] leading-7 text-[#8c867d]">{emptyText}</p>
  }

  return (
    <div className="space-y-5">
      {block.headline && (
        <div className="border-l-2 border-[#e5e7eb] pl-4">
          <p className="whitespace-pre-wrap break-words text-[15px] leading-8 text-[#4f4b45]">
            {block.headline}
          </p>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {block.items.map((item) => (
          <article
            key={`${tone}-${item.axis}`}
            className={`border-t border-[#e5e7eb] pt-5 ${
              tone === 'strength'
                ? ''
                : ''
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="inline-flex items-center gap-2">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: item.color || '#6b7280' }}
                />
                <p className="text-[12px] font-semibold uppercase tracking-[0.2em] text-[#9ca3af]">
                  {item.axis}
                </p>
              </div>
              <p className="text-[18px] font-semibold text-[#111827]">
                {formatDisplayScore(item.score)}/5
              </p>
            </div>
            {item.title && (
              <h4 className="mt-4 text-[18px] font-semibold leading-7 text-[#1f1f1c]">
                {item.title}
              </h4>
            )}
            {item.description && (
              <p className="mt-3 whitespace-pre-wrap break-words text-[14px] leading-7 text-[#2f2d29]">
                {item.description}
              </p>
            )}
            {item.evidence_quotes && item.evidence_quotes.length > 0 && (
              <div className="mt-4 border-t border-[#e5e7eb] pt-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">근거</p>
                <div className="mt-2 space-y-2">
                  {item.evidence_quotes.map((quote, quoteIdx) => (
                    <p
                      key={`${tone}-${item.axis}-${quoteIdx}`}
                      className="whitespace-pre-wrap break-words text-[13px] leading-6 text-[#6e685f]"
                    >
                      {quote}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}

const ThreePageFlowchartPreview = ({ flowchart }: { flowchart?: ThreePageFlowchart }) => {
  if (!flowchart || !flowchart.nodes?.length) {
    return <p className="text-[14px] leading-7 text-[#8c867d]">학년별 연결 흐름 데이터가 없습니다.</p>
  }

  return (
    <div className="space-y-5">
      {flowchart.headline && (
        <div className="border-l-2 border-[#e5e7eb] pl-4">
          <p className="whitespace-pre-wrap break-words text-[15px] leading-8 text-[#4f4b45]">
            {flowchart.headline}
          </p>
        </div>
      )}

      <div className="space-y-4">
        {flowchart.nodes.map((node, index) => {
          const link = flowchart.links?.[index]
          return (
            <div key={node.node_id} className="space-y-3">
              <article className="border-t border-[#e5e7eb] pt-5">
                <p className="text-[11px] uppercase tracking-[0.24em] text-[#b45309]">{node.grade}</p>
                <h4 className="mt-2 text-[19px] font-semibold text-[#1f1f1c]">
                  {node.title || node.grade}
                </h4>
                <p className="mt-3 whitespace-pre-wrap break-words text-[14px] leading-7 text-[#2f2d29]">
                  {node.summary}
                </p>
                {node.evidence_quotes && node.evidence_quotes.length > 0 && (
                  <div className="mt-4 border-t border-[#e5e7eb] pt-4">
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">근거</p>
                    <div className="mt-2 space-y-2">
                      {node.evidence_quotes.map((quote, quoteIdx) => (
                        <p
                          key={`${node.node_id}-${quoteIdx}`}
                          className="whitespace-pre-wrap break-words text-[13px] leading-6 text-[#6e685f]"
                        >
                          {quote}
                        </p>
                      ))}
                    </div>
                  </div>
                )}
              </article>

              {link && (
                <div className="pl-6">
                  <div className="inline-flex items-center border-l-2 border-[#e5e7eb] pl-3 text-[13px] text-[#6e685f]">
                    {link.label}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

const ThreePagePlanPreview = ({ plan }: { plan?: ThreePageNextSemesterPlan }) => {
  if (!plan || !plan.action_cards?.length) {
    return <p className="text-[14px] leading-7 text-[#8c867d]">다음 학기 제안 데이터가 없습니다.</p>
  }

  return (
    <div className="space-y-5">
      {plan.headline && (
        <div className="border-l-2 border-[#e5e7eb] pl-4">
          <p className="whitespace-pre-wrap break-words text-[15px] leading-8 text-[#4f4b45]">
            {plan.headline}
          </p>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {plan.action_cards.map((card, index) => (
          <article key={`${card.axis}-${index}`} className="border-t border-[#e5e7eb] pt-5">
            <div className="flex items-center justify-between gap-3">
              <span className="text-[11px] font-semibold text-[#6b7280]">
                {card.priority || '보완'}
              </span>
              <span className="text-[13px] font-medium text-[#6e685f]">
                {formatDisplayScore(card.current_score)}/5
              </span>
            </div>
            <p className="mt-4 text-[11px] uppercase tracking-[0.22em] text-[#9ca3af]">{card.axis}</p>
            <h4 className="mt-2 text-[18px] font-semibold leading-7 text-[#1f1f1c]">{card.title}</h4>
            {card.why && (
              <p className="mt-3 whitespace-pre-wrap break-words text-[14px] leading-7 text-[#2f2d29]">
                {card.why}
              </p>
            )}
            {card.actions && card.actions.length > 0 && (
              <div className="mt-4 space-y-2 border-t border-[#e5e7eb] pt-4">
                {card.actions.map((action, actionIdx) => (
                  <div key={`${card.axis}-${actionIdx}`} className="flex gap-3">
                    <span className="mt-1 text-[11px] font-semibold uppercase tracking-[0.2em] text-[#3182F6]">
                      {(actionIdx + 1).toString().padStart(2, '0')}
                    </span>
                    <p className="whitespace-pre-wrap break-words text-[14px] leading-7 text-[#2f2d29]">
                      {action}
                    </p>
                  </div>
                ))}
              </div>
            )}
            {card.expected_effect && (
              <div className="mt-4 border-t border-[#e5e7eb] pt-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">기대 효과</p>
                <p className="mt-2 whitespace-pre-wrap break-words text-[13px] leading-6 text-[#6e685f]">
                  {card.expected_effect}
                </p>
              </div>
            )}
          </article>
        ))}
      </div>
    </div>
  )
}

const ThreePageComparisonPreview = ({ page3 }: { page3?: ThreePageReport['page3'] }) => {
  if (!page3 || !page3.cards?.length) {
    return <p className="text-[14px] leading-7 text-[#8c867d]">비교 가능한 합격 사례가 없습니다.</p>
  }

  return (
    <div className="space-y-5">
      {page3.headline && (
        <div className="border-l-2 border-[#e5e7eb] pl-4">
          <p className="whitespace-pre-wrap break-words text-[15px] leading-8 text-[#4f4b45]">
            {page3.headline}
          </p>
        </div>
      )}

      <div className="space-y-5">
        {(page3.cards || []).map((card, cardIdx) => (
          <article key={card.card_id} className="border-t border-[#e5e7eb] pt-6">
            <p className="text-[11px] uppercase tracking-[0.24em] text-[#b45309]">
              Case {(cardIdx + 1).toString().padStart(2, '0')}
            </p>
            <h4 className="mt-3 text-[20px] font-semibold text-[#1f1f1c]">{card.label}</h4>
            {card.match_reason && (
              <p className="mt-3 whitespace-pre-wrap break-words text-[14px] leading-7 text-[#6e685f]">
                {card.match_reason}
              </p>
            )}
            {card.comparison_axis && (
              <div className="mt-4 border-l-2 border-[#e5e7eb] pl-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">비교 축</p>
                <p className="mt-2 whitespace-pre-wrap break-words text-[14px] leading-7 text-[#2f2d29]">
                  {card.comparison_axis}
                </p>
              </div>
            )}

            {card.excerpt_pairs && card.excerpt_pairs.length > 0 && (
              <div className="mt-5 space-y-4">
                {card.excerpt_pairs.map((pair, pairIdx) => (
                  <div key={pair.pair_id || `${card.card_id}-${pairIdx}`} className="border-y border-[#e5e7eb] py-4">
                    <div className="grid gap-4 lg:grid-cols-2">
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">
                          {pair.user_excerpt_label || '내 생기부'}
                        </p>
                        <p className="mt-2 whitespace-pre-wrap break-words text-[13px] leading-6 text-[#2f2d29]">
                          {pair.user_excerpt}
                        </p>
                      </div>
                      <div>
                        <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">
                          {pair.accepted_excerpt_label || '합격자 생기부'}
                        </p>
                        <p className="mt-2 whitespace-pre-wrap break-words text-[13px] leading-6 text-[#2f2d29]">
                          {pair.accepted_excerpt}
                        </p>
                      </div>
                    </div>
                    {pair.pair_comment && (
                      <div className="mt-4 border-t border-[#e5e7eb] pt-4">
                        <p className="whitespace-pre-wrap break-words text-[13px] leading-6 text-[#6e685f]">
                          {pair.pair_comment}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div className="mt-6 grid gap-5 lg:grid-cols-3">
              <div className="border-t border-[#e5e7eb] pt-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">닮은 점</p>
                <div className="mt-3 space-y-2">
                  {(card.good_points || []).length > 0 ? (
                    (card.good_points || []).map((item, itemIdx) => (
                      <p key={`${card.card_id}-good-${itemIdx}`} className="text-[14px] leading-7 text-[#2f2d29]">
                        {item}
                      </p>
                    ))
                  ) : (
                    <p className="text-[14px] leading-7 text-[#8c867d]">해당 내용 없음</p>
                  )}
                </div>
              </div>
              <div className="border-t border-[#e5e7eb] pt-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">부족한 점</p>
                <div className="mt-3 space-y-2">
                  {(card.gaps || []).length > 0 ? (
                    (card.gaps || []).map((item, itemIdx) => (
                      <p key={`${card.card_id}-gap-${itemIdx}`} className="text-[14px] leading-7 text-[#2f2d29]">
                        {item}
                      </p>
                    ))
                  ) : (
                    <p className="text-[14px] leading-7 text-[#8c867d]">해당 내용 없음</p>
                  )}
                </div>
              </div>
              <div className="border-t border-[#e5e7eb] pt-4">
                <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">보완 포인트</p>
                <div className="mt-3 space-y-2">
                  {(card.action_tips || []).length > 0 ? (
                    (card.action_tips || []).map((item, itemIdx) => (
                      <p key={`${card.card_id}-action-${itemIdx}`} className="text-[14px] leading-7 text-[#2f2d29]">
                        {item}
                      </p>
                    ))
                  ) : (
                    <p className="text-[14px] leading-7 text-[#8c867d]">해당 내용 없음</p>
                  )}
                </div>
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}

const getThreePageSummaryMetrics = (report: StructuredReport) => {
  const axisScores = report.student_profile?.axis_scores || []
  const topAxis = [...axisScores]
    .sort((a, b) => (b.score || 0) - (a.score || 0))[0]

  const topUniversity = report.university_recommendations?.cards?.[0]
  const gradeChart = report.three_page_report?.page1?.grade_chart
  const coreSeries = gradeChart?.series?.find((series) => series.key === 'core')
  const lastGrade =
    coreSeries?.values && coreSeries.values.length > 0
      ? [...coreSeries.values].reverse().find((value) => typeof value === 'number')
      : undefined
  const weaknessAxis = report.three_page_report?.page2?.weakness_block?.items?.[0]

  return [
    {
      label: '핵심 강점 축',
      value: topAxis ? `${topAxis.axis} ${formatDisplayScore(topAxis.score)}/5` : '-',
      description: topAxis?.summary || '가장 먼저 읽히는 강점 축',
    },
    {
      label: '추천 대학',
      value: topUniversity ? `${topUniversity.school_name} ${topUniversity.fit_level || ''}`.trim() : '-',
      description: topUniversity?.fit_summary || '학생부종합전형 기준 추천 결과',
    },
    {
      label: '최근 국영수탐',
      value: typeof lastGrade === 'number' ? `${formatDisplayScore(lastGrade)}등급` : '-',
      description: '학기별 내신 추이에서 읽히는 최근 평균',
    },
    {
      label: '우선 보완 축',
      value: weaknessAxis ? `${weaknessAxis.axis} ${formatDisplayScore(weaknessAxis.score)}/5` : '-',
      description: weaknessAxis?.description || weaknessAxis?.title || '다음 학기 제안의 출발점',
    },
  ]
}

const ThreePageSummaryStrip = ({ report }: { report: StructuredReport }) => {
  const metrics = getThreePageSummaryMetrics(report)
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((item) => (
        <article key={item.label} className="border-t border-[#e5e7eb] px-4 py-4">
          <p className="text-[11px] uppercase tracking-[0.22em] text-[#9ca3af]">{item.label}</p>
          <p className="mt-2 text-[18px] font-semibold text-[#111827]">{item.value}</p>
          <p className="mt-2 line-clamp-2 text-[12px] leading-6 text-[#6e685f]">{item.description}</p>
        </article>
      ))}
    </div>
  )
}

const renderThreePageReportPreview = (
  report: StructuredReport,
  reportTitle: string,
  questionText: string
) => {
  const threePage = report.three_page_report
  if (!threePage) return null

  return (
    <div className="mx-auto max-w-[1080px] bg-white">
      <div className="bg-white">
        <div className="space-y-4">
          <section className="bg-white">
            <div className="border-b border-[#e5e7eb] px-0 py-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div className="min-w-0 flex-1">
                  <div className="inline-flex items-center gap-2 text-[12px] font-semibold text-[#6b7280]">
                    Part 1 학교생활기록부 진단
                  </div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-[#b45309]">Page 01</p>
                  <h2 className="mt-3 text-[28px] font-semibold tracking-tight text-[#111827] md:text-[34px]">
                    {reportTitle}
                  </h2>
                  {questionText && (
                    <p className="mt-3 text-[13px] leading-6 text-[#7c7468]">질문: {questionText}</p>
                  )}
                  {report.summary && (
                    <p className="mt-4 whitespace-pre-wrap break-words text-[15px] leading-8 text-[#4f4b45]">
                      {report.summary}
                    </p>
                  )}
                </div>
                <div className="text-center">
                  <p className="text-[11px] uppercase tracking-[0.24em] text-[#b45309]">Report</p>
                  <p className="mt-1 text-[28px] font-semibold text-[#111827]">01</p>
                </div>
              </div>
            </div>

            <div className="space-y-8 px-0 py-6">
              <ThreePageSummaryStrip report={report} />

              <div className="grid gap-5 xl:grid-cols-[1.18fr_0.82fr]">
                <div className="relative border-y border-[#e5e7eb] py-5">
                  <div className="pointer-events-none absolute left-4 top-14 text-[72px] font-extrabold tracking-[-0.08em] text-[#111827]/[0.05]">
                    바이브온 세포 리포트
                  </div>
                  <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">Trend Plot</p>
                  <h3 className="mt-3 text-[20px] font-semibold text-[#1f1f1c]">
                    학기별 전체 내신 / 국영수탐 내신 변화
                  </h3>
                  <div className="relative z-[1] mt-5">
                    <ThreePageTrendChartPreview chart={threePage.page1?.grade_chart} />
                  </div>
                </div>

                <div className="border-y border-[#e5e7eb] py-5">
                  <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">Score Wheel</p>
                  <h3 className="mt-3 text-[20px] font-semibold text-[#1f1f1c]">
                    6요소 진단 점수
                  </h3>
                  <div className="mt-5">
                    <ThreePageScoreChartPreview chart={threePage.page1?.score_chart} />
                  </div>
                </div>
              </div>

              <section>
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">Core Strength</p>
                    <h3 className="mt-3 text-[24px] font-semibold tracking-tight text-[#111827]">
                      학생의 핵심 강점
                    </h3>
                  </div>
                  <p className="text-[12px] text-[#7c7468]">6요소 점수 중 상위 축 기반 요약</p>
                </div>
                <div className="mt-5">
                  <ThreePageAxisBlockPreview
                    block={threePage.page1?.strength_block}
                    tone="strength"
                    emptyText="강점 분석 데이터가 없습니다."
                  />
                </div>
              </section>

              <section>
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">Story Flow</p>
                    <h3 className="mt-3 text-[24px] font-semibold tracking-tight text-[#111827]">
                      1학년부터 3학년까지의 연결 흐름
                    </h3>
                  </div>
                  <p className="text-[12px] text-[#7c7468]">학년별 기록이 어떻게 이어지는지 압축 정리</p>
                </div>
                <div className="mt-5">
                  <ThreePageFlowchartPreview flowchart={threePage.page1?.flowchart} />
                </div>
              </section>
            </div>
          </section>

          <section className="border-t border-[#e5e7eb] bg-white">
            <div className="border-b border-[#e5e7eb] px-0 py-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="inline-flex items-center gap-2 text-[12px] font-semibold text-[#6b7280]">
                    Part 2 맞춤형 보완점
                  </div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-[#b45309]">Page 02</p>
                  <h3 className="mt-3 text-[28px] font-semibold tracking-tight text-[#111827]">
                    약점 진단과 다음 학기 제안
                  </h3>
                </div>
                <div className="text-center">
                  <p className="text-[11px] uppercase tracking-[0.24em] text-[#b45309]">Report</p>
                  <p className="mt-1 text-[28px] font-semibold text-[#111827]">02</p>
                </div>
              </div>
            </div>

            <div className="space-y-8 px-0 py-6">
              <section>
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">Weakness</p>
                    <h3 className="mt-3 text-[24px] font-semibold tracking-tight text-[#111827]">
                      학생 생기부의 핵심 약점
                    </h3>
                  </div>
                  <p className="text-[12px] text-[#7c7468]">낮게 읽히는 축과 그 이유</p>
                </div>
                <div className="mt-5">
                  <ThreePageAxisBlockPreview
                    block={threePage.page2?.weakness_block}
                    tone="weakness"
                    emptyText="약점 분석 데이터가 없습니다."
                  />
                </div>
              </section>

              <section>
                <div className="flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">Next Semester</p>
                    <h3 className="mt-3 text-[24px] font-semibold tracking-tight text-[#111827]">
                      다음 학기 제안
                    </h3>
                  </div>
                  <p className="text-[12px] text-[#7c7468]">바로 실행할 수 있는 보완 액션</p>
                </div>
                <div className="mt-5">
                  <ThreePagePlanPreview plan={threePage.page2?.next_semester_plan} />
                </div>
              </section>
            </div>
          </section>

          <section className="border-t border-[#e5e7eb] bg-white">
            <div className="border-b border-[#e5e7eb] px-0 py-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <div className="inline-flex items-center gap-2 text-[12px] font-semibold text-[#6b7280]">
                    Part 3 합격자 비교
                  </div>
                  <p className="text-[11px] uppercase tracking-[0.28em] text-[#b45309]">Page 03</p>
                  <h3 className="mt-3 text-[28px] font-semibold tracking-tight text-[#111827]">
                    합격자 생기부와의 비교
                  </h3>
                </div>
                <div className="text-center">
                  <p className="text-[11px] uppercase tracking-[0.24em] text-[#b45309]">Report</p>
                  <p className="mt-1 text-[28px] font-semibold text-[#111827]">03</p>
                </div>
              </div>
            </div>

            <div className="px-6 py-6 md:px-8">
              <ThreePageComparisonPreview page3={threePage.page3} />
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

export function SchoolRecordDeepResearchReportView({
  report,
  questionText = '',
}: {
  report: StructuredReport
  questionText?: string
}) {
  const hasDirectAnswer = Boolean(
    report.direct_answer?.intro ||
      (report.direct_answer?.items && report.direct_answer.items.length > 0) ||
      report.direct_answer?.closing
  )
  const hasStudentProfile = Boolean(
    report.student_profile?.headline ||
      report.student_profile?.dominant_track ||
      report.student_profile?.immediate_priority ||
      (report.student_profile?.axis_scores && report.student_profile.axis_scores.length > 0) ||
      (report.student_profile?.strengths && report.student_profile.strengths.length > 0) ||
      (report.student_profile?.risks && report.student_profile.risks.length > 0)
  )
  const hasUniversityRecommendations = Boolean(
    report.university_recommendations?.cards &&
      report.university_recommendations.cards.length > 0
  )
  const hasUniversityProfiles = Boolean(
    report.university_profiles && report.university_profiles.length > 0
  )
  const nonComparisonSections = report.sections.filter(
    (section) => !(section.comparison_cards && section.comparison_cards.length > 0)
  )
  const comparisonSections = report.sections.filter(
    (section) => section.comparison_cards && section.comparison_cards.length > 0
  )
  const prefaceSectionCount =
    (hasDirectAnswer ? 1 : 0) +
    (hasStudentProfile ? 1 : 0) +
    (hasUniversityProfiles ? 1 : 0) +
    (hasUniversityRecommendations ? 1 : 0)
  const reportTitle = report.report_title || '학교생활기록부 심층 분석'

  if (report.three_page_report) {
    return renderThreePageReportPreview(report, reportTitle, questionText)
  }

  return (
    <div className="mx-auto max-w-[1080px] bg-white">
      <div className="border-b border-[#e5e7eb] px-0 py-10 md:py-12">
        <div className="w-full">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#9ca3af]">
            School Record Report
          </p>
          <h2 className="mt-4 text-[30px] font-semibold tracking-tight text-[#111827] md:text-[36px]">
            {reportTitle}
          </h2>
          {questionText && (
            <p className="mt-5 text-[14px] leading-7 text-[#6b7280]">질문: {questionText}</p>
          )}
        </div>
      </div>

      {hasDirectAnswer && (
        <section id="executive-summary" className="scroll-mt-24 py-12 md:py-16">
          <div className="w-full">
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6b7280]">
              Executive Summary
            </p>
            <h2 className="mt-2 text-[24px] font-semibold tracking-tight text-[#111827] md:text-[28px]">
              {report.direct_answer?.title || '핵심 요약'}
            </h2>

            <div className="mt-8 space-y-6">
              {report.summary && (
                <p className="whitespace-pre-wrap break-words text-[20px] font-bold leading-[1.75] text-[#111827] md:text-[22px]">
                  {report.summary}
                </p>
              )}

              {report.summary &&
                (report.direct_answer?.intro || report.direct_answer?.items?.length) && (
                  <div className="h-px bg-[#e5e7eb]" />
                )}

              {report.direct_answer?.intro && (
                <p className="whitespace-pre-wrap break-words text-[17px] font-semibold leading-[1.9] text-[#111827] md:text-[18px]">
                  {report.direct_answer.intro}
                </p>
              )}

              {report.direct_answer?.items && report.direct_answer.items.length > 0 && (
                <div className="space-y-3">
                  {report.direct_answer.items.map((item, itemIdx) => (
                    <p
                      key={`direct-answer-item-${itemIdx}`}
                      className="whitespace-pre-wrap break-words text-[17px] font-semibold leading-[1.9] text-[#111827] md:text-[18px]"
                    >
                      {itemIdx + 1}. {item}
                    </p>
                  ))}
                </div>
              )}

              {report.direct_answer?.closing && (
                <div className="mt-6 border-t border-[#e5e7eb] pt-4">
                  <p className="whitespace-pre-wrap break-words text-[17px] font-semibold leading-[1.9] text-[#111827] md:text-[18px]">
                    {report.direct_answer.closing}
                  </p>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {hasStudentProfile && (
        <section id="student-profile" className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14">
          <div className="w-full">
            <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
              {((hasDirectAnswer ? 1 : 0) + 1).toString().padStart(2, '0')}
            </p>
            <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
              학생 평가 프로필
            </h3>
          </div>

          <div className="mt-8 w-full space-y-8">
            {report.student_profile?.headline &&
              renderEmphasizedParagraph(
                report.student_profile.headline,
                'whitespace-pre-wrap break-words text-[16px] leading-[1.9] text-[#374151]'
              )}

            {report.student_profile?.dominant_track && (
              <div className="space-y-2">
                <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                  현재 서사
                </p>
                {renderEmphasizedParagraph(
                  report.student_profile.dominant_track,
                  'whitespace-pre-wrap break-words text-[15px] leading-[1.85] text-[#374151]'
                )}
              </div>
            )}

            {report.student_profile?.immediate_priority && (
              <div className="space-y-2">
                <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                  가장 먼저 보완할 점
                </p>
                {renderEmphasizedParagraph(
                  report.student_profile.immediate_priority,
                  'whitespace-pre-wrap break-words text-[15px] leading-[1.85] text-[#374151]'
                )}
              </div>
            )}

            {report.student_profile?.axis_scores &&
              report.student_profile.axis_scores.length > 0 && (
                <DeepResearchTable
                  columns={['평가축', '점수', '해석', '근거']}
                  rows={report.student_profile.axis_scores.map((item) => [
                    item.axis,
                    `${item.score || 0}/5`,
                    item.summary || '-',
                    renderTableListCell(item.evidence_quotes || []),
                  ])}
                />
              )}

            <DeepResearchTable
              columns={['핵심 강점', '핵심 리스크']}
              rows={[
                [
                  renderTableListCell(report.student_profile?.strengths || []),
                  renderTableListCell(report.student_profile?.risks || []),
                ],
              ]}
            />
          </div>
        </section>
      )}

      {hasUniversityProfiles && (
        <section
          id="university-profile"
          className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14"
        >
          <div className="w-full">
            <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
              {((hasDirectAnswer ? 1 : 0) + (hasStudentProfile ? 1 : 0) + 1)
                .toString()
                .padStart(2, '0')}
            </p>
            <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
              대학 평가 프로필
            </h3>
          </div>

          <div className="mt-8 w-full space-y-6">
            <DeepResearchTable
              columns={['대학', '인재상 요약', '핵심 평가요소', '평가/면접 포인트', '문서 근거']}
              rows={(report.university_profiles || []).map((profile) => [
                profile.school_name,
                profile.talent_summary || '-',
                (profile.evaluation_keywords || []).join(', ') || '-',
                [profile.evaluation_summary, profile.interview_policy].filter(Boolean).join('\n\n') || '-',
                profile.evidence_excerpt
                  ? `${profile.source_title || '문서 근거'}\n\n${profile.evidence_excerpt}`
                  : '-',
              ])}
            />
          </div>
        </section>
      )}

      {hasUniversityRecommendations && (
        <section id="university-fit" className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14">
          <div className="w-full">
            <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
              {(
                (hasDirectAnswer ? 1 : 0) +
                (hasStudentProfile ? 1 : 0) +
                (hasUniversityProfiles ? 1 : 0) +
                1
              )
                .toString()
                .padStart(2, '0')}
            </p>
            <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
              추천 대학 카드
            </h3>
          </div>

          <div className="mt-8 w-full space-y-8">
            {report.university_recommendations?.summary &&
              renderEmphasizedParagraph(
                report.university_recommendations.summary,
                'whitespace-pre-wrap break-words text-[16px] leading-[1.9] text-[#374151]'
              )}

            <DeepResearchTable
              columns={['대학', '전형', '적합도', '추천 요약', '맞는 이유', '주의할 점']}
              rows={(report.university_recommendations?.cards || []).map((card) => [
                card.school_name,
                card.admission_label || '-',
                card.fit_level || (card.fit_score ? `${card.fit_score}` : '-'),
                [
                  card.fit_summary,
                  card.talent_keywords?.length ? `핵심 평가축: ${card.talent_keywords.join(', ')}` : '',
                  card.interview_note ? `면접 포인트: ${card.interview_note}` : '',
                  card.grade_support
                    ? `교과 보조 판정: ${card.grade_support.label} / ${
                        card.grade_support.department || '모집단위 미상'
                      } ${card.grade_support.admission_type || ''} / 내신 ${
                        card.grade_support.user_grade ?? '-'
                      } vs 컷 ${card.grade_support.cutoff_grade ?? '-'}`
                    : '',
                ]
                  .filter(Boolean)
                  .join('\n\n'),
                renderTableListCell(card.matching_points || []),
                renderTableListCell(card.caution_points || []),
              ])}
            />

            {report.university_recommendations?.accepted_case_hints &&
              report.university_recommendations.accepted_case_hints.length > 0 && (
                <div className="space-y-3">
                  <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                    합격 사례 유사도
                  </p>
                  <DeepResearchTable
                    columns={['사례', '유사도/설명']}
                    rows={report.university_recommendations.accepted_case_hints.map((hint, hintIdx) => [
                      hint.label || `유사 사례 ${hintIdx + 1}`,
                      `${hint.similarity_score ? `유사도 ${hint.similarity_score}\n\n` : ''}${
                        hint.match_reason || '-'
                      }`,
                    ])}
                  />
                </div>
              )}
          </div>
        </section>
      )}

      {nonComparisonSections.map((section, sectionIdx) => {
        const sectionDescription = buildSectionDescription(section)
        const sectionEvidenceIds = getSectionEvidenceIds(section)
        const displayNumber = sectionIdx + prefaceSectionCount + 1
        const sectionTableRows = buildSectionTableRows(section)
        const evidenceEntries = getEvidenceEntries(report, sectionEvidenceIds)

        return (
          <section
            key={section.section_id}
            id={section.section_id}
            className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14"
          >
            <div className="w-full">
              <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
                {displayNumber.toString().padStart(2, '0')}
              </p>
              <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
                {section.title}
              </h3>
            </div>

            <div className="mt-8 w-full space-y-8">
              {sectionDescription && (
                <div className="space-y-4">
                  {splitIntoReadableParagraphs(sectionDescription).map((paragraph, paragraphIdx) => (
                    <React.Fragment key={`${section.section_id}-paragraph-${paragraphIdx}`}>
                      {renderEmphasizedParagraph(
                        paragraph,
                        'whitespace-pre-wrap break-words text-[16px] leading-[1.9] text-[#374151]'
                      )}
                    </React.Fragment>
                  ))}
                </div>
              )}

              {sectionTableRows.length > 0 && (
                <div className="space-y-3">
                  <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                    생기부 구조표
                  </p>
                  <DeepResearchTable columns={['평가 기준', '생기부 해석']} rows={sectionTableRows} />
                </div>
              )}

              {evidenceEntries.length > 0 && (
                <div className="space-y-3">
                  <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                    근거 자료
                  </p>
                  <div className="space-y-3">
                    {evidenceEntries.map(({ evidenceId, evidence }, evidenceIdx) => {
                      const sourceLabel =
                        evidence.source_title ||
                        evidence.chunk_title ||
                        evidence.label ||
                        `출처 ${evidenceIdx + 1}`
                      const visibleExcerpt = getEvidenceExcerptForRender(evidence)
                      const isExcerptPending = isEvidenceExcerptPending(evidence)

                      return (
                        <EvidenceDisclosure
                          key={evidenceId}
                          sourceLabel={`문서 ${sourceLabel}`}
                          visibleExcerpt={visibleExcerpt}
                          isExcerptPending={isExcerptPending}
                          whyUsed={evidence.why_used}
                        />
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          </section>
        )
      })}

      {comparisonSections.map((section, comparisonSectionIdx) => {
        const baseIndex =
          nonComparisonSections.length + comparisonSectionIdx + prefaceSectionCount + 1
        const isTopAcceptedComparisonSection = section.title.trim() === '유사 합격자 비교'
        const comparisonSectionTitle = isTopAcceptedComparisonSection
          ? '실제 최고 수준의 합격자 생기부 분석'
          : section.title

        return (
          <section
            key={section.section_id}
            id={section.section_id}
            className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14"
          >
            <div className="w-full">
              <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
                {baseIndex.toString().padStart(2, '0')}
              </p>
              <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
                {comparisonSectionTitle}
              </h3>
            </div>

            <div className="mt-8 w-full space-y-8">
              {section.comparison_focus && !isTopAcceptedComparisonSection && (
                <div className="space-y-2">
                  <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                    비교 관점
                  </p>
                  {renderEmphasizedParagraph(
                    section.comparison_focus,
                    'whitespace-pre-wrap break-words text-[15px] leading-[1.85] text-[#374151]'
                  )}
                </div>
              )}

              {(section.comparison_cards || []).map((card, cardIdx) => (
                <div
                  key={card.card_id}
                  className="space-y-6 border-t border-[#e5e7eb] pt-8 first:border-t-0 first:pt-0"
                >
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">
                      Case {(cardIdx + 1).toString().padStart(2, '0')}
                    </p>
                    <h4 className="mt-3 text-[20px] font-semibold text-[#111827]">{card.label}</h4>
                    {card.match_reason && (
                      <p className="mt-3 whitespace-pre-wrap break-words text-[15px] leading-[1.8] text-[#4b5563]">
                        {card.match_reason}
                      </p>
                    )}
                  </div>

                  {card.comparison_axis && (
                    <div className="space-y-2">
                      <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                        세부 비교 관점
                      </p>
                      {renderEmphasizedParagraph(
                        card.comparison_axis,
                        'whitespace-pre-wrap break-words text-[14px] leading-[1.8] text-[#374151]'
                      )}
                    </div>
                  )}

                  {(card.excerpt_pairs || []).map((pair, pairIdx) => (
                    <div key={pair.pair_id || `${card.card_id}-pair-${pairIdx}`} className="space-y-3">
                      <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                        원문 비교 {(pairIdx + 1).toString().padStart(2, '0')}
                      </p>
                      <div className="border-y border-[#e5e7eb] bg-white">
                        <div className="overflow-x-auto">
                          <table className="min-w-full border-collapse">
                            <thead className="bg-[#f7f7f8]">
                              <tr>
                                <th className="border-b border-[#e5e7eb] px-5 py-4 text-left text-[12px] font-semibold tracking-[0.16em] text-[#6b7280]">
                                  {pair.user_excerpt_label || '내 생기부 원문'}
                                </th>
                                <th className="border-b border-[#e5e7eb] px-5 py-4 text-left text-[12px] font-semibold tracking-[0.16em] text-[#6b7280]">
                                  {pair.accepted_excerpt_label || '합격자 생기부 원문'}
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr className="align-top">
                                <td className="border-t border-[#eef0f3] px-5 py-4 text-[14px] leading-7 text-[#374151]">
                                  {pair.user_excerpt
                                    ? renderStructuredCellText(pair.user_excerpt)
                                    : '-'}
                                </td>
                                <td className="border-t border-[#eef0f3] px-5 py-4 text-[14px] leading-7 text-[#374151]">
                                  {pair.accepted_excerpt
                                    ? renderStructuredCellText(pair.accepted_excerpt)
                                    : '-'}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                        </div>
                        <div className="border-t border-[#e5e7eb] bg-[#fafafa] px-5 py-4">
                          <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                            해설
                          </p>
                          {pair.pair_comment ? (
                            <div className="mt-3 space-y-3">
                              {splitIntoReadableParagraphs(pair.pair_comment).map((paragraph, paragraphIdx) => (
                                <React.Fragment
                                  key={`${pair.pair_id || card.card_id}-comment-${paragraphIdx}`}
                                >
                                  {renderEmphasizedParagraph(
                                    paragraph,
                                    'whitespace-pre-wrap break-words text-[15px] leading-[1.85] text-[#111827]'
                                  )}
                                </React.Fragment>
                              ))}
                            </div>
                          ) : (
                            <p className="mt-3 text-[14px] leading-7 text-[#9ca3af]">
                              볼드 처리 이유에 대한 해설이 제공되지 않았습니다.
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}

                  <DeepResearchTable
                    columns={['강점', '보완이 필요한 점', '다음 행동']}
                    rows={[
                      [
                        renderTableListCell(getComparisonSummaryItems(card, 'good')),
                        renderTableListCell(getComparisonSummaryItems(card, 'gap')),
                        renderTableListCell(getComparisonSummaryItems(card, 'action'), true),
                      ],
                    ]}
                  />
                </div>
              ))}
            </div>
          </section>
        )
      })}
    </div>
  )
}

function SchoolRecordDeepChatPage() {
  const navigate = useNavigate()
  const { isAuthenticated, accessToken } = useAuth()

  // ─── 채팅 상태 ───
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [isGeneratingReport, setIsGeneratingReport] = useState(false)
  const [visualReportDownloadRequestId, setVisualReportDownloadRequestId] = useState(0)
  const [visualReportDownloadActive, setVisualReportDownloadActive] = useState(false)
  const [visualReportDownloadPhase, setVisualReportDownloadPhase] = useState<'idle' | 'generating' | 'rendering'>('idle')
  const [hasSchoolRecord, setHasSchoolRecord] = useState<boolean | null>(null)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // ─── 사이드 패널 상태 ───
  const [isSidePanelOpen, setIsSidePanelOpen] = useState(false)
  const [sidePanelTab, setSidePanelTab] = useState<'upload' | 'analysis'>('upload')
  const [selectedMsgIndex, setSelectedMsgIndex] = useState<number | null>(null)
  const [expandedChunks, setExpandedChunks] = useState<Set<number>>(new Set())
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadText, setUploadText] = useState('')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState<{
    ok: boolean
    message: string
  } | null>(null)
  const [sources, setSources] = useState<SourceItem[]>([])
  const [sourcesLoading, setSourcesLoading] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const isBusy = isStreaming || isGeneratingReport

  const getApiPrefix = useCallback(() => {
    const apiBase = getApiBaseUrl()
    return apiBase ? `${apiBase}/api` : '/api'
  }, [])

  const getApiPrefixCandidates = useCallback(() => {
    const primaryPrefix = getApiPrefix()
    const candidates = [primaryPrefix]

    if (typeof window !== 'undefined') {
      const sameOriginPrefix = '/api'
      if (!candidates.includes(sameOriginPrefix)) {
        candidates.push(sameOriginPrefix)
      }
    }

    return candidates
  }, [getApiPrefix])

  const getToken = useCallback((): string | null => {
    return (localStorage.getItem('access_token') || accessToken || '').trim() || null
  }, [accessToken])

  const getSourcePath = useCallback((src: SourceMeta) => {
    const path = src.heading_path?.filter(Boolean).join(' > ')
    if (path) return path
    return [src.chapter, src.part, src.sub_section].filter(Boolean).join(' > ')
  }, [])

  const applyDisplayExcerptsToMessage = useCallback(
    (messageId: string, displayExcerpts: Record<string, string>) => {
      const entries = Object.entries(displayExcerpts).filter(
        ([, text]) => typeof text === 'string' && text.trim()
      )
      if (!messageId || entries.length === 0) return

      setMessages((prev) => {
        const messageIndex = prev.findIndex((msg) => msg.id === messageId)
        if (messageIndex === -1) return prev

        const targetMessage = prev[messageIndex]
        if (!targetMessage?.report?.evidence_catalog) return prev
        const currentReport = targetMessage.report

        let changed = false
        const nextCatalog: Record<string, ReportEvidence> = { ...currentReport.evidence_catalog }

        entries.forEach(([evidenceId, displayExcerpt]) => {
          const current = nextCatalog[evidenceId]
          if (!current || current.display_excerpt === displayExcerpt.trim()) return
          nextCatalog[evidenceId] = {
            ...current,
            display_excerpt: displayExcerpt.trim(),
          }
          changed = true
        })

        if (!changed) return prev

        const updated = [...prev]
        updated[messageIndex] = {
          ...targetMessage,
          report: {
            ...currentReport,
            evidence_catalog: nextCatalog,
          },
        }
        return updated
      })
    },
    []
  )

  const hydrateEvidenceDisplayExcerpts = useCallback(
    async (messageId: string, report?: StructuredReport | null) => {
      const token = getToken()
      if (!token || !messageId || !report?.evidence_catalog) return

      const evidences: EvidenceDisplayExcerptRequestItem[] = Object.values(
        report.evidence_catalog
      )
        .filter((evidence) => isAcademicEvidenceDisplayTarget(evidence) && !evidence.display_excerpt?.trim())
        .map((evidence) => ({
          evidence_id: evidence.evidence_id,
          evidence_type: evidence.evidence_type,
          source_id: evidence.source_id,
          source_type: evidence.source_type,
          source_title: evidence.source_title,
          chunk_title: evidence.chunk_title,
          chunk_summary: evidence.chunk_summary,
          why_used: evidence.why_used,
          used_excerpt: evidence.used_excerpt,
        }))

      if (evidences.length === 0) return

      try {
        const res = await fetch(`${getApiPrefix()}/school-record-deep-chat/evidence-display-excerpts`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ evidences }),
        })
        if (!res.ok) return

        const data = await res.json().catch(() => null)
        const displayExcerpts =
          data?.display_excerpts && typeof data.display_excerpts === 'object'
            ? (data.display_excerpts as Record<string, string>)
            : null

        if (displayExcerpts) {
          applyDisplayExcerptsToMessage(messageId, displayExcerpts)
        }
      } catch {
        // ignore
      }
    },
    [applyDisplayExcerptsToMessage, getApiPrefix, getToken]
  )

  // ─── 스크롤 ───
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // ─── 생기부 연동 체크 ───
  useEffect(() => {
    if (!isAuthenticated) return
    const token = getToken()
    if (!token) return

    fetch(`${getApiPrefix()}/school-record/status`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => res.json())
      .then((data) => setHasSchoolRecord(data?.linked === true))
      .catch(() => setHasSchoolRecord(false))
  }, [isAuthenticated, getToken, getApiPrefix])

  // ─── 업로드 자료 목록 불러오기 ───
  const loadSources = useCallback(async () => {
    const token = getToken()
    if (!token) return
    setSourcesLoading(true)
    try {
      const res = await fetch(`${getApiPrefix()}/academic-contents/list`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await res.json()
      setSources(data?.sources || [])
    } catch {
      // ignore
    } finally {
      setSourcesLoading(false)
    }
  }, [getToken, getApiPrefix])

  useEffect(() => {
    if (isSidePanelOpen && isAuthenticated) {
      loadSources()
    }
  }, [isSidePanelOpen, isAuthenticated, loadSources])

  // ─── 텍스트/파일 업로드 ───
  const handleSelectFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0] || null
    if (!selected) {
      setUploadFile(null)
      return
    }

    const lower = selected.name.toLowerCase()
    if (!lower.endsWith('.md') && !lower.endsWith('.txt')) {
      setUploadFile(null)
      setUploadResult({ ok: false, message: '.md 또는 .txt 파일만 업로드할 수 있습니다.' })
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    if (selected.size > 5 * 1024 * 1024) {
      setUploadFile(null)
      setUploadResult({ ok: false, message: '파일이 너무 큽니다. 5MB 이하 파일만 업로드해 주세요.' })
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }

    setUploadFile(selected)
    setUploadResult(null)
  }

  const clearSelectedFile = () => {
    setUploadFile(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleUpload = async () => {
    const token = getToken()
    if (!token) return
    const title = uploadTitle.trim()
    const text = uploadText.trim()
    if (!uploadFile && !text) {
      setUploadResult({ ok: false, message: '텍스트를 입력하거나 .md/.txt 파일을 선택해 주세요.' })
      return
    }

    setIsUploading(true)
    setUploadResult(null)
    try {
      let res: Response
      if (uploadFile) {
        const formData = new FormData()
        formData.append('file', uploadFile)
        if (title) formData.append('source_title', title)

        res = await fetch(`${getApiPrefix()}/academic-contents/upload-file`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        })
      } else {
        res = await fetch(`${getApiPrefix()}/academic-contents/upload-text`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            source_title: title || undefined,
            raw_text: text,
          }),
        })
      }

      const data = await res.json()
      if (!res.ok) {
        setUploadResult({ ok: false, message: data?.detail || '업로드 실패' })
        return
      }
      setUploadResult({
        ok: true,
        message: `"${data.source_title}" 업로드 완료 (${data.chunk_count}개 청크, ${data.total_chars.toLocaleString()}자)`,
      })
      setUploadTitle('')
      setUploadText('')
      clearSelectedFile()
      loadSources()
    } catch (err: any) {
      setUploadResult({ ok: false, message: err.message || '네트워크 오류' })
    } finally {
      setIsUploading(false)
    }
  }

  // ─── 자료 삭제 ───
  const handleDeleteSource = async (sourceTitle: string) => {
    const token = getToken()
    if (!token) return
    if (!confirm(`"${sourceTitle}" 자료를 삭제하시겠습니까?`)) return

    try {
      await fetch(
        `${getApiPrefix()}/academic-contents/delete/${encodeURIComponent(sourceTitle)}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      loadSources()
    } catch {
      // ignore
    }
  }

  const handleGenerateReportDownload = useCallback(async () => {
    const token = getToken()
    if (!token || isBusy) return

    setError(null)
    setIsGeneratingReport(true)

    try {
      let res: Response | null = null
      let networkError: unknown = null

      for (const apiPrefix of getApiPrefixCandidates()) {
        try {
          res = await fetch(`${apiPrefix}/school-record-deep-chat/report`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({}),
          })
          networkError = null
          break
        } catch (error) {
          networkError = error
        }
      }

      if (!res) {
        throw new Error(
          networkError instanceof Error
            ? `${networkError.message} 백엔드 서버 연결을 확인해 주세요.`
            : '백엔드 서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.'
        )
      }

      const data: GenerateReportResponse | { detail?: string } = await res
        .json()
        .catch(() => ({}))

      if (!res.ok) {
        throw new Error((data as { detail?: string }).detail || '리포트 생성에 실패했습니다.')
      }

      const payload = data as GenerateReportResponse
      const report = payload.report
      const reportSources = Array.isArray(payload.sources) ? payload.sources : []

      if (!report || !Array.isArray(report.sections) || report.sections.length === 0) {
        throw new Error('리포트 본문이 비어 있습니다. 잠시 후 다시 시도해 주세요.')
      }

      const assistantMessageId = createMessageId()
      const nextMessages: ChatMessage[] = [
        ...messages,
        {
          id: assistantMessageId,
          role: 'assistant',
          content: report.plain_text || '',
          report,
          sources: reportSources,
          messageKind: 'report',
        },
      ]

      setMessages(nextMessages)
      setSelectedMsgIndex(nextMessages.length - 1)
      if (reportSources.length > 0) {
        setSidePanelTab('analysis')
        setIsSidePanelOpen(true)
        setExpandedChunks(new Set())
      }

      void hydrateEvidenceDisplayExcerpts(assistantMessageId, report)
      downloadStructuredReport(report)
    } catch (err: any) {
      setError(err.message || '리포트 생성에 실패했습니다.')
    } finally {
      setIsGeneratingReport(false)
    }
  }, [getApiPrefixCandidates, getToken, hydrateEvidenceDisplayExcerpts, isBusy, messages])

  // ─── 메시지 전송 ───
  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isBusy) return

      const token = getToken()
      if (!token) {
        setError('로그인이 필요합니다.')
        return
      }

      setError(null)
      const userMsg: ChatMessage = { id: createMessageId(), role: 'user', content: trimmed }
      setMessages((prev) => [...prev, userMsg])
      setInput('')
      setIsStreaming(true)

      const assistantMessageId = createMessageId()
      const assistantMsg: ChatMessage = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        sources: [],
        messageKind: 'chat',
      }
      setMessages((prev) => [...prev, assistantMsg])

      const controller = new AbortController()
      abortRef.current = controller

      try {
        const history = messages.map((m) => ({
          role: m.role,
          content: m.content,
        }))

        const res = await fetch(
          `${getApiPrefix()}/school-record-deep-chat/stream`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ message: trimmed, history }),
            signal: controller.signal,
          }
        )

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}))
          throw new Error(errData?.detail || `서버 오류 (${res.status})`)
        }

        const reader = res.body?.getReader()
        if (!reader) throw new Error('스트리밍을 시작할 수 없습니다.')

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            const jsonStr = line.slice(6).trim()
            if (!jsonStr) continue

            try {
              const event = JSON.parse(jsonStr)
              if (event.type === 'chunk' && event.text) {
                setMessages((prev) => {
                  const updated = [...prev]
                  const messageIndex = updated.findIndex((msg) => msg.id === assistantMessageId)
                  const target = messageIndex >= 0 ? updated[messageIndex] : null
                  if (target?.role === 'assistant') {
                    updated[messageIndex] = {
                      ...target,
                      content: target.content + event.text,
                    }
                  }
                  return updated
                })
              } else if (event.type === 'report' && event.report) {
                setMessages((prev) => {
                  const updated = [...prev]
                  const messageIndex = updated.findIndex((msg) => msg.id === assistantMessageId)
                  const target = messageIndex >= 0 ? updated[messageIndex] : null
                  if (target?.role === 'assistant') {
                    updated[messageIndex] = {
                      ...target,
                      report: event.report,
                      content: event.report.plain_text || target.content,
                    }
                    setSelectedMsgIndex(messageIndex)
                  }
                  return updated
                })
                void hydrateEvidenceDisplayExcerpts(assistantMessageId, event.report)
              } else if (event.type === 'sources' && event.sources) {
                setMessages((prev) => {
                  const updated = [...prev]
                  const messageIndex = updated.findIndex((msg) => msg.id === assistantMessageId)
                  const target = messageIndex >= 0 ? updated[messageIndex] : null
                  if (target?.role === 'assistant') {
                    updated[messageIndex] = {
                      ...target,
                      sources: event.sources,
                    }
                    setSelectedMsgIndex(messageIndex)
                    if (event.sources.length > 0) {
                      setSidePanelTab('analysis')
                      setIsSidePanelOpen(true)
                      setExpandedChunks(new Set())
                    }
                  }
                  return updated
                })
              } else if (event.type === 'error') {
                setError(event.message)
              }
            } catch {
              // skip
            }
          }
        }
      } catch (err: any) {
        if (err.name !== 'AbortError') {
          setError(err.message || '메시지 전송에 실패했습니다.')
          setMessages((prev) => {
            if (
              prev[prev.length - 1]?.role === 'assistant' &&
              !prev[prev.length - 1]?.content
            ) {
              return prev.slice(0, -1)
            }
            return prev
          })
        }
      } finally {
        setIsStreaming(false)
        abortRef.current = null
      }
    },
    [getApiPrefix, getToken, hydrateEvidenceDisplayExcerpts, isBusy, messages]
  )

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  // ─── 비로그인 / 생기부 미연동 화면 ───
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-4">
        <div className="text-center max-w-md">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg">
            <BookOpen className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-extrabold text-[#191F28]">로그인이 필요합니다</h1>
          <p className="mt-2 text-sm text-[#6B7684]">
            생활기록부 심층 분석을 이용하려면 로그인해 주세요.
          </p>
          <button
            onClick={() => navigate('/chat')}
            className="mt-6 inline-flex h-12 items-center justify-center rounded-xl bg-[#3182F6] px-6 text-sm font-bold text-white transition hover:bg-[#1f6fe2]"
          >
            채팅으로 돌아가기
          </button>
        </div>
      </div>
    )
  }

  if (hasSchoolRecord === false) {
    return (
      <div className="min-h-screen bg-[#F9FAFB] flex items-center justify-center p-4">
        <div className="text-center max-w-md">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-lg">
            <BookOpen className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-extrabold text-[#191F28]">
            생기부를 먼저 연동해 주세요
          </h1>
          <p className="mt-2 text-sm text-[#6B7684]">
            심층 분석을 위해서는 학교생활기록부 PDF를 업로드해야 합니다.
          </p>
          <button
            onClick={() => navigate('/school-record-deep')}
            className="mt-6 inline-flex h-12 items-center justify-center rounded-xl bg-[#3182F6] px-6 text-sm font-bold text-white transition hover:bg-[#1f6fe2]"
          >
            생기부 연동하러 가기
          </button>
        </div>
      </div>
    )
  }

  // ─── 메인 레이아웃 ───
  return (
    <div className="flex h-screen bg-white">
      {/* 왼쪽: 채팅 영역 */}
      <div
        className={`flex flex-col flex-1 min-w-0 transition-all duration-300 ${
          isSidePanelOpen ? 'mr-0' : ''
        }`}
      >
        {/* 헤더 */}
        <header className="shrink-0 border-b border-[#E5E8EB] bg-white px-4 py-3 safe-area-top">
          <div className="mx-auto flex max-w-[1440px] items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/chat')}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-[#4E5968] transition hover:bg-gray-100"
              >
                <ArrowLeft className="h-5 w-5" />
              </button>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600">
                  <Sparkles className="h-4 w-4 text-white" />
                </div>
                <div>
                  <h1 className="text-sm font-extrabold text-[#191F28]">
                    생기부 심층 분석
                  </h1>
                  <p className="text-[11px] text-[#8B95A1]">AI 기반 맞춤 분석</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  if (visualReportDownloadActive || visualReportDownloadPhase !== 'idle') return
                  setVisualReportDownloadPhase('generating')
                  setVisualReportDownloadActive(true)
                  setVisualReportDownloadRequestId((prev) => prev + 1)
                }}
                disabled={isBusy || visualReportDownloadPhase !== 'idle'}
                className={`inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3 text-[12px] font-bold text-white transition disabled:cursor-not-allowed ${
                  visualReportDownloadPhase !== 'idle'
                    ? 'bg-blue-500'
                    : 'bg-[#111827] hover:bg-[#1f2937] disabled:bg-[#9ca3af]'
                }`}
                title="연동된 생기부로 시각 분석 리포트를 생성하고 PDF 다운로드"
              >
                <Download className="h-4 w-4" />
                {visualReportDownloadPhase === 'idle' ? '리포트 받기' : visualReportDownloadPhase === 'generating' ? '생성 중...' : 'PDF 변환 중...'}
              </button>
              <button
                onClick={() => setIsSidePanelOpen(!isSidePanelOpen)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-[#4E5968] transition hover:bg-gray-100"
                title={isSidePanelOpen ? '패널 닫기' : '참고자료 패널'}
              >
                {isSidePanelOpen ? (
                  <PanelRightClose className="h-5 w-5" />
                ) : (
                  <PanelRightOpen className="h-5 w-5" />
                )}
              </button>
            </div>
          </div>
        </header>

        {/* 메시지 영역 */}
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="mx-auto max-w-[1440px] px-6 py-6">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center pt-8">
                <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg">
                  <Sparkles className="h-10 w-10 text-white" />
                </div>
                <h2 className="text-xl font-extrabold text-[#191F28]">
                  생활기록부 심층 상세 분석
                </h2>
                <p className="mt-2 text-center text-sm text-[#6B7684] max-w-sm">
                  연동된 생기부를 기반으로 학업 역량, 전공적합성, 강점·약점 등을
                  심층 분석합니다.
                </p>

                <div className="mt-6 w-full max-w-lg">
                  <button
                    onClick={() => {
                      if (visualReportDownloadActive || visualReportDownloadPhase !== 'idle') return
                      setVisualReportDownloadPhase('generating')
                      setVisualReportDownloadActive(true)
                      setVisualReportDownloadRequestId((prev) => prev + 1)
                    }}
                    disabled={isBusy || visualReportDownloadPhase !== 'idle'}
                    className={`flex w-full items-center justify-center gap-2 rounded-[22px] px-5 py-4 text-sm font-bold text-white shadow-[0_12px_30px_rgba(17,24,39,0.16)] transition disabled:cursor-not-allowed ${
                      visualReportDownloadPhase !== 'idle'
                        ? 'bg-blue-500'
                        : 'bg-[#111827] hover:-translate-y-0.5 hover:bg-[#1f2937] disabled:bg-[#9ca3af]'
                    }`}
                  >
                    <Download className="h-4 w-4" />
                    {visualReportDownloadPhase === 'idle' ? '분석 리포트 받기' : visualReportDownloadPhase === 'generating' ? '분석 리포트 생성 중...' : 'PDF 변환 중...'}
                  </button>
                  <p className="mt-2 text-center text-[12px] text-[#8B95A1]">
                    연동된 생기부를 기반으로 4페이지 시각 분석 리포트를 PDF로 다운로드합니다.
                  </p>
                </div>

                <div className="mt-8 w-full max-w-lg space-y-2">
                  {QUICK_ACTIONS.map((action) => (
                    <button
                      key={action}
                      onClick={() => sendMessage(action)}
                      disabled={isBusy}
                      className="w-full rounded-2xl border border-[#E5E8EB] bg-white px-4 py-3.5 text-left text-sm font-medium text-[#4E5968] shadow-sm transition hover:-translate-y-0.5 hover:shadow-md disabled:opacity-50"
                    >
                      {action}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="space-y-6">
                {messages.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`${
                        msg.role === 'assistant' && msg.report?.sections?.length
                          ? 'w-full'
                          : 'max-w-[92%]'
                      } ${msg.role === 'assistant' ? 'space-y-2' : ''}`}
                    >
                      <div
                        className={`text-sm leading-relaxed ${
                          msg.role === 'user'
                            ? 'rounded-2xl bg-[#3182F6] px-4 py-3 text-white'
                            : msg.report?.sections?.length
                              ? 'bg-transparent p-0 text-[#191F28]'
                              : `rounded-2xl bg-white px-4 py-3 text-[#191F28] shadow-sm border ${
                                  selectedMsgIndex === idx
                                    ? 'border-indigo-400 ring-2 ring-indigo-100'
                                    : 'border-[#EEF0F3]'
                                }`
                        }`}
                      >
                        {msg.role === 'assistant' && !msg.content && isStreaming ? (
                          <div className="flex items-center gap-2 text-[#8B95A1]">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="text-xs">분석 중...</span>
                          </div>
                        ) : msg.role === 'assistant' && msg.report?.sections?.length ? (
                          (() => {
                            const report = msg.report
                            const hasDirectAnswer = Boolean(
                              report.direct_answer?.intro ||
                                (report.direct_answer?.items &&
                                  report.direct_answer.items.length > 0) ||
                                report.direct_answer?.closing
                            )
                            const hasStudentProfile = Boolean(
                              report.student_profile?.headline ||
                                report.student_profile?.dominant_track ||
                                report.student_profile?.immediate_priority ||
                                (report.student_profile?.axis_scores &&
                                  report.student_profile.axis_scores.length > 0) ||
                                (report.student_profile?.strengths &&
                                  report.student_profile.strengths.length > 0) ||
                                (report.student_profile?.risks &&
                                  report.student_profile.risks.length > 0)
                            )
                            const hasUniversityRecommendations = Boolean(
                              report.university_recommendations?.cards &&
                                report.university_recommendations.cards.length > 0
                            )
                            const hasUniversityProfiles = Boolean(
                              report.university_profiles && report.university_profiles.length > 0
                            )
                            const nonComparisonSections = report.sections.filter(
                              (section) => !(section.comparison_cards && section.comparison_cards.length > 0)
                            )
                            const comparisonSections = report.sections.filter(
                              (section) => section.comparison_cards && section.comparison_cards.length > 0
                            )
                            const prefaceSectionCount =
                              (hasDirectAnswer ? 1 : 0) +
                              (hasStudentProfile ? 1 : 0) +
                              (hasUniversityProfiles ? 1 : 0) +
                              (hasUniversityRecommendations ? 1 : 0)
                            const questionText =
                              msg.messageKind !== 'report' &&
                              idx > 0 &&
                              messages[idx - 1]?.role === 'user'
                                ? messages[idx - 1]?.content
                                : ''
                            const reportTitle = report.report_title || '학교생활기록부 심층 분석'

                            if (report.three_page_report) {
                              return renderThreePageReportPreview(report, reportTitle, questionText)
                            }

                            return (
                              <div className="mx-auto max-w-[1080px] bg-white">
                                <div className="border-b border-[#e5e7eb] px-0 py-10 md:py-12">
                                  <div className="w-full">
                                    <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[#9ca3af]">
                                      School Record Report
                                    </p>
                                    <h2 className="mt-4 text-[30px] font-semibold tracking-tight text-[#111827] md:text-[36px]">
                                      {reportTitle}
                                    </h2>
                                    {questionText && (
                                      <p className="mt-5 text-[14px] leading-7 text-[#6b7280]">
                                        질문: {questionText}
                                      </p>
                                    )}
                                  </div>
                                </div>

                                {hasDirectAnswer && (
                                  <section
                                    id="executive-summary"
                                    className="scroll-mt-24 py-12 md:py-16"
                                  >
                                    <div className="w-full">
                                      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#6b7280]">
                                        Executive Summary
                                      </p>

                                      <h2 className="mt-2 text-[24px] font-semibold tracking-tight text-[#111827] md:text-[28px]">
                                        {report.direct_answer?.title || '핵심 요약'}
                                      </h2>

                                          <div className="mt-8 space-y-6">
                                            {report.summary && (
                                              <p className="whitespace-pre-wrap break-words text-[20px] font-bold leading-[1.75] text-[#111827] md:text-[22px]">
                                                {report.summary}
                                              </p>
                                            )}

                                            {(report.summary && (report.direct_answer?.intro || report.direct_answer?.items?.length)) && (
                                              <div className="h-px bg-[#e5e7eb]" />
                                            )}

                                            {report.direct_answer?.intro && (
                                              <p className="whitespace-pre-wrap break-words text-[17px] font-semibold leading-[1.9] text-[#111827] md:text-[18px]">
                                                {report.direct_answer.intro}
                                              </p>
                                            )}

                                            {report.direct_answer?.items &&
                                              report.direct_answer.items.length > 0 && (
                                                <div className="space-y-3">
                                                  {report.direct_answer.items.map((item, itemIdx) => (
                                                    <p
                                                      key={`direct-answer-item-${itemIdx}`}
                                                      className="whitespace-pre-wrap break-words text-[17px] font-semibold leading-[1.9] text-[#111827] md:text-[18px]"
                                                    >
                                                      {itemIdx + 1}. {item}
                                                    </p>
                                                  ))}
                                                </div>
                                              )}

                                            {report.direct_answer?.closing && (
                                              <div className="mt-6 border-t border-[#e5e7eb] pt-4">
                                                <p className="whitespace-pre-wrap break-words text-[17px] font-semibold leading-[1.9] text-[#111827] md:text-[18px]">
                                                  {report.direct_answer.closing}
                                                </p>
                                              </div>
                                            )}
                                          </div>
                                    </div>
                                  </section>
                                )}

                                    {hasStudentProfile && (
                                      <section
                                        id="student-profile"
                                        className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14"
                                      >
                                        <div className="w-full">
                                          <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
                                            {((hasDirectAnswer ? 1 : 0) + 1)
                                              .toString()
                                              .padStart(2, '0')}
                                          </p>
                                          <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
                                            학생 평가 프로필
                                          </h3>
                                        </div>

                                        <div className="mt-8 w-full space-y-8">
                                          {report.student_profile?.headline &&
                                            renderEmphasizedParagraph(
                                              report.student_profile.headline,
                                              'whitespace-pre-wrap break-words text-[16px] leading-[1.9] text-[#374151]'
                                            )}

                                          {report.student_profile?.dominant_track && (
                                            <div className="space-y-2">
                                              <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                                                현재 서사
                                              </p>
                                              {renderEmphasizedParagraph(
                                                report.student_profile.dominant_track,
                                                'whitespace-pre-wrap break-words text-[15px] leading-[1.85] text-[#374151]'
                                              )}
                                            </div>
                                          )}

                                          {report.student_profile?.immediate_priority && (
                                            <div className="space-y-2">
                                              <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                                                가장 먼저 보완할 점
                                              </p>
                                              {renderEmphasizedParagraph(
                                                report.student_profile.immediate_priority,
                                                'whitespace-pre-wrap break-words text-[15px] leading-[1.85] text-[#374151]'
                                              )}
                                            </div>
                                          )}

                                          {report.student_profile?.axis_scores &&
                                            report.student_profile.axis_scores.length > 0 && (
                                              <DeepResearchTable
                                                columns={['평가축', '점수', '해석', '근거']}
                                                rows={report.student_profile.axis_scores.map((item) => [
                                                  item.axis,
                                                  `${item.score || 0}/5`,
                                                  item.summary || '-',
                                                  renderTableListCell(item.evidence_quotes || []),
                                                ])}
                                              />
                                            )}

                                          <DeepResearchTable
                                            columns={['핵심 강점', '핵심 리스크']}
                                            rows={[
                                              [
                                                renderTableListCell(report.student_profile?.strengths || []),
                                                renderTableListCell(report.student_profile?.risks || []),
                                              ],
                                            ]}
                                          />
                                        </div>
                                      </section>
                                    )}

                                    {hasUniversityProfiles && (
                                      <section
                                        id="university-profile"
                                        className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14"
                                      >
                                        <div className="w-full">
                                          <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
                                            {((hasDirectAnswer ? 1 : 0) + (hasStudentProfile ? 1 : 0) + 1)
                                              .toString()
                                              .padStart(2, '0')}
                                          </p>
                                          <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
                                            대학 평가 프로필
                                          </h3>
                                        </div>

                                        <div className="mt-8 w-full space-y-6">
                                          <DeepResearchTable
                                            columns={['대학', '인재상 요약', '핵심 평가요소', '평가/면접 포인트', '문서 근거']}
                                            rows={(report.university_profiles || []).map((profile) => [
                                              profile.school_name,
                                              profile.talent_summary || '-',
                                              (profile.evaluation_keywords || []).join(', ') || '-',
                                              [profile.evaluation_summary, profile.interview_policy]
                                                .filter(Boolean)
                                                .join('\n\n') || '-',
                                              profile.evidence_excerpt
                                                ? `${profile.source_title || '문서 근거'}\n\n${profile.evidence_excerpt}`
                                                : '-',
                                            ])}
                                          />
                                        </div>
                                      </section>
                                    )}

                                    {hasUniversityRecommendations && (
                                      <section
                                        id="university-fit"
                                        className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14"
                                      >
                                        <div className="w-full">
                                          <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
                                            {(
                                              (hasDirectAnswer ? 1 : 0) +
                                              (hasStudentProfile ? 1 : 0) +
                                              (hasUniversityProfiles ? 1 : 0) +
                                              1
                                            )
                                              .toString()
                                              .padStart(2, '0')}
                                          </p>
                                          <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
                                            추천 대학 카드
                                          </h3>
                                        </div>

                                        <div className="mt-8 w-full space-y-8">
                                          {report.university_recommendations?.summary &&
                                            renderEmphasizedParagraph(
                                              report.university_recommendations.summary,
                                              'whitespace-pre-wrap break-words text-[16px] leading-[1.9] text-[#374151]'
                                            )}

                                          <DeepResearchTable
                                            columns={['대학', '전형', '적합도', '추천 요약', '맞는 이유', '주의할 점']}
                                            rows={(report.university_recommendations?.cards || []).map((card) => [
                                              card.school_name,
                                              card.admission_label || '-',
                                              card.fit_level || (card.fit_score ? `${card.fit_score}` : '-'),
                                              [
                                                card.fit_summary,
                                                card.talent_keywords?.length
                                                  ? `핵심 평가축: ${card.talent_keywords.join(', ')}`
                                                  : '',
                                                card.interview_note ? `면접 포인트: ${card.interview_note}` : '',
                                                card.grade_support
                                                  ? `교과 보조 판정: ${card.grade_support.label} / ${
                                                      card.grade_support.department || '모집단위 미상'
                                                    } ${card.grade_support.admission_type || ''} / 내신 ${
                                                      card.grade_support.user_grade ?? '-'
                                                    } vs 컷 ${card.grade_support.cutoff_grade ?? '-'}`
                                                  : '',
                                              ]
                                                .filter(Boolean)
                                                .join('\n\n'),
                                              renderTableListCell(card.matching_points || []),
                                              renderTableListCell(card.caution_points || []),
                                            ])}
                                          />

                                          {report.university_recommendations?.accepted_case_hints &&
                                            report.university_recommendations.accepted_case_hints.length > 0 && (
                                              <div className="space-y-3">
                                                <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                                                  합격 사례 유사도
                                                </p>
                                                <DeepResearchTable
                                                  columns={['사례', '유사도/설명']}
                                                  rows={report.university_recommendations.accepted_case_hints.map(
                                                    (hint, hintIdx) => [
                                                      hint.label || `유사 사례 ${hintIdx + 1}`,
                                                      `${hint.similarity_score ? `유사도 ${hint.similarity_score}\n\n` : ''}${
                                                        hint.match_reason || '-'
                                                      }`,
                                                    ]
                                                  )}
                                                />
                                              </div>
                                            )}
                                        </div>
                                      </section>
                                    )}

                                    {nonComparisonSections.map((section, sectionIdx) => {
                                      const sectionDescription = buildSectionDescription(section)
                                      const sectionEvidenceIds = getSectionEvidenceIds(section)
                                      const displayNumber = sectionIdx + prefaceSectionCount + 1
                                      const sectionTableRows = buildSectionTableRows(section)
                                      const evidenceEntries = getEvidenceEntries(report, sectionEvidenceIds)

                                      return (
                                        <section
                                          key={section.section_id}
                                          id={section.section_id}
                                          className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14"
                                        >
                                          <div className="w-full">
                                            <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
                                              {displayNumber.toString().padStart(2, '0')}
                                            </p>
                                            <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
                                              {section.title}
                                            </h3>
                                          </div>

                                          <div className="mt-8 w-full space-y-8">
                                            {sectionDescription && (
                                              <div className="space-y-4">
                                                {splitIntoReadableParagraphs(sectionDescription).map(
                                                  (paragraph, paragraphIdx) => (
                                                    <React.Fragment
                                                      key={`${section.section_id}-paragraph-${paragraphIdx}`}
                                                    >
                                                      {renderEmphasizedParagraph(
                                                        paragraph,
                                                        'whitespace-pre-wrap break-words text-[16px] leading-[1.9] text-[#374151]'
                                                      )}
                                                    </React.Fragment>
                                                  )
                                                )}
                                              </div>
                                            )}

                                            {sectionTableRows.length > 0 && (
                                              <div className="space-y-3">
                                                <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                                                  생기부 구조표
                                                </p>
                                                <DeepResearchTable
                                                  columns={['평가 기준', '생기부 해석']}
                                                  rows={sectionTableRows}
                                                />
                                              </div>
                                            )}

                                            {evidenceEntries.length > 0 && (
                                              <div className="space-y-3">
                                                <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                                                  근거 자료
                                                </p>
                                                <div className="space-y-3">
                                                  {evidenceEntries.map(({ evidenceId, evidence }, evidenceIdx) => {
                                                    const sourceLabel =
                                                      evidence.source_title ||
                                                      evidence.chunk_title ||
                                                      evidence.label ||
                                                      `출처 ${evidenceIdx + 1}`
                                                    const visibleExcerpt = getEvidenceExcerptForRender(evidence)
                                                    const isExcerptPending = isEvidenceExcerptPending(evidence)

                                                    return (
                                                      <EvidenceDisclosure
                                                        key={evidenceId}
                                                        sourceLabel={`문서 ${sourceLabel}`}
                                                        visibleExcerpt={visibleExcerpt}
                                                        isExcerptPending={isExcerptPending}
                                                        whyUsed={evidence.why_used}
                                                      />
                                                    )
                                                  })}
                                                </div>
                                              </div>
                                            )}
                                          </div>
                                        </section>
                                      )
                                    })}

                                    {comparisonSections.map((section, comparisonSectionIdx) => {
                                      const baseIndex =
                                        nonComparisonSections.length +
                                        comparisonSectionIdx +
                                        prefaceSectionCount +
                                        1
                                      const isTopAcceptedComparisonSection =
                                        section.title.trim() === '유사 합격자 비교'
                                      const comparisonSectionTitle = isTopAcceptedComparisonSection
                                        ? '실제 최고 수준의 합격자 생기부 분석'
                                        : section.title

                                      return (
                                        <section
                                          key={section.section_id}
                                          id={section.section_id}
                                          className="scroll-mt-24 border-t border-[#e5e7eb] py-10 md:py-14"
                                        >
                                          <div className="w-full">
                                            <p className="text-[11px] uppercase tracking-[0.28em] text-[#9ca3af]">
                                              {baseIndex.toString().padStart(2, '0')}
                                            </p>
                                            <h3 className="mt-3 text-[26px] font-semibold tracking-tight text-[#111827]">
                                              {comparisonSectionTitle}
                                            </h3>
                                          </div>

                                          <div className="mt-8 w-full space-y-8">
                                            {section.comparison_focus && !isTopAcceptedComparisonSection && (
                                              <div className="space-y-2">
                                                <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                                                  비교 관점
                                                </p>
                                                {renderEmphasizedParagraph(
                                                  section.comparison_focus,
                                                  'whitespace-pre-wrap break-words text-[15px] leading-[1.85] text-[#374151]'
                                                )}
                                              </div>
                                            )}

                                            {(section.comparison_cards || []).map((card, cardIdx) => (
                                              <div
                                                key={card.card_id}
                                                className="space-y-6 border-t border-[#e5e7eb] pt-8 first:border-t-0 first:pt-0"
                                              >
                                                  <div>
                                                    <p className="text-[11px] uppercase tracking-[0.24em] text-[#9ca3af]">
                                                      Case {(cardIdx + 1).toString().padStart(2, '0')}
                                                    </p>
                                                    <h4 className="mt-3 text-[20px] font-semibold text-[#111827]">
                                                      {card.label}
                                                    </h4>
                                                    {card.match_reason && (
                                                      <p className="mt-3 whitespace-pre-wrap break-words text-[15px] leading-[1.8] text-[#4b5563]">
                                                        {card.match_reason}
                                                      </p>
                                                    )}
                                                  </div>

                                                  {card.comparison_axis && (
                                                    <div className="space-y-2">
                                                      <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                                                        세부 비교 관점
                                                      </p>
                                                      {renderEmphasizedParagraph(
                                                        card.comparison_axis,
                                                        'whitespace-pre-wrap break-words text-[14px] leading-[1.8] text-[#374151]'
                                                      )}
                                                    </div>
                                                  )}

                                                  {(card.excerpt_pairs || []).map((pair, pairIdx) => (
                                                    <div
                                                      key={pair.pair_id || `${card.card_id}-pair-${pairIdx}`}
                                                      className="space-y-3"
                                                    >
                                                      <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                                                        원문 비교 {(pairIdx + 1).toString().padStart(2, '0')}
                                                      </p>
                                                      <div className="border-y border-[#e5e7eb] bg-white">
                                                        <div className="overflow-x-auto">
                                                          <table className="min-w-full border-collapse">
                                                            <thead className="bg-[#f7f7f8]">
                                                              <tr>
                                                                <th className="border-b border-[#e5e7eb] px-5 py-4 text-left text-[12px] font-semibold tracking-[0.16em] text-[#6b7280]">
                                                                  {pair.user_excerpt_label || '내 생기부 원문'}
                                                                </th>
                                                                <th className="border-b border-[#e5e7eb] px-5 py-4 text-left text-[12px] font-semibold tracking-[0.16em] text-[#6b7280]">
                                                                  {pair.accepted_excerpt_label || '합격자 생기부 원문'}
                                                                </th>
                                                              </tr>
                                                            </thead>
                                                            <tbody>
                                                              <tr className="align-top">
                                                                <td className="border-t border-[#eef0f3] px-5 py-4 text-[14px] leading-7 text-[#374151]">
                                                                  {pair.user_excerpt
                                                                    ? renderStructuredCellText(pair.user_excerpt)
                                                                    : '-'}
                                                                </td>
                                                                <td className="border-t border-[#eef0f3] px-5 py-4 text-[14px] leading-7 text-[#374151]">
                                                                  {pair.accepted_excerpt
                                                                    ? renderStructuredCellText(pair.accepted_excerpt)
                                                                    : '-'}
                                                                </td>
                                                              </tr>
                                                            </tbody>
                                                          </table>
                                                        </div>
                                                        <div className="border-t border-[#e5e7eb] bg-[#fafafa] px-5 py-4">
                                                          <p className="text-[12px] font-semibold tracking-[0.14em] text-[#6b7280]">
                                                            해설
                                                          </p>
                                                          {pair.pair_comment ? (
                                                            <div className="mt-3 space-y-3">
                                                              {splitIntoReadableParagraphs(pair.pair_comment).map(
                                                                (paragraph, paragraphIdx) => (
                                                                  <React.Fragment
                                                                    key={`${pair.pair_id || card.card_id}-comment-${paragraphIdx}`}
                                                                  >
                                                                    {renderEmphasizedParagraph(
                                                                      paragraph,
                                                                      'whitespace-pre-wrap break-words text-[15px] leading-[1.85] text-[#111827]'
                                                                    )}
                                                                  </React.Fragment>
                                                                )
                                                              )}
                                                            </div>
                                                          ) : (
                                                            <p className="mt-3 text-[14px] leading-7 text-[#9ca3af]">
                                                              볼드 처리 이유에 대한 해설이 제공되지 않았습니다.
                                                            </p>
                                                          )}
                                                        </div>
                                                      </div>
                                                    </div>
                                                  ))}

                                                  <DeepResearchTable
                                                    columns={['강점', '보완이 필요한 점', '다음 행동']}
                                                    rows={[
                                                      [
                                                        renderTableListCell(getComparisonSummaryItems(card, 'good')),
                                                        renderTableListCell(getComparisonSummaryItems(card, 'gap')),
                                                        renderTableListCell(
                                                          getComparisonSummaryItems(card, 'action'),
                                                          true
                                                        ),
                                                      ],
                                                    ]}
                                                  />
                                              </div>
                                            ))}
                                          </div>
                                        </section>
                                      )
                                    })}
                                  </div>
                            )
                          })()
                        ) : (
                          <div className="whitespace-pre-wrap break-words">
                            {msg.content}
                          </div>
                        )}
                      </div>
                      {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                        <button
                          onClick={() => {
                            setSelectedMsgIndex(idx)
                            setSidePanelTab('analysis')
                            setIsSidePanelOpen(true)
                            setExpandedChunks(new Set())
                          }}
                          className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-[11px] font-semibold transition ${
                            selectedMsgIndex === idx
                              ? 'bg-indigo-100 text-indigo-700'
                              : 'bg-[#F2F4F6] text-[#6B7684] hover:bg-indigo-50 hover:text-indigo-600'
                          }`}
                        >
                          <BookOpen className="h-3 w-3" />
                          참고자료 {msg.sources.length}건
                        </button>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>
        </div>

        {/* 에러 */}
        {error && (
          <div className="shrink-0 border-t border-red-200 bg-red-50 px-4 py-2">
            <p className="mx-auto max-w-[1440px] text-xs font-medium text-red-600">
              {error}
            </p>
          </div>
        )}

        {/* 입력 */}
        <div className="shrink-0 border-t border-[#E5E8EB] bg-white px-4 py-3 pb-safe">
          <div className="mx-auto flex max-w-[1440px] items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="생기부에 대해 궁금한 점을 물어보세요..."
              rows={1}
              disabled={isBusy}
              className="flex-1 resize-none rounded-2xl border border-[#D1D6DB] bg-[#F9FAFB] px-4 py-3 text-sm text-[#191F28] placeholder-[#ADB5BD] outline-none transition focus:border-[#3182F6] focus:ring-2 focus:ring-[#3182F6]/20 disabled:opacity-50"
              style={{ maxHeight: '120px' }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement
                target.style.height = 'auto'
                target.style.height = Math.min(target.scrollHeight, 120) + 'px'
              }}
            />
            <button
              onClick={() => sendMessage(input)}
              disabled={!input.trim() || isBusy}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#3182F6] text-white transition hover:bg-[#1f6fe2] disabled:bg-[#ADB5BD] disabled:cursor-not-allowed"
            >
              {isBusy ? (
                <Loader2 className="h-5 w-5 animate-spin" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </button>
          </div>
          <p className="mx-auto mt-1.5 max-w-3xl text-center text-[10px] text-[#ADB5BD]">
            AI가 생성한 분석은 참고용이며, 실제 입시 결과와 다를 수 있습니다.
          </p>
        </div>
      </div>

      {/* 오른쪽: 사이드 패널 (탭: 답변 분석 / 참고자료) */}
      {isSidePanelOpen && (
        <div className="w-[400px] shrink-0 border-l border-[#E5E8EB] bg-white flex flex-col h-screen">
          {/* 패널 헤더 + 탭 */}
          <div className="shrink-0 border-b border-[#E5E8EB]">
            <div className="px-4 pt-3 pb-0 flex items-center justify-between">
              <div className="flex gap-1">
                <button
                  onClick={() => setSidePanelTab('analysis')}
                  className={`px-3 py-2 text-xs font-bold rounded-t-lg transition ${
                    sidePanelTab === 'analysis'
                      ? 'text-indigo-600 bg-indigo-50 border border-b-0 border-indigo-200'
                      : 'text-[#8B95A1] hover:text-[#4E5968] hover:bg-gray-50'
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" />
                    답변 분석
                    {(() => {
                      const count = messages.filter(
                        (m) => m.role === 'assistant' && m.sources && m.sources.length > 0
                      ).length
                      return count > 0 ? (
                        <span className="ml-0.5 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-indigo-500 px-1 text-[10px] font-bold text-white">
                          {count}
                        </span>
                      ) : null
                    })()}
                  </span>
                </button>
                <button
                  onClick={() => setSidePanelTab('upload')}
                  className={`px-3 py-2 text-xs font-bold rounded-t-lg transition ${
                    sidePanelTab === 'upload'
                      ? 'text-[#3182F6] bg-blue-50 border border-b-0 border-blue-200'
                      : 'text-[#8B95A1] hover:text-[#4E5968] hover:bg-gray-50'
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <Upload className="h-3.5 w-3.5" />
                    참고자료
                  </span>
                </button>
              </div>
              <button
                onClick={() => setIsSidePanelOpen(false)}
                className="flex h-7 w-7 items-center justify-center rounded-md text-[#8B95A1] hover:bg-gray-100 transition"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* ── 답변 분석 탭 ── */}
          {sidePanelTab === 'analysis' && (
            <>
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
                {(() => {
                  const assistantMsgs = messages
                    .map((m, i) => ({ msg: m, idx: i }))
                    .filter(
                      (x) =>
                        x.msg.role === 'assistant' &&
                        x.msg.sources &&
                        x.msg.sources.length > 0
                    )

                  if (assistantMsgs.length === 0) {
                    return (
                      <div className="py-12 text-center">
                        <BookOpen className="h-10 w-10 text-[#D1D6DB] mx-auto mb-3" />
                        <p className="text-sm font-semibold text-[#8B95A1]">
                          아직 분석 데이터가 없습니다
                        </p>
                        <p className="mt-1 text-xs text-[#ADB5BD]">
                          질문을 보내면 답변에 사용된 참고자료 청크가
                          <br />
                          여기에 표시됩니다.
                        </p>
                      </div>
                    )
                  }

                  const selectedSources =
                    selectedMsgIndex !== null
                      ? messages[selectedMsgIndex]?.sources || []
                      : []

                  return (
                    <>
                      {assistantMsgs.length > 1 && (
                        <div>
                          <p className="text-[11px] font-bold text-[#8B95A1] mb-2 uppercase tracking-wider">
                            답변 선택
                          </p>
                          <div className="flex gap-1.5 overflow-x-auto pb-1">
                            {assistantMsgs.map(({ msg, idx }, chipIdx) => (
                              <button
                                key={idx}
                                onClick={() => {
                                  setSelectedMsgIndex(idx)
                                  setExpandedChunks(new Set())
                                }}
                                className={`shrink-0 rounded-lg px-3 py-1.5 text-[11px] font-semibold transition border ${
                                  selectedMsgIndex === idx
                                    ? 'bg-indigo-50 text-indigo-700 border-indigo-200'
                                    : 'bg-[#F9FAFB] text-[#6B7684] border-[#EEF0F3] hover:bg-gray-100'
                                }`}
                              >
                                #{chipIdx + 1} ({msg.sources?.length}건)
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {selectedMsgIndex !== null && selectedMsgIndex > 0 && (
                        <div className="rounded-xl bg-[#F2F4F6] px-3 py-2.5">
                          <p className="text-[10px] font-bold text-[#8B95A1] mb-1">질문</p>
                          <p className="text-xs text-[#4E5968] line-clamp-3">
                            {messages[selectedMsgIndex - 1]?.content || ''}
                          </p>
                        </div>
                      )}

                      {selectedSources.length > 0 && (
                        <div className="space-y-3">
                          <p className="text-[11px] font-bold text-[#8B95A1] uppercase tracking-wider">
                            사용된 청크 ({selectedSources.length}건)
                          </p>
                          {selectedSources.map((src, chunkIdx) => {
                            const isExpanded = expandedChunks.has(chunkIdx)
                            const content = src.raw_content || ''
                            const summary = src.chunk_summary || ''
                            const documentSummary = src.document_summary || ''
                            const sourcePath = getSourcePath(src)
                            const isLong = content.length > 200

                            return (
                              <div
                                key={chunkIdx}
                                className="rounded-xl border border-[#EEF0F3] bg-[#FAFBFC] overflow-hidden"
                              >
                                <div className="px-3 py-2.5 border-b border-[#EEF0F3] bg-white">
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0 flex-1">
                                      <p className="text-xs font-bold text-[#191F28] truncate">
                                        {src.chunk_title || src.source_title}
                                      </p>
                                      <p className="text-[11px] font-medium text-[#4E5968] mt-0.5 truncate">
                                        {src.source_title}
                                      </p>
                                      {sourcePath && (
                                        <p className="text-[11px] text-[#6B7684] mt-0.5 truncate">
                                          {sourcePath}
                                        </p>
                                      )}
                                    </div>
                                    <div className="shrink-0 flex items-center gap-1.5">
                                      {src.chunk_role && (
                                        <span className="inline-flex items-center rounded-md bg-indigo-50 px-1.5 py-0.5 text-[10px] font-bold text-indigo-600">
                                          {src.chunk_role}
                                        </span>
                                      )}
                                      <span className="text-[10px] text-[#ADB5BD]">
                                        #{src.chunk_index}
                                      </span>
                                      {typeof src.rerank_score === 'number' && (
                                        <span className="inline-flex items-center rounded-md bg-indigo-50 px-1.5 py-0.5 text-[10px] font-bold text-indigo-600">
                                          최종 {(src.rerank_score * 100).toFixed(0)}%
                                        </span>
                                      )}
                                      <span
                                        className={`inline-flex items-center rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
                                          src.similarity >= 0.8
                                            ? 'bg-green-50 text-green-600'
                                            : 'bg-gray-100 text-gray-500'
                                        }`}
                                      >
                                        벡터 {(src.similarity * 100).toFixed(0)}%
                                      </span>
                                    </div>
                                  </div>
                                </div>

                                {(summary || documentSummary || content) && (
                                  <div className="px-3 py-2.5">
                                    {summary && (
                                      <div className="rounded-lg bg-indigo-50 px-2.5 py-2">
                                        <p className="text-[10px] font-bold text-indigo-600">
                                          청크 요약
                                        </p>
                                        <p className="mt-1 text-[12px] leading-relaxed text-[#374151] whitespace-pre-wrap break-words">
                                          {summary}
                                        </p>
                                      </div>
                                    )}

                                    {documentSummary && (
                                      <div className="mt-2 rounded-lg bg-[#F5F7FA] px-2.5 py-2">
                                        <p className="text-[10px] font-bold text-[#6B7684]">
                                          문서 요약
                                        </p>
                                        <p className="mt-1 text-[11px] leading-relaxed text-[#4E5968] line-clamp-3">
                                          {documentSummary}
                                        </p>
                                      </div>
                                    )}

                                    {src.chunk_keywords && src.chunk_keywords.length > 0 && (
                                      <div className="mt-2 flex flex-wrap gap-1">
                                        {src.chunk_keywords.slice(0, 6).map((keyword) => (
                                          <span
                                            key={keyword}
                                            className="inline-flex items-center rounded-md bg-white px-1.5 py-0.5 text-[10px] font-medium text-[#6B7684] border border-[#E5E8EB]"
                                          >
                                            {keyword}
                                          </span>
                                        ))}
                                      </div>
                                    )}

                                    {content && (
                                      <>
                                        <p className="mt-3 text-[10px] font-bold text-[#8B95A1]">
                                          원문 발췌
                                        </p>
                                        <p
                                          className={`mt-1 text-[12px] leading-relaxed text-[#4E5968] whitespace-pre-wrap break-words ${
                                            !isExpanded && isLong ? 'line-clamp-5' : ''
                                          }`}
                                        >
                                          {content}
                                        </p>
                                        {isLong && (
                                          <button
                                            onClick={() => {
                                              setExpandedChunks((prev) => {
                                                const next = new Set(prev)
                                                if (next.has(chunkIdx)) {
                                                  next.delete(chunkIdx)
                                                } else {
                                                  next.add(chunkIdx)
                                                }
                                                return next
                                              })
                                            }}
                                            className="mt-2 text-[11px] font-semibold text-indigo-500 hover:text-indigo-700 transition"
                                          >
                                            {isExpanded ? '접기' : '전체 보기'}
                                          </button>
                                        )}
                                      </>
                                    )}
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </>
                  )
                })()}
              </div>

              <div className="shrink-0 border-t border-[#EEF0F3] px-4 py-3">
                <p className="text-[10px] text-[#ADB5BD] text-center leading-relaxed">
                  `최종`은 재랭킹 점수, `벡터`는 임베딩 유사도입니다.
                </p>
              </div>
            </>
          )}

          {/* ── 참고자료 업로드 탭 ── */}
          {sidePanelTab === 'upload' && (
            <>
              <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5">
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-bold text-[#4E5968] mb-1.5">
                      자료 제목
                    </label>
                    <input
                      type="text"
                      value={uploadTitle}
                      onChange={(e) => setUploadTitle(e.target.value)}
                      placeholder="예: 2025 학종 가이드북"
                      className="w-full rounded-xl border border-[#D1D6DB] bg-[#F9FAFB] px-3 py-2.5 text-sm text-[#191F28] placeholder-[#ADB5BD] outline-none focus:border-[#3182F6] focus:ring-2 focus:ring-[#3182F6]/20"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-[#4E5968] mb-1.5">
                      파일 업로드 (권장)
                    </label>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".md,.txt,text/markdown,text/plain"
                      className="hidden"
                      onChange={handleSelectFile}
                    />
                    <div className="space-y-2">
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="w-full rounded-xl border border-dashed border-[#B8C1CC] bg-[#F9FAFB] px-3 py-3 text-xs font-semibold text-[#4E5968] hover:border-[#3182F6] hover:text-[#3182F6] transition"
                      >
                        .md / .txt 파일 선택
                      </button>
                      {uploadFile && (
                        <div className="rounded-xl border border-[#DDE4EA] bg-[#F5F8FC] px-3 py-2">
                          <div className="flex items-center justify-between gap-2">
                            <div className="min-w-0">
                              <p className="truncate text-xs font-semibold text-[#191F28]">
                                {uploadFile.name}
                              </p>
                              <p className="text-[10px] text-[#8B95A1]">
                                {(uploadFile.size / 1024).toLocaleString(undefined, {
                                  maximumFractionDigits: 1,
                                })} KB
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={clearSelectedFile}
                              className="shrink-0 rounded-md p-1 text-[#8B95A1] hover:bg-white hover:text-[#4E5968] transition"
                              title="선택 해제"
                            >
                              <X className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-[#4E5968] mb-1.5">
                      텍스트 직접 입력 (선택)
                    </label>
                    <textarea
                      value={uploadText}
                      onChange={(e) => setUploadText(e.target.value)}
                      disabled={Boolean(uploadFile)}
                      placeholder="분석에 참고할 텍스트를 붙여넣으세요...&#10;&#10;Part, 장/절 등의 구조가 있으면 자동으로 분할됩니다."
                      rows={10}
                      className="w-full resize-none rounded-xl border border-[#D1D6DB] bg-[#F9FAFB] px-3 py-2.5 text-sm text-[#191F28] placeholder-[#ADB5BD] outline-none focus:border-[#3182F6] focus:ring-2 focus:ring-[#3182F6]/20 disabled:opacity-60"
                    />
                    {uploadFile ? (
                      <p className="mt-1 text-[11px] text-[#8B95A1]">
                        파일 업로드 모드에서는 직접 입력 텍스트를 사용하지 않습니다.
                      </p>
                    ) : uploadText ? (
                      <p className="mt-1 text-[11px] text-[#8B95A1]">
                        {uploadText.length.toLocaleString()}자 입력됨
                      </p>
                    ) : (
                      <p className="mt-1 text-[11px] text-[#8B95A1]">
                        대용량(예: 170,000자)은 파일 업로드를 권장합니다.
                      </p>
                    )}
                  </div>

                  <button
                    onClick={handleUpload}
                    disabled={isUploading || (!uploadFile && !uploadText.trim())}
                    className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#3182F6] px-4 py-3 text-sm font-bold text-white transition hover:bg-[#1f6fe2] disabled:bg-[#ADB5BD] disabled:cursor-not-allowed"
                  >
                    {isUploading ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        임베딩 및 업로드 중...
                      </>
                    ) : (
                      <>
                        <Upload className="h-4 w-4" />
                        업로드 및 임베딩
                      </>
                    )}
                  </button>

                  {uploadResult && (
                    <div
                      className={`flex items-start gap-2 rounded-xl px-3 py-2.5 text-xs font-medium ${
                        uploadResult.ok
                          ? 'bg-green-50 text-green-700'
                          : 'bg-red-50 text-red-600'
                      }`}
                    >
                      {uploadResult.ok ? (
                        <CheckCircle2 className="h-4 w-4 shrink-0 mt-0.5" />
                      ) : (
                        <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                      )}
                      <span>{uploadResult.message}</span>
                    </div>
                  )}
                </div>

                <div className="border-t border-[#EEF0F3]" />

                <div>
                  <h3 className="text-xs font-extrabold text-[#191F28] mb-2">
                    업로드된 자료
                  </h3>
                  {sourcesLoading ? (
                    <div className="flex items-center gap-2 py-4 justify-center text-[#8B95A1]">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span className="text-xs">불러오는 중...</span>
                    </div>
                  ) : sources.length === 0 ? (
                    <div className="py-6 text-center">
                      <FileText className="h-8 w-8 text-[#D1D6DB] mx-auto mb-2" />
                      <p className="text-xs text-[#8B95A1]">
                        아직 업로드된 자료가 없습니다
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {sources.map((src) => (
                        <div
                          key={src.source_title}
                          className="flex items-center justify-between rounded-xl border border-[#EEF0F3] bg-[#F9FAFB] px-3 py-2.5 group"
                        >
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold text-[#191F28] truncate">
                              {src.source_title}
                            </p>
                            <p className="text-[10px] text-[#8B95A1]">
                              {src.chunk_count}개 청크
                            </p>
                          </div>
                          <button
                            onClick={() => handleDeleteSource(src.source_title)}
                            className="shrink-0 ml-2 p-1.5 text-[#ADB5BD] hover:text-red-500 opacity-0 group-hover:opacity-100 transition rounded-lg hover:bg-red-50"
                            title="삭제"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              <div className="shrink-0 border-t border-[#EEF0F3] px-4 py-3">
                <p className="text-[10px] text-[#ADB5BD] text-center leading-relaxed">
                  텍스트는 Gemini text-embedding-004로 임베딩되어
                  <br />
                  RAG 기반 심층 분석에 활용됩니다.
                </p>
              </div>
            </>
          )}
        </div>
      )}
      <SchoolRecordPdfDownloadRunner
        active={visualReportDownloadActive}
        requestId={visualReportDownloadRequestId}
        token={accessToken}
        onPhaseChange={(phase) => setVisualReportDownloadPhase(phase)}
        onSuccess={() => {
          setVisualReportDownloadActive(false)
          setVisualReportDownloadPhase('idle')
        }}
        onError={() => {
          setVisualReportDownloadActive(false)
          setVisualReportDownloadPhase('idle')
        }}
      />
    </div>
  )
}

export default SchoolRecordDeepChatPage
