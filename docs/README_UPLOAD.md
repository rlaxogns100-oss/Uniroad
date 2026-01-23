# 점수 변환 문서 업로드 가이드

## 📄 문서 생성 완료

다음 파일들이 생성되었습니다:
- `수능_점수_변환_및_추정_방법.md` - Markdown 원본
- `수능_점수_변환_및_추정_방법.html` - 브라우저에서 열 수 있는 HTML 버전

---

## 🎯 PDF 생성 및 업로드 절차

### 1단계: HTML을 PDF로 변환

1. **브라우저에서 열기**
   ```bash
   open docs/수능_점수_변환_및_추정_방법.html
   ```

2. **PDF로 저장**
   - `Cmd + P` (Mac) 또는 `Ctrl + P` (Windows)
   - 프린터 대상: **"PDF로 저장"**
   - 저장 위치: `/Users/rlaxogns100/Desktop/Projects/UniZ/docs/`
   - 파일명: `수능_점수_변환_및_추정_방법.pdf`
   - **저장 클릭**

3. **권장 인쇄 설정**
   - 용지 크기: A4
   - 여백: 기본값
   - 배경 그래픽: ✅ 포함
   - 축척: 100%

---

### 2단계: Supabase에 업로드

PDF 저장 완료 후:

```bash
cd /Users/rlaxogns100/Desktop/Projects/UniZ
python3 backend/services/upload_conversion_doc.py
```

업로드가 성공하면 **Public URL**이 출력됩니다.

---

### 3단계: 환경변수 설정

1. **backend/.env 파일 열기**
   ```bash
   nano backend/.env
   # 또는
   code backend/.env
   ```

2. **다음 줄 추가** (업로드 시 출력된 URL 사용)
   ```
   SCORE_CONVERSION_GUIDE_URL=https://rnitmphvahpkosvxjshw.supabase.co/storage/v1/object/public/document/pdfs/xxxxx.pdf
   ```

3. **저장하고 닫기**

---

### 4단계: 서버 재시작

환경변수 적용을 위해 서버를 재시작하세요.

---

## ✅ 완료 확인

이제 컨설팅 에이전트가 점수 변환을 수행할 때마다:
- ✅ 자동으로 "수능 점수 변환 및 추정 방법" 문서가 출처로 추가됩니다
- ✅ 사용자가 문서를 다운로드할 수 있습니다
- ✅ 점수 변환 방법에 대한 신뢰성이 향상됩니다

---

## 🔄 문서 업데이트

문서 내용을 수정한 경우:

1. `수능_점수_변환_및_추정_방법.md` 수정
2. HTML 재생성:
   ```bash
   python3 docs/convert_to_pdf.py
   ```
3. 브라우저에서 HTML을 PDF로 다시 저장
4. Supabase에 재업로드:
   ```bash
   python3 backend/services/upload_conversion_doc.py
   ```
5. 새로운 URL을 .env에 업데이트

---

## 📝 참고사항

- **문서 제목**: "2026학년도 수능 점수 변환 및 추정 방법 안내"
- **적용 범위**: 모든 컨설팅 에이전트 응답에서 `extracted_scores` 사용 시
- **문서 형식**: PDF (고등학생 대상, 기술 용어 최소화)
- **데이터 기준**: 2026학년도 수능 공식 자료 및 주요 대학 정시 모집요강
