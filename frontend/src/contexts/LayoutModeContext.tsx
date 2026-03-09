import { createContext, useContext, useState, useMemo, useEffect, useCallback } from 'react'

const STORAGE_KEY = 'uniroad_layout_mode'
const BREAKPOINT = 640

export type LayoutMode = 'auto' | 'desktop' | 'mobile'

function loadLayoutMode(): LayoutMode {
  return 'auto'
}

interface LayoutModeContextValue {
  layoutMode: LayoutMode
  setLayoutMode: (mode: LayoutMode) => void
  /** 뷰포트 기준이면 화면 너비, 강제 모드면 그에 맞춤 */
  isDesktopLayout: boolean
}

const LayoutModeContext = createContext<LayoutModeContextValue | null>(null)

export function LayoutModeProvider({ children }: { children: React.ReactNode }) {
  const [layoutMode, setLayoutModeState] = useState<LayoutMode>(loadLayoutMode)
  const [viewportWidth, setViewportWidth] = useState(() =>
    typeof window === 'undefined' ? 1024 : window.innerWidth
  )

  const setLayoutMode = useCallback((mode: LayoutMode) => {
    setLayoutModeState(mode)
  }, [])

  const isDesktopLayout = useMemo(() => {
    if (layoutMode === 'desktop') return true
    if (layoutMode === 'mobile') return false
    return viewportWidth >= BREAKPOINT
  }, [layoutMode, viewportWidth])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const update = () => setViewportWidth(window.innerWidth)
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [])

  useEffect(() => {
    // 과거 강제 보기 모드(localStorage)로 레이아웃이 고정되는 문제를 방지한다.
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch (_) {}
  }, [])

  useEffect(() => {
    if (typeof document === 'undefined') return
    if (layoutMode === 'auto') {
      document.body.removeAttribute('data-layout-force')
    } else {
      document.body.setAttribute('data-layout-force', layoutMode)
    }
  }, [layoutMode])

  const value = useMemo<LayoutModeContextValue>(
    () => ({ layoutMode, setLayoutMode, isDesktopLayout }),
    [layoutMode, setLayoutMode, isDesktopLayout]
  )

  return (
    <LayoutModeContext.Provider value={value}>
      {children}
    </LayoutModeContext.Provider>
  )
}

export function useLayoutMode(): LayoutModeContextValue {
  const ctx = useContext(LayoutModeContext)
  if (!ctx) {
    const fallback = typeof window !== 'undefined' && window.innerWidth >= BREAKPOINT
    return {
      layoutMode: 'auto',
      setLayoutMode: () => {},
      isDesktopLayout: fallback,
    }
  }
  return ctx
}
