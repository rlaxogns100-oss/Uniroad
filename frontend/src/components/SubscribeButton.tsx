import { useAuth } from '../contexts/AuthContext'
import { redirectToGumroadCheckout } from '../utils/gumroad'

interface SubscribeButtonProps {
  className?: string
  children?: React.ReactNode
}

/**
 * 구독하기 버튼: 클릭 시 Gumroad Checkout URL로 리다이렉트
 */
export function SubscribeButton({ className = '', children }: SubscribeButtonProps) {
  const { user, isAuthenticated } = useAuth()

  const handleSubscribe = () => {
    if (!isAuthenticated || !user?.id) {
      return
    }
    const ok = redirectToGumroadCheckout(user.id, user.email)
    if (!ok) {
      alert('구독 페이지 URL이 설정되지 않았습니다. 잠시 후 다시 시도해 주세요.')
    }
  }

  if (!isAuthenticated || !user?.id) {
    return null
  }

  return (
    <button
      type="button"
      onClick={handleSubscribe}
      className={className}
      aria-label="구독하기"
    >
      {children ?? '구독하기'}
    </button>
  )
}
