import React, { createContext, useContext, useState, useEffect } from 'react'
import axios from 'axios'
import { supabase } from '../lib/supabase'

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
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string, name?: string) => Promise<void>
  signInWithGoogle: () => Promise<void>
  signInWithKakao: () => Promise<void>
  signOut: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // Supabase Auth 상태 변화 감지
  useEffect(() => {
    // 현재 세션 확인
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (session) {
        const userData: User = {
          id: session.user.id,
          email: session.user.email || '',
          name: session.user.user_metadata?.name || session.user.user_metadata?.full_name || session.user.email?.split('@')[0],
          avatar_url: session.user.user_metadata?.avatar_url
        }
        setUser(userData)
        setAccessToken(session.access_token)
        localStorage.setItem('access_token', session.access_token)
        localStorage.setItem('user', JSON.stringify(userData))
      }
      setLoading(false)
    })

    // Auth 상태 변화 리스너
    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event, session) => {
      console.log('Auth state changed:', event, session?.user?.email)
      
      if (event === 'SIGNED_IN' && session) {
        const userData: User = {
          id: session.user.id,
          email: session.user.email || '',
          name: session.user.user_metadata?.name || session.user.user_metadata?.full_name || session.user.email?.split('@')[0],
          avatar_url: session.user.user_metadata?.avatar_url
        }
        setUser(userData)
        setAccessToken(session.access_token)
        localStorage.setItem('access_token', session.access_token)
        localStorage.setItem('user', JSON.stringify(userData))
      } else if (event === 'SIGNED_OUT') {
        setUser(null)
        setAccessToken(null)
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        localStorage.removeItem('refresh_token')
      }
    })

    return () => subscription.unsubscribe()
  }, [])

  // 로컬스토리지에서 토큰 복원 (기존 호환)
  useEffect(() => {
    const storedToken = localStorage.getItem('access_token')
    const storedUser = localStorage.getItem('user')
    
    if (storedToken && storedUser && !user) {
      setAccessToken(storedToken)
      setUser(JSON.parse(storedUser))
      
      // 토큰 유효성 검증
      verifyToken(storedToken)
    }
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

  const signIn = async (email: string, password: string) => {
    try {
      const response = await axios.post('/api/auth/signin', { email, password })
      const { access_token, user: userData } = response.data
      
      setAccessToken(access_token)
      setUser(userData)
      
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('user', JSON.stringify(userData))
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || '로그인 실패')
    }
  }

  const signUp = async (email: string, password: string, name?: string) => {
    try {
      const response = await axios.post('/api/auth/signup', { email, password, name })
      const { access_token, user: userData } = response.data
      
      setAccessToken(access_token)
      setUser(userData)
      
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('user', JSON.stringify(userData))
    } catch (error: any) {
      throw new Error(error.response?.data?.detail || '회원가입 실패')
    }
  }

  const signInWithGoogle = async () => {
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: window.location.origin,
          queryParams: {
            access_type: 'offline',
            prompt: 'consent',
          }
        }
      })
      
      if (error) {
        throw new Error(error.message)
      }
    } catch (error: any) {
      throw new Error(error.message || 'Google 로그인 실패')
    }
  }

  const signInWithKakao = async () => {
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'kakao',
        options: {
          redirectTo: window.location.origin,
        }
      })
      
      if (error) {
        throw new Error(error.message)
      }
    } catch (error: any) {
      throw new Error(error.message || '카카오 로그인 실패')
    }
  }

  const signOut = async () => {
    try {
      await supabase.auth.signOut()
    } catch (e) {
      console.error('Supabase 로그아웃 오류:', e)
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

