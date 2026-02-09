# Uniroad iOS 앱 빌드 (Capacitor)

## 요구 사항

- Node.js, npm
- Xcode (Mac, iOS 시뮬레이터/실기기 빌드용)
- CocoaPods (`sudo gem install cocoapods`)

## 앱 전용 빌드 (권장)

iOS 앱용으로 **한 번에** 다음이 적용된 빌드를 하려면:

- API 베이스: `https://uni2road.com`
- Vite `base: './'` (앱 WebView에서 asset 로딩 안정)

```bash
cd frontend
npm run build:ios
npx cap sync ios
npx cap open ios
```

또는 빌드 + sync까지 한 번에:

```bash
npm run cap:ios
npx cap open ios
```

직접 API URL을 바꾸려면 `package.json`의 `build:ios` 스크립트에서 `VITE_API_BASE_URL` 값을 수정하거나, `.env.production`에 `VITE_API_BASE_URL=원하는URL`을 두고 `VITE_CAPACITOR=true npm run build`로 빌드하면 됩니다.

## 빌드 및 Xcode에서 실행

```bash
cd frontend
npm run cap:ios
npx cap open ios
```

Xcode가 열리면:

1. 시뮬레이터: 상단에서 대상(예: iPhone 15) 선택 후 ▶ Run
2. 실기기: 기기를 연결하고 서명(Team) 설정 후 Run

## 웹 자산만 갱신할 때

프론트 코드만 수정했을 때 (앱용 빌드 유지):

```bash
npm run cap:ios
```

그 다음 Xcode에서 다시 Run 하면 됩니다.

## 백엔드 CORS

앱(WebView)에서 `https://uni2road.com` 등으로 API를 호출하려면, 백엔드 CORS에 다음이 포함되어 있어야 합니다 (이미 추가됨):

- `capacitor://localhost`
- `ionic://localhost`

서버 배포 후 위 origin이 허용되는지 확인하세요.
