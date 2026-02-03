# PDF 업로드 작동 순서

프론트에서 PDF를 올리면 백엔드·Supabase까지 처리되는 전체 흐름입니다.

---

## 전체 흐름 요약

```
프론트 (AdminUploadPage) → POST /api/upload/
  → upload.py (검증·임시파일)
  → process_pdf() [스레드]
      → [0] 문서 요약 생성
      → [1] 목차 페이지 감지
      → [2] 목차 구조 파싱 (또는 요약 기반 목차)
      → [3] 페이지 범위 검증
      → [4] 섹션별 전처리 (PDF→이미지→Markdown→청킹)
  → upload_to_supabase_with_file() [스레드]
      → [Step 0] Storage에 PDF 업로드
      → [Step 1] documents 테이블 등록
      → [Step 2] document_sections 테이블 등록
      → [Step 3] 청크 임베딩 생성
      → [Step 4] document_chunks 테이블 등록
  → 임시파일 삭제 → 200 + stats 반환
```

---

## 1. 프론트엔드 (AdminUploadPage)

1. 사용자가 PDF 선택 + 학교명 입력 후 업로드 버튼 클릭
2. `uploadDocument(file, schoolName)` 호출 → `POST /api/upload/` (FormData: `file`, `school_name`)
3. 응답 대기 중 로그: "📦 모델 초기화 중...", "📝 PDF → Markdown 변환 중..." 등
4. 성공 시 결과 테이블·통계 표시, 실패 시 "❌ 오류: (서버에서 내려준 상세 메시지)" 표시

---

## 2. 백엔드 API (routers/upload.py)

| 순서 | 내용 |
|------|------|
| 1 | **검증** – Content-Type이 PDF인지, 크기 50MB 이하인지 확인 |
| 2 | **임시 파일** – 업로드된 바이트를 `tempfile.NamedTemporaryFile`로 디스크에 저장 (`tmp_path`) |
| 3 | **process_pdf** – `asyncio.to_thread(process_pdf, tmp_path, school_name, None, True)` 호출 (블로킹 방지) |
| 4 | **실패 처리** – `(None, 사유)` 반환 시 그 사유로 예외 → 500 + detail |
| 5 | **upload_to_supabase_with_file** – `asyncio.to_thread(upload_to_supabase_with_file, ...)` 호출 |
| 6 | **실패 처리** – `document_id`가 None이면 "Supabase 업로드 실패" → 500 |
| 7 | **정리** – `finally`에서 임시 파일 `os.unlink` |
| 8 | **응답** – 200 + `{ success, stats, preview }` 반환 |

---

## 3. PDF 처리 (services/pdf_processor.py → process_pdf)

| 단계 | 내용 | 사용 모듈 |
|------|------|-----------|
| **0** | **문서 요약 생성** – 전체(또는 최대 50페이지) 텍스트 추출 후 Gemini LLM으로 요약 | `TOCProcessor.generate_document_summary` |
| **1** | **목차 페이지 감지** – 처음 N페이지 텍스트로 "목차 페이지" 여부 LLM 판별 | `TOCProcessor.detect_toc_pages` |
| **2** | **목차 구조 파싱** – 목차 페이지에서 섹션 제목·페이지 범위 추출. 실패 시 요약 기반으로 섹션 생성 | `TOCProcessor.parse_toc_structure` 또는 `generate_toc_from_summary` |
| **3** | **페이지 범위 검증** – 섹션의 start_page/end_page가 PDF 페이지 수 안에 맞게 보정 | `TOCProcessor.validate_and_fix_sections` |
| **4** | **섹션별 전처리** – 각 섹션을 **병렬**로 처리: PDF 구간 추출 → 페이지를 이미지로 띄움 → Gemini Vision으로 Markdown 변환 → Dual Chunking으로 청크 생성 → FAISS 벡터스토어(메모리) 생성 | `SectionPreprocessor.preprocess_section` (TOCProcessor, VisionProcessor, Chunker 사용) |

**process_pdf 결과**

- 성공: `{ toc_sections, chunks, summary, failed_sections? }` 반환
- 실패: `(None, "실패_사유")` 반환 (예: "요약 기반 목차 생성 실패", "처리된 청크가 없습니다", 예외 메시지 등)

---

## 4. Supabase 업로드 (services/supabase_client.py → SupabaseUploader.upload_to_supabase)

| 순서 | 내용 |
|------|------|
| **Step 0** | PDF를 Supabase Storage 버킷 `document`에 업로드 → `file_url` 획득 |
| **Step 1** | `documents` 테이블에 1행 삽입 (school_name, filename, summary, embedding_summary, file_url, metadata) → `document_id` 획득 |
| **Step 2** | `document_sections` 테이블에 섹션별 행 삽입 (document_id, section_name, page_start, page_end) → `section_map` (페이지범위 → section_id) 생성 |
| **Step 3** | 청크 텍스트 전체에 대해 임베딩 API 호출 (배치) → `embeddings_list` |
| **Step 4** | `document_chunks` 테이블에 청크별 행 삽입 (document_id, section_id, content, raw_data, embedding, page_number, chunk_type) |

성공 시 `document_id` 반환, 실패 시 `None` 반환.

---

## 5. 데이터 흐름 정리

```
PDF 파일 (바이트)
  → 임시 파일 (tmp_path)
  → process_pdf
      → 요약 텍스트 (document_summary)
      → 목차/섹션 리스트 (toc_sections: [{ title, start_page, end_page }, ...])
      → 청크 리스트 (chunks: LangChain Document[], 메타데이터 포함)
  → upload_to_supabase_with_file
      → Storage: PDF 파일 → file_url
      → documents: 1행 (요약·embedding_summary·file_url)
      → document_sections: N행
      → document_chunks: M행 (content, embedding, section_id 등)
  → API 응답: { success, stats: { totalPages, chunksTotal, ... }, preview }
```

---

## 6. 실패 시 동작

- **process_pdf** 실패 → `(None, 사유)` → upload.py에서 해당 사유로 500 반환 → 프론트에 "❌ 오류: (사유)" 표시
- **upload_to_supabase_with_file** 실패 → `None` 반환 → "Supabase 업로드 실패"로 500 반환
- **그 밖의 예외** → main.py 전역 예외 핸들러에서 `detail` 담아 500 JSON 반환

이 문서는 현재 코드 기준 작동 순서만 설명한 것입니다.
