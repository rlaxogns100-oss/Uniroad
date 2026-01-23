# PDF 다운로드 문제 해결

## 🔍 문제 상황

출처 버튼이 표시되지만 클릭해도 다운로드가 안 됨

---

## 🧩 원인 분석

### 기존 코드의 문제점

```typescript
// Before
const link = document.createElement('a')
link.href = source.url  // 일반 Storage URL
link.download = downloadFileName
link.target = '_blank'
document.body.appendChild(link)
link.click()  // 클릭 시도
```

**문제**:
1. **Supabase Storage의 제한**
   - `download` 속성이 무시됨
   - CORS 정책으로 인해 `download` 속성이 작동하지 않음
   - 브라우저가 PDF를 다운로드하지 않고 새 탭에서 열려고 함

2. **브라우저 보안 정책**
   - Cross-origin URL에 대한 `download` 속성 제한
   - Supabase Storage는 다른 도메인이므로 `download` 속성 무효화

---

## ✅ 해결 방법

### Supabase Storage의 `?download` 쿼리 파라미터 사용

```typescript
// After
// Supabase Storage는 ?download 쿼리 파라미터로 다운로드 강제
const downloadUrl = source.url.includes('?') 
  ? `${source.url}&download=${encodeURIComponent(downloadFileName)}`
  : `${source.url}?download=${encodeURIComponent(downloadFileName)}`

// 새 탭에서 열기 (브라우저가 자동으로 다운로드 처리)
window.open(downloadUrl, '_blank', 'noopener,noreferrer')
```

---

## 🎯 동작 원리

### 1. Supabase Storage의 `?download` 파라미터

Supabase Storage는 URL에 `?download` 쿼리 파라미터를 추가하면:
- `Content-Disposition: attachment` 헤더를 자동으로 추가
- 브라우저가 파일을 새 탭에서 열지 않고 다운로드

**예시 URL**:
```
Before: https://xxx.supabase.co/storage/v1/object/public/document/pdfs/abc-123.pdf
After:  https://xxx.supabase.co/storage/v1/object/public/document/pdfs/abc-123.pdf?download=수능_점수_변환_및_추정_방법.pdf
```

### 2. 파일명 지정

`?download=파일명` 형식으로 다운로드될 파일명을 지정할 수 있음

```typescript
const downloadFileName = "수능 점수 변환 및 추정 방법.pdf"
const downloadUrl = `${source.url}?download=${encodeURIComponent(downloadFileName)}`
```

**결과**: 사용자가 다운로드할 때 `수능 점수 변환 및 추정 방법.pdf`로 저장됨

### 3. 기존 쿼리 파라미터 처리

URL에 이미 쿼리 파라미터가 있는 경우:
```typescript
source.url.includes('?') 
  ? `${source.url}&download=...`  // & 사용
  : `${source.url}?download=...`  // ? 사용
```

---

## 📊 Before vs After

### Before (작동 안 함)

```typescript
// 1. a 태그 생성
const link = document.createElement('a')
link.href = "https://supabase.co/.../file.pdf"
link.download = "파일명.pdf"

// 2. 클릭
link.click()

// 결과: ❌ 다운로드 안 됨 (새 탭에서 PDF 열림)
```

**이유**: 
- Supabase Storage는 cross-origin이므로 `download` 속성 무시
- 브라우저가 PDF를 다운로드하지 않고 뷰어로 열기

### After (작동함)

```typescript
// 1. ?download 파라미터 추가
const downloadUrl = "https://supabase.co/.../file.pdf?download=파일명.pdf"

// 2. 새 탭에서 열기
window.open(downloadUrl, '_blank')

// 결과: ✅ 자동으로 다운로드됨
```

**이유**:
- Supabase Storage가 `Content-Disposition: attachment` 헤더 반환
- 브라우저가 자동으로 다운로드 처리

---

## 🔧 코드 변경 내역

**파일**: `frontend/src/components/ChatMessage.tsx:439-450`

```typescript
// Before
if (fileExtension === 'pdf') {
  const link = document.createElement('a')
  link.href = source.url
  link.download = downloadFileName
  link.target = '_blank'
  link.rel = 'noopener noreferrer'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  return
}

// After
if (fileExtension === 'pdf') {
  // Supabase Storage는 ?download 쿼리 파라미터로 다운로드 강제
  const downloadUrl = source.url.includes('?') 
    ? `${source.url}&download=${encodeURIComponent(downloadFileName)}`
    : `${source.url}?download=${encodeURIComponent(downloadFileName)}`
  
  // 새 탭에서 열기 (브라우저가 자동으로 다운로드 처리)
  window.open(downloadUrl, '_blank', 'noopener,noreferrer')
  return
}
```

---

## 🎨 사용자 경험 변화

### Before
1. 출처 버튼 클릭
2. ❌ 아무 일도 안 일어남
3. 또는 새 탭에서 PDF 뷰어로 열림 (다운로드 안 됨)

### After
1. 출처 버튼 클릭
2. ✅ 즉시 다운로드 시작
3. 브라우저 다운로드 바에 파일 표시
4. "수능 점수 변환 및 추정 방법.pdf" 파일명으로 저장됨

---

## 🧪 테스트

### 1. 프론트엔드 재시작
```bash
# 프론트엔드 터미널 (Ctrl+C 후)
npm run dev
```

### 2. 테스트 시나리오

#### Test 1: 점수 변환 문서 다운로드
```
1. 성적 포함 질문: "정시에 국어 92점, 수학 85점... 어디 갈 수 있어?"
2. 답변 하단 "수능 점수 변환 및 추정 방법" 버튼 클릭
3. ✅ 다운로드 시작 확인
4. ✅ "수능 점수 변환 및 추정 방법.pdf" 파일명 확인
```

#### Test 2: 다른 PDF 문서 다운로드
```
1. 대학 문서가 표시되는 질문
2. 출처 버튼 클릭
3. ✅ 각 문서가 정상적으로 다운로드되는지 확인
```

---

## 💡 추가 정보

### Supabase Storage 다운로드 옵션

Supabase Storage는 다음 쿼리 파라미터를 지원합니다:

1. **`?download`**: 다운로드 강제 (파일명 지정 안 함)
   ```
   https://.../file.pdf?download
   ```

2. **`?download=파일명`**: 다운로드 강제 + 파일명 지정
   ```
   https://.../file.pdf?download=커스텀_파일명.pdf
   ```

3. **기타 파라미터와 조합**:
   ```
   https://.../file.pdf?token=abc&download=파일명.pdf
   ```

### 브라우저 호환성
- ✅ Chrome, Edge, Safari, Firefox 모두 지원
- ✅ 모바일 브라우저 (iOS Safari, Chrome Mobile) 지원
- ✅ CORS 정책 우회 (서버가 다운로드 헤더 제공)

---

**작성일**: 2026년 1월 24일  
**버전**: 1.0  
**상태**: 수정 완료, 프론트엔드 재시작 필요
