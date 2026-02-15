/**
 * OAuth 콜백 전용 페이지 (앱 딥링크용).
 * Google/Kakao 로그인 후 이 URL(https://uni2road.com/oauth-callback?code=xxx)로 리다이렉트되면,
 * code를 추출해 앱 스킴(uniroad://)으로 넘겨 앱이 다시 열리도록 합니다.
 */
import React, { useEffect, useState } from 'react'

const APP_OAUTH_SCHEME = 'uniroad://oauth-callback'

export default function OAuthCallbackPage() {
  const [status, setStatus] = useState<'redirecting' | 'done' | 'error'>('redirecting')
  const [message, setMessage] = useState('앱으로 돌아가는 중…')

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    const error = params.get('error')

    if (error) {
      setStatus('error')
      setMessage('로그인에 실패했습니다. 앱에서 다시 시도해 주세요.')
      return
    }

    if (!code) {
      setStatus('error')
      setMessage('인증 코드가 없습니다. 앱에서 다시 로그인해 주세요.')
      return
    }

    try {
      const appUrl = `${APP_OAUTH_SCHEME}?code=${encodeURIComponent(code)}`
      window.location.href = appUrl
      setMessage('앱이 열리지 않으면 유니로드 앱을 실행해 주세요.')
      const t = setTimeout(() => setStatus('done'), 2000)
      return () => clearTimeout(t)
    } catch (e) {
      setStatus('error')
      setMessage('앱으로 이동할 수 없습니다.')
    }
  }, [])

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-50 p-6">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-sm w-full text-center">
        <div className="mb-6">
          <img src="/로고.png" alt="유니로드" className="h-16 mx-auto" />
        </div>
        {status === 'redirecting' && (
          <>
            <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-gray-700 font-medium">{message}</p>
          </>
        )}
        {status === 'done' && (
          <p className="text-gray-600">{message}</p>
        )}
        {status === 'error' && (
          <p className="text-red-600 font-medium">{message}</p>
        )}
      </div>
    </div>
  )
}
