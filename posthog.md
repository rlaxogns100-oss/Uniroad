# PostHog 운영 가이드

## 목적
- 프론트의 유입, 활성화, 결제, 리텐션을 PostHog에서 일관되게 본다.
- `Autocapture`는 탐색용으로 두고, 핵심 KPI는 수동 비즈니스 이벤트로 집계한다.
- 기존 자체 추적(`/api/tracking/...`)과 PostHog를 병행해 기존 관리자 지표와 비교 가능하게 유지한다.

## 현재 구성
- `frontend/src/main.tsx`
  - `PostHogProvider` 연결
  - `api_host: '/ingest'`
  - `capture_pageview: false`
- `frontend/src/utils/tracking.ts`
  - 공통 컨텍스트 빌드
  - `trackPageView()`
  - `trackUserAction()`
  - `captureBusinessEvent()`
  - `identifyTrackingUser()`, `resetTrackingUser()`
- `frontend/src/utils/trackingSchema.ts`
  - 이벤트 이름, 인증 트리거, 페이월 사유, 결제 수단 상수
- `backend/routers/tracking.py`
  - business 이벤트를 `event_type=action_name`으로 저장
  - `custom_data` 전체를 저장
- `frontend/scripts/posthog-dashboard-spec.json`
  - Golden Path 대시보드 스펙
- `frontend/scripts/setup-posthog-dashboard.mjs`
  - PostHog 대시보드/인사이트 생성 스크립트
- `deploy/nginx/posthog-ingest.conf.example`
  - 운영 `/ingest` 프록시 예시

## 핵심 이벤트 스키마
### Acquisition
- `page_view`
- `landing_cta_click`
- `first_interaction`
- `feature_card_click`
- `example_question_click`

### Activation
- `auth_modal_view`
- `login_click`
- `signup_click`
- `oauth_click`
- `login_completed`
- `signup_completed`
- `chat_blocked_auth_required`

### Revenue
- `paywall_view`
- `payment_cta_click`
- `payment_method_selected`
- `payment_started`
- `payment_completed`
- `payment_failed`
- `referral_code_applied`

### Feature Usage
- `chat_first_message`
- `chat_message_sent`
- `school_record_entry_click`
- `school_record_pdf_upload_started`
- `school_record_pdf_upload_succeeded`
- `school_record_pdf_upload_failed`
- `school_record_saved`
- `school_record_analysis_requested`
- `score_link_entry_click`
- `score_input_mode_selected`
- `score_autofill_started`
- `score_saved`
- `score_recommendation_requested`

## 공통 속성
- `session_id`
- `entry_url`
- `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`
- `page_path`, `page_type`
- `is_logged_in`
- `user_id`
- `user_type`
- `is_internal`
- `auth_trigger`
- `first_interaction_type`

## 운영 프록시
운영 서버에서는 `/ingest`를 PostHog US 엔드포인트로 프록시해야 한다.

참고 파일:
- `deploy/nginx/posthog-ingest.conf.example`

적용 순서:
1. `/etc/nginx/sites-available/uniroad`의 TLS 서버 블록에 `/ingest/static/`, `/ingest/` location 추가
2. `sudo nginx -t`
3. `sudo systemctl reload nginx`
4. 브라우저 Network 탭에서 `/ingest/*` 요청이 `200` 또는 `304`로 끝나는지 확인

## 대시보드 자동 생성
실행 위치:

```bash
cd frontend
POSTHOG_PROJECT_ID="프로젝트_ID" \
POSTHOG_PERSONAL_API_KEY="개인_API_키" \
npm run posthog:setup
```

스펙 파일:
- `frontend/scripts/posthog-dashboard-spec.json`

현재 대시보드 섹션:
- Daily Visitors
- Traffic Source Mix
- Device Mix
- Activation Funnel
- Signup Funnel
- Revenue Funnel
- Feature Usage (Paid Users)
- Paid User Retention

## 데이터 품질 체크리스트
- `page_view`가 첫 진입에서 1회만 찍히는지 확인
- 로그인 후 anonymous -> identified user stitching이 되는지 확인
- 관리자 계정이 `is_internal=true`로 들어오는지 확인
- `paywall_view.reason`이 `daily_limit`, `deep_analysis`, `thinking`, `subscription_manage`로 잘 분기되는지 확인
- `payment_method_selected`, `payment_started`, `payment_completed`가 같은 세션에서 이어지는지 확인
- `school_record_*`, `score_*` 이벤트가 실제 액션과 1:1 대응하는지 확인
- Supabase `events` 수치와 PostHog 비즈니스 이벤트 수치가 큰 차이 없이 맞는지 확인

## 주의사항
- Autocapture와 수동 이벤트를 모두 켜두므로 KPI는 수동 이벤트 기준으로 본다.
- 버튼 텍스트 기반 분석은 금지하고 `cta_id`, `reason`, `payment_method` 같은 안정 속성으로 본다.
- 운영 지표에서는 항상 `is_internal != true` 조건을 적용한다.
- 브라우저 개발 모드에서는 React Strict Mode 영향으로 로컬에서 effect가 중복 실행될 수 있으므로 실제 집계는 운영 환경 기준으로 검증한다.

## 작업 로그
### 2026-03-09
- PostHog React SDK 설치
- `main.tsx`에 Provider 연결
- `/ingest` Vite 프록시 설정

### 2026-03-10
- `tracking.ts`에 비즈니스 이벤트 래퍼 추가
- 페이지뷰 중복 제거 및 `identify/reset` 도입
- 랜딩/채팅/인증/생기부/점수연동/결제 핵심 이벤트 계측
- 대시보드 스펙 및 생성 스크립트를 저장소 안으로 이동
- 운영 Nginx용 `/ingest` 프록시 예시 파일 추가
