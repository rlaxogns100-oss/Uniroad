import { Capacitor } from '@capacitor/core'

/**
 * 앱에서 사용하는 API 베이스 URL (빌드 시 설정).
 * - 로컬 개발(모바일): .env에 VITE_API_BASE_URL=http://localhost:8000, VITE_PRE_DEPLOY=true 두고 npm run build:ios:local / cap:ios:local
 * - 실제 기기 테스트: .env을 PC IP로 (예: http://192.168.0.5:8000)
 * - 배포용: npm run build:ios / cap:ios (VITE_PRE_DEPLOY 없음 → uni2road.com 사용)
 */
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

/** 배포 전 모드: true면 모바일도 웹과 같은 API 서버 사용 (프로덕션 폴백 비활성화) */
export const PRE_DEPLOY = import.meta.env.VITE_PRE_DEPLOY === 'true'

/** 프로덕션 API 서버 (Capacitor 앱에서 env 미설정 시 폴백, PRE_DEPLOY일 땐 사용 안 함) */
const PRODUCTION_API_BASE = 'https://uni2road.com'
const GALAXY_APP_SOURCE_QUERY_VALUE = 'galaxy'
const GALAXY_APP_SOURCE_QUERY_KEY = 'app_source'
const GALAXY_APP_REFERRER_PREFIX = 'android-app://com.uniroad.app'
const GALAXY_APP_SESSION_KEY = 'uniroad_galaxy_app_session'
const GALAXY_APP_SESSION_TS_KEY = 'uniroad_galaxy_app_session_ts'
const GALAXY_APP_SESSION_TTL_MS = 1000 * 60 * 60 * 6

/** 배포 전 로컬 개발 시 API 기본값 (모바일도 웹과 같은 서버 쓰기 위함) */
const DEV_API_BASE = 'http://localhost:8000'

/**
 * 실제 요청에 쓸 API 베이스 URL.
 * - PRE_DEPLOY(true): 모바일도 웹과 동일. API_BASE 있으면 사용, 없으면 DEV_API_BASE(로컬).
 * - 배포 빌드: Capacitor에서 API_BASE 비어 있으면 프로덕션(uni2road.com) 사용.
 */
export const getApiBaseUrl = (): string => {
  if (API_BASE) return API_BASE
  if (PRE_DEPLOY) return DEV_API_BASE
  if (typeof window !== 'undefined') {
    try {
      if (Capacitor.isNativePlatform()) return PRODUCTION_API_BASE
    } catch (_) {}
    const origin = (window.location?.origin || '').toLowerCase()
    if (/^(capacitor|ionic|file):/.test(origin)) return PRODUCTION_API_BASE
    // 웹에서는 현재 오리진을 API 베이스로 사용해 localhost fallback/CORS를 방지한다.
    if (origin && /^(https?):\/\//.test(origin)) return origin
  }
  return ''
}

/**
 * Capacitor 앱 여부 확인 (런타임에 호출)
 * iOS WebView에서 SSE ReadableStream이 제대로 동작하지 않아 비스트리밍 API 사용
 */
export const isCapacitorApp = (): boolean => {
  try {
    // Capacitor는 브라우저 환경에서만 사용 가능
    if (typeof window === 'undefined') return false
    return Capacitor.isNativePlatform()
  } catch (e) {
    return false
  }
}

/**
 * 스토어/앱 빌드에서 실행 중인지 여부 (UI: User 배지, 구독 관리 숨김용)
 * - Capacitor 네이티브 앱 또는 Galaxy 등 앱 웹뷰
 */
export const isAppBuild = (): boolean => {
  try {
    if (typeof window === 'undefined') return false
    return isCapacitorApp() || isGalaxyAppSession()
  } catch (e) {
    return false
  }
}

/**
 * 현재 플랫폼 확인 (런타임에 호출)
 */
export const getPlatform = (): string => {
  try {
    if (typeof window === 'undefined') return 'web'
    return Capacitor.getPlatform()
  } catch (e) {
    return 'web'
  }
}

const readGalaxySessionFlag = (): boolean => {
  try {
    if (typeof window === 'undefined') return false
    const ua = window.navigator?.userAgent || ''
    const isAndroidUa = /Android/i.test(ua)
    const isStandaloneMode =
      (typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches) ||
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      Boolean((window.navigator as any).standalone)
    const isNativeApp = isCapacitorApp()
    const isAppLikeRuntime = isAndroidUa && (isStandaloneMode || isNativeApp)
    if (!isAppLikeRuntime) return false

    const hasFlag =
      window.localStorage.getItem(GALAXY_APP_SESSION_KEY) === '1' ||
      window.sessionStorage.getItem(GALAXY_APP_SESSION_KEY) === '1'
    if (!hasFlag) return false

    const tsRaw =
      window.localStorage.getItem(GALAXY_APP_SESSION_TS_KEY) ||
      window.sessionStorage.getItem(GALAXY_APP_SESSION_TS_KEY)
    const ts = Number(tsRaw)
    if (!Number.isFinite(ts)) return false
    return Date.now() - ts <= GALAXY_APP_SESSION_TTL_MS
  } catch (_) {
    return false
  }
}

const persistGalaxySessionFlag = (): void => {
  try {
    if (typeof window === 'undefined') return
    const now = String(Date.now())
    window.localStorage.setItem(GALAXY_APP_SESSION_KEY, '1')
    window.sessionStorage.setItem(GALAXY_APP_SESSION_KEY, '1')
    window.localStorage.setItem(GALAXY_APP_SESSION_TS_KEY, now)
    window.sessionStorage.setItem(GALAXY_APP_SESSION_TS_KEY, now)
  } catch (_) {}
}

export const isGalaxyAppSession = (): boolean => {
  try {
    if (typeof window === 'undefined') return false

    const hasGalaxyQuery =
      new URLSearchParams(window.location.search).get(GALAXY_APP_SOURCE_QUERY_KEY) ===
      GALAXY_APP_SOURCE_QUERY_VALUE
    const hasGalaxyReferrer = (document.referrer || '').startsWith(GALAXY_APP_REFERRER_PREFIX)
    const ua = window.navigator?.userAgent || ''
    const isAndroidUa = /Android/i.test(ua)
    const isStandaloneMode =
      (typeof window.matchMedia === 'function' && window.matchMedia('(display-mode: standalone)').matches) ||
      // iOS PWA 호환 속성 (Android TWA에서는 false일 수 있으나 안전하게 체크)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      Boolean((window.navigator as any).standalone)
    const hasAndroidAppLikeContext = isAndroidUa && isStandaloneMode

    if (hasGalaxyQuery || hasGalaxyReferrer || hasAndroidAppLikeContext) {
      persistGalaxySessionFlag()
      return true
    }

    return readGalaxySessionFlag()
  } catch (_) {
    return false
  }
}
