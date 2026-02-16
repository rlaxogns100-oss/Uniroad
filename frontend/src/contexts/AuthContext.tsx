import React, { createContext, useContext, useState, useEffect } from 'react'
import axios from 'axios'
import { trackGA4SignUp, trackGA4Login, trackUserAction, trackMetaSignUp } from '../utils/tracking'
import { migrateMessages } from '../api/client'
import { isCapacitorApp } from '../config'

interface User {
  id: string
  email: string
  name?: string
  avatar_url?: string
  is_premium?: boolean
}

interface AuthContextType {
  user: User | null
  accessToken: string | null
  loading: boolean
  signIn: (email: string, password: string, skipRedirect?: boolean) => Promise<User | null>
  signUp: (email: string, password: string, name?: string) => Promise<User | null>
  signInWithGoogle: () => Promise<void>
  signInWithKakao: () => Promise<void>
  quickSignIn: (name: string) => void  // 비밀번호 없이 빠른 로그인
  signOut: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // 로컬스토리지에서 토큰 복원 + OAuth 콜백 처리
  useEffect(() => {
    const handleOAuthCallback = async () => {
      // OAuth 콜백 처리 (URL query에서 code 추출)
      const urlParams = new URLSearchParams(window.location.search)
      const code = urlParams.get('code')

      if (code) {
        console.log('OAuth code found, exchanging for token...')
        try {
          const response = await axios.post('/api/auth/oauth/callback', { code })
          const { access_token, refresh_token, user: userData, is_new_user } = response.data

          localStorage.setItem('access_token', access_token)
          if (refresh_token) {
            localStorage.setItem('refresh_token', refresh_token)
          }
          localStorage.setItem('user', JSON.stringify(userData))

          setAccessToken(access_token)
          setUser(userData)
          setLoading(false)

          const provider = (sessionStorage.getItem('uniroad_oauth_provider') || 'google') as 'google' | 'kakao'
          const signupSource = sessionStorage.getItem('uniroad_oauth_signup_source') || 'unknown'
          if (is_new_user) {
            trackGA4SignUp(provider)
            trackMetaSignUp(provider)
            trackUserAction('signup_success', provider, {
              customData: { signup_source: signupSource }
            })
          } else {
            trackGA4Login(provider)
            trackUserAction('login_success', provider, {
              customData: { signup_source: signupSource }
            })
          }
          sessionStorage.removeItem('uniroad_oauth_provider')
          sessionStorage.removeItem('uniroad_oauth_signup_source')

          // sessionStorage에서 마이그레이션 대기 중인 메시지 확인
          const pendingMigration = sessionStorage.getItem('uniroad_pending_migration')
          if (pendingMigration) {
            try {
              const { messages, sessionId } = JSON.parse(pendingMigration)
              if (messages && messages.length > 0) {
                console.log('🔄 OAuth 로그인 후 채팅 마이그레이션 시작:', messages.length, '개 메시지')
                const result = await migrateMessages(access_token, messages, sessionId)
                console.log('✅ OAuth 채팅 마이그레이션 완료, session_id:', result.session_id)
                // 마이그레이션된 세션 ID 저장 (ChatPage에서 자동 선택용)
                sessionStorage.setItem('uniroad_migrated_session_id', result.session_id)
              }
            } catch (migrationError) {
              console.error('❌ OAuth 채팅 마이그레이션 실패:', migrationError)
            } finally {
              sessionStorage.removeItem('uniroad_pending_migration')
            }
          }

          // OAuth 로그인 성공 시: 관리자(김도균)는 /chat/login/admin, 그 외는 /chat/login
          const isAdmin = userData?.name === '김도균' || userData?.email === 'herry0515@naver.com'
          console.log('✅ OAuth 로그인 성공:', userData, '관리자:', isAdmin)
          window.location.href = isAdmin ? '/chat/login/admin' : '/chat/login'
          return
        } catch (error) {
          console.error('OAuth 콜백 처리 실패:', error)
          window.history.replaceState(null, '', window.location.pathname)
        }
      }

      // 로컬스토리지에서 토큰 복원
      const storedToken = localStorage.getItem('access_token')
      const storedUser = localStorage.getItem('user')

      if (storedToken && storedUser) {
        // 토큰만 먼저 설정하고, 사용자 정보는 검증 후 설정
        // (검증 전에 localStorage의 user 정보를 사용하면 다른 사용자 정보가 표시될 수 있음)
        setAccessToken(storedToken)
        // setUser는 verifyToken에서 검증 후 설정
        verifyToken(storedToken)
      } else {
        setLoading(false)
      }
    }

    handleOAuthCallback()
  }, [])

  const verifyToken = async (token: string) => {
    try {
      const response = await axios.get('/api/auth/me', {
        headers: { Authorization: `Bearer ${token}` }
      })
      // 서버에서 검증된 사용자 정보로 업데이트
      const verifiedUser = response.data
      setUser(verifiedUser)
      // localStorage도 검증된 정보로 업데이트
      localStorage.setItem('user', JSON.stringify(verifiedUser))
      setLoading(false)
    } catch (error) {
      // 토큰이 만료되었거나 유효하지 않음
      console.error('토큰 검증 실패:', error)
      signOut()
      setLoading(false)
    }
  }

