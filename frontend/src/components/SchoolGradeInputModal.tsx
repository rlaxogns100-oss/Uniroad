import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  ADIGA_CURRICULUM_CATALOG,
  ADIGA_SCHOOL_YEAR_OPTIONS,
  ADIGA_TRACK_OPTIONS,
  type AdigaTrackType,
} from '../data/adigaSchoolGradeCatalog'
import { useAuth } from '../contexts/AuthContext'
import { getApiBaseUrl } from '../config'
import { captureBusinessEvent } from '../utils/tracking'
import { TrackingEventNames } from '../utils/trackingSchema'

interface SchoolGradeInputModalProps {
  isOpen: boolean
  onClose: () => void
  embedded?: boolean
  autoOpenSavedGradeReport?: boolean
  onAutoOpenSavedGradeReportHandled?: () => void
  onRequireSchoolRecordLink?: () => void
  /** 정시/모의고사 성적 입력 모달을 열 때 호출 (메뉴에서 "정시 성적 입력" 선택 시) */
  onOpenMockExamInput?: () => void
  onUseNaesinSuggestion?: (mention: string) => void
}

type ModalStep = 'menu' | 'semester' | 'extracurricular' | 'record_upload'
type SemesterKey = '1-1' | '1-2' | '2-1' | '2-2' | '3-1' | '3-2'
type GradeKey = '1' | '2' | '3'
type GradeAverageFieldKey = 'overall' | 'core'
type QuickInputMode = 'overall' | 'semester'

interface SemesterRow {
  id: string
  trackType: string
  curriculum: string
  subject: string
  credits: string
  classRank: string
  rawScore: string
  avgScore: string
  stdDev: string
  studentCount: string
  achievement: string
  distA: string
  distB: string
  distC: string
}

interface ExtracurricularAttendanceRow {
  absence: string
  tardy: string
  earlyLeave: string
  result: string
}

interface ExtracurricularData {
  attendance: Record<GradeKey, ExtracurricularAttendanceRow>
  volunteerHours: Record<GradeKey, string>
}

interface GradeSummaryData {
  overallAverage: string
  coreAverage: string
  semesterAverages: Record<SemesterKey, Record<GradeAverageFieldKey, string>>
}

interface SchoolGradeInputData {
  semesters: Record<SemesterKey, SemesterRow[]>
  extracurricular: ExtracurricularData
  gradeSummary: GradeSummaryData
  /** 성적표(생기부 연동) 업로드 여부. false이면 평균만 입력 모드로, 석차등급·원점수만 편집 가능 */
  hasReportCardData: boolean
  recordUpload: {
    fileName: string
    summary: string
  }
}

const STORAGE_KEY = 'uniroad_school_grade_input_v3'

const semesterLabels: Record<SemesterKey, string> = {
  '1-1': '1학년 1학기',
  '1-2': '1학년 2학기',
  '2-1': '2학년 1학기',
  '2-2': '2학년 2학기',
  '3-1': '3학년 1학기',
  '3-2': '3학년 2학기',
}

const semesterSections: Array<{ title: string; semesters: SemesterKey[] }> = [
  { title: '1학년', semesters: ['1-1', '1-2'] },
  { title: '2학년', semesters: ['2-1', '2-2'] },
  { title: '3학년', semesters: ['3-1', '3-2'] },
]
const semesterKeys: SemesterKey[] = ['1-1', '1-2', '2-1', '2-2', '3-1', '3-2']
const gradeKeys: GradeKey[] = ['1', '2', '3']
const NAESIN_CHAT_MENTION_EXAMPLE = '@내신 성적으로 갈 수 있는 학교 알려줘'
const NAESIN_SCHOOL_RECOMMEND_MENTION = '@내신 성적 학교 추천'

const schoolYearOptions = [...ADIGA_SCHOOL_YEAR_OPTIONS]
const trackTypeOptions = [...ADIGA_TRACK_OPTIONS]
const achievementOptions = ['선택', 'A', 'B', 'C', 'D', 'E', 'P', '·']

const isTrackType = (value: string): value is AdigaTrackType =>
  trackTypeOptions.includes(value as AdigaTrackType)

const getCatalogByTrackType = (trackType: string) =>
  ADIGA_CURRICULUM_CATALOG[isTrackType(trackType) ? trackType : trackTypeOptions[0]]

const getCurriculumOptions = (trackType: string): string[] =>
  getCatalogByTrackType(trackType).map((item) => item.name)

const getSubjectOptions = (trackType: string, curriculum: string): string[] => {
  const curriculumItem = getCatalogByTrackType(trackType).find((item) => item.name === curriculum)
  return curriculumItem ? curriculumItem.subjects : []
}

const normalizeTrackType = (value: string): AdigaTrackType =>
  isTrackType(value) ? value : trackTypeOptions[0]

const normalizeCurriculum = (trackType: string, curriculum: string): string => {
  const options = getCurriculumOptions(trackType)
  if (options.length === 0) return ''
  return options.includes(curriculum) ? curriculum : options[0]
}

const normalizeSemesterRow = (row: SemesterRow): SemesterRow => {
  const nextTrackType = normalizeTrackType(row.trackType)
  const nextCurriculum = normalizeCurriculum(nextTrackType, row.curriculum)

  return {
    ...row,
    trackType: nextTrackType,
    curriculum: nextCurriculum,
    subject: row.subject,
  }
}

const createEmptyRow = (): SemesterRow => ({
  id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
  trackType: trackTypeOptions[0],
  curriculum: getCurriculumOptions(trackTypeOptions[0])[0] || '',
  subject: '',
  credits: '',
  classRank: '',
  rawScore: '',
  avgScore: '',
  stdDev: '',
  studentCount: '',
  achievement: '선택',
  distA: '',
  distB: '',
  distC: '',
})

const createEmptyExtracurricularData = (): ExtracurricularData => ({
  attendance: {
    '1': { absence: '', tardy: '', earlyLeave: '', result: '' },
    '2': { absence: '', tardy: '', earlyLeave: '', result: '' },
    '3': { absence: '', tardy: '', earlyLeave: '', result: '' },
  },
  volunteerHours: {
    '1': '',
    '2': '',
    '3': '',
  },
})

const createEmptyGradeSummaryData = (): GradeSummaryData => ({
  overallAverage: '',
  coreAverage: '',
  semesterAverages: {
    '1-1': { overall: '', core: '' },
    '1-2': { overall: '', core: '' },
    '2-1': { overall: '', core: '' },
    '2-2': { overall: '', core: '' },
    '3-1': { overall: '', core: '' },
    '3-2': { overall: '', core: '' },
  },
})

const sanitizeGradeNumberInput = (value: string): string => {
  let cleaned = value.replace(/[^\d.]/g, '')
  if (!cleaned) return ''
  const firstDotIndex = cleaned.indexOf('.')
  if (firstDotIndex >= 0) {
    cleaned = `${cleaned.slice(0, firstDotIndex + 1)}${cleaned.slice(firstDotIndex + 1).replace(/\./g, '')}`
  }
  if (cleaned.startsWith('.')) cleaned = `0${cleaned}`
  const [intPartRaw, decimalPartRaw] = cleaned.split('.')
  const intPart = intPartRaw.replace(/^0+(?=\d)/, '')
  if (decimalPartRaw === undefined) return intPart
  return `${intPart || '0'}.${decimalPartRaw.slice(0, 2)}`
}

const parseGradeNumber = (value: string): number | null => {
  const text = value.trim()
  if (!text) return null
  const parsed = Number.parseFloat(text)
  if (!Number.isFinite(parsed)) return null
  return parsed
}

const formatGradeForDisplay = (value: number): string =>
  Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/\.?0+$/, '')

/** 석차등급은 1~9 정수만 허용 (한 자리) */
const sanitizeClassRankInput = (value: string): string => {
  const digits = value.replace(/[^\d]/g, '')
  if (!digits) return ''
  const first = digits.slice(0, 1)
  const n = Number.parseInt(first, 10)
  if (n >= 1 && n <= 9) return String(n)
  return ''
}

/** 석차등급(1~9)에 따른 기본 원점수 (내신 등급별 대표값, 사용자가 수정 가능) */
const RAW_SCORE_BY_CLASS_RANK: Record<number, number> = {
  1: 96, 2: 92, 3: 88, 4: 84, 5: 80, 6: 76, 7: 72, 8: 68, 9: 64,
}

const getRawScoreByClassRank = (classRank: number): string => {
  if (classRank >= 1 && classRank <= 9) return String(RAW_SCORE_BY_CLASS_RANK[classRank] ?? '')
  return ''
}

const formatAveragedGrade = (values: string[]): string => {
  const numericValues = values
    .map((v) => parseGradeNumber(v))
    .filter((v): v is number => v !== null)
  if (numericValues.length === 0) return ''
  const average = numericValues.reduce((sum, v) => sum + v, 0) / numericValues.length
  return Number.isInteger(average) ? String(average) : average.toFixed(2).replace(/\.?0+$/, '')
}

const buildDefaultData = (): SchoolGradeInputData => ({
  semesters: {
    '1-1': [createEmptyRow()],
    '1-2': [createEmptyRow()],
    '2-1': [createEmptyRow()],
    '2-2': [createEmptyRow()],
    '3-1': [createEmptyRow()],
    '3-2': [createEmptyRow()],
  },
  extracurricular: createEmptyExtracurricularData(),
  gradeSummary: createEmptyGradeSummaryData(),
  hasReportCardData: false,
  recordUpload: {
    fileName: '',
    summary: '',
  },
})

const normalizeRows = (rows: unknown): SemesterRow[] => {
  if (!Array.isArray(rows)) return [createEmptyRow()]

  const normalized = rows
    .filter((row) => row && typeof row === 'object')
    .map((row) => {
      const r = row as Record<string, unknown>
      let classRank = String(r.classRank || '').trim()
      let rawScore = String(r.rawScore || '')
      const parsed = parseGradeNumber(classRank)
      if (parsed !== null) {
        const grade = Math.min(9, Math.max(1, Math.round(parsed)))
        classRank = String(grade)
        rawScore = getRawScoreByClassRank(grade) || rawScore
      }
      return normalizeSemesterRow({
        id: String(r.id || createEmptyRow().id),
        trackType: String(r.trackType || trackTypeOptions[0]),
        curriculum: String(r.curriculum || getCurriculumOptions(trackTypeOptions[0])[0] || ''),
        subject: String(r.subject || ''),
        credits: String(r.credits || ''),
        classRank,
        rawScore,
        avgScore: String(r.avgScore || ''),
        stdDev: String(r.stdDev || ''),
        studentCount: String(r.studentCount || ''),
        achievement: String(r.achievement || '선택'),
        distA: String(r.distA || ''),
        distB: String(r.distB || ''),
        distC: String(r.distC || ''),
      })
    })

  return normalized.length > 0 ? normalized : [createEmptyRow()]
}

const normalizeSchoolGradeInputData = (rawData: unknown): SchoolGradeInputData => {
  const fallback = buildDefaultData()
  if (!rawData || typeof rawData !== 'object') return fallback

  const parsedRecord = rawData as Record<string, unknown>
  const semestersRaw = parsedRecord.semesters
  const semesters =
    semestersRaw && typeof semestersRaw === 'object'
      ? (semestersRaw as Partial<Record<SemesterKey, unknown>>)
      : {}
  const extracurricularRaw = parsedRecord.extracurricular
  const gradeSummaryRaw = parsedRecord.gradeSummary
  const fallbackExtracurricular = createEmptyExtracurricularData()
  const fallbackGradeSummary = createEmptyGradeSummaryData()
  const extracurricularRecord =
    extracurricularRaw && typeof extracurricularRaw === 'object'
      ? (extracurricularRaw as Record<string, unknown>)
      : null
  const attendanceRecordRaw =
    extracurricularRecord?.attendance && typeof extracurricularRecord.attendance === 'object'
      ? (extracurricularRecord.attendance as Record<string, unknown>)
      : {}
  const volunteerHoursRecordRaw =
    extracurricularRecord?.volunteerHours && typeof extracurricularRecord.volunteerHours === 'object'
      ? (extracurricularRecord.volunteerHours as Record<string, unknown>)
      : {}
  const gradeSummaryRecord =
    gradeSummaryRaw && typeof gradeSummaryRaw === 'object'
      ? (gradeSummaryRaw as Record<string, unknown>)
      : null
  const semesterAveragesRaw =
    gradeSummaryRecord?.semesterAverages && typeof gradeSummaryRecord.semesterAverages === 'object'
      ? (gradeSummaryRecord.semesterAverages as Record<string, unknown>)
      : {}

  const readAttendanceField = (grade: GradeKey, field: keyof ExtracurricularAttendanceRow): string => {
    const gradeRecordRaw = attendanceRecordRaw[grade]
    if (!gradeRecordRaw || typeof gradeRecordRaw !== 'object') return ''
    return String((gradeRecordRaw as Record<string, unknown>)[field] || '')
  }

  const extracurricular =
    extracurricularRecord
      ? {
          attendance: {
            '1': {
              absence: readAttendanceField('1', 'absence'),
              tardy: readAttendanceField('1', 'tardy'),
              earlyLeave: readAttendanceField('1', 'earlyLeave'),
              result: readAttendanceField('1', 'result'),
            },
            '2': {
              absence: readAttendanceField('2', 'absence'),
              tardy: readAttendanceField('2', 'tardy'),
              earlyLeave: readAttendanceField('2', 'earlyLeave'),
              result: readAttendanceField('2', 'result'),
            },
            '3': {
              absence: readAttendanceField('3', 'absence'),
              tardy: readAttendanceField('3', 'tardy'),
              earlyLeave: readAttendanceField('3', 'earlyLeave'),
              result: readAttendanceField('3', 'result'),
            },
          },
          volunteerHours: {
            '1': String(volunteerHoursRecordRaw['1'] || ''),
            '2': String(volunteerHoursRecordRaw['2'] || ''),
            '3': String(volunteerHoursRecordRaw['3'] || ''),
          },
        }
      : fallbackExtracurricular

  const readSemesterAverageField = (semester: SemesterKey, field: GradeAverageFieldKey): string => {
    const semesterRecord = semesterAveragesRaw[semester]
    if (!semesterRecord || typeof semesterRecord !== 'object') return ''
    return String((semesterRecord as Record<string, unknown>)[field] || '')
  }
  const gradeSummary = gradeSummaryRecord
    ? {
        overallAverage: String(gradeSummaryRecord.overallAverage || ''),
        coreAverage: String(gradeSummaryRecord.coreAverage || ''),
        semesterAverages: {
          '1-1': { overall: readSemesterAverageField('1-1', 'overall'), core: readSemesterAverageField('1-1', 'core') },
          '1-2': { overall: readSemesterAverageField('1-2', 'overall'), core: readSemesterAverageField('1-2', 'core') },
          '2-1': { overall: readSemesterAverageField('2-1', 'overall'), core: readSemesterAverageField('2-1', 'core') },
          '2-2': { overall: readSemesterAverageField('2-2', 'overall'), core: readSemesterAverageField('2-2', 'core') },
          '3-1': { overall: readSemesterAverageField('3-1', 'overall'), core: readSemesterAverageField('3-1', 'core') },
          '3-2': { overall: readSemesterAverageField('3-2', 'overall'), core: readSemesterAverageField('3-2', 'core') },
        },
      }
    : fallbackGradeSummary

  const hasReportCardData =
    parsedRecord.hasReportCardData === true

  return {
    semesters: {
      '1-1': normalizeRows(semesters['1-1']),
      '1-2': normalizeRows(semesters['1-2']),
      '2-1': normalizeRows(semesters['2-1']),
      '2-2': normalizeRows(semesters['2-2']),
      '3-1': normalizeRows(semesters['3-1']),
      '3-2': normalizeRows(semesters['3-2']),
    },
    extracurricular,
    gradeSummary,
    hasReportCardData: Boolean(hasReportCardData),
    recordUpload: {
      fileName: String(
        parsedRecord.recordUpload && typeof parsedRecord.recordUpload === 'object'
          ? ((parsedRecord.recordUpload as Record<string, unknown>).fileName || '')
          : ''
      ),
      summary: String(
        parsedRecord.recordUpload && typeof parsedRecord.recordUpload === 'object'
          ? ((parsedRecord.recordUpload as Record<string, unknown>).summary || '')
          : ''
      ),
    },
  }
}

