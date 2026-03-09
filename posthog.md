# PostHog 작업 기록

## 목적
- `uniroad_code_main/frontend`에 PostHog를 연동한다.
- 로컬에서 이벤트 수집을 검증한다.
- 광고 차단 우회를 위해 `/ingest` 프록시를 적용한다.
- PostHog 기본 대시보드를 API로 자동 생성할 수 있게 한다.

## 현재 상태 요약
- 프런트엔드에 `posthog-js`, `@posthog/react` 설치 완료
- `main.tsx`에서 `PostHogProvider` 연결 완료
- `tracking.ts`에서 기존 추적 로직과 함께 PostHog 이벤트도 전송하도록 반영 완료
- `vite.config.ts`에 `/ingest` 프록시 설정 완료
- PostHog 대시보드 자동 생성 스크립트 작성 및 실행 완료
- 로컬에서 PostHog 수집 자체는 가능함을 확인

## 이번에 수정한 파일
- `frontend/package.json`
  - PostHog 패키지 추가
- `frontend/.env.local`
  - PostHog 프로젝트 키/호스트 추가
  - 민감 정보라 Git에는 올라가지 않음
- `frontend/src/main.tsx`
  - `PostHogProvider` 적용
  - `api_host`를 `/ingest`로 변경
  - `ui_host`를 `https://us.posthog.com`으로 설정
- `frontend/src/utils/tracking.ts`
  - 기존 페이지뷰/행동 추적 시 PostHog `capture`도 함께 호출하도록 추가
- `frontend/vite.config.ts`
  - `/ingest/static/` -> `https://us-assets.i.posthog.com/static/`
  - `/ingest/` -> `https://us.i.posthog.com/`
- `../setup_dashboard.js`
  - Personal API Key로 기본 대시보드를 자동 생성하는 스크립트

## 적용한 주요 설정
### 1. 프런트엔드 PostHog 연결
- React + Vite 프로젝트 기준으로 연결
- 앱 루트에서 `PostHogProvider`로 감쌈
- 초기 설정:
  - `api_host: '/ingest'`
  - `ui_host: 'https://us.posthog.com'`
  - `defaults: '2026-01-30'`

### 2. 이벤트 전송 연결
- `initializeTracking()`에서 앱 초기화 이벤트 전송
- `trackPageView()`에서 `$pageview` 전송
- `trackUserAction()`에서 액션명을 이벤트 이름으로 전송

### 3. 광고 차단 우회
- Next.js가 아니라 Vite 프로젝트이므로 `next.config.*` 대신 `vite.config.ts`에 프록시 설정
- 로컬 개발 환경에서는 `/ingest` 경로로 PostHog 요청이 우회됨
- 운영 환경에서는 별도 웹서버/nginx 프록시 설정이 추가로 필요함

## 확인한 내용
### 환경변수
- `frontend/.env.local`에 PostHog 키/호스트 반영됨
- 번들 결과물에도 값이 포함되는 것 확인

### 로컬 이벤트 수집
- 로컬에서 PostHog 이벤트 전송 자체는 가능
- PostHog 수집 API에 직접 테스트 이벤트 전송 시 `HTTP 200`, `{"status":"Ok"}` 응답 확인

### 참고
- 브라우저 콘솔에서 `window.posthog?.capture(...)` 결과가 `undefined`로 보이는 것은 실패 의미가 아님
- 함수 반환값이 없어서 그렇게 보일 수 있음

## 대시보드 자동화
### 스크립트
- 파일: `../setup_dashboard.js`
- 실행 방식:

```bash
cd "/Users/rlaxogns100/Desktop/Projects/uniroad_renewer"
POSTHOG_PERSONAL_API_KEY="개인_API_키" node setup_dashboard.js
```

### 생성/확인된 대시보드
- 대시보드 이름: `기본 대시보드 (자동 생성)`
- 대시보드 URL: `https://us.posthog.com/project/335960/dashboard/1342741`

### 생성된 그래프
- `기기별 접속 현황 (OS)`
- `유입 경로`
- `유저 이동 경로 (Top paths)`

### 보안 메모
- Personal API Key는 파일에 하드코딩하지 않음
- 실행 시 환경변수로만 주입
- 문서에도 실제 키 값은 기록하지 않음

## 현재 이슈 / 주의사항
- 로컬 Vite 서버에서는 `/ingest` 프록시가 동작함
- 운영 서버에서는 `/ingest` 경로를 PostHog로 넘기는 서버 프록시 설정이 아직 필요함
- 기존 자체 추적 API(`/api/tracking/...`)는 로컬 백엔드가 없으면 `127.0.0.1:8000` 에러가 날 수 있음
- 이 에러는 PostHog 수집 자체와는 별개임

## 다음 작업 후보
- 운영 서버 nginx 또는 프록시 설정에 `/ingest` 라우팅 추가
- PostHog 대시보드에서 실제 이벤트 유입 재검증
- 회원가입/로그인/결제 같은 핵심 비즈니스 이벤트를 별도 이름으로 정리
- `tracking.ts`의 이벤트 명명 규칙 표준화
- 필요 시 `debug: true`로 임시 디버깅 후 제거
- UTM / 캠페인 / 랜딩 페이지 중심 인사이트 추가

## 작업 로그
### 2026-03-09
- PostHog React SDK 설치
- `main.tsx`에 Provider 연결
- `.env.local`에 PostHog 설정 추가
- `tracking.ts`에 PostHog capture 연결
- 로컬 dev 서버에서 이벤트 검증 시도
- PostHog 직접 capture API 테스트 성공
- `setup_dashboard.js` 작성 및 기본 대시보드 생성
- `/ingest` 프록시 방식으로 광고 차단 우회 설정 반영

## 이후 기록 규칙
- 새 작업을 하면 날짜별로 `작업 로그` 섹션에 추가
- 민감한 키/토큰/비밀번호는 절대 문서에 직접 기록하지 않음
- 변경 파일, 목적, 검증 결과, 남은 이슈를 같이 기록
