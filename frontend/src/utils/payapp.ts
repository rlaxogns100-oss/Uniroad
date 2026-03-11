type PayAppParams = Record<string, string>

declare global {
  interface Window {
    __UNIROAD_LAST_PAYAPP_PAYLOAD__?: PayAppParams
  }
}

export const PAYAPP_METHODS = {
  card: { label: '카드', openpaytype: 'card' },
  kakaopay: { label: '카카오페이', openpaytype: 'kakaopay' },
  naverpay: { label: '네이버페이', openpaytype: 'naverpay' },
  tosspay: { label: '토스페이', openpaytype: 'tosspay' },
} as const

export type PayAppMethodKey = keyof typeof PAYAPP_METHODS

interface OpenPayAppCheckoutOptions {
  goodname: string
  price: number | string
  userid?: string
  shopname?: string
  method?: PayAppMethodKey
  recvphone?: string
  memo?: string
  returnUrl?: string
  buyerId?: string
  var1?: string
  directWebPay?: boolean
}

const PAYAPP_PAY_URL = 'https://lite.payapp.kr/pay'
const DEFAULT_PAYAPP_USER_ID = 'rlaxogns100'
const DEFAULT_SHOP_NAME = '유니로드'

function compactParams(params: Record<string, string | undefined>): PayAppParams {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => String(value ?? '').trim() !== '')
  ) as PayAppParams
}

function normalizePhone(phone?: string): string {
  return String(phone ?? '').replace(/\D/g, '')
}

function buildPayAppParams(options: OpenPayAppCheckoutOptions): PayAppParams {
  const payappUserId = options.userid?.trim() || import.meta.env.VITE_PAYAPP_USERID || DEFAULT_PAYAPP_USER_ID
  const amount = Number(options.price)
  const method = options.method ? PAYAPP_METHODS[options.method] : null
  const recvphone = normalizePhone(options.recvphone)

  if (!payappUserId) {
    throw new Error('PayApp 판매자 아이디가 설정되지 않았습니다.')
  }
  if (!Number.isFinite(amount) || amount < 1000) {
    throw new Error('PayApp 결제 금액은 1,000원 이상이어야 합니다.')
  }
  if (options.directWebPay && recvphone.length < 8) {
    throw new Error('웹 즉시 결제를 위해 전화번호를 입력해 주세요.')
  }

  return compactParams({
    userid: payappUserId,
    shopname: options.shopname?.trim() || DEFAULT_SHOP_NAME,
    goodname: options.goodname.trim(),
    price: String(Math.round(amount)),
    openpaytype: method?.openpaytype,
    recvphone,
    redirectpay: options.directWebPay ? '1' : undefined,
    smsuse: options.directWebPay ? 'n' : undefined,
    memo: options.memo?.trim(),
    returnurl: options.returnUrl?.trim(),
    buyerid: options.buyerId?.trim(),
    var1: options.var1?.trim(),
  })
}

function logPayAppPayload(params: PayAppParams): void {
  if (typeof window === 'undefined') return
  window.__UNIROAD_LAST_PAYAPP_PAYLOAD__ = params
  console.groupCollapsed('[PayApp] submit payload')
  console.table(params)
  console.groupEnd()
}

function submitPayAppForm(params: PayAppParams): void {
  if (typeof document === 'undefined' || typeof window === 'undefined') {
    throw new Error('브라우저 환경에서만 PayApp 결제를 열 수 있습니다.')
  }

  const form = document.createElement('form')
  form.method = 'post'
  form.action = PAYAPP_PAY_URL
  form.target = '_self'
  form.acceptCharset = 'UTF-8'
  form.style.display = 'none'

  Object.entries(params).forEach(([key, value]) => {
    const input = document.createElement('input')
    input.type = 'hidden'
    input.name = key
    input.value = value
    form.appendChild(input)
  })

  logPayAppPayload(params)
  document.body.appendChild(form)

  if (typeof form.requestSubmit === 'function') {
    form.requestSubmit()
  } else {
    form.submit()
  }

  window.setTimeout(() => {
    form.remove()
  }, 1000)
}

export function openPayAppCheckout(options: OpenPayAppCheckoutOptions): void {
  const params = buildPayAppParams(options)
  submitPayAppForm(params)
}
