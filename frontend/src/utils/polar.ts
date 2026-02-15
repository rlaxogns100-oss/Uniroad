/**
 * Polar.sh 결제 연동 유틸
 * - 구독하기 클릭 시 Polar Checkout URL로 리다이렉트
 * - client_reference_id에 Supabase 유저 ID 전달
 */

const CHECKOUT_BASE = import.meta.env.VITE_POLAR_CHECKOUT_URL ?? ''

/**
 * Polar Checkout URL 생성 (client_reference_id = Supabase user id)
 * @param userId - 현재 로그인한 Supabase 유저 ID (auth.users.id)
 * @returns 체크아웃 URL (미설정 시 빈 문자열)
 */
export function getPolarCheckoutUrl(userId: string): string {
  if (!CHECKOUT_BASE || !userId) return ''
  const url = new URL(CHECKOUT_BASE)
  url.searchParams.set('client_reference_id', userId)
  return url.toString()
}

/**
 * 구독하기: Polar Checkout 페이지로 이동
 * @param userId - 현재 로그인한 Supabase 유저 ID
 * @returns 이동 성공 여부 (URL 미설정 또는 userId 없으면 false)
 */
export function redirectToPolarCheckout(userId: string): boolean {
  const url = getPolarCheckoutUrl(userId)
  if (!url) {
    if (!(import.meta.env.VITE_POLAR_CHECKOUT_URL ?? '')) {
      console.warn('[Polar] VITE_POLAR_CHECKOUT_URL이 설정되지 않았습니다. frontend/.env에 추가해 주세요.')
    }
    return false
  }
  window.location.href = url
  return true
}
