import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function AuthPage() {
  const navigate = useNavigate()
  const { signIn, signUp, signInWithGoogle, signInWithKakao } = useAuth()
  
  const [isSignUp, setIsSignUp] = useState(false)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isSignUp) {
        await signUp(email, password, name)
      } else {
        await signIn(email, password)
      }
      navigate('/')
    } catch (err: any) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 flex items-center justify-center p-4 sm:p-6 safe-area-inset">
      <div className="max-w-md sm:max-w-lg w-full">
        {/* 모바일: 앱 스타일 로고 */}
        <div className="sm:hidden text-center mb-8">
          <img src="/로고.png" alt="UniZ Logo" className="h-20 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-800">유니로드</h1>
          <p className="text-gray-600 mt-2 text-base">대학 입시 상담 AI</p>
        </div>
        
        {/* 데스크톱: 웹 스타일 로고 */}
        <div className="hidden sm:block text-center mb-10">
          <img src="/로고.png" alt="UniZ Logo" className="h-24 mx-auto mb-6" />
          <h1 className="text-4xl font-bold text-gray-800">유니로드</h1>
          <p className="text-gray-600 mt-3 text-lg">대학 입시 상담 AI</p>
          <p className="text-gray-500 mt-2 text-sm">무엇이든 물어보세요</p>
        </div>

        {/* 로그인/회원가입 폼 */}
        <div className="bg-white rounded-2xl sm:rounded-3xl shadow-xl p-6 sm:p-10">
          {/* 모바일: 큰 탭 버튼 */}
          <div className="sm:hidden flex gap-2 mb-8 bg-gray-100 p-1 rounded-xl">
            <button
              onClick={() => setIsSignUp(false)}
              className={`flex-1 py-4 px-4 rounded-lg font-semibold transition-all min-h-[52px] text-base ${
                !isSignUp
                  ? 'bg-white text-blue-600 shadow-sm active:scale-[0.98]'
                  : 'text-gray-600 active:bg-gray-50'
              }`}
            >
              로그인
            </button>
            <button
              onClick={() => setIsSignUp(true)}
              className={`flex-1 py-4 px-4 rounded-lg font-semibold transition-all min-h-[52px] text-base ${
                isSignUp
                  ? 'bg-white text-blue-600 shadow-sm active:scale-[0.98]'
                  : 'text-gray-600 active:bg-gray-50'
              }`}
            >
              회원가입
            </button>
          </div>
          
          {/* 데스크톱: 작은 탭 버튼 */}
          <div className="hidden sm:flex gap-2 mb-8 border-b border-gray-200">
            <button
              onClick={() => setIsSignUp(false)}
              className={`flex-1 py-3 px-4 rounded-t-lg font-medium transition-colors text-base ${
                !isSignUp
                  ? 'bg-blue-600 text-white border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              로그인
            </button>
            <button
              onClick={() => setIsSignUp(true)}
              className={`flex-1 py-3 px-4 rounded-t-lg font-medium transition-colors text-base ${
                isSignUp
                  ? 'bg-blue-600 text-white border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
              }`}
            >
              회원가입
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5 sm:space-y-6">
            {isSignUp && (
              <div>
                <label className="block text-sm sm:text-base font-semibold text-gray-700 mb-2 sm:mb-3">
                  이름
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="홍길동"
                  className="w-full px-4 sm:px-5 py-4 sm:py-3.5 text-base border-2 border-gray-300 rounded-xl sm:rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[52px] sm:min-h-[48px] transition-colors"
                />
              </div>
            )}

            <div>
              <label className="block text-sm sm:text-base font-semibold text-gray-700 mb-2 sm:mb-3">
                이메일
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="example@email.com"
                required
                className="w-full px-4 sm:px-5 py-4 sm:py-3.5 text-base border-2 border-gray-300 rounded-xl sm:rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[52px] sm:min-h-[48px] transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm sm:text-base font-semibold text-gray-700 mb-2 sm:mb-3">
                비밀번호
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
                className="w-full px-4 sm:px-5 py-4 sm:py-3.5 text-base border-2 border-gray-300 rounded-xl sm:rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 min-h-[52px] sm:min-h-[48px] transition-colors"
              />
              {isSignUp && (
                <p className="text-xs sm:text-sm text-gray-500 mt-2">최소 6자 이상</p>
              )}
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            {/* 모바일: 큰 버튼 */}
            <button
              type="submit"
              disabled={loading}
              className="sm:hidden w-full py-4 bg-blue-600 text-white rounded-xl font-semibold active:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors min-h-[56px] text-base shadow-md active:shadow-lg active:scale-[0.98]"
            >
              {loading ? '처리 중...' : isSignUp ? '회원가입' : '로그인'}
            </button>
            
            {/* 데스크톱: 일반 버튼 */}
            <button
              type="submit"
              disabled={loading}
              className="hidden sm:block w-full py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors min-h-[48px] text-base shadow-md hover:shadow-lg"
            >
              {loading ? '처리 중...' : isSignUp ? '회원가입' : '로그인'}
            </button>
          </form>

          {/* 소셜 로그인 구분선 */}
          <div className="mt-6 sm:mt-8 flex items-center gap-4">
            <div className="flex-1 h-px bg-gray-200"></div>
            <span className="text-xs sm:text-sm text-gray-500">또는</span>
            <div className="flex-1 h-px bg-gray-200"></div>
          </div>

          {/* 소셜 로그인 버튼들 */}
          <div className="mt-5 sm:mt-6 space-y-3">
            {/* Google 로그인 */}
            <button
              onClick={async () => {
                setLoading(true)
                setError('')
                try {
                  await signInWithGoogle()
                } catch (err: any) {
                  setError(err.message)
                  setLoading(false)
                }
              }}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 sm:py-3.5 bg-white border-2 border-gray-200 rounded-xl sm:rounded-lg hover:bg-gray-50 active:bg-gray-100 transition-colors min-h-[52px] sm:min-h-[48px] disabled:opacity-50"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              <span className="text-sm sm:text-base font-medium text-gray-700">Google로 계속하기</span>
            </button>

            {/* 카카오 로그인 */}
            <button
              onClick={async () => {
                setLoading(true)
                setError('')
                try {
                  await signInWithKakao()
                } catch (err: any) {
                  setError(err.message)
                  setLoading(false)
                }
              }}
              disabled={loading}
              className="w-full flex items-center justify-center gap-3 px-4 py-3 sm:py-3.5 bg-[#FEE500] rounded-xl sm:rounded-lg hover:bg-[#FDD800] active:bg-[#FCCC00] transition-colors min-h-[52px] sm:min-h-[48px] disabled:opacity-50"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24">
                <path
                  fill="#000000"
                  d="M12 3c-4.97 0-9 3.185-9 7.115 0 2.557 1.707 4.8 4.27 6.054-.188.702-.682 2.545-.78 2.94-.123.49.18.484.378.352.156-.103 2.5-1.667 3.51-2.349.525.078 1.064.118 1.622.118 4.97 0 9-3.186 9-7.115C21 6.185 16.97 3 12 3z"
                />
              </svg>
              <span className="text-sm sm:text-base font-semibold text-[#000000]">카카오로 계속하기</span>
            </button>
          </div>

          {!isSignUp && (
            <div className="mt-6 text-center">
              <button className="text-sm text-blue-600 hover:underline">
                비밀번호를 잊으셨나요?
              </button>
            </div>
          )}
        </div>

        {/* 부가 정보 */}
        <div className="mt-6 sm:mt-8 text-center text-sm sm:text-base text-gray-600">
          <p className="sm:hidden">모든 기기에서 대화 내역 동기화</p>
          <p className="hidden sm:block">로그인하면 모든 기기에서 대화 내역을 동기화할 수 있습니다</p>
        </div>
      </div>
    </div>
  )
}

