import { Capacitor } from '@capacitor/core'

/**
 * 앱에서 사용하는 API 베이스 URL (빌드 시 설정).
 * Capacitor(iOS/Android) 앱 빌드 시 .env에 VITE_API_BASE_URL=https://uni2road.com 로 설정하면
 * 번들된 앱이 해당 서버로 요청합니다. 미설정 시 상대 경로(웹 배포와 동일) 사용.
 */
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

/** 프로덕션 API 서버 (Capacitor 앱에서 env 미설정 시 폴백) */
const PRODUCTION_API_BASE = 'https://uni2road.com'

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
