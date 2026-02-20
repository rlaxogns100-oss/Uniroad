import { Capacitor } from '@capacitor/core'

/**
 * 앱에서 사용하는 API 베이스 URL (빌드 시 설정).
 * Capacitor(iOS/Android) 앱 빌드 시 .env에 VITE_API_BASE_URL=https://uni2road.com 로 설정하면
 * 번들된 앱이 해당 서버로 요청합니다. 미설정 시 상대 경로(웹 배포와 동일) 사용.
 */
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

/** 프로덕션 API 서버 (Capacitor 앱에서 env 미설정 시 폴백) */
const PRODUCTION_API_BASE = 'https://uni2road.com'
const GALAXY_APP_SOURCE_QUERY_VALUE = 'galaxy'
const GALAXY_APP_SOURCE_QUERY_KEY = 'app_source'
const GALAXY_APP_REFERRER_PREFIX = 'android-app://com.uniroad.app'
const GALAXY_APP_SESSION_KEY = 'uniroad_galaxy_app_session'

/**
 * 실제 요청에 쓸 API 베이스 URL.
 * Capacitor 앱인데 API_BASE가 비어 있으면 프로덕션 서버 사용 (npm run build만 했을 때 대비).
 */
export const getApiBaseUrl = (): string => {
  if (API_BASE) return API_BASE
  if (typeof window !== 'undefined') {
    try {
      if (Capacitor.isNativePlatform()) return PRODUCTION_API_BASE
    } catch (_) {}
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
    return (
      window.localStorage.getItem(GALAXY_APP_SESSION_KEY) === '1' ||
      window.sessionStorage.getItem(GALAXY_APP_SESSION_KEY) === '1'
    )
  } catch (_) {
    return false
  }
}

const persistGalaxySessionFlag = (): void => {
  try {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(GALAXY_APP_SESSION_KEY, '1')
    window.sessionStorage.setItem(GALAXY_APP_SESSION_KEY, '1')
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
