# 유니로드 iOS 앱 스토어 배포 체크리스트

## 이미 해둔 것 (코드/설정)
- [x] 버전: **1.0.1** (MARKETING_VERSION)
- [x] 빌드 번호: **2** (CURRENT_PROJECT_VERSION)
- [x] 웹 빌드 및 `cap sync`로 최신 코드 반영

---

## Xcode에서 할 일

### 1. 아카이브
1. **Product → Archive** (실기기 선택 후에만 Archive 메뉴 활성화)
2. 아카이브가 끝나면 **Organizer** 창이 열림

### 2. 스토어 업로드
1. Organizer에서 방금 만든 아카이브 선택
2. **Distribute App** 클릭
3. **App Store Connect** → Next
4. **Upload** → Next
5. 옵션 그대로 두고 **Upload**
6. 업로드 완료될 때까지 대기

### 3. App Store Connect에서 제출
1. [App Store Connect](https://appstoreconnect.apple.com) 로그인
2. 해당 앱 → **TestFlight** 또는 **앱 스토어** 탭
3. 새 빌드(1.0.1 (2))가 보이면 선택
4. **버전 정보** 입력 후 **심사에 제출**
5. 심사 통과 후 **이 버전 배포**하면 사용자가 업데이트 받을 수 있음

---

## 다음에 버전 올릴 때
1. `frontend/ios/App/App.xcodeproj/project.pbxproj`에서  
   - `MARKETING_VERSION` (예: 1.0.1 → 1.0.2)  
   - `CURRENT_PROJECT_VERSION` (예: 2 → 3)  
   각각 Debug/Release 두 군데 수정
2. `npm run build:ios && npx cap sync ios` 실행
3. 위 1~3 단계 반복
