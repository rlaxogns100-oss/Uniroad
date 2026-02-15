# Polar.sh 결제 연동 설정

## 1. 환경 변수 (.env)

`backend/.env`에 다음을 추가하세요.

```bash
# Polar.sh 웹훅 검증용 시크릿 (Polar 대시보드 → Webhooks → 엔드포인트 설정에서 복사)
POLAR_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Polar API 토큰 (구독 상태 조회 등 - Polar 대시보드에서 발급)
POLAR_ACCESS_TOKEN=polar_oat_xxxxxxxxxxxxxxxxx
```

- **POLAR_WEBHOOK_SECRET**: Polar 대시보드에서 웹훅 엔드포인트를 만들 때 발급되는 시크릿입니다.  
  값이 비어 있으면 웹훅이 500으로 거부됩니다.
- **POLAR_ACCESS_TOKEN**: Polar API 호출용 토큰. 구독 상태 조회(`GET /api/v1/payments/subscription-status`)에 사용됩니다.  
  비어 있으면 해당 API가 503을 반환합니다.

## 2. 프론트엔드 (선택)

Polar Checkout로 이동하는 URL을 쓰려면 `frontend/.env` 또는 `frontend/.env.production`에:

```bash
# Polar Checkout 링크 (Polar 대시보드에서 생성한 구독/체크아웃 URL)
VITE_POLAR_CHECKOUT_URL=https://polar.sh/your-org/checkout
```

- 이 값을 설정하지 않으면 구독하기 버튼이 동작하지 않습니다 (URL이 비어 있음).

## 3. 웹훅 URL

Polar 대시보드에서 웹훅 엔드포인트 URL을 다음으로 설정하세요.

- **개발**: `https://your-ngrok-or-tunnel-url/api/v1/payments/webhook`
- **운영**: `https://uni2road.com/api/v1/payments/webhook`

수신 이벤트: `subscription.created` (필수).

## 4. Checkout 시 client_reference_id

체크아웃 링크에 쿼리 파라미터로 Supabase 유저 ID를 넘깁니다.

- 프론트: `getPolarCheckoutUrl(userId)` / `redirectToPolarCheckout(userId)` 사용
- 예: `https://polar.sh/your-org/checkout?client_reference_id=<supabase_user_uuid>`

Polar에서 이 값을 구독/체크아웃 이벤트에 담아 웹훅으로 보내면, 백엔드에서 해당 유저의 `user_profiles.metadata.is_premium`를 `true`로 업데이트합니다.