const loadSavedData = (): SchoolGradeInputData => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return buildDefaultData()
    const parsedUnknown = JSON.parse(raw)
    return normalizeSchoolGradeInputData(parsedUnknown)
  } catch {
    return buildDefaultData()
  }
}

const hasSavedNaesinData = (value: SchoolGradeInputData): boolean => {
  const hasSemesterAverage = semesterKeys.some(
    (semesterKey) => parseGradeNumber(value.gradeSummary.semesterAverages[semesterKey].overall) !== null
  )
  if (hasSemesterAverage) return true
  return semesterKeys.some((semesterKey) => (value.semesters[semesterKey] || []).some(isMeaningfulSemesterRow))
}

type ParsedAcademicRow = Record<string, unknown>
type ParsedAcademicTableKey = 'general_elective' | 'career_elective' | 'pe_arts'

const parsedTableTrackTypeMap: Record<ParsedAcademicTableKey, AdigaTrackType> = {
  general_elective: '일반선택',
  career_elective: '진로선택',
  pe_arts: '일반선택',
}

const emptySemesterRows = (): Record<SemesterKey, SemesterRow[]> => ({
  '1-1': [],
  '1-2': [],
  '2-1': [],
  '2-2': [],
  '3-1': [],
  '3-2': [],
})

const sanitizeCellValue = (value: unknown): string => {
  const text = String(value ?? '').trim()
  if (!text || text === '-' || text.toLowerCase() === 'null' || text.toLowerCase() === 'none') return ''
  return text
}

const sanitizeNumberInput = (value: string): string =>
  value.replace(/[^\d]/g, '')

const isMeaningfulSemesterRow = (row: SemesterRow): boolean => {
  if (row.subject.trim()) return true
  if (row.credits.trim()) return true
  if (row.classRank.trim()) return true
  if (row.rawScore.trim()) return true
  if (row.avgScore.trim()) return true
  if (row.stdDev.trim()) return true
  if (row.studentCount.trim()) return true
  if (row.distA.trim()) return true
  if (row.distB.trim()) return true
  if (row.distC.trim()) return true
  if (row.achievement && row.achievement !== '선택') return true
  return false
}

const toNonNegativeInt = (value: string): number => {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0
}

const toNonNegativeNumber = (value: unknown): number => {
  if (typeof value === 'number') {
    return Number.isFinite(value) && value > 0 ? value : 0
  }
  const parsed = Number.parseFloat(String(value ?? '').replace(/[^0-9.]/g, ''))
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0
}

const valueFromNumberOrBlank = (value: unknown): string => {
  if (typeof value === 'number') return value > 0 ? String(Math.trunc(value)) : ''
  const text = sanitizeCellValue(value)
  const num = Number.parseInt(text, 10)
  return Number.isFinite(num) && num > 0 ? String(num) : ''
}

const normalizeMatchText = (value: string): string =>
  value
    .toLowerCase()
    .replace(/\s+/g, '')
    .replace(/[·ㆍ・‧•]/g, '')
    .replace(/[()]/g, '')
    .replace(/[\/-]/g, '')

const parseSemesterTerm = (value: unknown): '1' | '2' | null => {
  const text = sanitizeCellValue(value)
  if (!text) return null

  const compact = text.replace(/\s+/g, '')
  if (compact.includes('1학기')) return '1'
  if (compact.includes('2학기')) return '2'

  // 예: 11/12/21/22/31/32 처럼 들어오면 마지막 자리를 학기로 해석
  const digits = compact.match(/[12]/g)
  if (!digits || digits.length === 0) return null
  const last = digits[digits.length - 1]
  return last === '1' || last === '2' ? last : null
}

const parseGradeAndSemester = (
  value: unknown,
  fallbackGrade: '1' | '2' | '3'
): { grade: '1' | '2' | '3'; term: '1' | '2' | null } => {
  const text = sanitizeCellValue(value)
  if (!text) return { grade: fallbackGrade, term: null }

  const compact = text.replace(/\s+/g, '')
  let grade: '1' | '2' | '3' = fallbackGrade

  if (compact.includes('1학년')) grade = '1'
  else if (compact.includes('2학년')) grade = '2'
  else if (compact.includes('3학년')) grade = '3'

  return { grade, term: parseSemesterTerm(compact) }
}

const parseGradeKey = (value: unknown): GradeKey | null => {
  const text = sanitizeCellValue(value).replace(/\s+/g, '')
  if (!text) return null
  if (text === '1' || text.startsWith('1학년') || text.startsWith('제1학년')) return '1'
  if (text === '2' || text.startsWith('2학년') || text.startsWith('제2학년')) return '2'
  if (text === '3' || text.startsWith('3학년') || text.startsWith('제3학년')) return '3'

  const gradeMatch = text.match(/([123])학년/)
  if (gradeMatch) return gradeMatch[1] as GradeKey

  return null
}

const normalizeLooseKey = (value: string): string =>
  value
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '')

const hasMeaningfulCellValue = (value: unknown): boolean => {
  if (value === null || value === undefined) return false
  return String(value).trim().length > 0
}

const readRowValueByCandidates = (
  rowRecord: Record<string, unknown>,
  candidateKeys: string[]
): unknown => {
  for (const key of candidateKeys) {
    if (Object.prototype.hasOwnProperty.call(rowRecord, key)) {
      const directValue = rowRecord[key]
      if (hasMeaningfulCellValue(directValue)) return directValue
    }
  }

  const normalizedRow = new Map<string, unknown>()
  for (const [rawKey, rawValue] of Object.entries(rowRecord)) {
    const normalizedKey = normalizeLooseKey(rawKey)
    if (!normalizedKey) continue
    if (!normalizedRow.has(normalizedKey)) {
      normalizedRow.set(normalizedKey, rawValue)
      continue
    }
    if (hasMeaningfulCellValue(rawValue) && !hasMeaningfulCellValue(normalizedRow.get(normalizedKey))) {
      normalizedRow.set(normalizedKey, rawValue)
    }
  }

  for (const key of candidateKeys) {
    const normalizedKey = normalizeLooseKey(key)
    if (!normalizedKey) continue
    const value = normalizedRow.get(normalizedKey)
    if (hasMeaningfulCellValue(value)) return value
  }

  return undefined
}

const parseAttendanceTripletAt = (value: unknown, index: number): number | null => {
  const text = sanitizeCellValue(value)
  if (!text) return null
  const numbers = text.match(/\d+/g)?.map((token) => Number.parseInt(token, 10)) || []
  if (numbers.length < 3 || index < 0 || index >= numbers.length) return null
  const picked = numbers[index]
  return Number.isFinite(picked) && picked >= 0 ? picked : null
}

type AttendanceLabel = '결석' | '지각' | '조퇴' | '결과'

const getAttendanceUnexcusedValue = (
  rowRecord: Record<string, unknown>,
  label: AttendanceLabel,
  legacyUnexcusedKey: string
): string => {
  const englishLabelMap: Record<AttendanceLabel, string> = {
    결석: 'absence',
    지각: 'tardy',
    조퇴: 'earlyleave',
    결과: 'result',
  }

  const english = englishLabelMap[label]
  const unexcusedRaw = readRowValueByCandidates(rowRecord, [
    `${label}_미인정`,
    `${label}_무단`,
    `${label}미인정`,
    `${label}무단`,
    `${label}일수_미인정`,
    `${label}일수_무단`,
    `${label}일수미인정`,
    `${label}일수무단`,
    `미인정_${label}`,
    `무단_${label}`,
    `미인정${label}`,
    `무단${label}`,
    legacyUnexcusedKey,
    `무단(미인정)${label}`,
    `무단(미인정)${label}일수`,
    `${english}_unexcused`,
    `${english}Unexcused`,
    `unexcused_${english}`,
    `unexcused${english}`,
    `${english}_unauthorized`,
  ])

  let unexcused = toNonNegativeNumber(unexcusedRaw)
  if (unexcused === 0) {
    const packedRaw = readRowValueByCandidates(rowRecord, [
      label,
      `${label}일수`,
      english,
      `${english}_counts`,
    ])
    const middle = parseAttendanceTripletAt(packedRaw, 1)
    if (middle !== null) {
      unexcused = middle
    }
  }

  return String(Math.trunc(unexcused))
}

const propagateMissingSemesterTerms = <T extends { term: '1' | '2' | null }>(
  rows: T[]
): Array<T & { resolvedTerm: '1' | '2' | null }> => {
  const withForwardFill = rows.map((row) => ({ ...row, resolvedTerm: row.term }))

  let currentTerm: '1' | '2' | null = null
  for (const row of withForwardFill) {
    if (row.resolvedTerm) {
      currentTerm = row.resolvedTerm
      continue
    }
    if (currentTerm) {
      row.resolvedTerm = currentTerm
    }
  }

  const firstKnownTerm = withForwardFill.find((row) => row.resolvedTerm)?.resolvedTerm || null
  if (firstKnownTerm) {
    for (const row of withForwardFill) {
      if (row.resolvedTerm) break
      row.resolvedTerm = firstKnownTerm
    }
  }

  return withForwardFill
}

const buildSemesterRecoveryKey = (curriculum: string, subject: string): string => {
  const subjectKey = normalizeMatchText(subject)
  if (subjectKey) return `s:${subjectKey}`
  const curriculumKey = normalizeMatchText(curriculum)
  if (curriculumKey) return `c:${curriculumKey}`
  return ''
}

const recoverMisparsedSemesterTerms = <
  T extends {
    term: '1' | '2' | null
    resolvedTerm: '1' | '2' | null
    curriculum: string
    subject: string
  }
>(
  rows: T[]
): T[] => {
  const recovered = rows.map((row) => ({ ...row }))
  if (recovered.length < 8) return recovered

  const firstExplicitTwoIndex = recovered.findIndex((row) => row.term === '2')
  const seenKeyIndex = new Map<string, number>()
  let boundaryIndex = -1
  let duplicateCountBeforeTwo = 0

  for (let index = 0; index < recovered.length; index += 1) {
    const row = recovered[index]
    const key = buildSemesterRecoveryKey(row.curriculum, row.subject)
    if (!key) continue

    const firstIndex = seenKeyIndex.get(key)
    if (firstIndex === undefined) {
      seenKeyIndex.set(key, index)
      continue
    }

    if (firstExplicitTwoIndex === -1 || index < firstExplicitTwoIndex) {
      duplicateCountBeforeTwo += 1
      if (boundaryIndex === -1 || index < boundaryIndex) {
        boundaryIndex = index
      }
    }
  }

  const shouldRecover =
    boundaryIndex >= 4 &&
    duplicateCountBeforeTwo >= 3 &&
    (firstExplicitTwoIndex === -1 || boundaryIndex < firstExplicitTwoIndex)

  if (!shouldRecover) return recovered

  const endExclusive = firstExplicitTwoIndex === -1 ? recovered.length : firstExplicitTwoIndex
  for (let index = boundaryIndex; index < endExclusive; index += 1) {
    recovered[index].resolvedTerm = '2'
  }
  for (let index = 0; index < boundaryIndex; index += 1) {
    if (!recovered[index].resolvedTerm) {
      recovered[index].resolvedTerm = '1'
    }
  }

  return recovered
}

const resolveCurriculumFromParsed = (
  trackType: AdigaTrackType,
  rawCurriculum: string,
  rawSubject: string
): string => {
  const catalog = getCatalogByTrackType(trackType)
  const options = catalog.map((item) => item.name)
  if (options.length === 0) return ''

  if (options.includes(rawCurriculum)) return rawCurriculum

  const rawCurriculumNorm = normalizeMatchText(rawCurriculum)
  if (rawCurriculumNorm) {
    const normalizedMatch = options.find((option) => normalizeMatchText(option) === rawCurriculumNorm)
    if (normalizedMatch) return normalizedMatch
  }

  const rawSubjectNorm = normalizeMatchText(rawSubject)
  if (rawSubjectNorm) {
    const bySubject = catalog.find((item) =>
      item.subjects.some((subject) => normalizeMatchText(subject) === rawSubjectNorm)
    )
    if (bySubject) return bySubject.name
  }

  if (rawCurriculumNorm) {
    const partialMatch = options.find((option) => {
      const optionNorm = normalizeMatchText(option)
      return rawCurriculumNorm.includes(optionNorm) || optionNorm.includes(rawCurriculumNorm)
    })
    if (partialMatch) return partialMatch
  }

  if (rawCurriculum.includes('체육')) {
    const pe = options.find((option) => option.includes('체육'))
    if (pe) return pe
  }
  if (rawCurriculum.includes('예술') || rawCurriculum.includes('음악') || rawCurriculum.includes('미술')) {
    const arts = options.find((option) => option.includes('예술'))
    if (arts) return arts
  }

  return options[0]
}

const resolveSubjectFromParsed = (
  trackType: AdigaTrackType,
  curriculum: string,
  rawSubject: string
): string => {
  if (!rawSubject) return ''

  const options = getSubjectOptions(trackType, curriculum)
  if (options.includes(rawSubject)) return rawSubject

  const subjectNorm = normalizeMatchText(rawSubject)
  if (!subjectNorm) return rawSubject
  const normalizedMatch = options.find((option) => normalizeMatchText(option) === subjectNorm)
  return normalizedMatch || rawSubject
}

const splitShiftedCurriculumFromSubject = (
  trackType: AdigaTrackType,
  rawSubject: string
): { shiftedCurriculum: string; shiftedSubject: string } | null => {
  const subjectText = sanitizeCellValue(rawSubject)
  if (!subjectText) return null

  const parts = subjectText.split(/\s+/).filter(Boolean)
  if (parts.length < 2) return null

  const curriculumOptions = getCurriculumOptions(trackType)
  const firstToken = parts[0]
  const normalizedFirstToken = normalizeMatchText(firstToken)
  const matchedCurriculum = curriculumOptions.find(
    (option) => normalizeMatchText(option) === normalizedFirstToken
  )
  if (!matchedCurriculum) return null

  return {
    shiftedCurriculum: matchedCurriculum,
    shiftedSubject: parts.slice(1).join(' '),
  }
}

