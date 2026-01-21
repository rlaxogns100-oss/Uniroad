import { createClient, SupabaseClient } from '@supabase/supabase-js'

// 환경 변수에서 Supabase 설정 가져오기
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || ''
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

if (!supabaseUrl || !supabaseAnonKey) {
  console.warn('Supabase 환경 변수가 설정되지 않았습니다.')
}

// 기본 Supabase 클라이언트 생성
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    persistSession: false, // 세션은 AuthContext에서 관리
    autoRefreshToken: false,
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
      persistSession: false,
      autoRefreshToken: false,
    },
    global: {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    },
  })
}

