/**
 * 사용자 추적 유틸리티
 * - 페이지 뷰 추적
 * - 사용자 행동 추적
 * - UTM 파라미터 파싱
 */

import { v4 as uuidv4 } from 'uuid'
import posthog from 'posthog-js'
import { getApiBaseUrl } from '../config'
import type { AuthTriggerValue, TrackingEventName } from './trackingSchema'

// 세션 ID 관리
const SESSION_KEY = 'uniroad_session_id'
const SESSION_DURATION = 30 * 60 * 1000 // 30분

// 세션 ID 가져오기 또는 생성
export function getSessionId(): string {
  const stored = sessionStorage.getItem(SESSION_KEY)
  if (stored) {
    const { id, timestamp } = JSON.parse(stored)
    // 세션 만료 확인
    if (Date.now() - timestamp < SESSION_DURATION) {
      return id
    }
  }
  
  // 새 세션 생성
  const newId = uuidv4()
  sessionStorage.setItem(SESSION_KEY, JSON.stringify({
    id: newId,
    timestamp: Date.now()
  }))
  return newId
}

// UTM 파라미터 파싱
export function parseUTMParams(): Record<string, string | null> {
  const params = new URLSearchParams(window.location.search)
  return {
    utm_source: params.get('utm_source'),
    utm_medium: params.get('utm_medium'),
    utm_campaign: params.get('utm_campaign'),
    utm_content: params.get('utm_content'),
    utm_term: params.get('utm_term')
  }
}

// UTM 파라미터 저장 (세션 동안 유지)
const UTM_KEY = 'uniroad_utm_params'

// 진입 URL (세션 동안 유지 - 사용자가 처음 들어온 랜딩 페이지 URL)
const ENTRY_URL_KEY = 'uniroad_entry_url'
const FIRST_INTERACTION_KEY = 'uniroad_first_interaction'
const LAST_TRIGGER_KEY = 'uniroad_last_business_trigger'
const AUTH_TRIGGER_KEY = 'uniroad_login_modal_source'
const AUTH_TRIGGER_META_KEY = 'uniroad_login_modal_source_meta'
const INTERNAL_TRACKING_EMAILS = new Set(['herry0515@naver.com'])
const INTERNAL_TRACKING_NAMES = new Set(['김도균'])

/** 세션에서 진입 URL 가져오기 (처음 들어온 페이지의 전체 URL) */
export function getEntryUrl(): string | null {
  return sessionStorage.getItem(ENTRY_URL_KEY)
}

/** 진입 URL 저장 - 아직 없을 때만 저장 (첫 방문 페이지) */
export function setEntryUrlIfEmpty(): void {
  if (!sessionStorage.getItem(ENTRY_URL_KEY)) {
    sessionStorage.setItem(ENTRY_URL_KEY, window.location.href)
  }
}

export function saveUTMParams(): void {
  const utm = parseUTMParams()
  // UTM 파라미터가 있을 때만 저장
  if (utm.utm_source || utm.utm_medium || utm.utm_campaign) {
    sessionStorage.setItem(UTM_KEY, JSON.stringify(utm))
  }
}

export function getUTMParams(): Record<string, string | null> {
  const stored = sessionStorage.getItem(UTM_KEY)
  if (stored) {
    return JSON.parse(stored)
  }
  return parseUTMParams()
}

// 페이지 타입 결정
export function getPageType(pathname: string): string {
  if (pathname === '/') return 'landing'
  if (pathname.includes('/chat')) return 'chat'
  if (pathname.includes('/admin') || pathname.includes('/upload')) return 'admin'
  return 'other'
}

type StoredUser = {
  id?: string
  email?: string
  name?: string
  is_premium?: boolean
} | null