const convertParsedSchoolRecordToSemesterRows = (
  parsedSchoolRecord: unknown
): Record<SemesterKey, SemesterRow[]> | null => {
  if (!parsedSchoolRecord || typeof parsedSchoolRecord !== 'object') return null

  const sections = (parsedSchoolRecord as Record<string, unknown>).sections
  if (!sections || typeof sections !== 'object') return null

  const academic = (sections as Record<string, unknown>).academicDevelopment
  if (!academic || typeof academic !== 'object') return null

  const mappedSemesters = emptySemesterRows()
  let rowSequence = 0

  const appendRowsFromTable = (tableKey: ParsedAcademicTableKey) => {
    const table = (academic as Record<string, unknown>)[tableKey]
    if (!table || typeof table !== 'object') return

    for (const grade of ['1', '2', '3'] as const) {
      const gradeData = (table as Record<string, unknown>)[grade]
      if (!gradeData || typeof gradeData !== 'object') continue

      const rows = (gradeData as Record<string, unknown>).rows
      if (!Array.isArray(rows)) continue

      const trackType = parsedTableTrackTypeMap[tableKey]
      const curriculumOptions = getCurriculumOptions(trackType)
      const candidates: Array<{
        grade: '1' | '2' | '3'
        term: '1' | '2' | null
        rowRecord: ParsedAcademicRow
        curriculum: string
        subject: string
      }> = []

      for (const row of rows) {
        if (!row || typeof row !== 'object') continue
        const rowRecord = row as ParsedAcademicRow
        const parsedGradeAndTerm = parseGradeAndSemester(rowRecord['학기'], grade)
        let rawCurriculum = sanitizeCellValue(rowRecord['교과'])
        let rawSubject = sanitizeCellValue(rowRecord['과목'])

        // OCR/파싱 어긋남 복원:
        // 1) 교과가 짧게 잘린 경우(예: "평"), 과목 첫 토큰이 실제 교과면 교과/과목을 재분리
        // 2) 직전 과목의 끝 토큰이 교과명으로 섞여 있으면 잘린 교과 토큰으로 치환
        const shifted = splitShiftedCurriculumFromSubject(trackType, rawSubject)
        if (shifted && rawCurriculum.length <= 2) {
          const prev = candidates[candidates.length - 1]
          if (prev && prev.subject) {
            const prevParts = prev.subject.split(/\s+/).filter(Boolean)
            const lastToken = prevParts[prevParts.length - 1]
            const isLastTokenCurriculum = curriculumOptions.some(
              (option) => normalizeMatchText(option) === normalizeMatchText(lastToken)
            )
            if (isLastTokenCurriculum && normalizeMatchText(lastToken) !== normalizeMatchText(prev.curriculum)) {
              prev.subject = `${prevParts.slice(0, -1).join(' ')} ${rawCurriculum}`.trim()
            }
          }

          rawCurriculum = shifted.shiftedCurriculum
          rawSubject = shifted.shiftedSubject
        }

        const curriculum = resolveCurriculumFromParsed(trackType, rawCurriculum, rawSubject)
        const subject = resolveSubjectFromParsed(trackType, curriculum, rawSubject)

        candidates.push({
          grade: parsedGradeAndTerm.grade,
          term: parsedGradeAndTerm.term,
          rowRecord,
          curriculum,
          subject,
        })
      }

      const candidatesWithResolvedTerms = recoverMisparsedSemesterTerms(
        propagateMissingSemesterTerms(candidates)
      )
      for (let index = 0; index < candidatesWithResolvedTerms.length; index += 1) {
        const candidate = candidatesWithResolvedTerms[index]
        let semesterTerm = candidate.resolvedTerm
        if (!semesterTerm) {
          semesterTerm = '1'
        }

        if (!semesterTerm) continue

        rowSequence += 1
        const semesterKey = `${candidate.grade}-${semesterTerm}` as SemesterKey
        const achievementRaw = sanitizeCellValue(candidate.rowRecord['성취도'])
        const nextRow: SemesterRow = normalizeSemesterRow({
          id: `parsed-${Date.now()}-${rowSequence}`,
          trackType,
          curriculum: candidate.curriculum,
          subject: candidate.subject,
          credits: sanitizeCellValue(candidate.rowRecord['단위수']),
          classRank: sanitizeCellValue(candidate.rowRecord['석차등급']),
          rawScore: sanitizeCellValue(candidate.rowRecord['원점수']),
          avgScore: sanitizeCellValue(candidate.rowRecord['과목평균']),
          stdDev: sanitizeCellValue(candidate.rowRecord['표준편차']),
          studentCount: sanitizeCellValue(candidate.rowRecord['수강자수']),
          achievement: achievementOptions.includes(achievementRaw) ? achievementRaw : '선택',
          distA: sanitizeCellValue(candidate.rowRecord['성취도별분포_A'] ?? candidate.rowRecord['A']),
          distB: sanitizeCellValue(candidate.rowRecord['성취도별분포_B'] ?? candidate.rowRecord['B']),
          distC: sanitizeCellValue(candidate.rowRecord['성취도별분포_C'] ?? candidate.rowRecord['C']),
        })
        mappedSemesters[semesterKey].push(nextRow)
      }
    }
  }

  appendRowsFromTable('general_elective')
  appendRowsFromTable('career_elective')
  appendRowsFromTable('pe_arts')

  const hasAnyRows = (Object.keys(mappedSemesters) as SemesterKey[]).some((semester) => mappedSemesters[semester].length > 0)
  if (!hasAnyRows) return null

  return {
    '1-1': mappedSemesters['1-1'].length > 0 ? mappedSemesters['1-1'] : [createEmptyRow()],
    '1-2': mappedSemesters['1-2'].length > 0 ? mappedSemesters['1-2'] : [createEmptyRow()],
    '2-1': mappedSemesters['2-1'].length > 0 ? mappedSemesters['2-1'] : [createEmptyRow()],
    '2-2': mappedSemesters['2-2'].length > 0 ? mappedSemesters['2-2'] : [createEmptyRow()],
    '3-1': mappedSemesters['3-1'].length > 0 ? mappedSemesters['3-1'] : [createEmptyRow()],
    '3-2': mappedSemesters['3-2'].length > 0 ? mappedSemesters['3-2'] : [createEmptyRow()],
  }
}

const convertParsedSchoolRecordToExtracurricularData = (
  parsedSchoolRecord: unknown
): ExtracurricularData | null => {
  if (!parsedSchoolRecord || typeof parsedSchoolRecord !== 'object') return null
  const sections = (parsedSchoolRecord as Record<string, unknown>).sections
  if (!sections || typeof sections !== 'object') return null

  const nextData = createEmptyExtracurricularData()
  let hasMeaningfulValue = false
  let hasAttendanceRows = false
  let hasVolunteerRows = false

  const attendanceSection = (sections as Record<string, unknown>).attendance
  const attendanceRows =
    attendanceSection && typeof attendanceSection === 'object'
      ? (attendanceSection as Record<string, unknown>).rows
      : null
  if (Array.isArray(attendanceRows)) {
    for (const row of attendanceRows) {
      if (!row || typeof row !== 'object') continue
      const rowRecord = row as Record<string, unknown>
      const grade = parseGradeKey(rowRecord.grade ?? rowRecord['학년'])
      if (!grade) continue
      hasAttendanceRows = true

      const absence = getAttendanceUnexcusedValue(rowRecord, '결석', '무단결석일수')
      const tardy = getAttendanceUnexcusedValue(rowRecord, '지각', '무단지각일수')
      const earlyLeave = getAttendanceUnexcusedValue(rowRecord, '조퇴', '무단조퇴일수')
      const result = getAttendanceUnexcusedValue(rowRecord, '결과', '무단결과일수')

      nextData.attendance[grade] = { absence, tardy, earlyLeave, result }
      if (
        toNonNegativeInt(absence) > 0
        || toNonNegativeInt(tardy) > 0
        || toNonNegativeInt(earlyLeave) > 0
        || toNonNegativeInt(result) > 0
      ) {
        hasMeaningfulValue = true
      }
    }
  }

  const volunteerSection = (sections as Record<string, unknown>).volunteerActivity
  const volunteerRows =
    volunteerSection && typeof volunteerSection === 'object'
      ? (volunteerSection as Record<string, unknown>).rows
      : null
  if (Array.isArray(volunteerRows)) {
    const volunteerHoursSum: Record<GradeKey, number> = { '1': 0, '2': 0, '3': 0 }
    for (const row of volunteerRows) {
      if (!row || typeof row !== 'object') continue
      const rowRecord = row as Record<string, unknown>
      const grade = parseGradeKey(rowRecord.grade ?? rowRecord['학년'])
      if (!grade) continue
      hasVolunteerRows = true

      const rawHours = rowRecord.hours ?? rowRecord['시간']
      const hoursValue =
        typeof rawHours === 'number'
          ? rawHours
          : Number.parseFloat(String(rawHours ?? '').replace(/[^0-9.]/g, ''))
      if (Number.isFinite(hoursValue) && hoursValue > 0) {
        volunteerHoursSum[grade] += hoursValue
      }
    }

    for (const grade of gradeKeys) {
      const roundedHours = Math.round(volunteerHoursSum[grade])
      nextData.volunteerHours[grade] = roundedHours > 0 ? String(roundedHours) : ''
      if (roundedHours > 0) {
        hasMeaningfulValue = true
      }
    }
  }

  if (hasMeaningfulValue) return nextData
  return hasAttendanceRows || hasVolunteerRows ? nextData : null
}

interface ScrollableSelectProps {
  value: string
  options: string[]
  onChange: (nextValue: string) => void
  placeholder?: string
  minPanelWidth?: number
  buttonClassName?: string
  /** 스크롤 시 드롭다운 닫기 (다른 영역 클릭이 가능하도록) */
  scrollContainerRef?: React.RefObject<HTMLElement | null>
}

