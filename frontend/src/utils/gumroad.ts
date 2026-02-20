/**
 * Gumroad 결제 연동 유틸
 * - 결제 버튼 클릭 시 Gumroad Checkout URL로 즉시 이동
 */

const CHECKOUT_BASE = import.meta.env.VITE_GUMROAD_CHECKOUT_URL ?? ''

export function getGumroadCheckoutUrl(userId: string, email?: string): string {
  if (!CHECKOUT_BASE || !userId) return ''
  const url = new URL(CHECKOUT_BASE)
  // product 페이지 대신 checkout으로 바로 진입되도록 강제
  url.searchParams.set('wanted', 'true')
  // 사용자 식별 강화를 위해 user_id를 항상 전달
  url.searchParams.set('user_id', userId)
  // webhook 매칭 보강을 위해 email도 함께 전달
  if (email) {
    url.searchParams.set('email', email.trim().toLowerCase())
  }
  return url.toString()
}

export function redirectToGumroadCheckout(userId: string, email?: string): boolean {
  const url = getGumroadCheckoutUrl(userId, email)
  if (!url) {
    if (!(import.meta.env.VITE_GUMROAD_CHECKOUT_URL ?? '')) {
      console.warn('[Gumroad] VITE_GUMROAD_CHECKOUT_URL이 설정되지 않았습니다. frontend/.env에 추가해 주세요.')
    }
    return false
  }
  window.location.href = url
  return true
}
