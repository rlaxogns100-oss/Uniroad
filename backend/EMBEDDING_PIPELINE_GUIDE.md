# 임베딩 기반 업로드 가이드

## 1. 필수 환경 변수 (backend/.env 또는 프로젝트 루트 .env)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=eyJ...
GEMINI_API_KEY=...
```
선택: `GEMINI_LLM_MODEL=gemini-2.0-flash-exp` (기본값과 동일)

## 2. DB 마이그레이션 (업로드 전 반드시 1회 실행)
1. [Supabase Dashboard](https://supabase.com/dashboard) → 프로젝트 선택
2. 왼쪽 메뉴 **SQL Editor** 클릭
3. **New query** 선택 후 아래 파일 내용 전체 복사·붙여넣기  
   파일 경로: `backend/migrations/09_create_documents_tables.sql`
4. **Run** 실행 (에러 없이 완료될 때까지 확인)
5. Table Editor에서 `documents`, `document_sections`, `document_chunks` 테이블 생성 여부 확인

## 3. Storage 버킷 (PDF 다운로드 URL용)
- Supabase **Storage**에 `document` 버킷이 있어야 함 (없으면 생성)
- 버킷을 **Public**으로 두면 업로드된 PDF의 `file_url`로 다운로드 가능

## 4. 백엔드 실행
```bash
cd backend
pip install -r requirements.txt   # 최초 1회
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 5. 업로드 테스트
- **프론트**: 브라우저에서 `http://localhost:5173/upload` 접속 → 폴더/파일 선택 후 학교명 입력 → 업로드
- **API 직접**:  
  `curl -X POST http://localhost:8000/api/upload/ -F "file=@sample.pdf" -F "school_name=테스트대학"`

성공 시 응답 예:
```json
{"success":true,"message":"파일이 성공적으로 처리되었습니다.","stats":{"totalPages":N,"chunksTotal":M,...}}
```

## 6. 검증 체크리스트
- Supabase Table Editor: `documents`에 1행, `document_sections`에 N행, `document_chunks`에 M행 추가
- `document_chunks.embedding` 컬럼이 768차원 벡터로 저장
- `GET /api/documents` 호출 시 방금 올린 문서가 목록에 포함 (id, schoolName, fileUrl 등)

## 유의사항
- Vision 기반 처리로 PDF당 수십 초~수 분 소요될 수 있음 (대용량/목차 복잡 시)
- `strict_mode=True`이면 일부 섹션만 실패해도 해당 파일 전체 실패 처리
