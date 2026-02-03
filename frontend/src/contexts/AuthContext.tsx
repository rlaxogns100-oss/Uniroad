import React, { createContext, useContext, useState, useEffect } from 'react'
import axios from 'axios'

interface User {
  id: string
  email: string
  name?: string
  avatar_url?: string
}

interface AuthContextType {
  user: User | null
  accessToken: string | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<User | null>
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
          const { access_token, refresh_token, user: userData } = response.data

          localStorage.setItem('access_token', access_token)
          if (refresh_token) {
            localStorage.setItem('refresh_token', refresh_token)
          }
          localStorage.setItem('user', JSON.stringify(userData))

          setAccessToken(access_token)
          setUser(userData)
          setLoading(false)

          // OAuth 로그인 성공 시: 관리자(김도균)는 /chat/admin, 그 외는 /chat
          const isAdmin = userData?.name === '김도균'
          window.location.href = isAdmin ? '/chat/admin' : '/chat'
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
        setAccessToken(storedToken)
        setUser(JSON.parse(storedUser))
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
      setUser(response.data)
      setLoading(false)
    } catch (error) {
      // 토큰이 만료되었거나 유효하지 않음
      console.error('토큰 검증 실패:', error)
      signOut()
      setLoading(false)
    }
  }

  const signIn = async (email: string, password: string): Promise<User | null> => {
    try {
      const response = await axios.post('/api/auth/signin', { email, password })
      const { access_token, user: userData } = response.data
      
      setAccessToken(access_token)
      setUser(userData)
      
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('user', JSON.stringify(userData))
      return userData
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || '로그인 실패')
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
      return userData
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || '회원가입 실패')
    }
  }

  const signInWithGoogle = async () => {
    try {
      const response = await axios.post('/api/auth/oauth/url', {
        provider: 'google',
        redirect_to: window.location.origin
      })
      window.location.href = response.data.url
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || 'Google 로그인 실패')
    }
  }

  const signInWithKakao = async () => {
    try {
      const response = await axios.post('/api/auth/oauth/url', {
        provider: 'kakao',
        redirect_to: window.location.origin
      })
      window.location.href = response.data.url
    } catch (error: any) {
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
    setUser(userData)
    setAccessToken('quick-access-token')
    localStorage.setItem('access_token', 'quick-access-token')
    localStorage.setItem('user', JSON.stringify(userData))
  }

  const signOut = async () => {
    try {
      await axios.post('/api/auth/signout')
    } catch (e) {
      console.error('로그아웃 오류:', e)
    }
    setUser(null)
    setAccessToken(null)
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
    localStorage.removeItem('refresh_token')
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

