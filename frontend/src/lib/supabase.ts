import { createClient, SupabaseClient } from '@supabase/supabase-js'

// 환경 변수에서 Supabase 설정 가져오기
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase 환경 변수가 설정되지 않았습니다.')
}

// 기본 Supabase 클라이언트 생성 (세션 영구 저장)
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: true, // 세션을 localStorage에 저장하여 새로고침 시에도 유지
    autoRefreshToken: true, // 토큰 자동 갱신
    storageKey: 'uniroad-auth', // 저장 키
    storage: window.localStorage, // localStorage 사용
  },
})

// 토큰이 포함된 Supabase 클라이언트 생성 헬퍼
export const getSupabaseClient = (accessToken?: string): SupabaseClient => {
  if (!accessToken) {
    return supabase
  }
  
  // 토큰이 있는 경우 새로운 클라이언트 생성
  return createClient(supabaseUrl, supabaseAnonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
    },
    global: {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  })
}