function getStoredUser(): StoredUser {
  try {
    const raw = localStorage.getItem('user')
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function isInternalTrackingUser(user: StoredUser = getStoredUser()): boolean {
  if (!user) return false
  const email = String(user.email || '').trim().toLowerCase()
  const name = String(user.name || '').trim()
  return INTERNAL_TRACKING_EMAILS.has(email) || INTERNAL_TRACKING_NAMES.has(name)
}

function getApiBase(): string {
  return getApiBaseUrl() || ''
}

function buildCommonProperties(customData?: Record<string, any>): Record<string, any> {
  const sessionId = getSessionId()
  const pathname = window.location.pathname
  const storedUser = getStoredUser()
  const authTrigger = readAuthTrigger()

  return {
    session_id: sessionId,
    entry_url: getEntryUrl(),
    page_path: pathname,
    page_type: getPageType(pathname),
    is_logged_in: Boolean(localStorage.getItem('access_token')),
    user_id: storedUser?.id || null,
    user_type: storedUser?.is_premium ? 'premium' : storedUser?.id ? 'authenticated' : 'anonymous',
    is_internal: isInternalTrackingUser(storedUser),
    auth_trigger: authTrigger,
    first_interaction_type: sessionStorage.getItem(FIRST_INTERACTION_KEY),
    ...getUTMParams(),
    ...customData,
  }
}

// 이전 페이지 추적
let previousPageTimestamp: number | null = null
let previousPagePath: string | null = null
let lastTrackedPageViewKey: string | null = null
let lastTrackedPageViewAt = 0

function capturePostHogEvent(eventName: string, properties?: Record<string, any>): void {
  try {
    if (typeof window === 'undefined') return
    posthog.capture(eventName, properties)
  } catch {
    // PostHog 추적 실패는 무시
  }
}

async function sendTrackingRequest(path: string, payload: Record<string, any>): Promise<void> {
  const token = localStorage.getItem('access_token')
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 4000)
  try {
    await fetch(`${getApiBase()}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
  } finally {
    clearTimeout(timeoutId)
  }
}

function rememberFirstInteraction(interactionType?: string): void {
  if (!interactionType) return
  if (!sessionStorage.getItem(FIRST_INTERACTION_KEY)) {
    sessionStorage.setItem(FIRST_INTERACTION_KEY, interactionType)
  }
}

function rememberLastTrigger(eventName: string, properties: Record<string, any>): void {
  sessionStorage.setItem(LAST_TRIGGER_KEY, JSON.stringify({
    event_name: eventName,
    event_time: Date.now(),
    properties,
  }))
}

export function getLastBusinessTrigger(): Record<string, any> | null {
  try {
    const raw = sessionStorage.getItem(LAST_TRIGGER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setAuthTrigger(trigger: AuthTriggerValue | string, metadata?: Record<string, any>): void {
  sessionStorage.setItem(AUTH_TRIGGER_KEY, trigger)
  sessionStorage.setItem(
    AUTH_TRIGGER_META_KEY,
    JSON.stringify({
      trigger,
      ...metadata,
    })
  )
}

export function readAuthTrigger(): string | null {
  return sessionStorage.getItem(AUTH_TRIGGER_KEY)
}

export function consumeAuthTrigger(): Record<string, any> {
  let parsed: Record<string, any> = {}
  try {
    const raw = sessionStorage.getItem(AUTH_TRIGGER_META_KEY)
    parsed = raw ? JSON.parse(raw) : {}
  } catch {
    parsed = {}
  }
  const lastTrigger = getLastBusinessTrigger()
  sessionStorage.removeItem(AUTH_TRIGGER_KEY)
  sessionStorage.removeItem(AUTH_TRIGGER_META_KEY)
  return {
    auth_trigger: parsed.trigger || null,
    ...parsed,
    trigger_event: lastTrigger?.event_name || null,
  }
}

export function identifyTrackingUser(user: { id: string; email?: string; name?: string; is_premium?: boolean }): void {
  try {
    if (!user?.id) return
    posthog.identify(user.id, {
      email: user.email,
      name: user.name,
      is_premium: Boolean(user.is_premium),
      is_internal: isInternalTrackingUser(user),
    })
  } catch {
    // ignore identify failures
  }
}

export function resetTrackingUser(): void {
  try {
    posthog.reset()
  } catch {
    // ignore reset failures
  }
}

export async function captureBusinessEvent(
  eventName: TrackingEventName | string,
  customData?: Record<string, any>
): Promise<void> {
  try {
    const properties = buildCommonProperties({
      event_source: 'business',
      ...customData,
    })
    const interactionType = typeof customData?.interaction_type === 'string'
      ? customData.interaction_type
      : eventName
    rememberFirstInteraction(interactionType)
    rememberLastTrigger(eventName, properties)
    capturePostHogEvent(eventName, properties)
    await sendTrackingRequest('/api/tracking/user-action', {
      session_id: properties.session_id,
      action_type: 'business',
      action_name: eventName,
      action_category: customData?.category || 'business',
      customData: properties,
    })
  } catch {
    // business tracking failure should not break UX
  }
}

// 페이지 뷰 추적
export async function trackPageView(
  pagePath: string,
  pageTitle?: string,
  customData?: Record<string, any>
): Promise<void> {
  try {
    const pageType = getPageType(pagePath)
    const dedupeKey = `${pagePath}:${pageTitle || document.title}`
    if (lastTrackedPageViewKey === dedupeKey && Date.now() - lastTrackedPageViewAt < 800) return
    lastTrackedPageViewKey = dedupeKey
    lastTrackedPageViewAt = Date.now()
    
    // 이전 페이지 체류시간 계산
    let timeOnPage: number | undefined
    if (previousPageTimestamp && previousPagePath) {
      timeOnPage = Math.floor((Date.now() - previousPageTimestamp) / 1000)
    }
    
    // 현재 페이지 정보 저장
    previousPageTimestamp = Date.now()
    previousPagePath = pagePath
    
    const data = buildCommonProperties({
      page_path: pagePath,
      page_type: pageType,
      page_title: pageTitle || document.title,
      referrer: document.referrer,
      time_on_page: timeOnPage,
      event_source: 'business',
      ...customData,
    })

    capturePostHogEvent('page_view', data)
    await sendTrackingRequest('/api/tracking/page-view', data)
  } catch {
    // 추적 실패는 무시 (네트워크/서버 미연결 시 앱 사용에 영향 없음)
  }
}

// 사용자 행동 추적
export async function trackUserAction(
  actionType: string,
  actionName: string,
  options?: {
    category?: string
    elementId?: string
    elementText?: string
    customData?: Record<string, any>
  }
): Promise<void> {
  try {
    const data = buildCommonProperties({
      action_type: actionType,
      action_name: actionName,
      action_category: options?.category,
      element_id: options?.elementId,
      element_text: options?.elementText,
      customData: options?.customData,
      event_source: 'legacy',
      ...options?.customData,
    })

    capturePostHogEvent(actionName, data)
    await sendTrackingRequest('/api/tracking/user-action', {
      session_id: data.session_id,
      action_type: actionType,
      action_name: actionName,
      action_category: options?.category,
      element_id: options?.elementId,
      element_text: options?.elementText,
      customData: {
        ...options?.customData,
        page_path: data.page_path,
        page_type: data.page_type,
        entry_url: data.entry_url,
        is_internal: data.is_internal,
      },
    })
  } catch {
    // 추적 실패는 무시 (네트워크/서버 미연결 시 앱 사용에 영향 없음)
  }
}

// 자동 추적 초기화
export function initializeTracking(): void {
  // 진입 URL 저장 (첫 방문 페이지만, 세션당 한 번)
  setEntryUrlIfEmpty()
  // UTM 파라미터 저장
  saveUTMParams()
  capturePostHogEvent('app_initialized', {
    page_path: window.location.pathname,
    page_title: document.title
  })
}

function sendGA4Event(eventName: string, params?: Record<string, string>): void {
  try {
    if (typeof window === 'undefined') return
    const gtag = (window as any).gtag
    if (typeof gtag !== 'function') return
    gtag('event', eventName, params)
  } catch (e) {
    console.warn(`GA4 ${eventName} 이벤트 전송 실패:`, e)
  }
}

/** GA4 권장 이벤트: 회원가입 완료 시 호출 */
export function trackGA4SignUp(method: 'email' | 'google' | 'kakao'): void {
  sendGA4Event('sign_up', { method })
}

/** GA4 권장 이벤트: 로그인 완료 시 호출 */
export function trackGA4Login(method: 'email' | 'google' | 'kakao'): void {
  sendGA4Event('login', { method })
}

/** Meta Pixel 이벤트 전송 */
function sendMetaPixelEvent(eventName: string, params?: Record<string, any>): void {
  try {
    if (typeof window === 'undefined') return
    const fbq = (window as any).fbq
    if (typeof fbq !== 'function') return
    fbq('track', eventName, params)
  } catch (e) {
    console.warn(`Meta Pixel ${eventName} 이벤트 전송 실패:`, e)
  }
}

/** Meta Pixel: 회원가입 완료 시 호출 */
export function trackMetaSignUp(method: 'email' | 'google' | 'kakao'): void {
  sendMetaPixelEvent('CompleteRegistration', { content_name: method })
}

// 특정 이벤트 추적 헬퍼
export const TrackingEvents = {
  // 채팅 관련
  sendMessage: () => trackUserAction('submit', 'send_message', { category: 'chat' }),
  startChat: () => trackUserAction('click', 'chat_start', { category: 'conversion' }),
  
  // 인증 관련
  loginAttempt: () => trackUserAction('submit', 'login_attempt', { category: 'auth' }),
  loginSuccess: () => trackUserAction('submit', 'login_success', { category: 'auth' }),
  signupAttempt: () => trackUserAction('submit', 'signup_attempt', { category: 'auth' }),
  signupSuccess: () => trackUserAction('submit', 'signup_success', { category: 'auth' }),
  
  // CTA 버튼
  ctaClick: (ctaName: string) => captureBusinessEvent('landing_cta_click', {
    category: 'acquisition',
    cta_id: ctaName,
    interaction_type: 'cta_click',
  }),
  
  // 스크롤 깊이
  scrollDepth: (depth: number) => trackUserAction('scroll', `scroll_${depth}`, { 
    category: 'engagement' 
  })
}