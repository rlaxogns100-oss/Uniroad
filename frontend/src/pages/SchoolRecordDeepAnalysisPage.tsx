import React, { useState, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { getApiBaseUrl } from '../config'
import SchoolRecordRegisterModal, { RegisterMethod } from '../components/SchoolRecordRegisterModal'

type ParsedSchoolRecordPreview = Record<string, any>

type Grade = 1 | 2 | 3
type CreativeGrade = { autonomousNotes: string; clubNotes: string; careerNotes: string }
type AcademicGrade = { subjects: string[]; notes: string[] }
type IndividualGrade = { content: string }

const emptyCreativeGrade = (): CreativeGrade => ({ autonomousNotes: '', clubNotes: '', careerNotes: '' })
const emptyAcademicGrade = (): AcademicGrade => ({ subjects: ['', '', ''], notes: ['', '', ''] })

const INNER_SCHOOL_RECORD_TABS: Array<{ id: string; label: string }> = [
  { id: 'creative', label: '창의적체험활동상황' },
  { id: 'academic', label: '과목별 세특' },
  { id: 'individual', label: '개인별 세특' },
  { id: 'behavior', label: '행동특성 및 종합의견' },
]

/**
 * 학교생활기록부 연동/수정 페이지
 * - PDF 업로드 → 파싱 결과 확인/수정 → 저장
 */
export default function SchoolRecordDeepAnalysisPage() {
  const { isAuthenticated, accessToken } = useAuth()
  const baseUrl = getApiBaseUrl()
  const [innerSchoolRecordTab, setInnerSchoolRecordTab] = useState(0)
  const [formsSaveStatus, setFormsSaveStatus] = useState<'idle' | 'saving' | 'ok' | 'err'>('idle')
  const [formsLoading, setFormsLoading] = useState(false)
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [pdfUploading, setPdfUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStage, setUploadStage] = useState<'uploading' | 'processing'>('uploading')
  const [pdfUploadMessage, setPdfUploadMessage] = useState<string | null>(null)
  const [pdfUploadError, setPdfUploadError] = useState<string | null>(null)
  const [schoolRecordSaving, setSchoolRecordSaving] = useState(false)
  const [schoolRecordSaveMessage, setSchoolRecordSaveMessage] = useState<string | null>(null)
  const [schoolRecordSaveError, setSchoolRecordSaveError] = useState<string | null>(null)
  const [pdfImportMeta, setPdfImportMeta] = useState<Record<string, any> | null>(null)
  const [pdfParseTimings, setPdfParseTimings] = useState<Record<string, any> | null>(null)
  const [parsedPreview, setParsedPreview] = useState<ParsedSchoolRecordPreview | null>(null)
  /** 비교 보기에서 저장 후 변경 컬럼만 노출 */
  const [showChangedOnly, setShowChangedOnly] = useState(false)
  /** 전용 뷰: 학교생활기록부 등록 모달 */
  const [registerModalOpen, setRegisterModalOpen] = useState(false)
  /** 전용 뷰: 파싱 결과 직접 수정 모드 */
  const [standaloneEditMode, setStandaloneEditMode] = useState(false)
  /** 전용 뷰: STEP 아코디언 열림 (0~3 = STEP 01~04) */
  const [openAccordionStep, setOpenAccordionStep] = useState<number | null>(null)

  // 생기부 세특 평가와 동일한 폼 상태 (학년별)
  const [creativeGrade, setCreativeGrade] = useState<Grade>(1)
  const [creativeActivity, setCreativeActivity] = useState<Record<Grade, CreativeGrade>>({
    1: emptyCreativeGrade(),
    2: emptyCreativeGrade(),
    3: emptyCreativeGrade(),
  })
  const [academicGrade, setAcademicGrade] = useState<Grade>(1)
  const [academicDev, setAcademicDev] = useState<Record<Grade, AcademicGrade>>({
    1: emptyAcademicGrade(),
    2: emptyAcademicGrade(),
    3: emptyAcademicGrade(),
  })
  const [individualGrade, setIndividualGrade] = useState<Grade>(1)
  const [individualDev, setIndividualDev] = useState<Record<Grade, IndividualGrade>>({
    1: { content: '' },
    2: { content: '' },
    3: { content: '' },
  })
  const [behaviorGrade, setBehaviorGrade] = useState<Grade>(1)
  const [behaviorOpinion, setBehaviorOpinion] = useState<string[]>(['', '', ''])

  // user_profiles metadata에서 생기부 폼 불러오기 — 로그인된 경우에만, 유효한 토큰이 있을 때 한 번만
  const formsFetchedRef = React.useRef(false)
  useEffect(() => {
    const hasValidToken = typeof accessToken === 'string' && accessToken.length > 0
    if (!isAuthenticated || !hasValidToken) {
      formsFetchedRef.current = false
      return
    }
    if (formsFetchedRef.current) return
    formsFetchedRef.current = true
    setFormsLoading(true)
    fetch(`${baseUrl}/api/school-record/forms`, { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((res) => {
        if (res.status === 401) {
          formsFetchedRef.current = false
          return { forms: {} }
        }
        return res.ok ? res.json() : { forms: {} }
      })
      .then((data) => {
        const f = data?.forms || {}
        if (f.creativeActivity) {
          if (f.creativeActivity.byGrade && typeof f.creativeActivity.byGrade === 'object') {
            const byGrade = f.creativeActivity.byGrade as Record<string, Partial<CreativeGrade>>
            setCreativeActivity({
              1: { ...emptyCreativeGrade(), ...byGrade['1'] },
              2: { ...emptyCreativeGrade(), ...byGrade['2'] },
              3: { ...emptyCreativeGrade(), ...byGrade['3'] },
            })
          } else {
            const g = (f.creativeActivity.grade ?? 1) as Grade
            const one: CreativeGrade = {
              autonomousNotes: f.creativeActivity.autonomousNotes ?? '',
              clubNotes: f.creativeActivity.clubNotes ?? '',
              careerNotes: f.creativeActivity.careerNotes ?? '',
            }
            setCreativeActivity({ 1: emptyCreativeGrade(), 2: emptyCreativeGrade(), 3: emptyCreativeGrade(), [g]: one })
          }
        }
        if (f.academicDev) {
          if (f.academicDev.byGrade && typeof f.academicDev.byGrade === 'object') {
            const byGrade = f.academicDev.byGrade as Record<string, { subjects?: string[]; notes?: string[] }>
            const pad = (arr: string[] | undefined): string[] => (arr || []).slice(0, 3).concat(Array(3).fill('')).slice(0, 3)
            setAcademicDev({
              1: { subjects: pad(byGrade['1']?.subjects), notes: pad(byGrade['1']?.notes) },
              2: { subjects: pad(byGrade['2']?.subjects), notes: pad(byGrade['2']?.notes) },
              3: { subjects: pad(byGrade['3']?.subjects), notes: pad(byGrade['3']?.notes) },
            })
          } else {
            const g = (f.academicDev.grade ?? 1) as Grade
            const subj = Array.isArray(f.academicDev.subjects) ? f.academicDev.subjects.slice(0, 3).concat(Array(3).fill('')).slice(0, 3) : ['', '', '']
            const notes = Array.isArray(f.academicDev.notes) ? f.academicDev.notes.slice(0, 3).concat(Array(3).fill('')).slice(0, 3) : ['', '', '']
            setAcademicDev({ 1: emptyAcademicGrade(), 2: emptyAcademicGrade(), 3: emptyAcademicGrade(), [g]: { subjects: subj, notes } })
          }
        }
        if (f.individualDev && f.individualDev.byGrade && typeof f.individualDev.byGrade === 'object') {
          const byGrade = f.individualDev.byGrade as Record<string, { content?: string; notes?: string[] }>
          const toContent = (g: typeof byGrade['1']): string => {
            if (!g) return ''
            if (typeof g.content === 'string') return g.content
            if (Array.isArray(g.notes) && g.notes.some((n) => n && String(n).trim())) return g.notes.filter(Boolean).join('\n')
            return ''
          }
          setIndividualDev({
            1: { content: toContent(byGrade['1']) },
            2: { content: toContent(byGrade['2']) },
            3: { content: toContent(byGrade['3']) },
          })
        } else if (f.individualDev) {
          const g = (f.individualDev.grade ?? 1) as Grade
          const notes = (f.individualDev as { notes?: string[] }).notes
          const content = Array.isArray(notes) && notes.length ? notes.filter(Boolean).join('\n') : ''
          setIndividualDev({ 1: { content: '' }, 2: { content: '' }, 3: { content: '' }, [g]: { content } })
        }
        if (f.behaviorOpinion && Array.isArray(f.behaviorOpinion.opinions)) {
          setBehaviorOpinion(f.behaviorOpinion.opinions.slice(0, 3).concat(Array(3).fill('')).slice(0, 3))
        }
        setPdfImportMeta(f?.pdfImportMeta && typeof f.pdfImportMeta === 'object' ? f.pdfImportMeta : null)
        setPdfParseTimings(
          f?.pdfImportMeta?.timings_ms && typeof f.pdfImportMeta.timings_ms === 'object'
            ? f.pdfImportMeta.timings_ms
            : null
        )
        setParsedPreview(f?.parsedSchoolRecord && typeof f.parsedSchoolRecord === 'object' ? f.parsedSchoolRecord : null)
      })
      .catch(() => {})
      .finally(() => setFormsLoading(false))
  }, [isAuthenticated, accessToken, baseUrl])

  const handleSaveForms = async () => {
    if (!accessToken) return
    setFormsSaveStatus('saving')
    try {
      const payload =
        innerSchoolRecordTab === 0
          ? { creativeActivity: { byGrade: creativeActivity } }
          : innerSchoolRecordTab === 1
            ? { academicDev: { byGrade: academicDev } }
            : innerSchoolRecordTab === 2
              ? { individualDev: { showInputs: true, byGrade: individualDev } }
              : { behaviorOpinion: { showInputs: true, opinions: behaviorOpinion } }
      const res = await fetch(`${baseUrl}/api/school-record/forms`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('저장 실패')
      setFormsSaveStatus('ok')
      setTimeout(() => setFormsSaveStatus('idle'), 2000)
    } catch {
      setFormsSaveStatus('err')
      setTimeout(() => setFormsSaveStatus('idle'), 2000)
    }
  }

  const handleUploadSchoolRecordPdf = (fileOverride?: File) => {
    const fileToUse = fileOverride ?? pdfFile
    if (!accessToken) {
      setPdfUploadMessage(null)
      setPdfUploadError('로그인 후 업로드할 수 있습니다.')
      return false
    }
    if (!fileToUse) {
      setPdfUploadMessage(null)
      setPdfUploadError('PDF 파일을 먼저 선택해 주세요.')
      return false
    }

    setPdfUploadMessage(null)
    setPdfUploadError(null)
    setShowChangedOnly(false)
    setSchoolRecordSaveMessage(null)
    setSchoolRecordSaveError(null)
    setPdfUploading(true)
    setUploadProgress(0)
    setUploadStage('uploading')

    const formData = new FormData()
    formData.append('file', fileToUse)
    const url = `${baseUrl}/api/school-record/forms/upload-pdf`
    const xhr = new XMLHttpRequest()

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && e.total > 0) {
        const pct = Math.round((e.loaded / e.total) * 100)
        setUploadProgress(pct)
        if (pct >= 100) setUploadStage('processing')
      }
    })

    xhr.addEventListener('load', () => {
      setUploadProgress(100)
      if (xhr.status < 200 || xhr.status >= 300) {
        let errMsg = 'PDF 업로드에 실패했습니다.'
        try {
          const data = JSON.parse(xhr.responseText || '{}')
          errMsg = data?.detail || data?.error || errMsg
        } catch {
          if (xhr.responseText) errMsg = xhr.responseText.slice(0, 200)
        }
        setPdfUploadError(errMsg)
        setPdfUploading(false)
        setUploadProgress(0)
        setUploadStage('uploading')
        return
      }
      let data: Record<string, any> = {}
      try {
        data = JSON.parse(xhr.responseText || '{}')
      } catch {
        setPdfUploadError('응답을 읽을 수 없습니다.')
        setPdfUploading(false)
        setUploadProgress(0)
        setUploadStage('uploading')
        return
      }
      if (!data?.ok) {
        setPdfUploadError(data?.detail || data?.error || 'PDF 업로드에 실패했습니다.')
        setPdfUploading(false)
        setUploadProgress(0)
        setUploadStage('uploading')
        return
      }
      const pageCount = Number(data?.meta?.page_count || 0)
      const charCount = Number(data?.meta?.char_count || 0)
      const extractionMethod = String(data?.meta?.extraction_method || '')
      const parseMethod = String(data?.meta?.parse_method || '')
      const noteCount = Number(data?.summary?.academic_note_count || 0)
      const extractionLabel = extractionMethod === 'gemini_vision_ocr' ? 'OCR' : '텍스트 추출'
      const parseLabel = parseMethod === 'gemini' ? 'Gemini 파싱' : '규칙 파싱'
      const totalMs = Number(data?.timings?.total_ms || data?.meta?.timings_ms?.total_ms || 0)
      const speedLabel = totalMs > 0 ? ` / ${(totalMs / 1000).toFixed(2)}초` : ''
      setPdfUploadMessage(
        `PDF 연동 완료 (${pageCount || '?'}p / ${charCount.toLocaleString('ko-KR')}자, ${extractionLabel}, ${parseLabel}${speedLabel}, 세특 항목 ${noteCount}개).`
      )
      setPdfImportMeta(data?.meta && typeof data.meta === 'object' ? data.meta : null)
      setPdfParseTimings(data?.timings && typeof data.timings === 'object' ? data.timings : null)
      setParsedPreview(
        data?.parsedPreview && typeof data.parsedPreview === 'object'
          ? data.parsedPreview
          : data?.parsedSchoolRecord && typeof data.parsedSchoolRecord === 'object'
            ? data.parsedSchoolRecord
            : null
      )
      setPdfFile(null)
      setPdfUploading(false)
      setUploadProgress(0)
      setUploadStage('uploading')
    })

    xhr.addEventListener('error', () => {
      setPdfUploadError('네트워크 오류로 업로드에 실패했습니다.')
      setPdfUploading(false)
      setUploadProgress(0)
      setUploadStage('uploading')
    })

    xhr.addEventListener('abort', () => {
      setPdfUploading(false)
      setUploadProgress(0)
      setUploadStage('uploading')
    })

    xhr.open('POST', url)
    xhr.setRequestHeader('Authorization', `Bearer ${accessToken}`)
    xhr.send(formData)
    return true
  }

  const handleSaveParsedSchoolRecord = async (options?: { showChangedOnlyAfterSave?: boolean }) => {
    if (!accessToken) {
      setSchoolRecordSaveMessage(null)
      setSchoolRecordSaveError('로그인 후 저장할 수 있습니다.')
      return
    }
    if (!parsedPreview?.sections) {
      setSchoolRecordSaveMessage(null)
      setSchoolRecordSaveError('저장할 생기부 데이터가 없습니다.')
      return
    }

    setSchoolRecordSaving(true)
    setSchoolRecordSaveMessage(null)
    setSchoolRecordSaveError(null)
    try {
      const res = await fetch(`${baseUrl}/api/school-record/forms/save-parsed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({
          parsedPreview,
          pdfImportMeta,
        }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || !data?.ok) {
        throw new Error(data?.detail || data?.error || '저장에 실패했습니다.')
      }
      if (data?.parsedPreview && typeof data.parsedPreview === 'object') {
        setParsedPreview(data.parsedPreview)
      }
      setStandaloneEditMode(false)
      if (options?.showChangedOnlyAfterSave) setShowChangedOnly(true)
      setSchoolRecordSaveMessage('저장 완료')
    } catch (err) {
      setSchoolRecordSaveError(err instanceof Error ? err.message : '저장 중 오류가 발생했습니다.')
    } finally {
      setSchoolRecordSaving(false)
    }
  }

  // 업로드 후 서버 처리 구간 표시: 0.8초 후에도 진행 중이면 "처리 중"으로 전환
  React.useEffect(() => {
    if (!pdfUploading) return
    const t = setTimeout(() => setUploadStage('processing'), 800)
    return () => clearTimeout(t)
  }, [pdfUploading])

  React.useEffect(() => {
    if (!parsedPreview) return
    setShowChangedOnly(false)
    setStandaloneEditMode(false)
  }, [parsedPreview])

  const handleRegisterModalSave = (registerMethod: RegisterMethod, value: { docNumber?: string; file?: File }) => {
    if (registerMethod === 'file' && value.file) {
      const started = handleUploadSchoolRecordPdf(value.file)
      if (started) setRegisterModalOpen(false)
    }
    if (registerMethod === 'doc_number' && value.docNumber) {
      setRegisterModalOpen(false)
      setPdfUploadMessage('문서열람번호 연동은 준비 중입니다.')
    }
  }

  const parsedSections = (parsedPreview?.sections || {}) as Record<string, any>
  const attendanceRows = Array.isArray(parsedSections?.attendance?.rows) ? parsedSections.attendance.rows : []
  const certificateItems = Array.isArray(parsedSections?.certificates?.items) ? parsedSections.certificates.items : []
  const certificateRows = Array.isArray(parsedSections?.certificates?.rows) ? parsedSections.certificates.rows : []
  const volunteerRows = Array.isArray(parsedSections?.volunteerActivity?.rows) ? parsedSections.volunteerActivity.rows : []
  const academicByGrade = (parsedSections?.academicDevelopment?.by_grade || {}) as Record<string, Array<{ subject?: string; note?: string }>>
  const academicGeneralElective = (parsedSections?.academicDevelopment?.general_elective || {}) as Record<string, { rows: any[]; 이수단위합계?: number | null }>
  const academicCareerElective = (parsedSections?.academicDevelopment?.career_elective || {}) as Record<string, { rows: any[]; 이수단위합계?: number | null }>
  const academicPeArts = (parsedSections?.academicDevelopment?.pe_arts || {}) as Record<string, { rows: any[]; 이수단위합계?: number | null }>
  const academicGrades = ['1', '2', '3'] as const
  const academicGeneralCols = ['학기', '교과', '과목', '단위수', '원점수', '과목평균', '표준편차', '성취도', '수강자수', '석차등급'] as const
  const academicCareerCols = ['학기', '교과', '과목', '단위수', '원점수', '과목평균', '성취도', '수강자수', 'A', 'B', 'C'] as const
  const academicCareerKeys = ['학기', '교과', '과목', '단위수', '원점수', '과목평균', '성취도', '수강자수', '성취도별분포_A', '성취도별분포_B', '성취도별분포_C'] as const
  const academicPeCols = ['학기', '교과', '과목', '단위수', '성취도'] as const
  const creativeByGrade = (parsedSections?.creativeActivity?.by_grade || {}) as Record<string, Record<string, string>>
  const creativeHoursByGrade = (parsedSections?.creativeActivity?.hours_by_grade || {}) as Record<string, Record<string, number | null>>
  const behaviorByGrade = (parsedSections?.behaviorOpinion?.by_grade || {}) as Record<string, string>
  // 개인별 세특: 백엔드와 동일하게 과목별 세특을 학년별 한 덩어리로 표시
  const individualContentByGrade: Record<string, string> = {}
  ;(['1', '2', '3'] as const).forEach((g) => {
    const rows = academicByGrade[g] || []
    individualContentByGrade[g] = rows.map((r) => `[${r?.subject ?? '과목'}]\n${r?.note ?? ''}`).join('\n\n').trim()
  })

  const normalizeDisplayText = (value: unknown): string => {
    const raw = String(value ?? '').replace(/\r\n/g, '\n').trim()
    if (!raw) return '-'
    return raw
      .split(/\n{2,}/)
      .map((paragraph) => paragraph.replace(/\n+/g, ' ').replace(/[ \t]{2,}/g, ' ').trim())
      .filter(Boolean)
      .join('\n\n')
  }

  const updateParsedSections = React.useCallback((updater: (sections: Record<string, any>) => void) => {
    setParsedPreview((prev) => {
      if (!prev || typeof prev !== 'object') return prev
      const next = JSON.parse(JSON.stringify(prev))
      if (!next.sections || typeof next.sections !== 'object') next.sections = {}
      updater(next.sections as Record<string, any>)
      return next
    })
  }, [])

  const updateAttendanceCell = React.useCallback((rowIndex: number, fieldKey: string, value: string) => {
    updateParsedSections((sections) => {
      if (!sections.attendance || typeof sections.attendance !== 'object') sections.attendance = {}
      if (!Array.isArray(sections.attendance.rows)) sections.attendance.rows = []
      if (!sections.attendance.rows[rowIndex] || typeof sections.attendance.rows[rowIndex] !== 'object') {
        sections.attendance.rows[rowIndex] = {}
      }
      sections.attendance.rows[rowIndex][fieldKey] = value
    })
  }, [updateParsedSections])

  const updateCertificateCell = React.useCallback((rowIndex: number, fieldKey: string, value: string) => {
    updateParsedSections((sections) => {
      if (!sections.certificates || typeof sections.certificates !== 'object') sections.certificates = {}
      if (!Array.isArray(sections.certificates.rows)) sections.certificates.rows = []
      if (!sections.certificates.rows[rowIndex] || typeof sections.certificates.rows[rowIndex] !== 'object') {
        sections.certificates.rows[rowIndex] = {}
      }
      sections.certificates.rows[rowIndex][fieldKey] = value
    })
  }, [updateParsedSections])

  const updateCreativeNote = React.useCallback((grade: string, fieldKey: string, value: string) => {
    updateParsedSections((sections) => {
      if (!sections.creativeActivity || typeof sections.creativeActivity !== 'object') sections.creativeActivity = {}
      if (!sections.creativeActivity.by_grade || typeof sections.creativeActivity.by_grade !== 'object') {
        sections.creativeActivity.by_grade = {}
      }
      if (!sections.creativeActivity.by_grade[grade] || typeof sections.creativeActivity.by_grade[grade] !== 'object') {
        sections.creativeActivity.by_grade[grade] = {}
      }
      sections.creativeActivity.by_grade[grade][fieldKey] = value
    })
  }, [updateParsedSections])

  const updateCreativeHours = React.useCallback((grade: string, fieldKey: string, value: string) => {
    updateParsedSections((sections) => {
      if (!sections.creativeActivity || typeof sections.creativeActivity !== 'object') sections.creativeActivity = {}
      if (!sections.creativeActivity.hours_by_grade || typeof sections.creativeActivity.hours_by_grade !== 'object') {
        sections.creativeActivity.hours_by_grade = {}
      }
      if (!sections.creativeActivity.hours_by_grade[grade] || typeof sections.creativeActivity.hours_by_grade[grade] !== 'object') {
        sections.creativeActivity.hours_by_grade[grade] = {}
      }
      sections.creativeActivity.hours_by_grade[grade][fieldKey] = value
    })
  }, [updateParsedSections])

  const updateVolunteerCell = React.useCallback((rowIndex: number, fieldKey: string, value: string) => {
    updateParsedSections((sections) => {
      if (!sections.volunteerActivity || typeof sections.volunteerActivity !== 'object') sections.volunteerActivity = {}
      if (!Array.isArray(sections.volunteerActivity.rows)) sections.volunteerActivity.rows = []
      if (!sections.volunteerActivity.rows[rowIndex] || typeof sections.volunteerActivity.rows[rowIndex] !== 'object') {
        sections.volunteerActivity.rows[rowIndex] = {}
      }
      sections.volunteerActivity.rows[rowIndex][fieldKey] = value
    })
  }, [updateParsedSections])

  const updateAcademicRowCell = React.useCallback(
    (
      blockKey: 'general_elective' | 'career_elective' | 'pe_arts',
      grade: string,
      rowIndex: number,
      fieldKey: string,
      value: string
    ) => {
      updateParsedSections((sections) => {
        if (!sections.academicDevelopment || typeof sections.academicDevelopment !== 'object') {
          sections.academicDevelopment = {}
        }
        if (!sections.academicDevelopment[blockKey] || typeof sections.academicDevelopment[blockKey] !== 'object') {
          sections.academicDevelopment[blockKey] = {}
        }
        if (!sections.academicDevelopment[blockKey][grade] || typeof sections.academicDevelopment[blockKey][grade] !== 'object') {
          sections.academicDevelopment[blockKey][grade] = {}
        }
        if (!Array.isArray(sections.academicDevelopment[blockKey][grade].rows)) {
          sections.academicDevelopment[blockKey][grade].rows = []
        }
        if (
          !sections.academicDevelopment[blockKey][grade].rows[rowIndex] ||
          typeof sections.academicDevelopment[blockKey][grade].rows[rowIndex] !== 'object'
        ) {
          sections.academicDevelopment[blockKey][grade].rows[rowIndex] = {}
        }
        sections.academicDevelopment[blockKey][grade].rows[rowIndex][fieldKey] = value
      })
    },
    [updateParsedSections]
  )

  const updateAcademicTotalCredits = React.useCallback(
    (blockKey: 'general_elective' | 'career_elective' | 'pe_arts', grade: string, value: string) => {
      updateParsedSections((sections) => {
        if (!sections.academicDevelopment || typeof sections.academicDevelopment !== 'object') {
          sections.academicDevelopment = {}
        }
        if (!sections.academicDevelopment[blockKey] || typeof sections.academicDevelopment[blockKey] !== 'object') {
          sections.academicDevelopment[blockKey] = {}
        }
        if (!sections.academicDevelopment[blockKey][grade] || typeof sections.academicDevelopment[blockKey][grade] !== 'object') {
          sections.academicDevelopment[blockKey][grade] = {}
        }
        sections.academicDevelopment[blockKey][grade]['이수단위합계'] = value
      })
    },
    [updateParsedSections]
  )

  const updateAcademicSeteukCell = React.useCallback((grade: string, rowIndex: number, fieldKey: string, value: string) => {
    updateParsedSections((sections) => {
      if (!sections.academicDevelopment || typeof sections.academicDevelopment !== 'object') {
        sections.academicDevelopment = {}
      }
      if (!sections.academicDevelopment.by_grade || typeof sections.academicDevelopment.by_grade !== 'object') {
        sections.academicDevelopment.by_grade = {}
      }
      if (!Array.isArray(sections.academicDevelopment.by_grade[grade])) {
        sections.academicDevelopment.by_grade[grade] = []
      }
      if (!sections.academicDevelopment.by_grade[grade][rowIndex] || typeof sections.academicDevelopment.by_grade[grade][rowIndex] !== 'object') {
        sections.academicDevelopment.by_grade[grade][rowIndex] = {}
      }
      sections.academicDevelopment.by_grade[grade][rowIndex][fieldKey] = value
    })
  }, [updateParsedSections])

  const updateBehaviorOpinion = React.useCallback((grade: string, value: string) => {
    updateParsedSections((sections) => {
      if (!sections.behaviorOpinion || typeof sections.behaviorOpinion !== 'object') sections.behaviorOpinion = {}
      if (!sections.behaviorOpinion.by_grade || typeof sections.behaviorOpinion.by_grade !== 'object') {
        sections.behaviorOpinion.by_grade = {}
      }
      sections.behaviorOpinion.by_grade[grade] = value
    })
  }, [updateParsedSections])

  const renderEditableField = (
    value: unknown,
    onChange: (value: string) => void,
    options?: { multiline?: boolean; readClassName?: string; inputClassName?: string }
  ) => {
    const current = value == null ? '' : String(value)
    if (!standaloneEditMode) {
      if (options?.multiline) {
        return (
          <span className={options.readClassName || 'whitespace-pre-line break-words leading-5 text-xs text-gray-700'}>
            {normalizeDisplayText(value)}
          </span>
        )
      }
      return <span className={options?.readClassName}>{current || '-'}</span>
    }
    if (options?.multiline) {
      return (
        <textarea
          value={current}
          onChange={(e) => onChange(e.target.value)}
          className={
            options.inputClassName ||
            'w-full min-h-[120px] rounded-md border border-slate-200 bg-white px-2 py-1.5 text-[12px] leading-5 text-gray-900 focus:outline-none focus:ring-2 focus:ring-slate-200'
          }
        />
      )
    }
    return (
      <input
        type="text"
        value={current}
        onChange={(e) => onChange(e.target.value)}
        className={
          options?.inputClassName ||
          'w-full min-w-[56px] rounded-md border border-slate-200 bg-white px-1.5 py-1 text-xs text-gray-900 focus:outline-none focus:ring-2 focus:ring-slate-200'
        }
      />
    )
  }

  const renderAcademicGradeBlock = (
    title: string,
    cols: readonly string[],
    rowKeys: readonly string[],
    rows: any[],
    totalCredits: number | string | null | undefined,
    options?: {
      editable?: boolean
      onCellChange?: (rowIndex: number, key: string, value: string) => void
      onTotalCreditsChange?: (value: string) => void
    }
  ) => (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <p className="bg-gray-50 px-3 py-2 font-semibold text-gray-800 border-b border-gray-200">{title}</p>
      <div className="overflow-x-auto">
        <table className="min-w-[980px] w-full text-left border-collapse text-sm">
          <thead>
            <tr className="bg-gray-100 border-b border-gray-200">
              {cols.map((h) => (
                <th key={h} className="py-2 px-3 border-r border-gray-200 font-semibold text-gray-800 last:border-r-0 whitespace-nowrap">{h}*</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={cols.length} className="py-4 text-center text-gray-500">해당 사항 없음</td></tr>
            ) : (
              rows.map((r: any, i: number) => (
                <tr key={i} className="border-b border-gray-100">
                  {rowKeys.map((k) => (
                    <td key={k} className="py-2 px-3 border-r border-gray-200 last:border-r-0 whitespace-nowrap">
                      {options?.editable && options.onCellChange
                        ? renderEditableField(r?.[k], (value) => options.onCellChange?.(i, String(k), value))
                        : (r?.[k] ?? '-')}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <table className="w-full border-t border-gray-200">
        <tbody>
          <tr>
            <td className="w-32 py-2 px-3 bg-gray-100 font-medium text-gray-800 border-r border-gray-200">이수단위합계</td>
            <td className="py-2 px-3">
              {options?.editable && options.onTotalCreditsChange
                ? renderEditableField(totalCredits, (value) => options.onTotalCreditsChange?.(value))
                : (totalCredits ?? 0)}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  )

  const renderSeteukBlock = (
    rows: Array<{ subject?: string; note?: string }>,
    options?: {
      editable?: boolean
      onSubjectChange?: (rowIndex: number, value: string) => void
      onNoteChange?: (rowIndex: number, value: string) => void
    }
  ) => (
    <div className="rounded-lg border border-gray-200 overflow-hidden">
      <p className="bg-gray-50 px-3 py-2 font-semibold text-gray-800 border-b border-gray-200">과목 · 세부능력 및 특기사항</p>
      <table className="w-full text-left border-collapse text-sm">
        <thead>
          <tr className="bg-gray-100 border-b border-gray-200">
            <th className="py-2 px-3 border-r border-gray-200 font-semibold text-gray-800 w-28">과목</th>
            <th className="py-2 px-3 font-semibold text-gray-800">세부능력 및 특기사항</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td colSpan={2} className="py-4 text-center text-gray-500">해당 사항 없음</td></tr>
          ) : (
            rows.map((row, idx) => (
              <tr key={idx} className="border-b border-gray-100">
                <td className="py-2 px-3 border-r border-gray-200 align-top">
                  {options?.editable && options.onSubjectChange
                    ? renderEditableField(row?.subject, (value) => options.onSubjectChange?.(idx, value))
                    : (row?.subject ?? '-')}
                </td>
                <td className="py-2 px-3 align-top">
                  {options?.editable && options.onNoteChange
                    ? renderEditableField(row?.note, (value) => options.onNoteChange?.(idx, value), { multiline: true })
                    : (
                      <span className="whitespace-pre-line break-words leading-5 text-xs text-gray-700">
                        {normalizeDisplayText(row?.note)}
                      </span>
                    )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )

  const renderStandaloneStepContent = (step: number) => {
    if (!parsedPreview?.sections) {
      return (
        <p className="text-sm text-gray-500 font-sans">
          연동된 생기부가 없습니다. 위 <strong>업로드</strong> 버튼으로 학교생활기록부를 등록해 주세요.
        </p>
      )
    }

    if (step === 1) {
      return (
        <div className="space-y-4 text-sm">
          <p className="text-2xl font-semibold text-gray-900 leading-none">변경</p>
          <div>
            <p className="font-semibold text-gray-800 mb-2">출결상황</p>
            <div className="border border-gray-200 overflow-x-auto">
              <table className="w-full text-left border-collapse text-sm">
                <thead>
                  <tr className="bg-gray-100 border-b border-gray-200">
                    <th className="py-2 px-3 border-r border-gray-200 font-semibold text-gray-800">학년</th>
                    <th className="py-2 px-3 border-r border-gray-200 font-semibold text-gray-800">수업일수</th>
                    <th colSpan={3} className="py-2 px-3 border-r border-gray-200 font-semibold text-gray-800">결석일수</th>
                    <th colSpan={3} className="py-2 px-3 border-r border-gray-200 font-semibold text-gray-800">지각</th>
                    <th colSpan={3} className="py-2 px-3 border-r border-gray-200 font-semibold text-gray-800">조퇴</th>
                    <th colSpan={3} className="py-2 px-3 border-r border-gray-200 font-semibold text-gray-800">결과</th>
                    <th className="py-2 px-3 font-semibold text-gray-800">특기사항</th>
                  </tr>
                  <tr className="bg-gray-100 border-b border-gray-200">
                    <th className="py-1 px-3 border-r border-gray-200 text-xs text-gray-600" />
                    <th className="py-1 px-3 border-r border-gray-200 text-xs text-gray-600" />
                    {[...Array(12)].map((_, i) => (
                      <th key={i} className="py-1 px-2 border-r border-gray-200 font-medium text-gray-600 text-xs">
                        {['질병', '미인정', '기타'][i % 3]}
                      </th>
                    ))}
                    <th className="py-1 px-3 text-xs text-gray-600" />
                  </tr>
                </thead>
                <tbody>
                  {parsedSections?.attendance?.has_no_item || attendanceRows.length === 0 ? (
                    <tr><td colSpan={15} className="py-4 text-center text-gray-500">해당 사항 없음</td></tr>
                  ) : (
                    attendanceRows.map((row: any, idx: number) => (
                      <tr key={idx} className="border-b border-gray-100">
                        <td className="py-2 px-3 border-r border-gray-200">
                          {standaloneEditMode
                            ? renderEditableField(row?.grade, (value) => updateAttendanceCell(idx, 'grade', value))
                            : `${row?.grade || '-'}학년`}
                        </td>
                        <td className="py-2 px-3 border-r border-gray-200">{renderEditableField(row?.수업일수, (value) => updateAttendanceCell(idx, '수업일수', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.결석_질병, (value) => updateAttendanceCell(idx, '결석_질병', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.결석_미인정, (value) => updateAttendanceCell(idx, '결석_미인정', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.결석_기타, (value) => updateAttendanceCell(idx, '결석_기타', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.지각_질병, (value) => updateAttendanceCell(idx, '지각_질병', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.지각_미인정, (value) => updateAttendanceCell(idx, '지각_미인정', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.지각_기타, (value) => updateAttendanceCell(idx, '지각_기타', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.조퇴_질병, (value) => updateAttendanceCell(idx, '조퇴_질병', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.조퇴_미인정, (value) => updateAttendanceCell(idx, '조퇴_미인정', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.조퇴_기타, (value) => updateAttendanceCell(idx, '조퇴_기타', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.결과_질병, (value) => updateAttendanceCell(idx, '결과_질병', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.결과_미인정, (value) => updateAttendanceCell(idx, '결과_미인정', value))}</td>
                        <td className="py-2 px-2 border-r border-gray-200">{renderEditableField(row?.결과_기타, (value) => updateAttendanceCell(idx, '결과_기타', value))}</td>
                        <td className="py-2 px-3">
                          {renderEditableField(row?.특기사항, (value) => updateAttendanceCell(idx, '특기사항', value), { multiline: true })}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <p className="font-semibold text-gray-800 mb-2">자격증 및 인증 취득사항</p>
            <div className="border border-gray-200 overflow-x-auto">
              {parsedSections?.certificates?.has_no_item || (certificateRows.length === 0 && certificateItems.length === 0) ? (
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">구분</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">명칭 또는 종류</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">번호 또는 내용</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">취득년월일</th>
                      <th className="py-2 px-3 font-semibold">발급기관</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td colSpan={5} className="py-4 text-center text-gray-500">해당 사항 없음</td></tr>
                  </tbody>
                </table>
              ) : certificateRows.length > 0 ? (
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">구분</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">명칭 또는 종류</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">번호 또는 내용</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">취득년월일</th>
                      <th className="py-2 px-3 font-semibold">발급기관</th>
                    </tr>
                  </thead>
                  <tbody>
                    {certificateRows.map((row: any, idx: number) => (
                      <tr key={idx} className="border-b border-gray-100">
                        <td className="py-2 px-3 border-r border-gray-200">{renderEditableField(row?.구분, (value) => updateCertificateCell(idx, '구분', value))}</td>
                        <td className="py-2 px-3 border-r border-gray-200">{renderEditableField(row?.명칭또는종류, (value) => updateCertificateCell(idx, '명칭또는종류', value))}</td>
                        <td className="py-2 px-3 border-r border-gray-200">{renderEditableField(row?.번호또는내용, (value) => updateCertificateCell(idx, '번호또는내용', value))}</td>
                        <td className="py-2 px-3 border-r border-gray-200">{renderEditableField(row?.취득년월일, (value) => updateCertificateCell(idx, '취득년월일', value))}</td>
                        <td className="py-2 px-3">{renderEditableField(row?.발급기관, (value) => updateCertificateCell(idx, '발급기관', value))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div className="p-3 space-y-1">
                  {certificateItems.map((item: string, idx: number) => <p key={idx}>{item}</p>)}
                </div>
              )}
            </div>
          </div>
          <p className="text-xs text-gray-500 flex items-center gap-1">
            <span className="text-indigo-600 font-medium">(i)</span>
            <span>① 2022학년도 대입부터 진로희망사항은 반영되지 않습니다.</span>
          </p>
        </div>
      )
    }

    if (step === 2) {
      return (
        <div className="space-y-4 text-sm">
          <p className="text-2xl font-semibold text-gray-900 leading-none">변경</p>
          {(['1', '2', '3'] as const).map((g) => (
            <div key={`creative-new-${g}`}>
              <p className="font-semibold text-gray-800 mb-2">창의적체험활동상황 ({g}학년)</p>
              <div className="border border-gray-200 overflow-x-auto">
                <table className="w-full text-left border-collapse text-sm table-fixed">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold w-16">학년</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold w-28">영역</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold w-16">시간</th>
                      <th className="py-2 px-3 font-semibold">특기사항</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr className="border-b border-gray-100">
                      <td className="py-2 px-3 border-r border-gray-200 align-top" rowSpan={3}>{g}</td>
                      <td className="py-2 px-3 border-r border-gray-200 align-top whitespace-nowrap">자율활동</td>
                      <td className="py-2 px-3 border-r border-gray-200 align-top text-right">{renderEditableField(creativeHoursByGrade?.[g]?.autonomousHours, (value) => updateCreativeHours(g, 'autonomousHours', value))}</td>
                      <td className="py-2 px-3 align-top">{renderEditableField(creativeByGrade?.[g]?.autonomousNotes, (value) => updateCreativeNote(g, 'autonomousNotes', value), { multiline: true })}</td>
                    </tr>
                    <tr className="border-b border-gray-100">
                      <td className="py-2 px-3 border-r border-gray-200 align-top whitespace-nowrap">동아리활동</td>
                      <td className="py-2 px-3 border-r border-gray-200 align-top text-right">{renderEditableField(creativeHoursByGrade?.[g]?.clubHours, (value) => updateCreativeHours(g, 'clubHours', value))}</td>
                      <td className="py-2 px-3 align-top">{renderEditableField(creativeByGrade?.[g]?.clubNotes, (value) => updateCreativeNote(g, 'clubNotes', value), { multiline: true })}</td>
                    </tr>
                    <tr className="border-b border-gray-100">
                      <td className="py-2 px-3 border-r border-gray-200 align-top whitespace-nowrap">진로활동</td>
                      <td className="py-2 px-3 border-r border-gray-200 align-top text-right">{renderEditableField(creativeHoursByGrade?.[g]?.careerHours, (value) => updateCreativeHours(g, 'careerHours', value))}</td>
                      <td className="py-2 px-3 align-top">{renderEditableField(creativeByGrade?.[g]?.careerNotes, (value) => updateCreativeNote(g, 'careerNotes', value), { multiline: true })}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          <div>
            <p className="font-semibold text-gray-800 mb-2">봉사활동실적</p>
            <div className="border border-gray-200 overflow-x-auto">
              {parsedSections?.volunteerActivity?.has_no_item || volunteerRows.length === 0 ? (
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">학년</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">일자 또는 기간</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">장소 또는 주관기관명</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">활동내용</th>
                      <th className="py-2 px-3 font-semibold">시간</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td colSpan={5} className="py-4 text-center text-gray-500">해당 사항 없음</td></tr>
                  </tbody>
                </table>
              ) : (
                <table className="w-full text-left border-collapse text-sm">
                  <thead>
                    <tr className="bg-gray-50 border-b border-gray-200">
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">학년</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">일자 또는 기간</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">장소 또는 주관기관명</th>
                      <th className="py-2 px-3 border-r border-gray-200 font-semibold">활동내용</th>
                      <th className="py-2 px-3 font-semibold">시간</th>
                    </tr>
                  </thead>
                  <tbody>
                    {volunteerRows.map((row: any, idx: number) => (
                      <tr key={idx} className="border-b border-gray-100">
                        <td className="py-2 px-3 border-r border-gray-200 align-top whitespace-nowrap">{renderEditableField(row?.grade, (value) => updateVolunteerCell(idx, 'grade', value))}</td>
                        <td className="py-2 px-3 border-r border-gray-200 align-top whitespace-nowrap">{renderEditableField(row?.일자또는기간, (value) => updateVolunteerCell(idx, '일자또는기간', value))}</td>
                        <td className="py-2 px-3 border-r border-gray-200 align-top">{renderEditableField(row?.장소또는주관기관명, (value) => updateVolunteerCell(idx, '장소또는주관기관명', value))}</td>
                        <td className="py-2 px-3 border-r border-gray-200 align-top">{renderEditableField(row?.활동내용, (value) => updateVolunteerCell(idx, '활동내용', value), { multiline: true })}</td>
                        <td className="py-2 px-3 align-top text-right whitespace-nowrap">{renderEditableField(row?.hours, (value) => updateVolunteerCell(idx, 'hours', value))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
          <p className="text-xs text-gray-500 flex items-center gap-1">
            <span className="text-indigo-600 font-medium">(i)</span>
            <span>2022학년도 대입부터 진로희망사항은 반영되지 않습니다.</span>
          </p>
        </div>
      )
    }

    if (step === 3) {
      return (
        <div className="space-y-6 text-sm">
          <p className="text-2xl font-semibold text-gray-900 leading-none">변경</p>
          {academicGrades.map((g) => {
            const gen = academicGeneralElective[g]
            const career = academicCareerElective[g]
            const pe = academicPeArts[g]
            const genRows = Array.isArray(gen?.rows) ? gen.rows : []
            const careerRows = Array.isArray(career?.rows) ? career.rows : []
            const peRows = Array.isArray(pe?.rows) ? pe.rows : []
            const seteukRows = Array.isArray(academicByGrade?.[g]) ? academicByGrade[g] : []
            return (
              <div key={`academic-new-${g}`} className="space-y-4">
                {renderAcademicGradeBlock(
                  `${g}학년 일반선택과목`,
                  academicGeneralCols,
                  academicGeneralCols,
                  genRows,
                  gen?.이수단위합계 ?? null,
                  {
                    editable: standaloneEditMode,
                    onCellChange: (rowIndex, key, value) => updateAcademicRowCell('general_elective', g, rowIndex, key, value),
                    onTotalCreditsChange: (value) => updateAcademicTotalCredits('general_elective', g, value),
                  }
                )}
                {renderAcademicGradeBlock(
                  `${g}학년 진로선택과목`,
                  academicCareerCols,
                  academicCareerKeys,
                  careerRows,
                  career?.이수단위합계 ?? null,
                  {
                    editable: standaloneEditMode,
                    onCellChange: (rowIndex, key, value) => updateAcademicRowCell('career_elective', g, rowIndex, key, value),
                    onTotalCreditsChange: (value) => updateAcademicTotalCredits('career_elective', g, value),
                  }
                )}
                {Number(g) === 1 && (
                  <p className="text-xs text-gray-500 flex items-center gap-1">
                    <span className="text-indigo-600 font-medium">①</span>
                    <span>2021년 졸업생 이하는 일반선택, 진로선택 과목 구분 없이 교과학습발달상황에 기입됩니다.</span>
                  </p>
                )}
                {renderAcademicGradeBlock(
                  `${g}학년 체육·예술과목`,
                  academicPeCols,
                  academicPeCols,
                  peRows,
                  pe?.이수단위합계 ?? null,
                  {
                    editable: standaloneEditMode,
                    onCellChange: (rowIndex, key, value) => updateAcademicRowCell('pe_arts', g, rowIndex, key, value),
                    onTotalCreditsChange: (value) => updateAcademicTotalCredits('pe_arts', g, value),
                  }
                )}
                {renderSeteukBlock(seteukRows, {
                  editable: standaloneEditMode,
                  onSubjectChange: (rowIndex, value) => updateAcademicSeteukCell(g, rowIndex, 'subject', value),
                  onNoteChange: (rowIndex, value) => updateAcademicSeteukCell(g, rowIndex, 'note', value),
                })}
              </div>
            )
          })}
        </div>
      )
    }

    return (
      <div className="space-y-4 text-sm">
        <p className="text-2xl font-semibold text-gray-900 leading-none">변경</p>
        <div className="border border-gray-200 overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="py-2 px-3 border-r border-gray-200 font-semibold w-24">학년</th>
                <th className="py-2 px-3 font-semibold">행동특성 및 종합의견</th>
              </tr>
            </thead>
            <tbody>
              {!(behaviorByGrade?.['1'] || behaviorByGrade?.['2'] || behaviorByGrade?.['3']) ? (
                <tr><td colSpan={2} className="py-6 text-center text-gray-500">해당 사항 없음</td></tr>
              ) : (
                (['1', '2', '3'] as const).map((g) => (
                  <tr key={g} className="border-b border-gray-100">
                    <td className="py-2 px-3 border-r border-gray-200">{g}</td>
                    <td className="py-2 px-3">
                      {renderEditableField(behaviorByGrade?.[g], (value) => updateBehaviorOpinion(g, value), { multiline: true })}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-full bg-white">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 sm:py-14">
        {/* 전용 뷰(?tab=link): 참고 UI — 헤더(이름·학교·입학) + 업로드/수정 + STEP 아코디언 */}
          <>
            {/* 상단: 사용자 정보 + 액션(오른쪽 상단) */}
            <div className="sticky top-0 z-30 -mx-4 px-4 sm:-mx-6 sm:px-6 py-3 bg-white/95 backdrop-blur border-b border-gray-200">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h1 className="text-base sm:text-lg font-bold text-gray-900 font-sans truncate">생활기록부 연동하기</h1>
                  <p className="mt-0.5 text-[11px] text-gray-600 font-sans">업로드 후 변경사항을 확인하고 저장하세요.</p>
                </div>

                <div className="flex items-center gap-2 flex-shrink-0">
                  <button
                    type="button"
                    onClick={() => setRegisterModalOpen(true)}
                    disabled={pdfUploading}
                    className="inline-flex items-center justify-center px-3 py-1.5 rounded-lg bg-[#0e6093] text-white text-xs font-semibold hover:bg-[#0b4f78] transition-colors font-sans disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                  >
                    업로드
                  </button>

                  <button
                    type="button"
                    onClick={() => void handleSaveParsedSchoolRecord()}
                    disabled={!parsedPreview?.sections || schoolRecordSaving || pdfUploading}
                    className="inline-flex items-center justify-center px-3 py-1.5 rounded-lg bg-[#0e6093] text-white text-xs font-semibold hover:bg-[#0b4f78] transition-colors font-sans disabled:opacity-40 disabled:cursor-not-allowed shadow-sm"
                  >
                    {schoolRecordSaving ? '저장 중...' : '저장'}
                  </button>

                  <button
                    type="button"
                    onClick={() => setStandaloneEditMode((prev) => !prev)}
                    disabled={!parsedPreview?.sections}
                    className={`inline-flex items-center justify-center px-3 py-1.5 rounded-lg border text-xs font-semibold transition-colors font-sans ${
                      standaloneEditMode
                        ? 'border-uniroad-navy text-uniroad-navy bg-uniroad-navy-light hover:bg-slate-50'
                        : 'border-gray-300 text-gray-700 bg-white hover:bg-gray-50'
                    } disabled:opacity-40 disabled:cursor-not-allowed`}
                  >
                    {standaloneEditMode ? '수정 완료' : '수정'}
                  </button>
                </div>
              </div>
            </div>

            {/* 진행 상태/메시지 */}
            {(pdfUploading || pdfUploadMessage || pdfUploadError || schoolRecordSaving || schoolRecordSaveMessage || schoolRecordSaveError) && (
              <div className="mt-4 rounded-xl border border-gray-200 bg-gray-50 px-4 py-3">
                {pdfUploading && (
                  <div className="w-full">
                    <div className="flex items-center justify-between text-xs text-gray-600 mb-1 font-sans">
                      <span>{uploadStage === 'processing' ? '텍스트 추출 및 파싱 중...' : `파일 업로드 중 (${uploadProgress}%)`}</span>
                      {uploadStage === 'uploading' && <span>{uploadProgress}%</span>}
                    </div>
                    <div className="h-2 w-full rounded-full bg-gray-200 overflow-hidden">
                      <div
                        className="h-full bg-uniroad-navy transition-all duration-300 ease-out"
                        style={{ width: uploadStage === 'processing' ? '100%' : `${uploadProgress}%` }}
                      />
                    </div>
                  </div>
                )}
                {pdfUploadMessage && <p className="text-xs text-green-700 mt-2 font-sans">{pdfUploadMessage}</p>}
                {pdfUploadError && <p className="text-xs text-red-600 mt-2 font-sans">{pdfUploadError}</p>}
                {schoolRecordSaving && <p className="text-xs text-[#0e6093] mt-2 font-sans">저장 중...</p>}
                {schoolRecordSaveMessage && <p className="text-xs text-green-700 mt-2 font-sans">{schoolRecordSaveMessage}</p>}
                {schoolRecordSaveError && <p className="text-xs text-red-600 mt-2 font-sans">{schoolRecordSaveError}</p>}
              </div>
            )}
            {standaloneEditMode && (
              <div className="mt-3 rounded-lg border border-[#0e6093]/30 bg-[#0e6093]/5 px-3 py-2 text-xs text-[#0e6093] font-sans">
                수정 모드입니다. 각 칸을 직접 편집할 수 있습니다.
              </div>
            )}

            {/* STEP 01~04: 리스트형 UI (참고 이미지 스타일) */}
            <div className="mt-8 border-t border-[#0e6093]">
              {[
                { step: 1, label: '출결상황, 자격증 및 인증 취득상황' },
                { step: 2, label: '창의적체험활동상황, 봉사활동실적' },
                { step: 3, label: '교과학습발달상황' },
                { step: 4, label: '행동특성 및 종합의견' },
              ].map(({ step, label }) => {
                const isOpen = openAccordionStep === step - 1
                return (
                  <div key={step} className="border-b border-gray-200">
                    <button
                      type="button"
                      onClick={() => setOpenAccordionStep(isOpen ? null : step - 1)}
                      className="w-full flex items-center gap-4 px-2 sm:px-4 py-5 text-left hover:bg-gray-50 transition-colors"
                    >
                      <span className="flex-shrink-0 rounded-full bg-[#0e6093] px-4 py-2 text-sm font-extrabold tracking-wide text-white font-sans">
                        STEP {String(step).padStart(2, '0')}
                      </span>
                      <span className="flex-1 text-base font-semibold text-gray-900 font-sans">{label}</span>
                      <svg
                        className={`w-6 h-6 text-[#0e6093] flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </button>
                    {isOpen && (
                      <div className="px-2 sm:px-4 py-4 border-t border-gray-200 bg-[#f7f9fc]">
                        {renderStandaloneStepContent(step)}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            <SchoolRecordRegisterModal
              isOpen={registerModalOpen}
              onClose={() => setRegisterModalOpen(false)}
              onSave={handleRegisterModalSave}
              isSaving={pdfUploading}
            />
          </>
      </div>
    </div>
  )
}
