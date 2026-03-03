# PWA (Progressive Web App) 안내

## 휴대폰에서 보는 방법

### 1) 이미 배포된 사이트가 있을 때 (권장)

- 휴대폰 브라우저에서 **https://uni2road.com** (또는 사용 중인 도메인) 접속
- PWA로 쓰려면: Chrome → 메뉴 → "앱 설치" / Safari → 공유 → "홈 화면에 추가"

### 2) 같은 Wi‑Fi에서 개발 중인 화면을 폰으로 볼 때

1. **백엔드 실행** (PC에서)
   ```bash
   cd backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **프론트 개발 서버를 폰에서 접속 가능하게 실행** (PC에서)
   ```bash
   cd frontend
   npm run dev:mobile
   ```
   → `--host` 로 띄워서 같은 Wi‑Fi의 다른 기기에서 접속 가능해짐.

3. **PC IP 확인**
   - Mac: 시스템 설정 → 네트워크 → Wi‑Fi → 상세 → IP 주소  
   - 또는 터미널: `ipconfig getifaddr en0` (Wi‑Fi가 en0일 때)

4. **휴대폰에서 접속**
   - 휴대폰을 **같은 Wi‑Fi**에 연결한 뒤
   - 브라우저 주소창에 `http://<PC의_IP>:8147` 입력  
     예: `http://192.168.0.10:8147`

**주의**: 개발용이므로 `http`이고, PWA 설치/캐시는 HTTPS 배포 환경에서 테스트하는 것이 좋습니다.

---

## 설치 후 사용 방법 (PWA)

1. **의존성 설치** (최초 1회)
   ```bash
   npm install
   ```

2. **프로덕션 빌드**
   ```bash
   npm run build
   ```
   - 빌드 결과물에 Service Worker와 manifest가 포함됩니다.

3. **HTTPS로 배포**
   - PWA는 보안 컨텍스트(HTTPS 또는 localhost)에서만 동작합니다.
   - uni2road.com 등 실제 도메인에 배포하면 됩니다.

4. **홈 화면에 추가**
   - **Android (Chrome)**: 주소창 메뉴 → "앱 설치" 또는 "홈 화면에 추가"
   - **iOS (Safari)**: 공유 버튼 → "홈 화면에 추가"

## 아이콘 (선택)

현재는 `public/로고.png`를 192·512 크기로 공통 사용합니다.  
앱 아이콘 품질을 높이려면 다음을 추가하세요.

- `public/icon-192.png` — 192×192 px
- `public/icon-512.png` — 512×512 px

추가 후 `vite.config.ts`의 `manifest.icons`에서 경로를 위 파일로 바꾸면 됩니다.
