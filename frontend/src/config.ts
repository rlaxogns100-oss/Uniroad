/**
 * 앱에서 사용하는 API 베이스 URL.
 * Capacitor(iOS/Android) 앱 빌드 시 .env에 VITE_API_BASE_URL=https://uni2road.com 로 설정하면
 * 번들된 앱이 해당 서버로 요청합니다. 미설정 시 상대 경로(웹 배포와 동일) 사용.
 */
export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
