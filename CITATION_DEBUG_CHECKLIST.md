# Citation 클릭 문제 완전 점검

## ✅ 1단계: 환경변수 확인
```bash
✅ SCORE_CONVERSION_GUIDE_URL=https://rnitmphvahpkosvxjshw.supabase.co/storage/v1/object/public/document/pdfs/efe55407-d51c-4cab-8c20-aabb2445ac2b.pdf
```

## ✅ 2단계: PDF URL 접근 확인
```bash
✅ HTTP/2 200
✅ content-type: application/pdf
✅ content-length: 729761 (712 KB)
✅ access-control-allow-origin: *
```

## ✅ 3단계: 프론트엔드 코드 확인
**파일**: `frontend/src/components/ChatMessage.tsx:439-482`

```typescript
<a
  key={idx}
  href={source.url}
  onClick={async (e) => {
    e.preventDefault()
    console.log('클릭:', source.text)
    // ... fetch + blob 다운로드
  }}
  className="... cursor-pointer ..."
>
  <svg>...</svg>
  <span>{source.text}</span>
</a>
```

✅ 코드 저장됨

## ✅ 4단계: 프론트엔드 실행 확인
```bash
✅ vite 실행 중 (PID: 34864)
✅ npm run dev 실행 중 (PID: 34847)
```

## ❌ 5단계: 백엔드 실행 확인
```bash
❌ uvicorn 실행 안 됨
→ 백엔드를 시작하세요!
```

---

## 🧪 즉시 테스트

### 1. 독립 테스트 (백엔드 필요 없음)
```
파일: /Users/rlaxogns100/Desktop/Projects/UniZ/frontend/test_citation_debug.html

1. 브라우저에서 열림 (자동으로 열림)
2. 회색 버튼 클릭
3. 콘솔에 "클릭 이벤트 발생!" 표시 확인
4. 다운로드 시작 확인
```

### 2. 실제 앱 테스트

#### Step 1: 백엔드 시작
```bash
cd /Users/rlaxogns100/Desktop/Projects/UniZ/backend
uvicorn main:app --reload
```

#### Step 2: 프론트엔드 새로고침
- 브라우저에서 `Cmd + R`로 새로고침
- 또는 프론트엔드 재시작:
  ```bash
  cd /Users/rlaxogns100/Desktop/Projects/UniZ/frontend
  # Ctrl+C 후
  npm run dev
  ```

#### Step 3: 테스트
```
1. 질문: "정시에 국어 92점, 수학 85점, 영어 88점, 생활과윤리 90점, 사회문화 87점을 맞았는데 어디 갈 수 있어?"

2. 답변 하단 확인:
   - 회색 버튼들 보이는가? → 보임
   - "수능 점수 변환 및 추정 방법" 버튼 있는가? → 있음
   
3. 버튼 클릭:
   - 커서가 포인터로 바뀌는가? → Yes (cursor-pointer)
   - 클릭 시 콘솔에 "클릭:" 로그 나오는가? → 개발자 도구 확인
   - 다운로드 시작되는가? → 확인

4. 개발자 도구 (F12):
   - Console 탭 열기
   - 버튼 클릭 시 로그 확인:
     ✅ "클릭: 수능 점수 변환 및 추정 방법"
     ✅ blob 생성 로그
   - 에러 있으면 확인
```

---

## 🔍 문제 진단

### Case 1: 버튼이 아예 안 보임
**원인**: citation이 백엔드에서 전달 안 됨
**해결**: 
1. 백엔드 시작 확인
2. `extracted_scores` 전달 확인
3. 백엔드 로그 확인

### Case 2: 버튼은 보이는데 클릭이 안 됨
**원인**: 
- CSS `pointer-events: none`이 어딘가 적용됨
- 다른 요소가 위에 겹쳐있음
- JavaScript 이벤트 리스너 안 붙음

**해결**:
1. 개발자 도구 → Elements 탭
2. 버튼 요소 검사
3. Computed 스타일에서 `pointer-events` 확인
4. `cursor` 속성 확인

### Case 3: 클릭은 되는데 다운로드 안 됨
**원인**: fetch 실패 또는 blob 생성 실패
**해결**:
1. 개발자 도구 → Console 탭
2. 에러 메시지 확인
3. Network 탭에서 PDF 요청 확인

### Case 4: 커서가 pointer로 안 바뀜
**원인**: CSS `cursor-pointer`가 안 먹힘
**해결**:
```typescript
// inline style 추가
<a
  style={{ cursor: 'pointer' }}
  className="..."
>
```

---

## 💡 즉시 적용 가능한 해결책

### 해결책 1: inline 이벤트로 변경
```typescript
<a
  href={source.url}
  onMouseDown={(e) => {
    e.preventDefault();
    // 다운로드 로직
  }}
  style={{ cursor: 'pointer', pointerEvents: 'auto' }}
>
```

### 해결책 2: button으로 변경
```typescript
<button
  type="button"
  onClick={async (e) => {
    // 다운로드 로직
  }}
  style={{ cursor: 'pointer' }}
  className="..."
>
```

---

## 📝 최종 확인 사항

- [ ] 백엔드 실행 중
- [ ] 프론트엔드 실행 중
- [ ] 브라우저 새로고침 완료
- [ ] 성적 포함 질문 입력
- [ ] 답변에 버튼 표시됨
- [ ] 버튼 hover 시 배경색 변경됨
- [ ] 버튼 클릭 시 console.log 출력됨
- [ ] 다운로드 시작됨

---

**테스트 파일**: `/Users/rlaxogns100/Desktop/Projects/UniZ/frontend/test_citation_debug.html`  
**상태**: 브라우저에서 자동으로 열림
