import { useEffect, useRef, useState } from 'react'
import { toCanvas, getFontEmbedCSS } from 'html-to-image'
import { jsPDF } from 'jspdf'
import SchoolRecordVisualReport, { type VisualReportData } from './SchoolRecordVisualReport'
import { getApiBaseUrl } from '../config'

type RunnerPhase = 'idle' | 'generating' | 'rendering'

interface Props {
  active: boolean
  requestId: number
  token: string | null
  onPhaseChange: (phase: RunnerPhase) => void
  onSuccess: () => void
  onError: (message: string) => void
}

export default function SchoolRecordPdfDownloadRunner({
  active,
  requestId,
  token,
  onPhaseChange,
  onSuccess,
  onError,
}: Props) {
  const [reportData, setReportData] = useState<VisualReportData | null>(null)
  const reportRef = useRef<HTMLDivElement>(null)
  const startedRequestIdRef = useRef<number | null>(null)
  const renderedRequestIdRef = useRef<number | null>(null)
  const onPhaseChangeRef = useRef(onPhaseChange)
  const onSuccessRef = useRef(onSuccess)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onPhaseChangeRef.current = onPhaseChange
    onSuccessRef.current = onSuccess
    onErrorRef.current = onError
  }, [onPhaseChange, onSuccess, onError])

  useEffect(() => {
    if (!active || !requestId) return
    if (startedRequestIdRef.current === requestId) return
    if (!token) {
      onErrorRef.current('로그인이 필요합니다.')
      return
    }

    startedRequestIdRef.current = requestId
    renderedRequestIdRef.current = null

    const controller = new AbortController()
    let cancelled = false

    const run = async () => {
      onPhaseChangeRef.current('generating')
      setReportData(null)

      try {
        const apiBase = getApiBaseUrl()
        const url = `${apiBase}/api/school-record/generate-visual-report`
        const res = await fetch(url, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          signal: controller.signal,
        })

        if (!res.ok) {
          const errBody = await res.text()
          throw new Error(errBody || `HTTP ${res.status}`)
        }

        const reader = res.body?.getReader()
        if (!reader) throw new Error('스트림을 열 수 없습니다.')

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed.startsWith('data: ')) continue

            const payload = trimmed.slice(6)
            if (!payload) continue

            try {
              const event = JSON.parse(payload)
              if (event.type === 'done' && event.data) {
                if (!cancelled) setReportData(event.data as VisualReportData)
                return
              }
              if (event.type === 'error') {
                throw new Error(String(event.message || '보고서 생성에 실패했습니다.'))
              }
            } catch (err) {
              if (err instanceof Error && !err.message.toLowerCase().includes('json')) {
                throw err
              }
            }
          }
        }
      } catch (err) {
        if (controller.signal.aborted || cancelled) return
        startedRequestIdRef.current = null
        onErrorRef.current(err instanceof Error ? err.message : '보고서 생성에 실패했습니다.')
      }
    }

    void run()

    return () => {
      cancelled = true
      controller.abort()
    }
  }, [active, requestId, token])

  useEffect(() => {
    if (!active || !reportData) return
    if (!requestId) return
    if (renderedRequestIdRef.current === requestId) return

    renderedRequestIdRef.current = requestId

    let cancelled = false

    const renderPdf = async () => {
      try {
        onPhaseChangeRef.current('rendering')
        await document.fonts.ready
        await new Promise((resolve) => window.setTimeout(resolve, 100))

        const root = reportRef.current
        if (!root) throw new Error('PDF 렌더링 대상을 찾지 못했습니다.')

        const pageElements = Array.from(root.querySelectorAll<HTMLElement>('[data-page]'))
        if (pageElements.length === 0) {
          throw new Error('리포트 페이지를 찾지 못했습니다.')
        }

        const pdf = new jsPDF({
          orientation: 'portrait',
          unit: 'mm',
          format: 'a4',
          compress: true,
        })

        const pdfWidth = 210
        const pdfHeight = 297
        const scale = 2.5

        const fontCSS = await getFontEmbedCSS(root)

        for (let index = 0; index < pageElements.length; index += 1) {
          const page = pageElements[index]
          const canvas = await toCanvas(page, {
            backgroundColor: '#ffffff',
            pixelRatio: scale,
            fontEmbedCSS: fontCSS,
          })

          const imgData = canvas.toDataURL('image/png')
          if (index > 0) pdf.addPage()
          pdf.addImage(imgData, 'PNG', 0, 0, pdfWidth, pdfHeight, undefined, 'FAST')
        }

        if (!cancelled) {
          pdf.save(`${reportData.studentName}_생기부_분석_리포트.pdf`)
          startedRequestIdRef.current = null
          onSuccessRef.current()
        }
      } catch (err) {
        if (!cancelled) {
          startedRequestIdRef.current = null
          renderedRequestIdRef.current = null
          onErrorRef.current(err instanceof Error ? err.message : 'PDF 생성에 실패했습니다.')
        }
      }
    }

    void renderPdf()

    return () => {
      cancelled = true
    }
  }, [active, reportData, requestId])

  if (!active) return null

  return (
    <div
      style={{
        position: 'fixed',
        left: '-100000px',
        top: 0,
        opacity: 0,
        pointerEvents: 'none',
      }}
      aria-hidden="true"
    >
      {reportData ? <SchoolRecordVisualReport ref={reportRef} data={reportData} /> : null}
    </div>
  )
}
