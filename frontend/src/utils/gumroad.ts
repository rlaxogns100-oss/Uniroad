/**
 * Gumroad 결제 연동 유틸
 * - 결제 버튼 클릭 시 Gumroad Checkout URL로 즉시 이동
 */

const CHECKOUT_BASE = import.meta.env.VITE_GUMROAD_CHECKOUT_URL ?? ''

export function getGumroadCheckoutUrl(userId: string, email?: string): string {
  if (!CHECKOUT_BASE || !userId) return ''
  const url = new URL(CHECKOUT_BASE)
  // 사용자 식별 강화를 위해 user_id를 항상 전달
  url.searchParams.set('user_id', userId)
  // email은 결제창 안정성을 위해 기본 전달하지 않음 (서버 fallback은 구매 이메일 사용)
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
