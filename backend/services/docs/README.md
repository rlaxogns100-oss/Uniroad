# 문서 디렉토리

## 파일 목록

### 1. score_calculation_method.md
- **설명:** 2026 수능 표준점수 및 백분위 산출 방식 (Markdown 원본)
- **용도:** 문서 관리 및 버전 관리

### 2. score_calculation_method.html
- **설명:** 산출 방식 문서 (HTML 버전)
- **용도:** 브라우저에서 바로 볼 수 있는 형식
- **PDF 변환:** 브라우저에서 열고 `Ctrl+P` (또는 `Cmd+P`) → PDF로 저장 선택
- **접근 URL:** `http://localhost:8000/docs/score_calculation_method.html`

### 3. 유니로드 표준점수 및 백분위 산출 방식.pdf
- **설명:** 산출 방식 문서 (PDF 버전)
- **용도:** 사용자가 다운로드할 수 있는 최종 문서
- **접근 URL:** `http://localhost:8000/docs/유니로드 표준점수 및 백분위 산출 방식.pdf`

## PDF 파일 생성 방법

### 방법 1: 브라우저에서 직접 변환 (권장)

1. 서버 실행:
   ```bash
   cd backend
   python3 main.py
   ```

2. 브라우저에서 열기:
   ```
   http://localhost:8000/docs/score_calculation_method.html
   ```

3. 인쇄 다이얼로그 열기:
   - Windows/Linux: `Ctrl + P`
   - macOS: `Cmd + P`

4. "대상"에서 "PDF로 저장" 선택

5. 저장 위치 지정 후 저장

### 방법 2: Python 스크립트 사용 (추후 구현 가능)

```bash
# 필요한 패키지 설치
pip install weasyprint

# PDF 생성 스크립트 작성 및 실행
# (현재는 방법 1 권장)
```

## 출처 표시

ConsultingAgent에서 성적 변환을 수행한 경우, 자동으로 다음 출처가 표시됩니다:

```
출처: 표준점수, 백분위 산출방식
```

클릭 시 `/docs/score_calculation_method.html` 문서로 이동합니다.

## 문서 업데이트

문서를 수정할 때:

1. `score_calculation_method.md` 파일 수정
2. `score_calculation_method.html` 파일 수정 (또는 자동 변환 스크립트 사용)
3. 버전 번호 및 최종 수정일 갱신
4. Git 커밋

## 문의

문서에 대한 문의사항은 시스템 관리자에게 연락하세요.
