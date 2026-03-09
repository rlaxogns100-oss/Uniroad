import { useState, useEffect, useRef, useCallback } from 'react'
import SchoolRecordVisualReport, { type VisualReportData } from './SchoolRecordVisualReport'
import { getApiBaseUrl } from '../config'

type LogEntry = { ts: number; msg: string }

type Phase = 'idle' | 'generating' | 'rendering' | 'done' | 'error'

interface Props {
  open: boolean
  onClose: () => void
  token: string | null
}

export default function ReportGeneratorModal({ open, onClose, token }: Props) {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [phase, setPhase] = useState<Phase>('idle')
  const [reportData, setReportData] = useState<VisualReportData | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const reportRef = useRef<HTMLDivElement>(null)
  const logEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  const addLog = useCallback((msg: string) => {
    setLogs(prev => [...prev, { ts: Date.now(), msg }])
  }, [])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const startGeneration = useCallback(async () => {
    if (!token) {
      setPhase('error')
      setErrorMsg('로그인이 필요합니다.')
      return
    }

    setPhase('generating')
    setLogs([])
    setReportData(null)
    setErrorMsg('')
    addLog('🚀 시각 보고서 생성을 시작합니다...')

    const ctrl = new AbortController()
    abortRef.current = ctrl

    const apiBase = getApiBaseUrl()
    const url = `${apiBase}/api/school-record/generate-visual-report`

    try {
      const res = await fetch(url, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        signal: ctrl.signal,
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

          try {
            const event = JSON.parse(trimmed.slice(6))

            if (event.type === 'log') {
              addLog(event.message)
            } else if (event.type === 'done') {
              addLog('✅ 데이터 수신 완료! PDF를 생성합니다...')
              setReportData(event.data as VisualReportData)
              setPhase('rendering')
            } else if (event.type === 'error') {
              throw new Error(event.message)
            }
          } catch (parseErr: any) {
            if (parseErr.message && !parseErr.message.includes('JSON')) {
              throw parseErr
            }
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        addLog('⚠️ 생성이 취소되었습니다.')
        setPhase('idle')
        return
      }
      console.error('Report generation error:', err)
      setPhase('error')
      setErrorMsg(err.message || '알 수 없는 오류가 발생했습니다.')
      addLog(`❌ 오류: ${err.message}`)
    }
  }, [token, addLog])

  useEffect(() => {
    if (open && phase === 'idle') {
      startGeneration()
    }
  }, [open, phase, startGeneration])

  useEffect(() => {
    if (phase !== 'rendering' || !reportData) return

    const timer = setTimeout(async () => {
      try {
        addLog('📄 React 컴포넌트를 렌더링하고 있습니다...')

        await new Promise(r => setTimeout(r, 500))

        const el = reportRef.current
        if (!el) throw new Error('렌더링 요소를 찾을 수 없습니다.')

        addLog('🖨️ PDF로 변환 중입니다...')

        const html2pdf = (await import('html2pdf.js')).default

        const pages = el.querySelectorAll('[data-page]')
        if (pages.length === 0) {
          const opt = {
            margin: 0,
            filename: `${reportData.studentName}_생기부_분석_리포트.pdf`,
            image: { type: 'jpeg' as const, quality: 0.95 },
            html2canvas: { scale: 2, useCORS: true, logging: false },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' as const },
          }

          await html2pdf().set(opt).from(el).save()
        } else {
          const opt = {
            margin: 0,
            filename: `${reportData.studentName}_생기부_분석_리포트.pdf`,
            image: { type: 'jpeg' as const, quality: 0.95 },
            html2canvas: { scale: 2, useCORS: true, logging: false },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' as const },
            pagebreak: { mode: ['css', 'legacy'] },
          }

          await html2pdf().set(opt).from(el).save()
        }

        addLog('✅ PDF 다운로드 완료!')
        setPhase('done')
      } catch (err: any) {
        console.error('PDF generation error:', err)
        setPhase('error')
        setErrorMsg(err.message || 'PDF 변환 중 오류가 발생했습니다.')
        addLog(`❌ PDF 변환 오류: ${err.message}`)
      }
    }, 1000)

    return () => clearTimeout(timer)
  }, [phase, reportData, addLog])

  const handleClose = () => {
    abortRef.current?.abort()
    setPhase('idle')
    setLogs([])
    setReportData(null)
    setErrorMsg('')
    onClose()
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={handleClose}>
      <div
        className="relative flex max-h-[90vh] w-full max-w-[560px] flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        onClick={e => e.stopPropagation()}
      >
        {/* 헤더 */}
        <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4">
          <div>
            <h2 className="text-base font-bold text-gray-900">📊 분석 리포트 생성</h2>
            <p className="mt-0.5 text-xs text-gray-500">
              {phase === 'generating' && '생기부를 분석하고 있습니다...'}
              {phase === 'rendering' && 'PDF를 생성하고 있습니다...'}
              {phase === 'done' && '완료되었습니다!'}
              {phase === 'error' && '오류가 발생했습니다.'}
              {phase === 'idle' && '준비 중...'}
            </p>
          </div>
          <button
            type="button"
            onClick={handleClose}
            className="flex h-8 w-8 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
          >
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 진행 바 */}
        <div className="h-1 w-full bg-gray-100">
          <div
            className="h-full transition-all duration-700 ease-out"
            style={{
              width: phase === 'idle' ? '0%'
                : phase === 'generating' ? '60%'
                : phase === 'rendering' ? '85%'
                : phase === 'done' ? '100%'
                : '0%',
              backgroundColor: phase === 'error' ? '#EF4444' : '#5B9BD5',
            }}
          />
        </div>

        {/* 로그 영역 */}
        <div className="flex-1 overflow-y-auto bg-gray-50 px-6 py-4" style={{ minHeight: '280px', maxHeight: '400px' }}>
          <div className="space-y-2">
            {logs.map((log, i) => (
              <div key={i} className="flex items-start gap-2">
                <span className="mt-0.5 text-[10px] text-gray-400 tabular-nums">
                  {new Date(log.ts).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
                <span className="text-[13px] leading-5 text-gray-700">{log.msg}</span>
              </div>
            ))}
            {phase === 'generating' && (
              <div className="flex items-center gap-2 pt-1">
                <div className="h-2 w-2 animate-pulse rounded-full bg-blue-400" />
                <span className="text-xs text-gray-400">처리 중...</span>
              </div>
            )}
          </div>
          <div ref={logEndRef} />
        </div>

        {/* 에러 메시지 */}
        {phase === 'error' && errorMsg && (
          <div className="border-t border-red-200 bg-red-50 px-6 py-3">
            <p className="text-xs text-red-600">{errorMsg}</p>
          </div>
        )}

        {/* 하단 버튼 */}
        <div className="flex items-center justify-end gap-3 border-t border-gray-200 px-6 py-4">
          {phase === 'error' && (
            <button
              type="button"
              onClick={() => { setPhase('idle'); startGeneration() }}
              className="rounded-lg bg-blue-500 px-4 py-2 text-sm font-bold text-white transition hover:bg-blue-600"
            >
              다시 시도
            </button>
          )}
          <button
            type="button"
            onClick={handleClose}
            className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-bold text-gray-700 transition hover:bg-gray-50"
          >
            {phase === 'done' ? '닫기' : '취소'}
          </button>
        </div>
      </div>

      {/* 오프스크린 렌더링 영역 */}
      {reportData && (
        <div
          style={{
            position: 'fixed',
            left: '-9999px',
            top: 0,
            opacity: 0,
            pointerEvents: 'none',
          }}
        >
          <SchoolRecordVisualReport ref={reportRef} data={reportData} />
        </div>
      )}
    </div>
  )
}
