/**
 * Gumroad 결제 연동 유틸
 * - 결제 버튼 클릭 시 Gumroad Checkout URL로 즉시 이동
 */

const CHECKOUT_BASE = import.meta.env.VITE_GUMROAD_CHECKOUT_URL ?? ''

export function getGumroadCheckoutUrl(userId: string, email?: string): string {
  if (!CHECKOUT_BASE || !userId) return ''
  // Gumroad checkout 안정성을 위해 원본 링크를 그대로 사용
  // (추가 쿼리 파라미터 부착 시 일부 환경에서 checkout 에러가 발생할 수 있음)
  return CHECKOUT_BASE
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