  const signIn = async (email: string, password: string, skipRedirect?: boolean): Promise<User | null> => {
    try {
      const response = await axios.post('/api/auth/signin', { email, password }, { timeout: 15000 })
      const { access_token, user: userData } = response.data
      
      setAccessToken(access_token)
      setUser(userData)
      
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('user', JSON.stringify(userData))
      
      trackGA4Login('email')
      
      // skipRedirect가 true면 리다이렉트 하지 않음 (모달에서 로그인 시)
      // Capacitor 앱에서는 window.location.href 사용 시 전체 리로드로 하얀 화면이 나올 수 있으므로 리다이렉트 생략 → 호출부에서 navigate 사용
      if (!skipRedirect && !isCapacitorApp()) {
        const isAdmin = userData?.name === '김도균' || userData?.email === 'herry0515@naver.com'
        window.location.href = isAdmin ? '/chat/login/admin' : '/chat/login'
      }
      
      return userData
    } catch (error: any) {
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        throw new Error('요청 시간이 초과되었습니다. 백엔드가 켜져 있는지 확인해 주세요.')
      }
      if (!error.response) {
        throw new Error('서버에 연결할 수 없습니다. 네트워크와 백엔드를 확인해 주세요.')
      }
      const detail = error.response?.data?.detail
      throw new Error(typeof detail === 'string' ? detail : '로그인 실패')
    }
  }

  const signUp = async (email: string, password: string, name?: string): Promise<User | null> => {
    try {
      const response = await axios.post('/api/auth/signup', { email, password, name })
      const { access_token, user: userData } = response.data
      
      setAccessToken(access_token)
      setUser(userData)
      
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('user', JSON.stringify(userData))
      
      trackGA4SignUp('email')
      trackMetaSignUp('email')
      return userData
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || '회원가입 실패')
    }
  }

  const signInWithGoogle = async () => {
    try {
      sessionStorage.setItem('uniroad_oauth_provider', 'google')
      // 앱(Capacitor)에서는 Google/Kakao가 capacitor:// 리다이렉트를 허용하지 않으므로 웹 URL로 콜백 받은 뒤 앱 딥링크로 복귀
      const redirectTo = isCapacitorApp()
        ? 'https://uni2road.com/oauth-callback'
        : `${window.location.origin}/chat`
      const response = await axios.post('/api/auth/oauth/url', {
        provider: 'google',
        redirect_to: redirectTo
      })
      if (isCapacitorApp()) {
        try {
          const { Browser } = await import('@capacitor/browser')
          await Browser.open({ url: response.data.url })
        } catch {
          window.location.href = response.data.url
        }
      } else {
        window.location.href = response.data.url
      }
    } catch (error: any) {
      sessionStorage.removeItem('uniroad_oauth_provider')
      throw new Error(error.response?.data?.detail || 'Google 로그인 실패')
    }
  }

  const signInWithKakao = async () => {
    try {
      sessionStorage.setItem('uniroad_oauth_provider', 'kakao')
      const redirectTo = isCapacitorApp()
        ? 'https://uni2road.com/oauth-callback'
        : `${window.location.origin}/chat`
      const response = await axios.post('/api/auth/oauth/url', {
        provider: 'kakao',
        redirect_to: redirectTo
      })
      if (isCapacitorApp()) {
        try {
          const { Browser } = await import('@capacitor/browser')
          await Browser.open({ url: response.data.url })
        } catch {
          window.location.href = response.data.url
        }
      } else {
        window.location.href = response.data.url
      }
    } catch (error: any) {
      sessionStorage.removeItem('uniroad_oauth_provider')
      throw new Error(error.response?.data?.detail || '카카오 로그인 실패')
    }
  }

  // 비밀번호 없이 빠른 로그인 (테스트용)
  const quickSignIn = (name: string) => {
    const userData: User = {
      id: `quick-${Date.now()}`,
      email: `${name}@test.com`,
      name: name,
    }
    console.log('✅ 빠른 로그인:', userData)
    setUser(userData)
    setAccessToken('quick-access-token')
    localStorage.setItem('access_token', 'quick-access-token')
    localStorage.setItem('user', JSON.stringify(userData))
    
    // 빠른 로그인 후 리다이렉트
    const isAdmin = name === '김도균'
    window.location.href = isAdmin ? '/chat/login/admin' : '/chat/login'
  }

  const signOut = async () => {
    try {
      await axios.post('/api/auth/signout')
    } catch (e) {
      console.error('로그아웃 오류:', e)
    }
    setUser(null)
    setAccessToken(null)
    
    // localStorage 정리
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    localStorage.removeItem('refresh_token')
    
    // sessionStorage 정리 (채팅 관련 데이터)
    // 로그아웃 시 이전 사용자의 채팅 데이터가 남아있지 않도록 삭제
    sessionStorage.removeItem('uniroad_chat_messages')
    sessionStorage.removeItem('uniroad_chat_session_id')
    
    // 로그아웃 후 /chat 페이지로 이동 (비로그인 상태로 채팅 가능)
    window.location.href = '/chat'
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        accessToken,
        loading,
        signIn,
        signUp,
        signInWithGoogle,
        signInWithKakao,
        quickSignIn,
        signOut,
        isAuthenticated: !!user,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