function ScrollableSelect({
  value,
  options,
  onChange,
  placeholder = '선택',
  minPanelWidth = 0,
  buttonClassName = 'h-10 w-full rounded-md border border-gray-300 bg-white px-2',
  scrollContainerRef,
}: ScrollableSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [panelVisible, setPanelVisible] = useState(false)
  const [panelRect, setPanelRect] = useState({ top: 0, left: 0, width: 0 })
  const rootRef = useRef<HTMLDivElement | null>(null)
  const buttonRef = useRef<HTMLButtonElement | null>(null)
  const panelRef = useRef<HTMLDivElement | null>(null)
  const openedAtRef = useRef<number>(0)

  const selectedValue = value || ''
  const hasValue = selectedValue.length > 0
  const displayValue = hasValue ? selectedValue : placeholder

  // isOpen이 true가 된 뒤 한 프레임 지연해서 패널 표시 (열기 클릭 이벤트가 완전히 끝난 뒤)
  useEffect(() => {
    if (!isOpen) {
      setPanelVisible(false)
      return
    }
    openedAtRef.current = Date.now()
    const frame = requestAnimationFrame(() => {
      setPanelVisible(true)
    })
    return () => cancelAnimationFrame(frame)
  }, [isOpen])

  useEffect(() => {
    if (!isOpen || !panelVisible) return

    const updatePanelPosition = () => {
      if (!buttonRef.current) return
      const rect = buttonRef.current.getBoundingClientRect()
      setPanelRect({
        top: rect.bottom + 6,
        left: rect.left,
        width: Math.max(rect.width, minPanelWidth),
      })
    }

    const handlePointerDown = (event: MouseEvent) => {
      const target = event.target as Node
      if (Date.now() - openedAtRef.current < 400) return
      if (rootRef.current?.contains(target)) return
      if (panelRef.current?.contains(target)) return
      setIsOpen(false)
    }

    const handleWindowScroll = () => {
      updatePanelPosition()
    }

    updatePanelPosition()
    window.addEventListener('resize', updatePanelPosition)
    window.addEventListener('scroll', handleWindowScroll, true)

    const scrollContainer = scrollContainerRef?.current
    const handleContainerScroll = () => {
      if (Date.now() - openedAtRef.current < 400) return
      setIsOpen(false)
    }

    // 닫기 리스너는 패널 표시 후 250ms 뒤에 등록
    const tid = setTimeout(() => {
      document.addEventListener('mousedown', handlePointerDown)
      if (scrollContainer) {
        scrollContainer.addEventListener('scroll', handleContainerScroll, true)
      }
    }, 250)

    return () => {
      clearTimeout(tid)
      document.removeEventListener('mousedown', handlePointerDown)
      if (scrollContainer) {
        scrollContainer.removeEventListener('scroll', handleContainerScroll, true)
      }
      window.removeEventListener('resize', updatePanelPosition)
      window.removeEventListener('scroll', handleWindowScroll, true)
    }
  }, [isOpen, panelVisible, minPanelWidth])

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setIsOpen((prev) => !prev)}
        className={`${buttonClassName} flex items-center justify-between gap-2 text-left text-sm text-gray-800`}
      >
        <span className={hasValue ? 'truncate' : 'truncate text-gray-500'}>{displayValue}</span>
        <span className="shrink-0 text-xs text-gray-500">▼</span>
      </button>

      {panelVisible && createPortal(
        <div
          ref={panelRef}
          style={{ top: panelRect.top, left: panelRect.left, width: panelRect.width }}
          className="fixed z-[80] rounded-2xl border border-gray-900 bg-white shadow-2xl"
        >
          <div
            className="max-h-72 overflow-y-auto overscroll-contain p-2"
          >
            {options.length > 0 ? (
              options.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => onChange(option)}
                  className={`block w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-[#eef5fb] ${
                    option === selectedValue ? 'bg-[#0e6093]/10 font-semibold text-[#0e6093]' : 'text-gray-800'
                  }`}
                >
                  {option}
                </button>
              ))
            ) : (
              <div className="px-3 py-2 text-sm text-gray-500">선택 가능한 항목이 없습니다.</div>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

function CountUpGrade({
  value,
  className,
}: {
  value: string
  className?: string
}) {
  const initialNumeric = parseGradeNumber(value)
  const [displayValue, setDisplayValue] = useState<string>(
    initialNumeric === null ? '-' : formatGradeForDisplay(initialNumeric)
  )
  const previousNumericRef = useRef<number | null>(initialNumeric)

  useEffect(() => {
    const targetNumeric = parseGradeNumber(value)
    if (targetNumeric === null) {
      previousNumericRef.current = null
      setDisplayValue('-')
      return
    }

    const fromNumeric = previousNumericRef.current ?? targetNumeric
    previousNumericRef.current = targetNumeric
    if (Math.abs(fromNumeric - targetNumeric) < 0.0001) {
      setDisplayValue(formatGradeForDisplay(targetNumeric))
      return
    }

    let animationFrameId = 0
    const startedAt = performance.now()
    const duration = 360
    const delta = targetNumeric - fromNumeric

    const animate = (now: number) => {
      const progress = Math.min(1, (now - startedAt) / duration)
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = fromNumeric + delta * eased
      setDisplayValue(formatGradeForDisplay(current))
      if (progress < 1) {
        animationFrameId = requestAnimationFrame(animate)
      }
    }

    animationFrameId = requestAnimationFrame(animate)
    return () => {
      cancelAnimationFrame(animationFrameId)
    }
  }, [value])

  return <span className={className}>{displayValue}</span>
}

export default function SchoolGradeInputModal({
  isOpen,
  onClose,
  embedded = false,
  autoOpenSavedGradeReport = false,
  onAutoOpenSavedGradeReportHandled,
  onRequireSchoolRecordLink,
  onOpenMockExamInput,
  onUseNaesinSuggestion,
}: SchoolGradeInputModalProps) {
  const { isAuthenticated, accessToken } = useAuth()
  const [step, setStep] = useState<ModalStep>('menu')
  const [selectedSemester, setSelectedSemester] = useState<SemesterKey>('1-1')
  const [selectedSchoolYear, setSelectedSchoolYear] = useState<string>(schoolYearOptions[0])
  const [data, setData] = useState<SchoolGradeInputData>(() => buildDefaultData())
  const [selectedInputChoice, setSelectedInputChoice] = useState<QuickInputMode | null>(null)
  const [isChoiceFormVisible, setIsChoiceFormVisible] = useState(false)
  const [isOverallEstimateSubmitted, setIsOverallEstimateSubmitted] = useState(false)
  const [isOverallInputLeaving, setIsOverallInputLeaving] = useState(false)
  const [, setHasCalculatedResult] = useState(false)
  const [isInlineDetailVisible, setIsInlineDetailVisible] = useState(false)
  const [isEstimateToastVisible, setIsEstimateToastVisible] = useState(false)
  const [isGradeReportModalOpen, setIsGradeReportModalOpen] = useState(false)
  const [reportSemester, setReportSemester] = useState<SemesterKey>('1-1')
  const [showSavedGradeLinkHint, setShowSavedGradeLinkHint] = useState(false)
  const [isSubjectDetailModalOpen, setIsSubjectDetailModalOpen] = useState(false)
  const [subjectDetailSemester, setSubjectDetailSemester] = useState<SemesterKey>('1-1')
  const [message, setMessage] = useState('')
  const [isAutofillLoading, setIsAutofillLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const rightMainScrollRef = useRef<HTMLDivElement>(null)
  const dataRef = useRef<SchoolGradeInputData>(data)
  const hasUserInteractedRef = useRef(false)
  const overallTransitionTimerRef = useRef<number | null>(null)
  const estimateToastTimerRef = useRef<number | null>(null)

  useEffect(() => {
    dataRef.current = data
  }, [data])

  useEffect(() => {
    return () => {
      if (overallTransitionTimerRef.current !== null) {
        window.clearTimeout(overallTransitionTimerRef.current)
      }
      if (estimateToastTimerRef.current !== null) {
        window.clearTimeout(estimateToastTimerRef.current)
      }
    }
  }, [])

  const loadSchoolGradeInputFromServer = useCallback(
    async (signal?: AbortSignal) => {
      if (!isAuthenticated || !accessToken) return

      try {
        const apiBase = getApiBaseUrl()
        const response = await fetch(`${apiBase ? `${apiBase}/api` : '/api'}/profile/me/school-grade-input?ts=${Date.now()}`, {
          headers: { Authorization: `Bearer ${accessToken}` },
          cache: 'no-store',
          signal,
        })
        if (!response.ok) return

        const payload = await response.json().catch(() => null)
        const rawServerData = payload?.school_grade_input
        if (!rawServerData || typeof rawServerData !== 'object' || Object.keys(rawServerData).length === 0) {
          return
        }

        const serverData = normalizeSchoolGradeInputData(rawServerData)
        if (hasUserInteractedRef.current) return
        setData(serverData)
        setHasCalculatedResult(hasSavedNaesinData(serverData))
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(serverData))
        } catch {
          // ignore localStorage failure
        }
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') return
      }
    },
    [isAuthenticated, accessToken]
  )

  const persistSchoolGradeInput = useCallback(async (nextData: SchoolGradeInputData, successMessage: string) => {
    setData(nextData)
    let isLocalSaved = false

    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(nextData))
      isLocalSaved = true
    } catch {
      isLocalSaved = false
    }

    if (!isAuthenticated || !accessToken) {
      if (isLocalSaved) {
        setMessage(successMessage)
      } else {
        setMessage('저장에 실패했습니다. 브라우저 저장 공간을 확인해주세요.')
      }
      return
    }

    setIsSaving(true)
    try {
      const apiBase = getApiBaseUrl()
      const response = await fetch(`${apiBase ? `${apiBase}/api` : '/api'}/profile/me/school-grade-input`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ school_grade_input: nextData }),
      })

      if (!response.ok) {
        if (isLocalSaved) {
          setMessage('서버 저장에 실패했습니다. 브라우저에는 저장되었습니다.')
        } else {
          setMessage('저장에 실패했습니다. 잠시 후 다시 시도해주세요.')
        }
        return
      }

      const payload = await response.json().catch(() => null)
      const rawSaved = payload?.school_grade_input
      const normalizedSaved =
        rawSaved && typeof rawSaved === 'object'
          ? normalizeSchoolGradeInputData(rawSaved)
          : nextData
      setData(normalizedSaved)
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(normalizedSaved))
      } catch {
        // ignore localStorage failure
      }
      setMessage(successMessage)
    } catch {
      if (isLocalSaved) {
        setMessage('서버 저장에 실패했습니다. 브라우저에는 저장되었습니다.')
      } else {
        setMessage('저장에 실패했습니다. 잠시 후 다시 시도해주세요.')
      }
    } finally {
      setIsSaving(false)
    }
  }, [isAuthenticated, accessToken])

  const autofillFromLinkedSchoolRecord = useCallback(
    async ({
      signal,
      silentWhenUnavailable = false,
      redirectIfNotLinked = false,
      persistAfterFill = false,
      showLoading = true,
    }: {
      signal?: AbortSignal
      silentWhenUnavailable?: boolean
      redirectIfNotLinked?: boolean
      persistAfterFill?: boolean
      showLoading?: boolean
    } = {}) => {
      if (!isAuthenticated || !accessToken) {
        if (!silentWhenUnavailable) {
          setMessage('생기부 연동 자동 입력은 로그인 후 사용할 수 있습니다.')
        }
        return
      }

      if (showLoading) setIsAutofillLoading(true)
      void captureBusinessEvent(TrackingEventNames.scoreAutofillStarted, {
        category: 'engagement',
        source: 'school_grade_input_modal',
        persist_after_fill: persistAfterFill,
      })
      try {
        const moveToSchoolRecordLinkPage = () => {
          if (!silentWhenUnavailable) {
            setMessage('연동된 생기부가 없어 내 프로필/생활기록부로 이동할게요.')
          }
          onRequireSchoolRecordLink?.()
        }

        if (redirectIfNotLinked) {
          const apiBase = getApiBaseUrl()
          const statusRes = await fetch(`${apiBase ? `${apiBase}/api` : '/api'}/school-record/status`, {
            headers: { Authorization: `Bearer ${accessToken}` },
            cache: 'no-store',
            signal,
          })
          const linkedStatus =
            statusRes.ok
              ? ((await statusRes.json().catch(() => null))?.linked === true)
              : null

          if (linkedStatus === false) {
            moveToSchoolRecordLinkPage()
            return
          }
        }

        const apiBase = getApiBaseUrl()
        const response = await fetch(`${apiBase ? `${apiBase}/api` : '/api'}/school-record/forms?ts=${Date.now()}`, {
          headers: { Authorization: `Bearer ${accessToken}` },
          cache: 'no-store',
          signal,
        })
        if (!response.ok) {
          if (!silentWhenUnavailable) {
            setMessage('연동된 생기부 정보를 불러오지 못했습니다.')
          }
          return
        }

        const payload = await response.json().catch(() => null)
        const parsedSchoolRecord =
          payload?.forms?.parsedSchoolRecord
          || payload?.parsedSchoolRecord
          || payload?.school_record?.parsedSchoolRecord
        const semesterRows = convertParsedSchoolRecordToSemesterRows(parsedSchoolRecord)
        const extracurricularData = convertParsedSchoolRecordToExtracurricularData(parsedSchoolRecord)
        if (!semesterRows && !extracurricularData) {
          if (redirectIfNotLinked) {
            moveToSchoolRecordLinkPage()
            return
          }
          if (!silentWhenUnavailable) {
            setMessage('연동된 생기부에서 가져올 데이터가 없습니다.')
          }
          return
        }

        const isBackgroundAutofill = !persistAfterFill && !redirectIfNotLinked
        if (isBackgroundAutofill && hasUserInteractedRef.current) {
          return
        }

        const baseData = dataRef.current
        const nextSemesters = semesterRows || baseData.semesters
        const nextData: SchoolGradeInputData = {
          ...baseData,
          semesters: nextSemesters,
          extracurricular: extracurricularData || baseData.extracurricular,
          gradeSummary: semesterRows
            ? buildGradeSummaryFromSemesters(nextSemesters, baseData.gradeSummary)
            : baseData.gradeSummary,
          hasReportCardData: Boolean(semesterRows) || baseData.hasReportCardData,
        }
        const filledMessage =
          semesterRows && extracurricularData
            ? '연동된 생기부 정보를 기반으로 교과/비교과를 자동으로 채우고 저장했습니다.'
            : semesterRows
              ? '연동된 생기부 정보를 기반으로 내신 성적을 자동으로 채우고 저장했습니다.'
              : '연동된 생기부 정보를 기반으로 비교과를 자동으로 채우고 저장했습니다.'

        if (persistAfterFill) {
          await persistSchoolGradeInput(nextData, filledMessage)
        } else {
          setData(nextData)
          try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(nextData))
          } catch {
            // ignore localStorage failures and keep UI state update
          }
          if (!silentWhenUnavailable) {
            setMessage(
              filledMessage.replace('자동으로 채우고 저장했습니다.', '자동으로 채웠습니다.')
            )
          }
        }
        setHasCalculatedResult(hasSavedNaesinData(nextData))
        setIsSubjectDetailModalOpen(false)
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') return
        if (!silentWhenUnavailable) {
          setMessage('생기부 자동 입력 중 오류가 발생했습니다.')
        }
      } finally {
        if (showLoading) setIsAutofillLoading(false)
      }
    },
    [isAuthenticated, accessToken, onRequireSchoolRecordLink, persistSchoolGradeInput]
  )

  useEffect(() => {
    if (!isOpen) return

    if (overallTransitionTimerRef.current !== null) {
      window.clearTimeout(overallTransitionTimerRef.current)
      overallTransitionTimerRef.current = null
    }
    if (estimateToastTimerRef.current !== null) {
      window.clearTimeout(estimateToastTimerRef.current)
      estimateToastTimerRef.current = null
    }
    hasUserInteractedRef.current = false
    const savedData = loadSavedData()
    setStep(embedded ? 'menu' : 'semester')
    setSelectedSemester('1-1')
    setSelectedSchoolYear(schoolYearOptions[0])
    setSelectedInputChoice(null)
    setIsChoiceFormVisible(false)
    setIsOverallEstimateSubmitted(false)
    setIsOverallInputLeaving(false)
    setHasCalculatedResult(hasSavedNaesinData(savedData))
    setIsInlineDetailVisible(false)
    setIsEstimateToastVisible(false)
    setIsGradeReportModalOpen(false)
    setReportSemester('1-1')
    setShowSavedGradeLinkHint(false)
    setSubjectDetailSemester('1-1')
    setMessage('')
    setData(savedData)
  }, [isOpen, embedded])

  useEffect(() => {
    if (!selectedInputChoice) {
      setIsChoiceFormVisible(false)
      return
    }

    setIsChoiceFormVisible(false)
    const tid = window.setTimeout(() => {
      setIsChoiceFormVisible(true)
    }, 10)
    return () => {
      window.clearTimeout(tid)
    }
  }, [selectedInputChoice])

  useEffect(() => {
    if (!isOpen) return

    const controller = new AbortController()

    const loadThenAutofill = async () => {
      await loadSchoolGradeInputFromServer(controller.signal)

      if (controller.signal.aborted) return

      await autofillFromLinkedSchoolRecord({
        signal: controller.signal,
        silentWhenUnavailable: true,
        showLoading: false,
        persistAfterFill: true,
      })
    }

    void loadThenAutofill()

    return () => {
      controller.abort()
    }
  }, [isOpen, loadSchoolGradeInputFromServer, autofillFromLinkedSchoolRecord])

  const currentSemesterRows = useMemo(
    () => data.semesters[selectedSemester] || [createEmptyRow()],
    [data.semesters, selectedSemester]
  )

  const goMenu = () => {
    setStep('menu')
    setMessage('')
  }

  const saveData = useCallback(async (nextData: SchoolGradeInputData, successMessage: string) => {
    await persistSchoolGradeInput(nextData, successMessage)
  }, [persistSchoolGradeInput])

  const updateSemesterRow = (
    semester: SemesterKey,
    rowId: string,
    field: keyof Omit<SemesterRow, 'id'>,
    value: string
  ) => {
    setData((prev) => {
      const nextSemesters = {
        ...prev.semesters,
        [semester]: prev.semesters[semester].map((row) => {
          if (row.id !== rowId) return row

          if (field === 'trackType') {
            const nextTrackType = normalizeTrackType(value)
            const nextCurriculum = normalizeCurriculum(nextTrackType, row.curriculum)
            const subjects = getSubjectOptions(nextTrackType, nextCurriculum)
            const nextSubject = subjects.includes(row.subject) ? row.subject : (subjects[0] || row.subject)

            return {
              ...row,
              trackType: nextTrackType,
              curriculum: nextCurriculum,
              subject: nextSubject,
            }
          }

          if (field === 'curriculum') {
            const nextCurriculum = normalizeCurriculum(row.trackType, value)
            const subjects = getSubjectOptions(row.trackType, nextCurriculum)
            const nextSubject = subjects.includes(row.subject) ? row.subject : (subjects[0] || row.subject)

            return {
              ...row,
              curriculum: nextCurriculum,
              subject: nextSubject,
            }
          }

          if (field === 'classRank') {
            const sanitized = sanitizeClassRankInput(value)
            const grade = sanitized ? Number.parseInt(sanitized, 10) : null
            const rawScore = grade != null && grade >= 1 && grade <= 9 ? getRawScoreByClassRank(grade) : row.rawScore
            return { ...row, classRank: sanitized, rawScore }
          }

          return { ...row, [field]: value }
        }),
      }

      return {
        ...prev,
        semesters: nextSemesters,
        gradeSummary: buildGradeSummaryFromSemesters(nextSemesters, prev.gradeSummary),
      }
    })
  }

  const addSemesterRow = (semester: SemesterKey, count = 1) => {
    setData((prev) => {
      const nextSemesters = {
        ...prev.semesters,
        [semester]: [
          ...prev.semesters[semester],
          ...Array.from({ length: count }).map(() => createEmptyRow()),
        ],
      }
      return {
        ...prev,
        semesters: nextSemesters,
        gradeSummary: buildGradeSummaryFromSemesters(nextSemesters, prev.gradeSummary),
      }
    })
  }

  const coreCurriculumNames = new Set(['국어', '수학', '영어', '한국사', '과학', '사회(역사/도덕포함)', '통합사회', '통합과학'])

  const buildGradeSummaryFromSemesters = (
    semesters: Record<SemesterKey, SemesterRow[]>,
    baseSummary: GradeSummaryData
  ): GradeSummaryData => {
    const nextSemesterAverages: Record<SemesterKey, Record<GradeAverageFieldKey, string>> = {
      '1-1': { ...baseSummary.semesterAverages['1-1'] },
      '1-2': { ...baseSummary.semesterAverages['1-2'] },
      '2-1': { ...baseSummary.semesterAverages['2-1'] },
      '2-2': { ...baseSummary.semesterAverages['2-2'] },
      '3-1': { ...baseSummary.semesterAverages['3-1'] },
      '3-2': { ...baseSummary.semesterAverages['3-2'] },
    }

    for (const semesterKey of semesterKeys) {
      const rows = semesters[semesterKey] || []
      const overallGrades: number[] = []
      const coreGrades: number[] = []
      for (const row of rows) {
        const value = parseGradeNumber(row.classRank)
        if (value === null) continue
        overallGrades.push(value)
        if (coreCurriculumNames.has(row.curriculum)) {
          coreGrades.push(value)
        }
      }

      nextSemesterAverages[semesterKey] = {
        overall: formatAveragedGrade(overallGrades.map(String)),
        core: formatAveragedGrade(coreGrades.map(String)),
      }
    }

    return {
      ...baseSummary,
      semesterAverages: nextSemesterAverages,
      overallAverage: formatAveragedGrade(semesterKeys.map((k) => nextSemesterAverages[k].overall)),
      coreAverage: formatAveragedGrade(semesterKeys.map((k) => nextSemesterAverages[k].core)),
    }
  }

  const applyClassRanksFromSummary = (
    semesters: Record<SemesterKey, SemesterRow[]>,
    summary: GradeSummaryData
  ): Record<SemesterKey, SemesterRow[]> => {
    const fallbackOverall = parseGradeNumber(summary.overallAverage)
    const fallbackCore = parseGradeNumber(summary.coreAverage)
    if (fallbackOverall === null && fallbackCore === null) {
      return semesters
    }

    const defaultOverall = fallbackOverall ?? fallbackCore ?? 0
    const defaultCore = fallbackCore ?? fallbackOverall ?? 0

    const allocateGrades = (count: number, targetSum: number): number[] => {
      if (count <= 0) return []
      const sum = Math.round(targetSum)
      const base = Math.max(1, Math.min(9, Math.floor(sum / count)))
      const remainder = sum - base * count
      const grades: number[] = []
      if (remainder > 0 && base < 9) {
        const high = Math.min(9, base + 1)
        for (let i = 0; i < remainder; i++) grades.push(high)
        for (let i = remainder; i < count; i++) grades.push(base)
        return grades
      }
      for (let i = 0; i < count; i++) grades.push(base)
      return grades
    }

    const nextSemesters = { ...semesters }
    for (const semesterKey of semesterKeys) {
      const rows = semesters[semesterKey] || []
      if (rows.length === 0) continue

      const semOverall = parseGradeNumber(summary.semesterAverages[semesterKey].overall)
      const semCore = parseGradeNumber(summary.semesterAverages[semesterKey].core)
      const overall = semOverall ?? defaultOverall
      const core = semCore ?? defaultCore

      const coreRows: typeof rows = []
      const nonCoreRows: typeof rows = []
      for (const row of rows) {
        if (coreCurriculumNames.has(row.curriculum)) coreRows.push(row)
        else nonCoreRows.push(row)
      }

      const nCore = coreRows.length
      const nNonCore = nonCoreRows.length
      const n = nCore + nNonCore
      const sumTotal = Math.round(overall * n)
      const sumCore = Math.round(core * nCore)
      const sumNonCore = nNonCore > 0 ? sumTotal - sumCore : 0

      const coreGrades = allocateGrades(nCore, nCore > 0 ? sumCore : 0)
      const nonCoreGrades = allocateGrades(nNonCore, sumNonCore)
      let coreIdx = 0
      let nonCoreIdx = 0

      nextSemesters[semesterKey] = rows.map((row) => {
        const isCore = coreCurriculumNames.has(row.curriculum)
        const rank = isCore ? coreGrades[coreIdx++] : nonCoreGrades[nonCoreIdx++]
        const grade = rank >= 1 && rank <= 9 ? rank : 1
        return { ...row, classRank: String(grade), rawScore: getRawScoreByClassRank(grade) }
      })
    }

    return nextSemesters
  }

  const updateSummaryAverage = (field: GradeAverageFieldKey, value: string) => {
    const sanitized = sanitizeGradeNumberInput(value)
    setData((prev) => {
      const nextSemesterAverages = semesterKeys.reduce<Record<SemesterKey, Record<GradeAverageFieldKey, string>>>(
        (acc, semesterKey) => {
          acc[semesterKey] = {
            ...prev.gradeSummary.semesterAverages[semesterKey],
            [field]: sanitized,
          }
          return acc
        },
        {} as Record<SemesterKey, Record<GradeAverageFieldKey, string>>
      )
      const nextGradeSummary = {
        ...prev.gradeSummary,
        overallAverage: field === 'overall' ? sanitized : prev.gradeSummary.overallAverage,
        coreAverage: field === 'core' ? sanitized : prev.gradeSummary.coreAverage,
        semesterAverages: nextSemesterAverages,
      }
      const nextSemesters = applyClassRanksFromSummary(prev.semesters, nextGradeSummary)
      return {
        ...prev,
        semesters: nextSemesters,
        gradeSummary: nextGradeSummary,
      }
    })
  }

  const updateSemesterAverage = (semester: SemesterKey, field: GradeAverageFieldKey, value: string) => {
    const sanitized = sanitizeGradeNumberInput(value)
    setData((prev) => {
      const nextSemesterAverages = {
        ...prev.gradeSummary.semesterAverages,
        [semester]: {
          ...prev.gradeSummary.semesterAverages[semester],
          [field]: sanitized,
        },
      }
      const nextAverage = formatAveragedGrade(
        semesterKeys.map((semesterKey) => nextSemesterAverages[semesterKey][field])
      )
      const nextGradeSummary = {
        ...prev.gradeSummary,
        semesterAverages: nextSemesterAverages,
        overallAverage: field === 'overall' ? nextAverage : prev.gradeSummary.overallAverage,
        coreAverage: field === 'core' ? nextAverage : prev.gradeSummary.coreAverage,
      }
      const nextSemesters = applyClassRanksFromSummary(prev.semesters, nextGradeSummary)
      return {
        ...prev,
        semesters: nextSemesters,
        gradeSummary: nextGradeSummary,
      }
    })
  }

  const handleQuickAverageChange = (value: string) => {
    const sanitized = sanitizeGradeNumberInput(value)
    updateSummaryAverage('overall', sanitized)
  }

  const handleSemesterModeAverageChange = (semester: SemesterKey, value: string) => {
    updateSemesterAverage(semester, 'overall', value)
  }

  const handleSaveAll = useCallback(() => {
    void captureBusinessEvent(TrackingEventNames.scoreSaved, {
      category: 'engagement',
      source: 'school_grade_input_modal',
      has_report_card_data: data.hasReportCardData,
    })
    void saveData(
      data,
      `전체 입력 데이터가 저장되었습니다. 채팅창에서 "${NAESIN_CHAT_MENTION_EXAMPLE}"로 바로 활용할 수 있어요.`
    )
  }, [data, saveData])

  const handleSemesterSave = () => {
    handleSaveAll()
  }

  const handleSemesterCancel = () => {
    setData(loadSavedData())
    goMenu()
  }

  const handleExtracurricularSave = () => {
    handleSaveAll()
  }

  const handleExtracurricularCancel = () => {
    setData(loadSavedData())
    goMenu()
  }

  const updateAttendanceField = (
    grade: GradeKey,
    field: keyof ExtracurricularAttendanceRow,
    value: string
  ) => {
    const sanitized = sanitizeNumberInput(value)
    setData((prev) => ({
      ...prev,
      extracurricular: {
        ...prev.extracurricular,
        attendance: {
          ...prev.extracurricular.attendance,
          [grade]: {
            ...prev.extracurricular.attendance[grade],
            [field]: sanitized,
          },
        },
      },
    }))
  }

  const updateVolunteerHours = (grade: GradeKey, value: string) => {
    const sanitized = sanitizeNumberInput(value)
    setData((prev) => ({
      ...prev,
      extracurricular: {
        ...prev.extracurricular,
        volunteerHours: {
          ...prev.extracurricular.volunteerHours,
          [grade]: sanitized,
        },
      },
    }))
  }

  const attendanceTotalsByGrade = useMemo(
    () =>
      gradeKeys.reduce<Record<GradeKey, number>>((acc, grade) => {
        const row = data.extracurricular.attendance[grade]
        acc[grade] =
          toNonNegativeInt(row.absence)
          + toNonNegativeInt(row.tardy)
          + toNonNegativeInt(row.earlyLeave)
          + toNonNegativeInt(row.result)
        return acc
      }, { '1': 0, '2': 0, '3': 0 }),
    [data.extracurricular.attendance]
  )

  const attendanceColumnTotals = useMemo(
    () =>
      gradeKeys.reduce(
        (acc, grade) => {
          const row = data.extracurricular.attendance[grade]
          acc.absence += toNonNegativeInt(row.absence)
          acc.tardy += toNonNegativeInt(row.tardy)
          acc.earlyLeave += toNonNegativeInt(row.earlyLeave)
          acc.result += toNonNegativeInt(row.result)
          return acc
        },
        { absence: 0, tardy: 0, earlyLeave: 0, result: 0 }
      ),
    [data.extracurricular.attendance]
  )

  const attendanceGrandTotal = useMemo(
    () => gradeKeys.reduce((sum, grade) => sum + attendanceTotalsByGrade[grade], 0),
    [attendanceTotalsByGrade]
  )

  const volunteerTotal = useMemo(
    () => gradeKeys.reduce((sum, grade) => sum + toNonNegativeInt(data.extracurricular.volunteerHours[grade]), 0),
    [data.extracurricular.volunteerHours]
  )

  const handleRecordUploadSave = () => {
    handleSaveAll()
  }

  const handleRecordUploadCancel = () => {
    setData(loadSavedData())
    goMenu()
  }

  const handleRecordFileChange = (file: File | null) => {
    if (!file) return

    setData((prev) => ({
      ...prev,
      recordUpload: {
        ...prev.recordUpload,
        fileName: file.name,
      },
    }))
  }

  const quickAverageValue = data.gradeSummary.overallAverage
  const hasQuickAverage = parseGradeNumber(quickAverageValue) !== null
  const hasAnySemesterAverage = semesterKeys.some(
    (semesterKey) => parseGradeNumber(data.gradeSummary.semesterAverages[semesterKey].overall) !== null
  )

  const showEstimateToast = useCallback(() => {
    setIsEstimateToastVisible(true)
    if (estimateToastTimerRef.current !== null) {
      window.clearTimeout(estimateToastTimerRef.current)
    }
    estimateToastTimerRef.current = window.setTimeout(() => {
      setIsEstimateToastVisible(false)
      estimateToastTimerRef.current = null
    }, 2600)
  }, [])

  const handleOverallEstimateSubmit = useCallback(() => {
    if (!hasQuickAverage) {
      setMessage('평균 등급을 먼저 입력해 주세요.')
      return
    }

    void captureBusinessEvent(TrackingEventNames.scoreInputModeSelected, {
      category: 'engagement',
      mode: 'overall',
    })
    void captureBusinessEvent(TrackingEventNames.scoreSaved, {
      category: 'engagement',
      source: 'overall_estimate',
    })
    void saveData(data, '입력하신 평균으로 학기별 성적을 추산했어요')
    setIsOverallInputLeaving(true)
    if (overallTransitionTimerRef.current !== null) {
      window.clearTimeout(overallTransitionTimerRef.current)
    }
    overallTransitionTimerRef.current = window.setTimeout(() => {
      setIsOverallEstimateSubmitted(true)
      setIsOverallInputLeaving(false)
      setHasCalculatedResult(true)
      setIsInlineDetailVisible(true)
      showEstimateToast()
      overallTransitionTimerRef.current = null
    }, 280)
  }, [data, hasQuickAverage, saveData, showEstimateToast])

  const handleSemesterEstimateSubmit = useCallback(() => {
    if (!hasAnySemesterAverage) {
      setMessage('학기별 평균을 먼저 입력해 주세요.')
      return
    }

    void captureBusinessEvent(TrackingEventNames.scoreInputModeSelected, {
      category: 'engagement',
      mode: 'semester',
    })
    void captureBusinessEvent(TrackingEventNames.scoreSaved, {
      category: 'engagement',
      source: 'semester_estimate',
    })
    void saveData(data, '입력하신 성적으로 과목별 상세 입력까지 이어서 도와드릴게요')
    setHasCalculatedResult(true)
    setIsInlineDetailVisible(true)
  }, [data, hasAnySemesterAverage, saveData])

  const subjectDetailRows = data.semesters[subjectDetailSemester] || [createEmptyRow()]
  const reportRowsBySemester = useMemo(
    () =>
      semesterKeys.reduce<Record<SemesterKey, SemesterRow[]>>((acc, semesterKey) => {
        acc[semesterKey] = (data.semesters[semesterKey] || []).filter(isMeaningfulSemesterRow)
        return acc
      }, {} as Record<SemesterKey, SemesterRow[]>),
    [data.semesters]
  )
  const hasSavedGradeData = hasSavedNaesinData(data)

  useEffect(() => {
    if (hasSavedGradeData) {
      setShowSavedGradeLinkHint(false)
    }
  }, [hasSavedGradeData])

  useEffect(() => {
    if (!embedded || !autoOpenSavedGradeReport) return

    if (hasSavedGradeData) {
      setReportSemester(selectedSemester)
      setIsGradeReportModalOpen(true)
      setShowSavedGradeLinkHint(false)
    } else {
      setShowSavedGradeLinkHint(true)
    }

    onAutoOpenSavedGradeReportHandled?.()
  }, [
    embedded,
    autoOpenSavedGradeReport,
    hasSavedGradeData,
    selectedSemester,
    onAutoOpenSavedGradeReportHandled,
  ])

  if (!isOpen && !embedded) return null

  // 임베디드 UI: Toss 스타일 간편 입력 플로우
  if (embedded) {
    return (
      <div
        className="flex h-full w-full flex-col bg-gray-50"
        style={{ fontFamily: "'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif" }}
        onPointerDownCapture={() => {
          hasUserInteractedRef.current = true
        }}
        onKeyDownCapture={() => {
          hasUserInteractedRef.current = true
        }}
      >
        <div className="mx-auto flex h-full w-full max-w-6xl flex-col px-3 pb-4 pt-4 sm:px-6 lg:px-8 overflow-x-hidden">
          <div className="flex-shrink-0">
            <div className="flex items-center justify-between gap-2 rounded-2xl sm:rounded-3xl bg-white px-4 sm:px-5 py-3.5 sm:py-4">
              <div className="min-w-0 flex-1">
                <button
                  type="button"
                  onClick={() => {
                    if (!hasSavedGradeData) {
                      setShowSavedGradeLinkHint(true)
                      return
                    }
                    setShowSavedGradeLinkHint(false)
                    setReportSemester(selectedSemester)
                    setIsGradeReportModalOpen(true)
                  }}
                  className={`mt-1 inline-flex min-h-[52px] items-center justify-center rounded-2xl px-5 sm:px-6 text-[16px] sm:text-[17px] font-extrabold leading-none transition-all ${
                    hasSavedGradeData
                      ? 'bg-[#1f3b61] text-white shadow-sm hover:bg-[#162b49] hover:shadow-md active:scale-[0.99]'
                      : 'bg-gray-200 text-gray-500'
                  }`}
                >
                  저장된 내 내신 성적 보기
                </button>
                <p className="mt-2 text-xs text-gray-500">학기별로 나눠서 성적표를 확인할 수 있어요.</p>
                {showSavedGradeLinkHint && !hasSavedGradeData && (
                  <p className="mt-1 text-xs font-semibold text-[#0e6093]">아래에서 연동하세요</p>
                )}
              </div>
              <button
                onClick={onClose}
                className="shrink-0 inline-flex h-11 min-h-[44px] items-center justify-center rounded-xl border border-gray-200 bg-white px-4 text-sm font-bold text-gray-700 transition-colors hover:bg-gray-100 active:bg-gray-200 touch-manipulation"
                aria-label="닫기"
              >
                닫기
              </button>
            </div>
          </div>

          <div className="mt-4 min-h-0 flex-1">
            <div className="min-h-0 h-full overflow-y-auto">
          {message && (
            <div className="mb-3 rounded-2xl border border-[#0e6093]/20 bg-[#0e6093]/10 px-4 py-3 text-sm font-medium text-[#0e6093]">
              {message}
            </div>
          )}

          <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-[#e9f2ff] via-[#f3efff] to-[#edf5ff] p-6 shadow-sm transition-all hover:shadow-lg sm:p-7">
            <div className="pointer-events-none absolute -left-10 -top-14 h-40 w-40 rounded-full bg-blue-200/40 blur-3xl" />
            <div className="pointer-events-none absolute -bottom-14 -right-10 h-44 w-44 rounded-full bg-violet-200/40 blur-3xl" />
            <div className="relative">
              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center rounded-full bg-white/80 px-3 py-1 text-xs font-semibold text-[#34507a]">가장 정확한 입력</span>
              </div>
              <h3 className="mt-3 text-2xl font-black tracking-tight text-[#1f2937] sm:text-3xl">생기부 연동으로 바로 끝낼까요?</h3>
              <p className="mt-2 text-sm font-medium text-[#4b5563] sm:text-base">
                생기부를 연동하면 학기별 성적이 자동으로 채워져요.
              </p>
              <div className="mt-5 rounded-2xl bg-white/80 p-4 shadow-sm">
                <p className="text-sm font-semibold text-[#4b5563]">생기부로 3초안에 연동하기</p>
                <button
                  type="button"
                  onClick={() => {
                    void captureBusinessEvent(TrackingEventNames.scoreLinkEntryClick, {
                      category: 'engagement',
                      source: 'school_grade_input_modal',
                      interaction_type: 'score_link_start',
                    })
                    void autofillFromLinkedSchoolRecord({ redirectIfNotLinked: true, persistAfterFill: true })
                  }}
                  disabled={isAutofillLoading}
                  className="mt-3 inline-flex h-16 w-full items-center justify-center rounded-2xl bg-[#1f3b61] px-6 text-lg font-extrabold text-white shadow-sm transition-all hover:scale-[1.01] hover:bg-[#162b49] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isAutofillLoading ? '연동 중...' : '생기부 연동하기'}
                </button>
              </div>
            </div>
          </div>

          <section className="mt-6 rounded-3xl bg-white p-5 shadow-sm transition-all hover:shadow-lg sm:p-6">
            <p className="text-2xl font-black tracking-tight text-gray-900 sm:text-3xl">성적을 직접 입력하시겠어요?</p>
            <p className="mt-2 text-base text-gray-500 sm:text-lg">알고 있는 방식 하나만 선택하면 바로 시작할 수 있어요.</p>
            <div className="mt-5 grid grid-cols-1 gap-6 md:grid-cols-2">
              <button
                type="button"
                onClick={() => {
                    void captureBusinessEvent(TrackingEventNames.scoreInputModeSelected, {
                      category: 'engagement',
                      mode: 'overall',
                      source: 'school_grade_input_modal',
                    })
                    setSelectedInputChoice('overall')
                    setIsOverallEstimateSubmitted(false)
                    setIsOverallInputLeaving(false)
                    setHasCalculatedResult(false)
                    setIsInlineDetailVisible(false)
                    setIsEstimateToastVisible(false)
                }}
                className={`h-44 w-full rounded-3xl border-2 p-4 transition-all hover:scale-[1.01] hover:shadow-lg ${
                  selectedInputChoice === 'overall'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-transparent bg-gray-50 hover:bg-gray-100'
                }`}
              >
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-blue-600 shadow-sm">
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.6} d="M4 19h16M7 15l3-3 2 2 5-5" />
                    </svg>
                  </div>
                  <p className="mt-3 text-2xl font-bold text-gray-900">전체 평균만 알아요</p>
                  <p className="mt-1 text-sm text-gray-500 sm:text-base">평균 등급 1개만 입력하면 빠르게 계산해드릴게요.</p>
                </div>
              </button>

              <button
                type="button"
                onClick={() => {
                    void captureBusinessEvent(TrackingEventNames.scoreInputModeSelected, {
                      category: 'engagement',
                      mode: 'semester',
                      source: 'school_grade_input_modal',
                    })
                    setSelectedInputChoice('semester')
                    setIsOverallEstimateSubmitted(false)
                    setIsOverallInputLeaving(false)
                    setHasCalculatedResult(false)
                    setIsInlineDetailVisible(false)
                    setIsEstimateToastVisible(false)
                }}
                className={`h-44 w-full rounded-3xl border-2 p-4 transition-all hover:scale-[1.01] hover:shadow-lg ${
                  selectedInputChoice === 'semester'
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-transparent bg-gray-50 hover:bg-gray-100'
                }`}
              >
                <div className="flex h-full flex-col items-center justify-center text-center">
                  <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-blue-600 shadow-sm">
                    <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.6} d="M5 7h14M5 12h14M5 17h14" />
                    </svg>
                  </div>
                  <p className="mt-3 text-2xl font-bold text-gray-900">학기별 성적을 알아요</p>
                  <p className="mt-1 text-sm text-gray-500 sm:text-base">6개 학기 평균을 바로 입력해서 더 정확히 볼 수 있어요.</p>
                </div>
              </button>
            </div>
          </section>

          {selectedInputChoice === 'overall' && (
            <section
              className={`mt-10 rounded-3xl bg-white p-5 shadow-sm transition-all duration-300 sm:p-8 ${
                isChoiceFormVisible ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
              }`}
            >
              <div className="mx-auto w-full max-w-5xl">
                <div
                  className={`transition-all duration-300 ${
                    isOverallEstimateSubmitted
                      ? 'pointer-events-none max-h-0 -translate-y-3 overflow-hidden opacity-0'
                      : isOverallInputLeaving
                        ? 'pointer-events-none max-h-[420px] -translate-y-2 opacity-0'
                        : 'max-h-[420px] translate-y-0 opacity-100'
                  }`}
                >
                  <div className="mx-auto flex w-full max-w-2xl flex-col items-center gap-10">
                    <label className="w-full text-center">
                      <span className="text-sm font-medium text-gray-500">님은 평균 몇 등급인가요?</span>
                      <input
                        value={quickAverageValue}
                        onChange={(e) => handleQuickAverageChange(e.target.value)}
                        inputMode="decimal"
                        placeholder="2.3"
                        className="mt-3 h-24 w-full rounded-3xl border border-gray-200 bg-white px-6 text-center text-5xl font-black tracking-tight text-gray-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100 sm:h-28 sm:text-6xl"
                      />
                    </label>

                    <button
                      type="button"
                      onClick={handleOverallEstimateSubmit}
                      disabled={isSaving}
                      className="inline-flex h-14 min-w-[260px] items-center justify-center rounded-2xl bg-[#1f3b61] px-8 text-base font-extrabold text-white transition-all hover:scale-[1.01] hover:bg-[#162b49] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {isSaving ? '저장 중...' : '이 성적으로 계산하기'}
                    </button>
                  </div>
                </div>

                <div
                  className={`transition-all duration-500 ${
                    isOverallEstimateSubmitted
                      ? 'max-h-[1200px] translate-y-0 opacity-100'
                      : 'max-h-0 translate-y-4 overflow-hidden opacity-0'
                  }`}
                >
                  <div className="grid gap-4 pt-2 md:grid-cols-2 lg:grid-cols-3">
                    {semesterKeys.map((semesterKey, index) => {
                      const semesterValue = data.gradeSummary.semesterAverages[semesterKey].overall
                      return (
                        <button
                          key={`estimated-semester-${semesterKey}`}
                          type="button"
                          onClick={() => {
                            setSubjectDetailSemester(semesterKey)
                            setSelectedSemester(semesterKey)
                            setIsInlineDetailVisible(true)
                          }}
                          className="rounded-3xl bg-white p-5 text-left shadow-sm transition-all duration-500 hover:scale-[1.01] hover:shadow-lg"
                          style={{ transitionDelay: `${70 + index * 40}ms` }}
                        >
                          <p className="text-xs font-semibold text-gray-500">{semesterLabels[semesterKey]}</p>
                          <div className="mt-2">
                            <CountUpGrade
                              value={semesterValue}
                              className="text-4xl font-black tracking-tight text-gray-900"
                            />
                          </div>
                          <p className="mt-2 text-xs text-gray-400">[자동 추산됨]</p>
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>
            </section>
          )}

          {selectedInputChoice === 'semester' && (
            <section
              className={`mt-10 rounded-3xl bg-white p-5 shadow-sm transition-all duration-300 sm:p-8 ${
                isChoiceFormVisible ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
              }`}
            >
              <div className="mx-auto flex w-full max-w-5xl flex-col items-center gap-10">
                <p className="text-sm font-medium text-gray-500">학기별 평균을 알려주시면 바로 반영할게요.</p>
                <div className="grid w-full gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {semesterKeys.map((semesterKey) => (
                    <label key={`semester-input-${semesterKey}`} className="rounded-3xl bg-gray-50 p-4">
                      <span className="text-xs font-semibold text-gray-500">{semesterLabels[semesterKey]}</span>
                      <input
                        value={data.gradeSummary.semesterAverages[semesterKey].overall}
                        onChange={(e) => handleSemesterModeAverageChange(semesterKey, e.target.value)}
                        onFocus={() => setSelectedSemester(semesterKey)}
                        inputMode="decimal"
                        placeholder="-"
                        className="mt-3 h-24 w-full rounded-3xl border border-gray-200 bg-white px-5 text-center text-5xl font-black tracking-tight text-gray-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                      />
                    </label>
                  ))}
                </div>

                <button
                  type="button"
                  onClick={handleSemesterEstimateSubmit}
                  disabled={isSaving}
                  className="inline-flex h-14 min-w-[260px] items-center justify-center rounded-2xl bg-[#1f3b61] px-8 text-base font-extrabold text-white transition-all hover:scale-[1.01] hover:bg-[#162b49] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? '저장 중...' : '이 성적으로 계산하기'}
                </button>
              </div>
            </section>
          )}

          {isInlineDetailVisible && (
            <section className="mt-10 rounded-3xl bg-white p-5 shadow-sm sm:p-6">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-black text-gray-900">과목별 상세 입력</p>
                  <p className="text-xs text-gray-500">여기서 바로 과목, 출결, 봉사까지 수정할 수 있어요.</p>
                </div>
                <button
                  type="button"
                  onClick={() => setIsInlineDetailVisible(false)}
                  className="inline-flex h-10 items-center justify-center rounded-xl bg-gray-100 px-3 text-xs font-bold text-gray-700 transition-colors hover:bg-gray-200"
                >
                  접기
                </button>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-3">
                {semesterKeys.map((semesterKey) => (
                  <button
                    key={`inline-detail-semester-${semesterKey}`}
                    type="button"
                    onClick={() => {
                      setSubjectDetailSemester(semesterKey)
                      setSelectedSemester(semesterKey)
                    }}
                    className={`h-11 w-full rounded-xl px-3 text-sm font-semibold transition-all hover:scale-[1.01] ${
                      subjectDetailSemester === semesterKey
                        ? 'bg-[#1f3b61] text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {semesterLabels[semesterKey]}
                  </button>
                ))}
              </div>

              <div className="mt-4 overflow-x-auto">
                <div className="min-w-[1120px] space-y-2">
                  <div className="grid grid-cols-[48px_1.2fr_1.2fr_1.4fr_0.7fr_0.8fr_0.8fr_0.7fr_0.8fr_0.8fr_0.8fr] gap-2 px-2 text-[11px] font-medium text-gray-400">
                    <span className="text-center">번호</span>
                    <span>교과구분</span>
                    <span>교과</span>
                    <span>과목명</span>
                    <span>단위수</span>
                    <span>원점수</span>
                    <span>성취도</span>
                    <span>석차등급</span>
                    <span>과목평균</span>
                    <span>표준편차</span>
                    <span>수강자수</span>
                  </div>

                  {subjectDetailRows.map((row, index) => {
                    const availableCurriculumOptions = getCurriculumOptions(row.trackType)
                    const availableSubjectOptions = getSubjectOptions(row.trackType, row.curriculum)
                    const hasCustomCurriculum = Boolean(row.curriculum) && !availableCurriculumOptions.includes(row.curriculum)
                    const hasCustomSubject = Boolean(row.subject) && !availableSubjectOptions.includes(row.subject)
                    const curriculumOptionsForRow = hasCustomCurriculum
                      ? [row.curriculum, ...availableCurriculumOptions]
                      : availableCurriculumOptions
                    const subjectOptionsForRow = hasCustomSubject
                      ? [row.subject, ...availableSubjectOptions]
                      : availableSubjectOptions
                    const cellClassName =
                      'h-11 w-full rounded-xl border border-transparent bg-white px-2.5 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20'
                    return (
                      <div
                        key={`inline-detail-row-${row.id}`}
                        className="grid grid-cols-[48px_1.2fr_1.2fr_1.4fr_0.7fr_0.8fr_0.8fr_0.7fr_0.8fr_0.8fr_0.8fr] gap-2 rounded-2xl bg-[#f5f7fb] p-2"
                      >
                        <div className="flex items-center justify-center text-sm font-bold text-gray-500">{index + 1}</div>
                        <select
                          value={row.trackType}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'trackType', e.target.value)}
                          className={cellClassName}
                        >
                          {trackTypeOptions.map((opt) => (
                            <option key={`${row.id}-inline-track-${opt}`} value={opt}>{opt}</option>
                          ))}
                        </select>
                        <select
                          value={row.curriculum}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'curriculum', e.target.value)}
                          className={cellClassName}
                        >
                          {curriculumOptionsForRow.map((opt) => (
                            <option key={`${row.id}-inline-curriculum-${opt}`} value={opt}>{opt}</option>
                          ))}
                        </select>
                        <select
                          value={row.subject}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'subject', e.target.value)}
                          className={cellClassName}
                        >
                          <option value="">과목 선택</option>
                          {subjectOptionsForRow.map((opt) => (
                            <option key={`${row.id}-inline-subject-${opt}`} value={opt}>{opt}</option>
                          ))}
                        </select>
                        <input
                          value={row.credits}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'credits', e.target.value)}
                          inputMode="numeric"
                          className={cellClassName}
                        />
                        <input
                          value={row.rawScore}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'rawScore', e.target.value)}
                          inputMode="numeric"
                          className={cellClassName}
                        />
                        <select
                          value={row.achievement}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'achievement', e.target.value)}
                          className={cellClassName}
                        >
                          {achievementOptions.map((opt) => (
                            <option key={`${row.id}-inline-achievement-${opt}`} value={opt}>{opt}</option>
                          ))}
                        </select>
                        <input
                          value={row.classRank}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'classRank', e.target.value)}
                          inputMode="numeric"
                          className={cellClassName}
                        />
                        <input
                          value={row.avgScore}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'avgScore', e.target.value)}
                          inputMode="numeric"
                          className={cellClassName}
                        />
                        <input
                          value={row.stdDev}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'stdDev', e.target.value)}
                          inputMode="numeric"
                          className={cellClassName}
                        />
                        <input
                          value={row.studentCount}
                          onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'studentCount', e.target.value)}
                          inputMode="numeric"
                          className={cellClassName}
                        />
                      </div>
                    )
                  })}
                </div>
              </div>

              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="rounded-2xl bg-gray-50 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-bold text-gray-900">출결</p>
                    <p className="text-xs font-semibold text-gray-500">총 {attendanceGrandTotal}일</p>
                  </div>
                  <div className="mt-3 grid grid-cols-5 gap-2 text-[11px] text-gray-400">
                    <span>학년</span>
                    <span>결석</span>
                    <span>지각</span>
                    <span>조퇴</span>
                    <span>결과</span>
                  </div>
                  <div className="mt-2 space-y-2">
                    {gradeKeys.map((grade) => (
                      <div key={`inline-attendance-${grade}`} className="grid grid-cols-5 gap-2 rounded-xl bg-white p-2">
                        <div className="flex items-center text-sm font-semibold text-gray-700">{grade}학년</div>
                        <input value={data.extracurricular.attendance[grade].absence} onChange={(e) => updateAttendanceField(grade, 'absence', e.target.value)} inputMode="numeric" className="h-10 rounded-xl border border-gray-100 px-2 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                        <input value={data.extracurricular.attendance[grade].tardy} onChange={(e) => updateAttendanceField(grade, 'tardy', e.target.value)} inputMode="numeric" className="h-10 rounded-xl border border-gray-100 px-2 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                        <input value={data.extracurricular.attendance[grade].earlyLeave} onChange={(e) => updateAttendanceField(grade, 'earlyLeave', e.target.value)} inputMode="numeric" className="h-10 rounded-xl border border-gray-100 px-2 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                        <input value={data.extracurricular.attendance[grade].result} onChange={(e) => updateAttendanceField(grade, 'result', e.target.value)} inputMode="numeric" className="h-10 rounded-xl border border-gray-100 px-2 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl bg-gray-50 p-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-bold text-gray-900">봉사</p>
                    <p className="text-xs font-semibold text-gray-500">총 {volunteerTotal}시간</p>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-gray-400">
                    <span>학년</span>
                    <span>시간</span>
                  </div>
                  <div className="mt-2 space-y-2">
                    {gradeKeys.map((grade) => (
                      <div key={`inline-volunteer-${grade}`} className="grid grid-cols-2 gap-2 rounded-xl bg-white p-2">
                        <div className="flex items-center text-sm font-semibold text-gray-700">{grade}학년</div>
                        <input value={data.extracurricular.volunteerHours[grade]} onChange={(e) => updateVolunteerHours(grade, e.target.value)} inputMode="numeric" className="h-10 rounded-xl border border-gray-100 px-2 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => addSemesterRow(subjectDetailSemester, 1)}
                  className="inline-flex h-11 items-center justify-center rounded-xl border border-gray-200 bg-white px-4 text-sm font-bold text-gray-700 transition-colors hover:bg-gray-50"
                >
                  + 과목 한 줄 더 추가
                </button>
                <button
                  type="button"
                  onClick={handleSaveAll}
                  disabled={isSaving}
                  className="inline-flex h-12 min-w-[220px] items-center justify-center rounded-xl bg-[#1f3b61] px-6 text-base font-extrabold text-white transition-colors hover:bg-[#162b49] disabled:opacity-60"
                >
                  {isSaving ? '저장 중...' : '상세 입력 저장하기'}
                </button>
              </div>
            </section>
          )}

          <div
            className={`fixed bottom-5 left-1/2 z-[92] w-[calc(100%-24px)] max-w-xl -translate-x-1/2 transition-all duration-300 ${
              isEstimateToastVisible
                ? 'translate-y-0 opacity-100'
                : 'pointer-events-none translate-y-3 opacity-0'
            }`}
          >
            <div className="rounded-2xl border border-gray-200 bg-white/95 p-3 shadow-lg backdrop-blur">
              <p className="text-xs font-semibold text-gray-700">내신 성적이 반영되었어요</p>
              <p className="mt-0.5 text-[11px] text-gray-500">입력하신 평균으로 학기별 성적을 추산했어요</p>
              <button
                type="button"
                onClick={() => {
                  setIsEstimateToastVisible(false)
                  void captureBusinessEvent(TrackingEventNames.scoreRecommendationRequested, {
                    category: 'engagement',
                    source: 'naesin_toast',
                  })
                  onUseNaesinSuggestion?.(NAESIN_SCHOOL_RECOMMEND_MENTION)
                }}
                className="mt-2 inline-flex h-9 items-center justify-center rounded-xl bg-[#1f3b61] px-3 text-xs font-bold text-white transition-colors hover:bg-[#162b49]"
              >
                @내신 성적 학교 추천
              </button>
            </div>
          </div>
            </div>
          </div>

        {isGradeReportModalOpen && (
          <div className="fixed inset-0 z-[94]">
            <div
              className="absolute inset-0 bg-black/45 backdrop-blur-[2px]"
              onClick={() => setIsGradeReportModalOpen(false)}
              aria-hidden
            />
            <div className="relative mx-auto flex h-full w-full max-w-4xl flex-col bg-gray-50">
              <div className="border-b border-gray-200 bg-white px-4 py-4 sm:px-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-lg font-black text-gray-900 sm:text-xl">나의 성적표</p>
                    <p className="text-xs text-gray-500">입력한 과목을 학기별 카드로 한눈에 볼 수 있어요.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsGradeReportModalOpen(false)}
                    className="inline-flex h-11 min-h-[44px] items-center justify-center rounded-xl border border-gray-200 bg-white px-4 text-sm font-bold text-gray-700 transition hover:bg-gray-100"
                    aria-label="닫기"
                  >
                    닫기
                  </button>
                </div>

                <div className="mt-3 rounded-3xl bg-gray-50 px-4 py-3">
                  <p className="text-[11px] font-medium text-gray-500">전체 평균 등급</p>
                  <CountUpGrade
                    value={data.gradeSummary.overallAverage}
                    className="mt-1 text-4xl font-black tracking-tight text-gray-900 sm:text-5xl"
                  />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
                <div className="mb-4 flex flex-wrap gap-2">
                  {semesterKeys.map((semesterKey) => (
                    <button
                      key={`report-tab-${semesterKey}`}
                      type="button"
                      onClick={() => setReportSemester(semesterKey)}
                      className={`h-10 rounded-xl px-3 text-sm font-semibold transition-colors ${
                        reportSemester === semesterKey
                          ? 'bg-[#1f3b61] text-white'
                          : 'bg-white text-gray-600 hover:bg-gray-100'
                      }`}
                    >
                      {semesterLabels[semesterKey]}
                    </button>
                  ))}
                </div>

                {(() => {
                  const rows = reportRowsBySemester[reportSemester] || []
                  const semesterAverage = data.gradeSummary.semesterAverages[reportSemester].overall
                  return (
                    <section className="rounded-3xl bg-white p-4 shadow-sm sm:p-5">
                      <div className="flex items-end justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-gray-900">{semesterLabels[reportSemester]}</p>
                          <p className="text-xs text-gray-400">입력된 과목 {rows.length}개</p>
                        </div>
                        <div className="text-right">
                          <p className="text-[11px] font-medium text-gray-500">학기 평균</p>
                          <CountUpGrade
                            value={semesterAverage}
                            className="text-2xl font-black tracking-tight text-gray-900"
                          />
                        </div>
                      </div>

                      {rows.length === 0 ? (
                        <div className="mt-3 rounded-2xl bg-gray-50 px-4 py-3 text-xs text-gray-500">
                          이 학기는 아직 입력한 과목이 없어요.
                        </div>
                      ) : (
                        <div className="mt-3 space-y-2">
                          {rows.map((row, index) => (
                            <article key={`report-row-${reportSemester}-${row.id}`} className="rounded-2xl bg-gray-50 p-3">
                              <div className="flex items-start justify-between gap-2">
                                <div>
                                  <p className="text-sm font-bold text-gray-900">{row.subject.trim() || `과목 ${index + 1}`}</p>
                                  <p className="text-xs text-gray-400">{row.curriculum || '교과 미설정'} · {row.trackType}</p>
                                </div>
                                <span className="text-[11px] font-medium text-gray-400">
                                  {row.achievement && row.achievement !== '선택' ? `성취도 ${row.achievement}` : '성취도 -'}
                                </span>
                              </div>

                              <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">
                                <div className="rounded-xl bg-white px-2.5 py-2">
                                  <p className="text-[10px] text-gray-400">단위수</p>
                                  <p className="text-sm font-black text-gray-900">{row.credits || '-'}</p>
                                </div>
                                <div className="rounded-xl bg-white px-2.5 py-2">
                                  <p className="text-[10px] text-gray-400">석차등급</p>
                                  <p className="text-sm font-black text-gray-900">{row.classRank || '-'}</p>
                                </div>
                                <div className="rounded-xl bg-white px-2.5 py-2">
                                  <p className="text-[10px] text-gray-400">원점수</p>
                                  <p className="text-sm font-black text-gray-900">{row.rawScore || '-'}</p>
                                </div>
                                <div className="rounded-xl bg-white px-2.5 py-2">
                                  <p className="text-[10px] text-gray-400">과목평균</p>
                                  <p className="text-sm font-black text-gray-900">{row.avgScore || '-'}</p>
                                </div>
                                <div className="rounded-xl bg-white px-2.5 py-2">
                                  <p className="text-[10px] text-gray-400">표준편차</p>
                                  <p className="text-sm font-black text-gray-900">{row.stdDev || '-'}</p>
                                </div>
                                <div className="rounded-xl bg-white px-2.5 py-2">
                                  <p className="text-[10px] text-gray-400">수강자수</p>
                                  <p className="text-sm font-black text-gray-900">{row.studentCount || '-'}</p>
                                </div>
                              </div>
                            </article>
                          ))}
                        </div>
                      )}
                    </section>
                  )
                })()}
              </div>

              <div className="border-t border-gray-200 bg-white px-4 py-4 sm:px-6">
                <button
                  type="button"
                  onClick={() => setIsGradeReportModalOpen(false)}
                  className="inline-flex h-12 w-full items-center justify-center rounded-2xl bg-[#1f3b61] px-6 text-base font-bold text-white transition-colors hover:bg-[#162b49]"
                >
                  닫기
                </button>
              </div>
            </div>
          </div>
        )}

        {isSubjectDetailModalOpen && (
          <div className="fixed inset-0 z-[95]">
            <div
              className="absolute inset-0 bg-black/55 backdrop-blur-[2px]"
              onClick={() => setIsSubjectDetailModalOpen(false)}
              aria-hidden
            />
            <div className="relative h-full w-full bg-gray-50">
              <div className="flex h-full flex-col">
                <div className="border-b border-gray-200 bg-white px-4 py-4 sm:px-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-lg font-black text-gray-900">{semesterLabels[subjectDetailSemester]} 성적을 입력해주세요</p>
                      <p className="text-xs text-gray-500">숫자를 바꾸면 평균이 바로 업데이트돼요.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setIsSubjectDetailModalOpen(false)}
                      className="flex h-10 w-10 items-center justify-center rounded-xl text-gray-500 transition hover:bg-gray-100 hover:text-gray-700"
                      aria-label="닫기"
                    >
                      <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <div className="rounded-xl bg-gray-50 px-3 py-2">
                      <p className="text-[11px] font-medium text-gray-500">전체 평균</p>
                      <CountUpGrade
                        value={data.gradeSummary.overallAverage}
                        className="mt-1 text-2xl font-black tracking-tight text-gray-900"
                      />
                    </div>
                    <div className="rounded-xl bg-gray-50 px-3 py-2">
                      <p className="text-[11px] font-medium text-gray-500">{semesterLabels[subjectDetailSemester]} 평균</p>
                      <CountUpGrade
                        value={data.gradeSummary.semesterAverages[subjectDetailSemester].overall}
                        className="mt-1 text-2xl font-black tracking-tight text-gray-900"
                      />
                    </div>
                  </div>
                </div>

                <div className="flex-1 overflow-auto px-4 py-4 sm:px-6">
                  <div className="flex flex-wrap gap-2">
                    {semesterKeys.map((semesterKey) => (
                      <button
                        key={`detail-semester-${semesterKey}`}
                        type="button"
                        onClick={() => {
                          setSubjectDetailSemester(semesterKey)
                          setSelectedSemester(semesterKey)
                        }}
                        className={`h-10 rounded-xl px-3 text-sm font-semibold transition-colors ${
                          subjectDetailSemester === semesterKey
                            ? 'bg-[#1f3b61] text-white'
                            : 'bg-white text-gray-600 hover:bg-gray-100'
                        }`}
                      >
                        {semesterLabels[semesterKey]}
                      </button>
                    ))}
                  </div>

                  <div className="mt-4 space-y-2">
                    <div className="grid grid-cols-[48px_1.2fr_1.2fr_1.4fr_0.7fr_0.8fr_0.8fr_0.7fr_0.8fr_0.8fr_0.8fr] gap-2 px-2 text-[11px] font-medium text-gray-400">
                      <span className="text-center">번호</span>
                      <span>교과구분</span>
                      <span>교과</span>
                      <span>과목명</span>
                      <span>단위수</span>
                      <span>원점수</span>
                      <span>성취도</span>
                      <span>석차등급</span>
                      <span>과목평균</span>
                      <span>표준편차</span>
                      <span>수강자수</span>
                    </div>

                    {subjectDetailRows.map((row, index) => {
                      const availableCurriculumOptions = getCurriculumOptions(row.trackType)
                      const availableSubjectOptions = getSubjectOptions(row.trackType, row.curriculum)
                      const hasCustomCurriculum = Boolean(row.curriculum) && !availableCurriculumOptions.includes(row.curriculum)
                      const hasCustomSubject = Boolean(row.subject) && !availableSubjectOptions.includes(row.subject)
                      const curriculumOptionsForRow = hasCustomCurriculum
                        ? [row.curriculum, ...availableCurriculumOptions]
                        : availableCurriculumOptions
                      const subjectOptionsForRow = hasCustomSubject
                        ? [row.subject, ...availableSubjectOptions]
                        : availableSubjectOptions
                      const cellClassName =
                        'h-11 w-full rounded-xl border border-transparent bg-white px-2.5 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20'
                      return (
                        <div
                          key={`detail-row-${row.id}`}
                          className="grid grid-cols-[48px_1.2fr_1.2fr_1.4fr_0.7fr_0.8fr_0.8fr_0.7fr_0.8fr_0.8fr_0.8fr] gap-2 rounded-2xl bg-[#f5f7fb] p-2"
                        >
                          <div className="flex items-center justify-center text-sm font-bold text-gray-500">{index + 1}</div>
                          <select
                            value={row.trackType}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'trackType', e.target.value)}
                            className={cellClassName}
                          >
                            {trackTypeOptions.map((opt) => (
                              <option key={`${row.id}-track-${opt}`} value={opt}>{opt}</option>
                            ))}
                          </select>
                          <select
                            value={row.curriculum}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'curriculum', e.target.value)}
                            className={cellClassName}
                          >
                            {curriculumOptionsForRow.map((opt) => (
                              <option key={`${row.id}-curriculum-${opt}`} value={opt}>{opt}</option>
                            ))}
                          </select>
                          <select
                            value={row.subject}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'subject', e.target.value)}
                            className={cellClassName}
                          >
                            <option value="">과목 선택</option>
                            {subjectOptionsForRow.map((opt) => (
                              <option key={`${row.id}-subject-${opt}`} value={opt}>{opt}</option>
                            ))}
                          </select>
                          <input
                            value={row.credits}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'credits', e.target.value)}
                            inputMode="numeric"
                            className={cellClassName}
                          />
                          <input
                            value={row.rawScore}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'rawScore', e.target.value)}
                            inputMode="numeric"
                            className={cellClassName}
                          />
                          <select
                            value={row.achievement}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'achievement', e.target.value)}
                            className={cellClassName}
                          >
                            {achievementOptions.map((opt) => (
                              <option key={`${row.id}-achievement-${opt}`} value={opt}>{opt}</option>
                            ))}
                          </select>
                          <input
                            value={row.classRank}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'classRank', e.target.value)}
                            inputMode="numeric"
                            className={cellClassName}
                          />
                          <input
                            value={row.avgScore}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'avgScore', e.target.value)}
                            inputMode="numeric"
                            className={cellClassName}
                          />
                          <input
                            value={row.stdDev}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'stdDev', e.target.value)}
                            inputMode="numeric"
                            className={cellClassName}
                          />
                          <input
                            value={row.studentCount}
                            onChange={(e) => updateSemesterRow(subjectDetailSemester, row.id, 'studentCount', e.target.value)}
                            inputMode="numeric"
                            className={cellClassName}
                          />
                        </div>
                      )
                    })}
                  </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="rounded-2xl bg-white p-4">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-bold text-gray-900">출결도 같이 입력할까요?</p>
                        <p className="text-xs font-semibold text-gray-500">총 {attendanceGrandTotal}일</p>
                      </div>
                      <div className="mt-3 grid grid-cols-5 gap-2 text-[11px] text-gray-400">
                        <span>학년</span>
                        <span>결석</span>
                        <span>지각</span>
                        <span>조퇴</span>
                        <span>결과</span>
                      </div>
                      <div className="mt-2 space-y-2">
                        {gradeKeys.map((grade) => (
                          <div key={`detail-attendance-${grade}`} className="grid grid-cols-5 gap-2 rounded-xl bg-[#f5f7fb] p-2">
                            <div className="flex items-center text-sm font-semibold text-gray-700">{grade}학년</div>
                            <input value={data.extracurricular.attendance[grade].absence} onChange={(e) => updateAttendanceField(grade, 'absence', e.target.value)} inputMode="numeric" className="h-11 rounded-xl border border-transparent bg-white px-2.5 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                            <input value={data.extracurricular.attendance[grade].tardy} onChange={(e) => updateAttendanceField(grade, 'tardy', e.target.value)} inputMode="numeric" className="h-11 rounded-xl border border-transparent bg-white px-2.5 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                            <input value={data.extracurricular.attendance[grade].earlyLeave} onChange={(e) => updateAttendanceField(grade, 'earlyLeave', e.target.value)} inputMode="numeric" className="h-11 rounded-xl border border-transparent bg-white px-2.5 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                            <input value={data.extracurricular.attendance[grade].result} onChange={(e) => updateAttendanceField(grade, 'result', e.target.value)} inputMode="numeric" className="h-11 rounded-xl border border-transparent bg-white px-2.5 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="rounded-2xl bg-white p-4">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-bold text-gray-900">봉사 시간도 같이 적어둘까요?</p>
                        <p className="text-xs font-semibold text-gray-500">총 {volunteerTotal}시간</p>
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-gray-400">
                        <span>학년</span>
                        <span>시간</span>
                      </div>
                      <div className="mt-2 space-y-2">
                        {gradeKeys.map((grade) => (
                          <div key={`detail-volunteer-${grade}`} className="grid grid-cols-2 gap-2 rounded-xl bg-[#f5f7fb] p-2">
                            <div className="flex items-center text-sm font-semibold text-gray-700">{grade}학년</div>
                            <input value={data.extracurricular.volunteerHours[grade]} onChange={(e) => updateVolunteerHours(grade, e.target.value)} inputMode="numeric" className="h-11 rounded-xl border border-transparent bg-white px-2.5 text-sm font-semibold text-gray-900 outline-none transition focus:border-[#1f3b61]/40 focus:ring-2 focus:ring-[#1f3b61]/20" />
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>

                <div className="border-t border-gray-200 bg-white px-4 py-4 sm:px-6">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => addSemesterRow(subjectDetailSemester, 1)}
                      className="inline-flex h-11 items-center justify-center rounded-xl border border-gray-200 bg-white px-4 text-sm font-bold text-gray-700 transition-colors hover:bg-gray-50"
                    >
                      + 과목 한 줄 더 추가
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        handleSaveAll()
                        setIsSubjectDetailModalOpen(false)
                      }}
                      disabled={isSaving}
                      className="inline-flex h-12 min-w-[220px] items-center justify-center rounded-xl bg-[#1f3b61] px-6 text-base font-extrabold text-white transition-colors hover:bg-[#162b49] disabled:opacity-60"
                    >
                      {isSaving ? '저장 중...' : '저장하고 닫기'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
    )
  }

  // 모달 모드 (기존 UI 유지)
  return (
    <div className='fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4'>
      <div className='w-full max-w-[1240px] max-h-[92vh] overflow-y-auto rounded-3xl border border-gray-300 bg-[#f7f8fa] shadow-2xl'>
        <div className="sticky top-0 z-10 border-b border-gray-300 bg-[#f7f8fa] px-6 py-4">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-gray-900 md:text-3xl">{step === 'menu' ? '성적입력' : '학생부 성적입력'}</h2>
            <button
              onClick={onClose}
              className="rounded-full px-2 text-4xl leading-none text-gray-500 transition-colors hover:bg-gray-200 hover:text-gray-700"
              aria-label="닫기"
            >
              ×
            </button>
          </div>
        </div>

        <div className="px-6 pb-6 pt-5">
          {message && (
            <div className="mb-4 rounded-xl border border-[#0e6093]/20 bg-[#0e6093]/10 px-4 py-3 text-sm font-medium text-[#0e6093]">
              {message}
            </div>
          )}

          {step === 'menu' && (
            <div className="space-y-4">
              <div className="rounded-xl border border-[#0e6093]/25 bg-white px-4 py-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">생기부 연동으로 자동으로 입력하기</p>
                    <p className="mt-1 text-xs text-gray-600">연동된 생기부 정보를 불러와 교과/비교과 입력 칸을 자동으로 채웁니다.</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void autofillFromLinkedSchoolRecord({ redirectIfNotLinked: true, persistAfterFill: true })}
                    disabled={isAutofillLoading}
                    className="inline-flex h-9 items-center justify-center rounded-lg bg-[#0e6093] px-4 text-sm font-semibold text-white transition-colors hover:bg-[#0b4f77] disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isAutofillLoading ? '연동 중...' : '자동으로 입력하기'}
                  </button>
                </div>
              </div>

              {semesterSections.map((section) => (
                <div key={section.title}>
                  <h3 className="mb-2 text-xl font-bold text-gray-900">{section.title}</h3>
                  <div className="space-y-2.5">
                    {section.semesters.map((semester) => (
                      <button
                        key={semester}
                        onClick={() => {
                          setSelectedSemester(semester)
                          setStep('semester')
                          setMessage('')
                        }}
                        className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-center text-xl font-semibold text-gray-800 transition-colors hover:border-[#0e6093]/35 hover:bg-[#eef5fb]"
                      >
                        {semesterLabels[semester]} 입력
                      </button>
                    ))}
                  </div>
                </div>
              ))}

              <div>
                <h3 className="mb-2 text-xl font-bold text-gray-900">비교과</h3>
                <button
                  onClick={() => {
                    setStep('extracurricular')
                    setMessage('')
                  }}
                  className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-center text-xl font-semibold text-gray-800 transition-colors hover:border-[#0e6093]/35 hover:bg-[#eef5fb]"
                >
                  입력
                </button>
              </div>

              <div>
                <h3 className="mb-2 text-xl font-bold text-gray-900">학생부 성적 업로드</h3>
                <button
                  onClick={() => {
                    setStep('record_upload')
                    setMessage('')
                  }}
                  className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-center text-xl font-semibold text-gray-800 transition-colors hover:border-[#0e6093]/35 hover:bg-[#eef5fb]"
                >
                  입력
                </button>
              </div>

              {onOpenMockExamInput && (
                <div>
                  <h3 className="mb-2 text-xl font-bold text-gray-900">정시 / 모의고사 성적</h3>
                  <button
                    onClick={() => {
                      onClose()
                      onOpenMockExamInput()
                    }}
                    className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-center text-xl font-semibold text-gray-800 transition-colors hover:border-[#0e6093]/35 hover:bg-[#eef5fb]"
                  >
                    모의고사 성적 입력하기
                  </button>
                </div>
              )}
            </div>
          )}

          {step === 'semester' && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-gray-300 bg-white p-5">
                <p className="mb-4 flex items-start gap-2 text-lg font-semibold text-gray-700 sm:text-xl">
                  <span className="text-red-500">ⓘ</span>
                  <span>입력이 안되거나 과목수가 충분하지 않은 경우 다른 성적을 참조하게 되므로 정확도가 떨어집니다</span>
                </p>

                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <select
                    value={selectedSemester}
                    onChange={(e) => setSelectedSemester(e.target.value as SemesterKey)}
                    className="h-12 rounded-xl border border-gray-300 bg-white px-4 text-lg font-semibold text-gray-700"
                  >
                    {(Object.keys(semesterLabels) as SemesterKey[]).map((key) => (
                      <option key={key} value={key}>{semesterLabels[key]}</option>
                    ))}
                  </select>

                  <select
                    value={selectedSchoolYear}
                    onChange={(e) => setSelectedSchoolYear(e.target.value)}
                    className="h-12 rounded-xl border border-gray-300 bg-white px-4 text-lg font-semibold text-gray-700"
                  >
                    {schoolYearOptions.map((year) => (
                      <option key={year} value={year}>{year}</option>
                    ))}
                  </select>
                </div>

                <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                  <button
                    onClick={() => {
                      addSemesterRow(selectedSemester, 3)
                      setMessage('3개 과목 입력 행을 추가했습니다.')
                    }}
                    className="h-11 rounded-full bg-[#0e8098] px-5 text-lg font-bold text-white hover:bg-[#0d7288]"
                  >
                    여러 과목 추가하기
                  </button>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setMessage('수정은 표에서 직접 입력하면 바로 반영됩니다.')}
                      className="h-11 rounded-full border border-gray-300 bg-white px-4 text-lg font-semibold text-gray-700 hover:bg-gray-50"
                    >
                      수정
                    </button>
                    <button
                      onClick={() => addSemesterRow(selectedSemester, 1)}
                      className="h-11 w-11 rounded-lg border border-gray-300 bg-white text-3xl leading-none text-gray-700 hover:bg-gray-50"
                    >
                      +
                    </button>
                  </div>
                </div>

                <div className="overflow-x-auto rounded-xl border border-gray-300">
                  <table className="min-w-[1320px] w-full border-collapse bg-white">
                    <thead>
                      <tr className="bg-[#f2f4f7] text-center text-sm font-bold text-gray-800 lg:text-base">
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>번호</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>교과종류 구분</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>교과</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>과목</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>단위수</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>석차등급</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>원점수</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>과목평균</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>표준편차</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>수강자수</th>
                        <th className="border border-gray-300 px-2 py-3" rowSpan={2}>성취도</th>
                        <th className="border border-gray-300 px-2 py-3" colSpan={3}>성취도별 분포</th>
                      </tr>
                      <tr className="bg-[#f2f4f7] text-center text-sm font-bold text-gray-800 lg:text-base">
                        <th className="border border-gray-300 px-2 py-3">A</th>
                        <th className="border border-gray-300 px-2 py-3">B</th>
                        <th className="border border-gray-300 px-2 py-3">C</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentSemesterRows.map((row, index) => {
                        const availableCurriculumOptions = getCurriculumOptions(row.trackType)
                        const availableSubjectOptions = getSubjectOptions(row.trackType, row.curriculum)
                        const hasCustomCurriculum = Boolean(row.curriculum) && !availableCurriculumOptions.includes(row.curriculum)
                        const hasCustomSubject = Boolean(row.subject) && !availableSubjectOptions.includes(row.subject)
                        const curriculumOptionsForRow = hasCustomCurriculum
                          ? [row.curriculum, ...availableCurriculumOptions]
                          : availableCurriculumOptions
                        const subjectOptionsForRow = hasCustomSubject
                          ? [row.subject, ...availableSubjectOptions]
                          : availableSubjectOptions

                        return (
                          <tr key={row.id} className="text-sm text-gray-800 lg:text-base">
                          <td className="border border-gray-300 px-2 py-2 text-center">{index + 1}</td>

                          <td className="border border-gray-300 px-2 py-2">
                            <ScrollableSelect
                              value={row.trackType}
                              options={trackTypeOptions}
                              onChange={(nextValue) => updateSemesterRow(selectedSemester, row.id, 'trackType', nextValue)}
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <ScrollableSelect
                              value={row.curriculum}
                              options={curriculumOptionsForRow}
                              onChange={(nextValue) => updateSemesterRow(selectedSemester, row.id, 'curriculum', nextValue)}
                              minPanelWidth={320}
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <ScrollableSelect
                              value={row.subject}
                              options={subjectOptionsForRow}
                              onChange={(nextValue) => updateSemesterRow(selectedSemester, row.id, 'subject', nextValue)}
                              minPanelWidth={360}
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <input
                              value={row.credits}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'credits', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <input
                              value={row.classRank}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'classRank', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <input
                              value={row.rawScore}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'rawScore', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <input
                              value={row.avgScore}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'avgScore', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <input
                              value={row.stdDev}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'stdDev', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <input
                              value={row.studentCount}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'studentCount', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <select
                              value={row.achievement}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'achievement', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            >
                              {achievementOptions.map((opt) => (
                                <option key={opt} value={opt}>{opt}</option>
                              ))}
                            </select>
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <input
                              value={row.distA}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'distA', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <input
                              value={row.distB}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'distB', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            />
                          </td>

                          <td className="border border-gray-300 px-2 py-2">
                            <input
                              value={row.distC}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'distC', e.target.value)}
                              className="h-10 w-full rounded-md border border-gray-300 px-2"
                            />
                          </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="flex justify-center gap-3 pt-1">
                <button
                  onClick={handleSemesterCancel}
                  className="h-12 min-w-[200px] rounded-2xl bg-[#cfd6db] px-6 text-xl font-bold text-gray-700 hover:bg-[#bec7cd]"
                >
                  취소
                </button>
                <button
                  onClick={handleSemesterSave}
                  disabled={isSaving}
                  className="h-12 min-w-[200px] rounded-2xl bg-[#0e8098] px-6 text-xl font-bold text-white hover:bg-[#0d7288] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? '저장 중...' : '전체 저장'}
                </button>
              </div>
            </div>
          )}

          {step === 'extracurricular' && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-gray-300 bg-white p-5">
                <p className="mb-5 flex items-start gap-2 text-2xl font-semibold text-gray-700">
                  <span className="text-red-500">ⓘ</span>
                  <span>입력이 안되거나 과목수가 충분하지 않은 경우 다른 성적을 참조하게 되므로 정확도가 떨어집니다</span>
                </p>

                <div className="grid gap-6 xl:grid-cols-[2.6fr_1fr]">
                  <div>
                    <h3 className="mb-3 text-3xl font-bold text-gray-900 md:text-4xl">출결사항</h3>
                    <div className="overflow-x-auto rounded-xl border border-gray-300">
                      <table className="min-w-[760px] w-full border-collapse bg-white text-lg">
                        <thead>
                          <tr className="bg-[#f2f4f7] text-center font-bold text-gray-800">
                            <th className="border border-gray-300 px-3 py-3">학년</th>
                            <th className="border border-gray-300 px-3 py-3">무단(미인정) 결석</th>
                            <th className="border border-gray-300 px-3 py-3">무단(미인정) 지각</th>
                            <th className="border border-gray-300 px-3 py-3">무단(미인정) 조퇴</th>
                            <th className="border border-gray-300 px-3 py-3">무단(미인정) 결과</th>
                            <th className="border border-gray-300 px-3 py-3">
                              <span className="inline-flex items-center gap-2">
                                합계
                                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-gray-300 text-sm text-gray-500">?</span>
                              </span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {gradeKeys.map((grade) => (
                            <tr key={`attendance-${grade}`} className="text-center text-gray-800">
                              <td className="border border-gray-300 px-3 py-3 text-3xl font-semibold">{grade}</td>
                              <td className="border border-gray-300 px-3 py-3">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.attendance[grade].absence}
                                  onChange={(e) => updateAttendanceField(grade, 'absence', e.target.value)}
                                  className="h-11 w-full rounded-xl border border-gray-300 px-3 text-center text-xl"
                                />
                              </td>
                              <td className="border border-gray-300 px-3 py-3">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.attendance[grade].tardy}
                                  onChange={(e) => updateAttendanceField(grade, 'tardy', e.target.value)}
                                  className="h-11 w-full rounded-xl border border-gray-300 px-3 text-center text-xl"
                                />
                              </td>
                              <td className="border border-gray-300 px-3 py-3">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.attendance[grade].earlyLeave}
                                  onChange={(e) => updateAttendanceField(grade, 'earlyLeave', e.target.value)}
                                  className="h-11 w-full rounded-xl border border-gray-300 px-3 text-center text-xl"
                                />
                              </td>
                              <td className="border border-gray-300 px-3 py-3">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.attendance[grade].result}
                                  onChange={(e) => updateAttendanceField(grade, 'result', e.target.value)}
                                  className="h-11 w-full rounded-xl border border-gray-300 px-3 text-center text-xl"
                                />
                              </td>
                              <td className="border border-gray-300 px-3 py-3 text-3xl font-semibold text-gray-700">
                                {attendanceTotalsByGrade[grade]}
                              </td>
                            </tr>
                          ))}
                          <tr className="bg-[#f7f8fa] text-center font-semibold text-gray-700">
                            <td className="border border-gray-300 px-3 py-3 text-xl">전학년</td>
                            <td className="border border-gray-300 px-3 py-3 text-xl">{attendanceColumnTotals.absence}</td>
                            <td className="border border-gray-300 px-3 py-3 text-xl">{attendanceColumnTotals.tardy}</td>
                            <td className="border border-gray-300 px-3 py-3 text-xl">{attendanceColumnTotals.earlyLeave}</td>
                            <td className="border border-gray-300 px-3 py-3 text-xl">{attendanceColumnTotals.result}</td>
                            <td className="border border-gray-300 px-3 py-3 text-xl">{attendanceGrandTotal}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div>
                    <h3 className="mb-3 text-3xl font-bold text-gray-900 md:text-4xl">봉사활동</h3>
                    <div className="overflow-x-auto rounded-xl border border-gray-300">
                      <table className="min-w-[320px] w-full border-collapse bg-white text-lg">
                        <thead>
                          <tr className="bg-[#f2f4f7] text-center font-bold text-gray-800">
                            <th className="border border-gray-300 px-3 py-3">학년</th>
                            <th className="border border-gray-300 px-3 py-3">시간</th>
                          </tr>
                        </thead>
                        <tbody>
                          {gradeKeys.map((grade) => (
                            <tr key={`volunteer-${grade}`} className="text-center text-gray-800">
                              <td className="border border-gray-300 px-3 py-3 text-3xl font-semibold">{grade}</td>
                              <td className="border border-gray-300 px-3 py-3">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.volunteerHours[grade]}
                                  onChange={(e) => updateVolunteerHours(grade, e.target.value)}
                                  className="h-11 w-full rounded-xl border border-gray-300 px-3 text-center text-xl"
                                />
                              </td>
                            </tr>
                          ))}
                          <tr className="bg-[#f7f8fa] text-center font-semibold text-gray-700">
                            <td className="border border-gray-300 px-3 py-3 text-xl">전학년</td>
                            <td className="border border-gray-300 px-3 py-3 text-xl">{volunteerTotal}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>

              <div className="flex justify-center gap-3 pt-1">
                <button
                  onClick={handleExtracurricularCancel}
                  className="h-12 min-w-[200px] rounded-2xl bg-[#cfd6db] px-6 text-xl font-bold text-gray-700 hover:bg-[#bec7cd]"
                >
                  취소
                </button>
                <button
                  onClick={handleExtracurricularSave}
                  disabled={isSaving}
                  className="h-12 min-w-[200px] rounded-2xl bg-[#0e8098] px-6 text-xl font-bold text-white hover:bg-[#0d7288] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? '저장 중...' : '전체 저장'}
                </button>
              </div>
            </div>
          )}

          {step === 'record_upload' && (
            <div className="space-y-4">
              <h3 className="text-xl font-bold text-gray-900">학생부 성적 업로드 정보</h3>
              <div>
                <label className="mb-2 block text-sm font-medium text-gray-700">파일 선택</label>
                <input
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  onChange={(e) => handleRecordFileChange(e.target.files?.[0] || null)}
                  className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-[#0e6093]/10 file:px-3 file:py-2 file:text-xs file:font-semibold file:text-[#0e6093]"
                />
                <p className="mt-2 text-xs text-gray-500">선택된 파일: {data.recordUpload.fileName || '없음'}</p>
              </div>
              <textarea
                value={data.recordUpload.summary}
                onChange={(e) => setData((prev) => ({
                  ...prev,
                  recordUpload: {
                    ...prev.recordUpload,
                    summary: e.target.value,
                  },
                }))}
                placeholder="업로드한 학생부 성적에 대한 메모를 입력하세요."
                rows={8}
                className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm focus:border-[#0e6093] focus:outline-none"
              />
              <div className="flex justify-center gap-3 pt-1">
                <button
                  onClick={handleRecordUploadCancel}
                  className="h-12 min-w-[200px] rounded-2xl bg-[#cfd6db] px-6 text-xl font-bold text-gray-700 hover:bg-[#bec7cd]"
                >
                  취소
                </button>
                <button
                  onClick={handleRecordUploadSave}
                  disabled={isSaving}
                  className="h-12 min-w-[200px] rounded-2xl bg-[#0e8098] px-6 text-xl font-bold text-white hover:bg-[#0d7288] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSaving ? '저장 중...' : '전체 저장'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
