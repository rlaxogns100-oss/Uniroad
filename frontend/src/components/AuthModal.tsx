import React, { useState } from 'react'
import { GraduationCap } from 'lucide-react'
import { useAuth } from '../contexts/AuthContext'
import { captureBusinessEvent, readAuthTrigger } from '../utils/tracking'
import { TrackingEventNames } from '../utils/trackingSchema'

interface AuthModalProps {
  isOpen: boolean
  onClose: () => void
  customMessage?: {
    title: string
    description: string
  }
  onLoginSuccess?: () => void  // 로그인 성공 시 콜백
  onOAuthStart?: () => void  // OAuth 리다이렉트 시작 전 콜백 (메시지 저장용)
}

export default function AuthModal({ isOpen, onClose, customMessage, onLoginSuccess, onOAuthStart }: AuthModalProps) {
  const { signIn, signUp, signInWithGoogle, signInWithKakao } = useAuth()
  
  const [view, setView] = useState<'main' | 'signup'>('main')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)
  const [kakaoLoading, setKakaoLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  // 모달이 열릴 때 로딩 상태 초기화 (뒤로가기 등으로 돌아왔을 때 대비)
  React.useEffect(() => {
    if (isOpen) {
      setGoogleLoading(false)
      setKakaoLoading(false)
      setLoading(false)
      setError('')
      void captureBusinessEvent(TrackingEventNames.authModalView, {
        category: 'activation',
        auth_trigger: readAuthTrigger() || 'unknown',
        auth_view: view,
      })
    }
  }, [isOpen, view])

  if (!isOpen) return null

  const handleEmailSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      void captureBusinessEvent(TrackingEventNames.loginClick, {
        category: 'activation',
        method: 'email',
        auth_trigger: readAuthTrigger() || 'unknown',
      })
      await signIn(email, password, true)  // skipRedirect: true - 모달에서 로그인 시 리다이렉트 안함
      onLoginSuccess?.()
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
      void captureBusinessEvent(TrackingEventNames.signupClick, {
        category: 'activation',
        method: 'email',
        auth_trigger: readAuthTrigger() || 'unknown',
      })
      await signUp(email, password, name)
      onLoginSuccess?.()
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
      // OAuth 리다이렉트 전에 콜백 호출 (메시지 저장용)
      onOAuthStart?.()
      // OAuth 리다이렉트 전에 signup_source 저장 (OAuth 콜백에서 사용)
      const signupSource = sessionStorage.getItem('uniroad_login_modal_source') || 'unknown'
      sessionStorage.setItem('uniroad_oauth_signup_source', signupSource)
      void captureBusinessEvent(TrackingEventNames.oauthClick, {
        category: 'activation',
        method: 'google',
        auth_trigger: readAuthTrigger() || 'unknown',
      })
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
      // OAuth 리다이렉트 전에 콜백 호출 (메시지 저장용)
      onOAuthStart?.()
      // OAuth 리다이렉트 전에 signup_source 저장 (OAuth 콜백에서 사용)
      const signupSource = sessionStorage.getItem('uniroad_login_modal_source') || 'unknown'
      sessionStorage.setItem('uniroad_oauth_signup_source', signupSource)
      void captureBusinessEvent(TrackingEventNames.oauthClick, {
        category: 'activation',
        method: 'kakao',
        auth_trigger: readAuthTrigger() || 'unknown',
      })
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
      <div className="bg-white rounded-3xl shadow-2xl max-w-md w-full max-h-[88vh] overflow-visible flex flex-col transform transition-all animate-slideUp" style={{ fontFamily: "'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, Roboto, 'Helvetica Neue', 'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', sans-serif" }}>
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

        {/* 메인 뷰 - 로그인 폼 + 소셜 (아이콘·제목은 고정, 폼만 스크롤) */}
        {view === 'main' && (
          <div className="flex flex-col flex-1 min-h-0 pt-2">
            {/* 브랜드 아이콘 - 모달 위로 걸쳐 보이도록 (잘리지 않음) */}
            <div className="w-full flex justify-center -mt-[2.75rem] mb-5 flex-none">
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 shadow-lg shadow-blue-500/25 shrink-0 ring-4 ring-white">
                <GraduationCap className="w-8 h-8 text-white" strokeWidth={2} />
              </div>
            </div>
            <div className="px-8 flex-none">
              <h1 className="text-2xl font-bold text-center text-gray-900 mt-0 mb-2 tracking-tight">
                로그인 또는 회원가입
              </h1>
              <p className="text-center text-gray-600 text-sm mb-7">
                {customMessage?.description || '맞춤형 입시 상담, 대화 기록을 이용하세요.'}
              </p>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto px-8 pb-10">
            <form onSubmit={handleEmailSignIn} className="space-y-5">
              <div>
                <label className="block text-base font-medium text-gray-900 mb-1.5">이메일</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="이메일 주소 입력"
                  required
                  className="w-full px-4 py-3 text-base border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-gray-400 transition-colors placeholder:text-gray-400 bg-white"
                />
              </div>

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="block text-base font-medium text-gray-900">비밀번호</label>
                  <a href="/policy" className="text-sm text-blue-600 hover:underline font-normal">
                    비밀번호 찾기
                  </a>
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="비밀번호 입력"
                    required
                    minLength={6}
                    className="w-full px-4 py-3 pr-10 text-base border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-gray-400 transition-colors placeholder:text-gray-400 bg-white"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  >
                    {showPassword ? (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                    ) : (
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                    )}
                  </button>
                </div>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="w-4 h-4 rounded border-gray-300 text-gray-600 focus:ring-gray-400" />
                <span className="text-base text-gray-900 font-normal">로그인 상태 유지</span>
              </label>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-2.5 rounded-lg text-sm">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 bg-gray-900 text-white rounded-lg font-semibold text-base hover:bg-black active:bg-black disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors mt-1"
              >
                {loading ? '로그인 중...' : '로그인'}
              </button>
            </form>

            <div className="flex items-center gap-3 my-6">
              <span className="flex-1 h-px bg-gray-200" />
              <span className="text-sm text-gray-500 font-normal">또는</span>
              <span className="flex-1 h-px bg-gray-200" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={handleKakaoSignIn}
                disabled={isLoading}
                className="flex items-center justify-center gap-2 py-3 px-4 bg-white border border-gray-200 rounded-lg font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors text-sm"
              >
                {kakaoLoading ? (
                  <span className="text-sm">로그인 중...</span>
                ) : (
                  <>
                    <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24" fill="#191919">
                      <path d="M12 3C6.477 3 2 6.463 2 10.691c0 2.726 1.785 5.117 4.47 6.476-.18.605-.65 2.19-.745 2.528-.117.418.153.412.323.3.133-.087 2.11-1.44 2.963-2.025.626.089 1.272.136 1.989.136 5.523 0 10-3.463 10-7.415C21 6.463 17.523 3 12 3z"/>
                    </svg>
                    <span>카카오</span>
                  </>
                )}
              </button>
              <button
                type="button"
                onClick={handleGoogleSignIn}
                disabled={isLoading}
                className="flex items-center justify-center gap-2 py-3 px-4 bg-white border border-gray-200 rounded-lg font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors text-sm"
              >
                {googleLoading ? (
                  <span className="text-sm">로그인 중...</span>
                ) : (
                  <>
                    <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24">
                      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                    <span>Google</span>
                  </>
                )}
              </button>
            </div>

            <p className="text-center text-gray-600 text-xs mt-6 leading-relaxed">
              계속하면 유니로드의 이용 약관에 동의하는 것으로 간주됩니다.
            </p>
            <p className="text-center mt-1.5">
              <a href="/policy" className="text-xs text-blue-600 hover:underline font-normal">
                유니로드의 개인정보 처리방침을 확인하세요.
              </a>
            </p>

            <div className="text-center mt-7 pt-5 border-t border-gray-100">
              <span className="text-gray-600 text-sm font-normal">계정이 없으신가요? </span>
              <button
                type="button"
                onClick={() => { setView('signup'); setError(''); }}
                className="text-blue-600 font-medium hover:underline text-sm"
              >
                이메일로 회원가입
              </button>
            </div>
            </div>
          </div>
        )}

        {/* 회원가입 뷰 - 로그인 모달과 동일한 비율·패딩 */}
        {view === 'signup' && (
          <div className="px-6 pb-6 pt-2">
            <div className="flex items-center mb-4">
              <button
                type="button"
                onClick={() => { setView('main'); setError(''); }}
                className="p-2 -ml-2 hover:bg-gray-100 rounded-full transition-colors"
              >
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <h1 className="text-lg font-bold text-gray-900 ml-2">회원가입</h1>
            </div>

            <form onSubmit={handleSignUp} className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-900 mb-1">이름</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="이름 입력"
                  maxLength={30}
                  className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-gray-400 transition-colors placeholder:text-gray-400 bg-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-900 mb-1">이메일</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="이메일 주소 입력"
                  required
                  className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-gray-400 transition-colors placeholder:text-gray-400 bg-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-900 mb-1">비밀번호</label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="비밀번호 입력"
                  required
                  minLength={6}
                  className="w-full px-3 py-2.5 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-gray-400 transition-colors placeholder:text-gray-400 bg-white"
                />
                <p className="text-xs text-gray-500 mt-0.5">최소 6자 이상</p>
              </div>

              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-3 py-2 rounded-lg text-xs">
                  {error}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3 bg-gray-900 text-white rounded-lg font-semibold text-sm hover:bg-black active:bg-black disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? '가입 중...' : '회원가입'}
              </button>
            </form>

            <div className="text-center mt-4 pt-3 border-t border-gray-100">
              <span className="text-gray-600 text-sm font-normal">이미 계정이 있으신가요? </span>
              <button
                type="button"
                onClick={() => { setView('main'); setError(''); }}
                className="text-blue-600 font-medium hover:underline text-sm"
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
