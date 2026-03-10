import React, { createContext, useCallback, useContext, useRef, useState } from 'react'
import type { VisualReportData } from '../components/SchoolRecordVisualReport'
import { getApiBaseUrl } from '../config'

type CacheStatus = 'idle' | 'generating' | 'done' | 'error'

interface VisualReportCacheContextType {
  cachedData: VisualReportData | null
  status: CacheStatus
  pregenerate: (token: string) => void
  consumeCachedData: () => VisualReportData | null
  waitForData: () => Promise<VisualReportData | null>
  invalidate: () => void
}

const VisualReportCacheContext = createContext<VisualReportCacheContextType>({
  cachedData: null,
  status: 'idle',
  pregenerate: () => {},
  consumeCachedData: () => null,
  waitForData: () => Promise.resolve(null),
  invalidate: () => {},
})

export function VisualReportCacheProvider({ children }: { children: React.ReactNode }) {
  const [cachedData, setCachedData] = useState<VisualReportData | null>(null)
  const [status, setStatus] = useState<CacheStatus>('idle')
  const abortRef = useRef<AbortController | null>(null)
  const resolversRef = useRef<Array<(data: VisualReportData | null) => void>>([])
  const dataRef = useRef<VisualReportData | null>(null)
  const statusRef = useRef<CacheStatus>('idle')

  const flushResolvers = useCallback((data: VisualReportData | null) => {
    const pending = resolversRef.current
    resolversRef.current = []
    pending.forEach((r) => r(data))
  }, [])

  const pregenerate = useCallback((token: string) => {
    if (statusRef.current === 'generating') return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setCachedData(null)
    dataRef.current = null
    setStatus('generating')
    statusRef.current = 'generating'

    const run = async () => {
      try {
        const apiBase = getApiBaseUrl()
        const res = await fetch(`${apiBase}/api/school-record/generate-visual-report`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          signal: controller.signal,
        })

        if (!res.ok) throw new Error(`HTTP ${res.status}`)

        const reader = res.body?.getReader()
        if (!reader) throw new Error('No stream')

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
                const data = event.data as VisualReportData
                setCachedData(data)
                dataRef.current = data
                setStatus('done')
                statusRef.current = 'done'
                flushResolvers(data)
                return
              }
              if (event.type === 'error') {
                throw new Error(String(event.message || '보고서 생성 실패'))
              }
            } catch (err) {
              if (err instanceof Error && !err.message.toLowerCase().includes('json')) {
                throw err
              }
            }
          }
        }
      } catch (err) {
        if (controller.signal.aborted) return
        setStatus('error')
        statusRef.current = 'error'
        flushResolvers(null)
      }
    }

    void run()
  }, [flushResolvers])

  const consumeCachedData = useCallback(() => {
    const data = dataRef.current
    if (data) {
      setCachedData(null)
      dataRef.current = null
      setStatus('idle')
      statusRef.current = 'idle'
    }
    return data
  }, [])

  const waitForData = useCallback((): Promise<VisualReportData | null> => {
    if (statusRef.current === 'done' && dataRef.current) {
      return Promise.resolve(dataRef.current)
    }
    if (statusRef.current === 'generating') {
      return new Promise<VisualReportData | null>((resolve) => {
        resolversRef.current.push(resolve)
      })
    }
    return Promise.resolve(null)
  }, [])

  const invalidate = useCallback(() => {
    abortRef.current?.abort()
    setCachedData(null)
    dataRef.current = null
    setStatus('idle')
    statusRef.current = 'idle'
    flushResolvers(null)
  }, [flushResolvers])

  return (
    <VisualReportCacheContext.Provider
      value={{ cachedData, status, pregenerate, consumeCachedData, waitForData, invalidate }}
    >
      {children}
    </VisualReportCacheContext.Provider>
  )
}

export function useVisualReportCache() {
  return useContext(VisualReportCacheContext)
}
