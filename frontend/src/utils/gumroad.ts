/**
 * Gumroad 결제 연동 유틸
 * - 결제 버튼 클릭 시 Gumroad Checkout URL로 즉시 이동
 */

const CHECKOUT_BASE = import.meta.env.VITE_GUMROAD_CHECKOUT_URL ?? ''

export function getGumroadCheckoutUrl(userId: string, email?: string): string {
  if (!CHECKOUT_BASE || !userId) return ''
  const url = new URL(CHECKOUT_BASE)
  // direct checkout 복귀: 상품페이지 경유 없이 결제창으로 바로 이동
  url.searchParams.set('wanted', 'true')
  url.searchParams.set('user_id', userId)
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
