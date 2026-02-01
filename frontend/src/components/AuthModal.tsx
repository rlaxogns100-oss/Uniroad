import React, { useState } from 'react'
import { useAuth } from '../contexts/AuthContext'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function AuthModal({ isOpen, onClose }: AuthModalProps) {
  const { signIn, signUp, signInWithGoogle, signInWithKakao } = useAuth()
  
  const [view, setView] = useState<'main' | 'email' | 'signup'>('main')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [kakaoLoading, setKakaoLoading] = useState(false)

  if (!isOpen) return null

  const handleEmailSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await signIn(email, password)
      onClose()
      resetForm()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await signUp(email, password, name)
      onClose()
      resetForm()
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSignIn = async () => {
    setError('')
    setGoogleLoading(true)
    
    try {
      await signInWithGoogle()
    } catch (err: any) {
      setError(err.message)
      setGoogleLoading(false)
    }
  }

  const handleKakaoSignIn = async () => {
    setError('')
    setKakaoLoading(true)
    
    try {
      await signInWithKakao()
    } catch (err: any) {
      setError(err.message)
      setKakaoLoading(false)
    }
  }

  const resetForm = () => {
    setEmail('')
    setPassword('')
    setName('')
    setError('')
    setView('main')
  }

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose()
      resetForm()
    }
  }

  const handleClose = () => {
    onClose()
    resetForm()
  }

  const isLoading = loading || googleLoading || kakaoLoading

  return (
    <div 
      className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4 sm:p-6 animate-fadeIn"
      onClick={handleBackdropClick}
    >
      <div className="bg-white rounded-3xl shadow-2xl max-w-lg w-full transform transition-all animate-slideUp" style={{ fontFamily: "'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif" }}>
        {/* 헤더: 닫기 버튼 */}
        <div className="relative px-6 pt-6">
          <button
            onClick={handleClose}
            className="absolute top-4 right-4 w-10 h-10 flex items-center justify-center rounded-full hover:bg-gray-100 active:bg-gray-200 transition-colors"
          >
            <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* 메인 뷰 - 소셜 로그인 버튼들 */}
        {view === 'main' && (
          <div className="px-8 pb-12 pt-4">
            {/* 로고 */}
            <div className="flex justify-center mb-6">
              <img src="/로고.png" alt="유니로드 로고" className="h-20" />
            </div>

            {/* 제목 */}
            <h1 className="text-2xl font-bold text-center text-gray-900 mb-3">
              유니로드에 오신 것을 환영합니다 👋🎓
            </h1>
            
            {/* 부제목 */}
            <p className="text-center text-gray-500 text-sm mb-10">
              로그인하여 맞춤형 입시 상담, 대화 기록 등에 접근하세요.
            </p>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm mb-6">
                {error}
              </div>
            )}

            {/* 로그인 버튼들 */}
            <div className="space-y-4">
              {/* 카카오 로그인 버튼 (메인) */}
              <button
                type="button"
                onClick={handleKakaoSignIn}
                disabled={isLoading}
                className="w-full py-4 bg-[#FEE500] text-[#191919] rounded-2xl font-semibold text-lg hover:bg-[#FADA0A] active:bg-[#F5D000] disabled:bg-gray-200 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-3"
              >
                {kakaoLoading ? (
                  <span>로그인 중...</span>
                ) : (
                  <>
                    <svg className="w-6 h-6" viewBox="0 0 24 24" fill="#191919">
                      <path d="M12 3C6.477 3 2 6.463 2 10.691c0 2.726 1.785 5.117 4.47 6.476-.18.605-.65 2.19-.745 2.528-.117.418.153.412.323.3.133-.087 2.11-1.44 2.963-2.025.626.089 1.272.136 1.989.136 5.523 0 10-3.463 10-7.415C21 6.463 17.523 3 12 3z"/>
                    </svg>
                    <span>카카오로 계속하기</span>
                  </>
                )}
              </button>

              {/* 구글 로그인 버튼 */}
              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={isLoading}
                className="w-full py-4 bg-gray-100 text-gray-700 rounded-2xl font-semibold text-lg hover:bg-gray-200 active:bg-gray-300 disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-3"
              >
                {googleLoading ? (
                  <span>로그인 중...</span>
                ) : (
                  <>
                    <svg className="w-6 h-6" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                    <span>Google로 계속하기</span>
                  </>
                )}
              </button>

              {/* 이메일 로그인 버튼 */}
              <button
                type="button"
                onClick={() => setView('email')}
                disabled={isLoading}
                className="w-full py-4 bg-gray-100 text-gray-700 rounded-2xl font-semibold text-lg hover:bg-gray-200 active:bg-gray-300 disabled:bg-gray-100 disabled:text-gray-400 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-3"
              >
                <span>이메일로 로그인</span>
              </button>
            </div>
          </div>
        )}

        {/* 이메일 로그인 뷰 */}
        {view === 'email' && (
          <div className="px-8 pb-12 pt-6">
            {/* 뒤로가기 + 제목 */}
            <div className="flex items-center mb-8">
              <button
                type="button"
                onClick={() => { setView('main'); setError(''); }}
                className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <h1 className="text-xl font-bold text-gray-900 ml-2">이메일로 로그인</h1>
            </div>

            <form onSubmit={handleEmailSignIn} className="space-y-5">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">이메일</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="example@email.com"
                  required
                  className="w-full px-4 py-3 text-base border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">비밀번호</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="w-full px-4 py-3 text-base border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-blue-500 text-white rounded-2xl font-semibold text-lg hover:bg-blue-600 active:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors mt-2"
              >
                {loading ? '로그인 중...' : '로그인'}
              </button>
            </form>

            {/* 회원가입 링크 */}
            <div className="text-center mt-6">
              <span className="text-gray-500">계정이 없으신가요? </span>
              <button 
                type="button"
                onClick={() => { setView('signup'); setError(''); }}
                className="text-blue-600 font-semibold hover:underline"
              >
                회원가입
              </button>
            </div>
          </div>
        )}

        {/* 회원가입 뷰 */}
        {view === 'signup' && (
          <div className="px-8 pb-12 pt-6">
            {/* 뒤로가기 + 제목 */}
            <div className="flex items-center mb-8">
              <button
                type="button"
                onClick={() => { setView('email'); setError(''); }}
                className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <h1 className="text-xl font-bold text-gray-900 ml-2">회원가입</h1>
            </div>

            <form onSubmit={handleSignUp} className="space-y-5">
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">이름</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="홍길동"
                  maxLength={30}
                  className="w-full px-4 py-3 text-base border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">이메일</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="example@email.com"
                  required
                  className="w-full px-4 py-3 text-base border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">비밀번호</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="w-full px-4 py-3 text-base border-2 border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                />
                <p className="text-xs text-gray-500 mt-1">최소 6자 이상</p>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-xl text-sm">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-4 bg-blue-500 text-white rounded-2xl font-semibold text-lg hover:bg-blue-600 active:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors mt-2"
              >
                {loading ? '가입 중...' : '회원가입'}
              </button>
            </form>

            {/* 로그인 링크 */}
            <div className="text-center mt-6">
              <span className="text-gray-500">이미 계정이 있으신가요? </span>
              <button 
                type="button"
                onClick={() => { setView('email'); setError(''); }}
                className="text-blue-600 font-semibold hover:underline"
              >
                로그인
              </button>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes slideUp {
          from { opacity: 0; transform: translateY(20px) scale(0.95); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .animate-fadeIn { animation: fadeIn 0.2s ease-out; }
        .animate-slideUp { animation: slideUp 0.3s ease-out; }
      `}</style>
    </div>
  )
}
