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

interface SchoolGradeInputModalProps {
  isOpen: boolean
  onClose: () => void
  embedded?: boolean
  onRequireSchoolRecordLink?: () => void
  /** 정시/모의고사 성적 입력 모달을 열 때 호출 (메뉴에서 "정시 성적 입력" 선택 시) */
  onOpenMockExamInput?: () => void
}

type ModalStep = 'menu' | 'semester' | 'extracurricular' | 'record_upload'
type SemesterKey = '1-1' | '1-2' | '2-1' | '2-2' | '3-1' | '3-2'
type GradeKey = '1' | '2' | '3'
type GradeAverageFieldKey = 'overall' | 'core'

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
const semesterKeys: SemesterKey[] = ['1-1', '1-2', '2-1', '2-2', '3-1', '3-2']

const gradeKeys: GradeKey[] = ['1', '2', '3']

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

      return normalizeSemesterRow({
        id: String(r.id || createEmptyRow().id),
        trackType: String(r.trackType || trackTypeOptions[0]),
        curriculum: String(r.curriculum || getCurriculumOptions(trackTypeOptions[0])[0] || ''),
        subject: String(r.subject || ''),
        credits: String(r.credits || ''),
        classRank: String(r.classRank || ''),
        rawScore: String(r.rawScore || ''),
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
  const gradeSummary =
    gradeSummaryRecord
      ? {
          overallAverage: String(gradeSummaryRecord.overallAverage || ''),
          coreAverage: String(gradeSummaryRecord.coreAverage || ''),
          semesterAverages: {
            '1-1': {
              overall: readSemesterAverageField('1-1', 'overall'),
              core: readSemesterAverageField('1-1', 'core'),
            },
            '1-2': {
              overall: readSemesterAverageField('1-2', 'overall'),
              core: readSemesterAverageField('1-2', 'core'),
            },
            '2-1': {
              overall: readSemesterAverageField('2-1', 'overall'),
              core: readSemesterAverageField('2-1', 'core'),
            },
            '2-2': {
              overall: readSemesterAverageField('2-2', 'overall'),
              core: readSemesterAverageField('2-2', 'core'),
            },
            '3-1': {
              overall: readSemesterAverageField('3-1', 'overall'),
              core: readSemesterAverageField('3-1', 'core'),
            },
            '3-2': {
              overall: readSemesterAverageField('3-2', 'overall'),
              core: readSemesterAverageField('3-2', 'core'),
            },
          },
        }
      : fallbackGradeSummary

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

const formatAveragedGrade = (values: string[]): string => {
  const numericValues = values
    .map((value) => parseGradeNumber(value))
    .filter((value): value is number => value !== null)
  if (numericValues.length === 0) return ''
  const average = numericValues.reduce((sum, value) => sum + value, 0) / numericValues.length
  return Number.isInteger(average) ? String(average) : average.toFixed(2).replace(/\.?0+$/, '')
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
}

function ScrollableSelect({
  value,
  options,
  onChange,
  placeholder = '선택',
  minPanelWidth = 0,
  buttonClassName = 'h-10 w-full rounded-md border border-gray-300 bg-white px-2',
}: ScrollableSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [panelRect, setPanelRect] = useState({ top: 0, left: 0, width: 0 })
  const rootRef = useRef<HTMLDivElement | null>(null)
  const buttonRef = useRef<HTMLButtonElement | null>(null)
  const panelRef = useRef<HTMLDivElement | null>(null)

  const selectedValue = value || ''
  const hasValue = selectedValue.length > 0
  const displayValue = hasValue ? selectedValue : placeholder

  useEffect(() => {
    if (!isOpen) return

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
      if (rootRef.current?.contains(target)) return
      if (panelRef.current?.contains(target)) return
      setIsOpen(false)
    }

    const handleWindowScroll = () => {
      updatePanelPosition()
    }

    updatePanelPosition()
    document.addEventListener('mousedown', handlePointerDown)
    window.addEventListener('resize', updatePanelPosition)
    window.addEventListener('scroll', handleWindowScroll, true)

    return () => {
      document.removeEventListener('mousedown', handlePointerDown)
      window.removeEventListener('resize', updatePanelPosition)
      window.removeEventListener('scroll', handleWindowScroll, true)
    }
  }, [isOpen, minPanelWidth])

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

      {isOpen && createPortal(
        <div
          ref={panelRef}
          style={{ top: panelRect.top, left: panelRect.left, width: panelRect.width }}
          className="fixed z-[80] rounded-2xl border border-gray-900 bg-white shadow-2xl"
        >
          <div
            className="max-h-72 overflow-y-auto overscroll-contain p-2"
            onWheel={(event) => event.stopPropagation()}
          >
            {options.length > 0 ? (
              options.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => {
                    onChange(option)
                    setIsOpen(false)
                  }}
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

export default function SchoolGradeInputModal({
  isOpen,
  onClose,
  embedded = false,
  onRequireSchoolRecordLink,
  onOpenMockExamInput,
}: SchoolGradeInputModalProps) {
  const { isAuthenticated, accessToken } = useAuth()
  const baseUrl = getApiBaseUrl()
  const [step, setStep] = useState<ModalStep>('menu')
  const [selectedSemester, setSelectedSemester] = useState<SemesterKey>('1-1')
  const [selectedSchoolYear, setSelectedSchoolYear] = useState<string>(schoolYearOptions[0])
  const [data, setData] = useState<SchoolGradeInputData>(() => buildDefaultData())
  const [message, setMessage] = useState('')
  const [isAutofillLoading, setIsAutofillLoading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [selectedSemesterColumn, setSelectedSemesterColumn] = useState<SemesterKey | null>(null)
  const [inlineSemesterOpen, setInlineSemesterOpen] = useState(false)
  const [inlineExtracurricularOpen, setInlineExtracurricularOpen] = useState(false)

  const loadSchoolGradeInputFromServer = useCallback(
    async (signal?: AbortSignal) => {
      if (!isAuthenticated || !accessToken) return

      try {
        const response = await fetch(`${baseUrl}/api/profile/me/school-grade-input?ts=${Date.now()}`, {
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
        setData(serverData)
        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(serverData))
        } catch {
          // ignore localStorage failure
        }
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') return
      }
    },
    [isAuthenticated, accessToken, baseUrl]
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
      const response = await fetch(`${baseUrl}/api/profile/me/school-grade-input`, {
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
  }, [isAuthenticated, accessToken, baseUrl])

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
      try {
        if (redirectIfNotLinked) {
          const statusRes = await fetch(`${baseUrl}/api/school-record/status`, {
            headers: { Authorization: `Bearer ${accessToken}` },
            cache: 'no-store',
            signal,
          })
          const linked =
            statusRes.ok
              ? ((await statusRes.json().catch(() => null))?.linked === true)
              : false

          if (!linked) {
            if (!silentWhenUnavailable) {
              setMessage('연동된 생기부가 없어 생활기록부 연동하기 페이지로 이동합니다.')
            }
            onRequireSchoolRecordLink?.()
            return
          }
        }

        const response = await fetch(`${baseUrl}/api/school-record/forms?ts=${Date.now()}`, {
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
          if (!silentWhenUnavailable) {
            setMessage('연동된 생기부에서 가져올 데이터가 없습니다.')
          }
          return
        }

        const nextData: SchoolGradeInputData = {
          ...data,
          semesters: semesterRows || data.semesters,
          extracurricular: extracurricularData || data.extracurricular,
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
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') return
        if (!silentWhenUnavailable) {
          setMessage('생기부 자동 입력 중 오류가 발생했습니다.')
        }
      } finally {
        if (showLoading) setIsAutofillLoading(false)
      }
    },
    [isAuthenticated, accessToken, baseUrl, onRequireSchoolRecordLink, data, persistSchoolGradeInput]
  )

  useEffect(() => {
    if (!isOpen) return

    setStep('menu')
    setSelectedSemester('1-1')
    setSelectedSchoolYear(schoolYearOptions[0])
    setMessage('')
    setInlineSemesterOpen(false)
    setInlineExtracurricularOpen(false)
    setData(loadSavedData())
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return

    const controller = new AbortController()
    void loadSchoolGradeInputFromServer(controller.signal)

    return () => {
      controller.abort()
    }
  }, [isOpen, loadSchoolGradeInputFromServer])

  useEffect(() => {
    if (!isOpen) return

    const controller = new AbortController()
    void autofillFromLinkedSchoolRecord({
      signal: controller.signal,
      silentWhenUnavailable: true,
      showLoading: false,
    })

    return () => {
      controller.abort()
    }
  }, [isOpen, autofillFromLinkedSchoolRecord])

  const currentSemesterRows = useMemo(
    () => data.semesters[selectedSemester] || [createEmptyRow()],
    [data.semesters, selectedSemester]
  )

  const goMenu = () => {
    setStep('menu')
    setMessage('')
    setInlineSemesterOpen(false)
    setInlineExtracurricularOpen(false)
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
    setData((prev) => ({
      ...prev,
      semesters: {
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

          return { ...row, [field]: value }
        }),
      },
    }))
  }

  const addSemesterRow = (semester: SemesterKey, count = 1) => {
    setData((prev) => ({
      ...prev,
      semesters: {
        ...prev.semesters,
        [semester]: [
          ...prev.semesters[semester],
          ...Array.from({ length: count }).map(() => createEmptyRow()),
        ],
      },
    }))
  }

  const handleSemesterSave = () => {
    void saveData(data, `${semesterLabels[selectedSemester]} 성적이 저장되었습니다.`)
  }

  const handleSemesterCancel = () => {
    setData(loadSavedData())
    if (step === 'menu') {
      setInlineSemesterOpen(false)
      setMessage('')
      return
    }
    goMenu()
  }

  const handleExtracurricularSave = () => {
    void saveData(data, '비교과 데이터가 저장되었습니다.')
  }

  const handleExtracurricularCancel = () => {
    setData(loadSavedData())
    if (step === 'menu') {
      setInlineExtracurricularOpen(false)
      setMessage('')
      return
    }
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
    void saveData(data, '학생부 성적 업로드 정보가 저장되었습니다.')
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

  if (!isOpen && !embedded) return null

  const updateSummaryAverage = (field: GradeAverageFieldKey, value: string) => {
    const sanitized = sanitizeGradeNumberInput(value)
    setData((prev) => {
      const nextSemesterAverages = semesterKeys.reduce<Record<SemesterKey, Record<GradeAverageFieldKey, string>>>((acc, semesterKey) => {
        acc[semesterKey] = {
          ...prev.gradeSummary.semesterAverages[semesterKey],
          [field]: sanitized,
        }
        return acc
      }, {} as Record<SemesterKey, Record<GradeAverageFieldKey, string>>)

      return {
        ...prev,
        gradeSummary: {
          ...prev.gradeSummary,
          overallAverage: field === 'overall' ? sanitized : prev.gradeSummary.overallAverage,
          coreAverage: field === 'core' ? sanitized : prev.gradeSummary.coreAverage,
          semesterAverages: nextSemesterAverages,
        },
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

      return {
        ...prev,
        gradeSummary: {
          ...prev.gradeSummary,
          semesterAverages: nextSemesterAverages,
          overallAverage: field === 'overall' ? nextAverage : prev.gradeSummary.overallAverage,
          coreAverage: field === 'core' ? nextAverage : prev.gradeSummary.coreAverage,
        },
      }
    })
  }

  return (
    <div className={embedded ? 'w-full h-full overflow-y-auto px-4 py-4 sm:px-6 sm:py-6' : 'fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4'}>
      <div className={embedded ? 'mx-auto w-full max-w-[1240px] max-h-[calc(100vh-3rem)] overflow-y-auto rounded-3xl border border-gray-300 bg-[#f7f8fa] shadow-sm' : 'w-full max-w-[1240px] max-h-[92vh] overflow-y-auto rounded-3xl border border-gray-300 bg-[#f7f8fa] shadow-2xl'}>
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

              <div className="rounded-xl border border-gray-300 bg-white px-4 py-4">
                <div className="space-y-1">
                  <div className="rounded-lg border border-gray-200 bg-[#fbfcfd] p-3">
                    <div className="flex flex-wrap items-center gap-3 sm:flex-nowrap sm:gap-4">
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-semibold text-gray-600">평균 내신(전체)</p>
                        <input
                          value={data.gradeSummary.overallAverage}
                          onChange={(e) => updateSummaryAverage('overall', e.target.value)}
                          inputMode="decimal"
                          placeholder="예: 2.35"
                          className="h-10 w-[150px] rounded-lg border border-gray-300 px-3 text-sm text-gray-900"
                        />
                      </div>
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-semibold text-gray-600">평균 내신(국영수탐)</p>
                        <input
                          value={data.gradeSummary.coreAverage}
                          onChange={(e) => updateSummaryAverage('core', e.target.value)}
                          inputMode="decimal"
                          placeholder="예: 2.11"
                          className="h-10 w-[150px] rounded-lg border border-gray-300 px-3 text-sm text-gray-900"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setInlineSemesterOpen(false)
                          setInlineExtracurricularOpen((prev) => !prev)
                          setMessage('')
                        }}
                        className="inline-flex h-10 items-center justify-center rounded-lg bg-[#0e6093] px-4 text-sm font-semibold text-white transition-colors hover:bg-[#0b4f77] sm:ml-auto"
                      >
                        출결/봉사
                      </button>
                    </div>
                  </div>

                  <div className="relative flex w-full items-center justify-center py-1.5">
                    <div className="absolute left-1/2 flex -translate-x-1/2 items-center gap-2">
                      <span className="invisible text-xs" aria-hidden>하나만 채워도 자동 완성돼요!</span>
                      <div className="flex flex-col items-center gap-[0.5px]">
                        <span className="h-1 w-1 shrink-0 rounded-full bg-gradient-to-br from-[#61b7df] to-[#0e6093]" />
                        <span className="h-1 w-1 shrink-0 rounded-full bg-gradient-to-br from-[#61b7df] to-[#0e6093]" />
                        <span className="h-1 w-1 shrink-0 rounded-full bg-gradient-to-br from-[#61b7df] to-[#0e6093]" />
                      </div>
                      <span className="text-xs text-gray-400">하나만 채워도 자동 완성돼요!</span>
                    </div>
                  </div>

                  <div className="rounded-lg border border-gray-200 bg-[#fbfcfd] p-3">
                    <div
                      className="grid items-start gap-2"
                      style={{ gridTemplateColumns: '110px repeat(6, minmax(0, 1fr))' }}
                    >
                      <div className="flex flex-col gap-2">
                        <div className="text-[11px] font-semibold leading-tight text-gray-600">구분</div>
                        <div className="flex h-8 items-center text-xs font-semibold text-gray-700">평균 내신(전체)</div>
                        <div className="flex h-8 items-center text-xs font-semibold text-gray-700">평균 내신(국영수탐)</div>
                      </div>
                      {semesterKeys.map((semesterKey) => (
                        <div
                          key={semesterKey}
                          role="group"
                          tabIndex={0}
                          onClick={(e) => {
                            if (e.target instanceof HTMLInputElement) return
                            if (selectedSemesterColumn === semesterKey) {
                              setSelectedSemesterColumn(null)
                              setStep('menu')
                              setInlineSemesterOpen(false)
                              setMessage('')
                              return
                            }
                            setSelectedSemesterColumn(semesterKey)
                            setSelectedSemester(semesterKey)
                            setStep('menu')
                            setInlineSemesterOpen(true)
                            setInlineExtracurricularOpen(false)
                            setMessage('')
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault()
                              if (selectedSemesterColumn === semesterKey) {
                                setSelectedSemesterColumn(null)
                                setStep('menu')
                                setInlineSemesterOpen(false)
                                setMessage('')
                                return
                              }
                              setSelectedSemesterColumn(semesterKey)
                              setSelectedSemester(semesterKey)
                              setStep('menu')
                              setInlineSemesterOpen(true)
                              setInlineExtracurricularOpen(false)
                              setMessage('')
                            }
                          }}
                          className={`flex flex-col gap-2 rounded-lg border-2 py-1 px-0.5 transition-[border-color,box-shadow] cursor-pointer ${selectedSemesterColumn === semesterKey ? 'border-[#0e6093] ring-2 ring-[#0e6093]/20' : 'border-transparent hover:border-[#0e6093] hover:ring-2 hover:ring-[#0e6093]/20'}`}
                        >
                          <div
                            className="text-center text-[11px] font-semibold leading-tight text-gray-600"
                            title={`${semesterLabels[semesterKey]} 상세 입력`}
                          >
                            {semesterLabels[semesterKey]}
                          </div>
                          <input
                            value={data.gradeSummary.semesterAverages[semesterKey].overall}
                            onChange={(e) => updateSemesterAverage(semesterKey, 'overall', e.target.value)}
                            onFocus={() => {
                              setSelectedSemesterColumn(semesterKey)
                              setSelectedSemester(semesterKey)
                              setStep('menu')
                              setInlineSemesterOpen(true)
                              setInlineExtracurricularOpen(false)
                            }}
                            inputMode="decimal"
                            className="h-8 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm text-gray-900 outline-none"
                          />
                          <input
                            value={data.gradeSummary.semesterAverages[semesterKey].core}
                            onChange={(e) => updateSemesterAverage(semesterKey, 'core', e.target.value)}
                            onFocus={() => {
                              setSelectedSemesterColumn(semesterKey)
                              setSelectedSemester(semesterKey)
                              setStep('menu')
                              setInlineSemesterOpen(true)
                              setInlineExtracurricularOpen(false)
                            }}
                            inputMode="decimal"
                            className="h-8 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm text-gray-900 outline-none"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

            </div>
          )}

          {(step === 'semester' || (step === 'menu' && inlineSemesterOpen)) && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-gray-300 bg-white p-3">
                <div className="overflow-x-auto rounded-xl border border-gray-300">
                  <table className="min-w-[980px] w-full border-collapse bg-white text-xs">
                    <thead>
                      <tr className="bg-[#f2f4f7] text-center font-bold text-gray-800">
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>번호</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>교과종류 구분</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>교과</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>과목</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>단위수</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>석차등급</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>원점수</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>과목평균</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>표준편차</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>수강자수</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" rowSpan={2}>성취도</th>
                        <th className="border border-gray-300 px-1.5 py-1.5" colSpan={3}>성취도별 분포</th>
                      </tr>
                      <tr className="bg-[#f2f4f7] text-center font-bold text-gray-800">
                        <th className="border border-gray-300 px-1.5 py-1.5">A</th>
                        <th className="border border-gray-300 px-1.5 py-1.5">B</th>
                        <th className="border border-gray-300 px-1.5 py-1.5">C</th>
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
                          <tr key={row.id} className="text-xs text-gray-800">
                          <td className="border border-gray-300 px-1.5 py-1.5 text-center">{index + 1}</td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <ScrollableSelect
                              value={row.trackType}
                              options={trackTypeOptions}
                              onChange={(nextValue) => updateSemesterRow(selectedSemester, row.id, 'trackType', nextValue)}
                              buttonClassName="h-7 w-full rounded-md border border-gray-300 bg-white px-1.5 text-xs"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <ScrollableSelect
                              value={row.curriculum}
                              options={curriculumOptionsForRow}
                              onChange={(nextValue) => updateSemesterRow(selectedSemester, row.id, 'curriculum', nextValue)}
                              minPanelWidth={320}
                              buttonClassName="h-7 w-full rounded-md border border-gray-300 bg-white px-1.5 text-xs"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <ScrollableSelect
                              value={row.subject}
                              options={subjectOptionsForRow}
                              onChange={(nextValue) => updateSemesterRow(selectedSemester, row.id, 'subject', nextValue)}
                              minPanelWidth={360}
                              buttonClassName="h-7 w-full rounded-md border border-gray-300 bg-white px-1.5 text-xs"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <input
                              value={row.credits}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'credits', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <input
                              value={row.classRank}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'classRank', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <input
                              value={row.rawScore}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'rawScore', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <input
                              value={row.avgScore}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'avgScore', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <input
                              value={row.stdDev}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'stdDev', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <input
                              value={row.studentCount}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'studentCount', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <select
                              value={row.achievement}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'achievement', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            >
                              {achievementOptions.map((opt) => (
                                <option key={opt} value={opt}>{opt}</option>
                              ))}
                            </select>
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <input
                              value={row.distA}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'distA', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <input
                              value={row.distB}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'distB', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            />
                          </td>

                          <td className="border border-gray-300 px-1.5 py-1.5">
                            <input
                              value={row.distC}
                              onChange={(e) => updateSemesterRow(selectedSemester, row.id, 'distC', e.target.value)}
                              className="h-7 w-full rounded-md border border-gray-300 px-1.5 text-center text-sm"
                            />
                          </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {(step === 'extracurricular' || (step === 'menu' && inlineExtracurricularOpen)) && (
            <div className="space-y-4">
              <div className="rounded-2xl border border-gray-300 bg-white p-3">
                <div className="grid gap-3 xl:grid-cols-[2.6fr_1fr]">
                  <div>
                    <div className="overflow-x-auto rounded-xl border border-gray-300">
                      <table className="min-w-[560px] w-full border-collapse bg-white text-xs">
                        <thead>
                          <tr className="bg-[#f2f4f7] text-center font-bold text-gray-800">
                            <th className="border border-gray-300 px-2 py-1.5">학년</th>
                            <th className="border border-gray-300 px-2 py-1.5">무단(미인정) 결석</th>
                            <th className="border border-gray-300 px-2 py-1.5">무단(미인정) 지각</th>
                            <th className="border border-gray-300 px-2 py-1.5">무단(미인정) 조퇴</th>
                            <th className="border border-gray-300 px-2 py-1.5">무단(미인정) 결과</th>
                            <th className="border border-gray-300 px-2 py-1.5">
                              <span className="inline-flex items-center gap-2">
                                합계
                                <span className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-gray-300 text-[10px] text-gray-500">?</span>
                              </span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {gradeKeys.map((grade) => (
                            <tr key={`attendance-${grade}`} className="text-center text-gray-800">
                              <td className="border border-gray-300 px-2 py-1.5 text-base font-semibold">{grade}</td>
                              <td className="border border-gray-300 px-2 py-1.5">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.attendance[grade].absence}
                                  onChange={(e) => updateAttendanceField(grade, 'absence', e.target.value)}
                                  className="h-7 w-full rounded-md border border-gray-300 px-2 text-center text-sm"
                                />
                              </td>
                              <td className="border border-gray-300 px-2 py-1.5">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.attendance[grade].tardy}
                                  onChange={(e) => updateAttendanceField(grade, 'tardy', e.target.value)}
                                  className="h-7 w-full rounded-md border border-gray-300 px-2 text-center text-sm"
                                />
                              </td>
                              <td className="border border-gray-300 px-2 py-1.5">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.attendance[grade].earlyLeave}
                                  onChange={(e) => updateAttendanceField(grade, 'earlyLeave', e.target.value)}
                                  className="h-7 w-full rounded-md border border-gray-300 px-2 text-center text-sm"
                                />
                              </td>
                              <td className="border border-gray-300 px-2 py-1.5">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.attendance[grade].result}
                                  onChange={(e) => updateAttendanceField(grade, 'result', e.target.value)}
                                  className="h-7 w-full rounded-md border border-gray-300 px-2 text-center text-sm"
                                />
                              </td>
                              <td className="border border-gray-300 px-2 py-1.5 text-base font-semibold text-gray-700">
                                {attendanceTotalsByGrade[grade]}
                              </td>
                            </tr>
                          ))}
                          <tr className="bg-[#f7f8fa] text-center font-semibold text-gray-700">
                            <td className="border border-gray-300 px-2 py-1.5 text-sm">전학년</td>
                            <td className="border border-gray-300 px-2 py-1.5 text-sm">{attendanceColumnTotals.absence}</td>
                            <td className="border border-gray-300 px-2 py-1.5 text-sm">{attendanceColumnTotals.tardy}</td>
                            <td className="border border-gray-300 px-2 py-1.5 text-sm">{attendanceColumnTotals.earlyLeave}</td>
                            <td className="border border-gray-300 px-2 py-1.5 text-sm">{attendanceColumnTotals.result}</td>
                            <td className="border border-gray-300 px-2 py-1.5 text-sm">{attendanceGrandTotal}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div>
                    <div className="overflow-x-auto rounded-xl border border-gray-300">
                      <table className="min-w-[220px] w-full border-collapse bg-white text-xs">
                        <thead>
                          <tr className="bg-[#f2f4f7] text-center font-bold text-gray-800">
                            <th className="border border-gray-300 px-2 py-1.5">학년</th>
                            <th className="border border-gray-300 px-2 py-1.5">봉사시간</th>
                          </tr>
                        </thead>
                        <tbody>
                          {gradeKeys.map((grade) => (
                            <tr key={`volunteer-${grade}`} className="text-center text-gray-800">
                              <td className="border border-gray-300 px-2 py-1.5 text-base font-semibold">{grade}</td>
                              <td className="border border-gray-300 px-2 py-1.5">
                                <input
                                  inputMode="numeric"
                                  value={data.extracurricular.volunteerHours[grade]}
                                  onChange={(e) => updateVolunteerHours(grade, e.target.value)}
                                  className="h-7 w-full rounded-md border border-gray-300 px-2 text-center text-sm"
                                />
                              </td>
                            </tr>
                          ))}
                          <tr className="bg-[#f7f8fa] text-center font-semibold text-gray-700">
                            <td className="border border-gray-300 px-2 py-1.5 text-sm">전학년</td>
                            <td className="border border-gray-300 px-2 py-1.5 text-sm">{volunteerTotal}</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
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
                  {isSaving ? '저장 중...' : '저장'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
