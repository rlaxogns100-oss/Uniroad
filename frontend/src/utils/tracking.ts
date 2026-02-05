/**
 * 사용자 추적 유틸리티
 * - 페이지 뷰 추적
 * - 사용자 행동 추적
 * - UTM 파라미터 파싱
 */

import { v4 as uuidv4 } from 'uuid'

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
  if (pathname.includes('/auth')) return 'auth'
  if (pathname.includes('/admin') || pathname.includes('/upload')) return 'admin'
  return 'other'
}

// 이전 페이지 추적
let previousPageTimestamp: number | null = null
let previousPagePath: string | null = null

// 페이지 뷰 추적
export async function trackPageView(
  pagePath: string,
  pageTitle?: string,
  customData?: Record<string, any>
): Promise<void> {
  try {
    const sessionId = getSessionId()
    const utm = getUTMParams()
    const pageType = getPageType(pagePath)
    
    // 이전 페이지 체류시간 계산
    let timeOnPage: number | undefined
    if (previousPageTimestamp && previousPagePath) {
      timeOnPage = Math.floor((Date.now() - previousPageTimestamp) / 1000)
    }
    
    // 현재 페이지 정보 저장
    previousPageTimestamp = Date.now()
    previousPagePath = pagePath
    
    const data = {
      session_id: sessionId,
      page_type: pageType,
      page_path: pagePath,
      page_title: pageTitle || document.title,
      ...utm,
      referrer: document.referrer,
      time_on_page: timeOnPage,
      ...customData
    }
    
    // 토큰 가져오기 (있으면)
    const token = localStorage.getItem('access_token')
    
    await fetch('/api/tracking/page-view', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: JSON.stringify(data)
    })
  } catch (error) {
    console.error('페이지 뷰 추적 실패:', error)
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
    const sessionId = getSessionId()
    
    const data = {
      session_id: sessionId,
      action_type: actionType,
      action_name: actionName,
      action_category: options?.category,
      element_id: options?.elementId,
      element_text: options?.elementText,
      ...options?.customData
    }
    
    // 토큰 가져오기 (있으면)
    const token = localStorage.getItem('access_token')
    
    await fetch('/api/tracking/user-action', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { 'Authorization': `Bearer ${token}` })
      },
      body: JSON.stringify(data)
    })
  } catch (error) {
    console.error('사용자 행동 추적 실패:', error)
  }
}

// 페이지 이탈 시 체류시간 전송
export function trackPageLeave(): void {
  if (previousPageTimestamp && previousPagePath) {
    const timeOnPage = Math.floor((Date.now() - previousPageTimestamp) / 1000)
    
    // Beacon API 사용 (페이지 이탈 시에도 전송 보장)
    const data = {
      session_id: getSessionId(),
      page_path: previousPagePath,
      time_on_page: timeOnPage
    }
    
    navigator.sendBeacon('/api/tracking/page-leave', JSON.stringify(data))
  }
}

// 자동 추적 초기화
export function initializeTracking(): void {
  // 진입 URL 저장 (첫 방문 페이지만, 세션당 한 번)
  setEntryUrlIfEmpty()
  // UTM 파라미터 저장
  saveUTMParams()
  
  // 현재 페이지 추적
  trackPageView(window.location.pathname)
  
  // 페이지 이탈 시 추적
  window.addEventListener('beforeunload', trackPageLeave)
  
  // 클릭 이벤트 자동 추적
  document.addEventListener('click', (event) => {
    const target = event.target as HTMLElement
    
    // 버튼 클릭
    if (target.tagName === 'BUTTON' || target.closest('button')) {
      const button = target.tagName === 'BUTTON' ? target : target.closest('button')!
      trackUserAction('click', 'button_click', {
        elementId: button.id,
        elementText: button.textContent?.trim().substring(0, 50)
      })
    }
    
    // 링크 클릭
    if (target.tagName === 'A' || target.closest('a')) {
      const link = target.tagName === 'A' ? target : target.closest('a')!
      trackUserAction('click', 'link_click', {
        elementId: link.id,
        elementText: link.textContent?.trim().substring(0, 50)
      })
    }
  })
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
  ctaClick: (ctaName: string) => trackUserAction('click', 'cta_click', { 
    category: 'conversion',
    elementText: ctaName 
  }),
  
  // 스크롤 깊이
  scrollDepth: (depth: number) => trackUserAction('scroll', `scroll_${depth}`, { 
    category: 'engagement' 
  })
}