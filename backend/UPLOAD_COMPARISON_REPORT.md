# 업로드 관련 파일 비교 보고서 (임베딩_기반 vs 유니로드)

코드 수정 없이, 발생 가능한 문제만 체계적으로 점검한 결과입니다.

---

## 1. 설정 (Config)

| 항목 | 임베딩_기반 | 유니로드 | 발생 가능 문제 |
|------|-------------|----------|----------------|
| **설정 파일** | `config/settings.py` | `config/embedding_settings.py` + `config/config.py` | 유니로드는 설정이 둘로 나뉨. PDF 업로드 흐름은 `embedding_settings`만 쓰지만, Supabase는 `config.settings`(SUPABASE_URL, SUPABASE_KEY) 사용. |
| **.env 로드** | `load_dotenv(override=True)` (경로 없음 → **CWD 기준**) | `embedding_settings`: `backend/.env` 또는 프로젝트 루트 `.env` | 임베딩_기반은 실행 디렉터리(보통 프로젝트 루트)의 `.env`만 읽음. 유니로드는 backend 또는 루트 둘 다 시도. **유니로드에서 .env를 루트에만 두고 uvicorn을 backend/에서 실행하면**, `config.Settings`는 CWD=backend/의 `.env`를 찾아 **backend/.env가 없으면** SUPABASE_URL 등 누락으로 기동 실패 가능. |
| **모델** | `DEFAULT_LLM_MODEL = "gemini-3-flash-preview"` | 동일하게 `gemini-3-flash-preview` 사용 가능 (env 오버라이드 있음) | 차이 없음. |
| **임베딩 모델** | `DEFAULT_EMBEDDING_MODEL = "models/gemini-embedding-001"` | `"models/text-embedding-004"` | **모델이 다름.** 차원/API 제한이 다르면 임베딩 생성 실패·차원 불일치(768 아님) 가능. 마이그레이션은 768차원 기준. |
| **캐시 경로** | `.cache`, `.cache/toc_sections` (CWD 기준) | `backend/.cache`, `backend/.cache/toc_sections` (절대 경로) | 유니로드는 실행 위치와 무관하게 backend 아래에만 씀. 문제 가능성 낮음. |

**점검 권장:**  
- 유니로드 실행 시 실제 CWD와 `backend/.env` 존재 여부 확인.  
- 임베딩 모델을 임베딩_기반과 맞출지, 768 차원 보장되는지 확인.

---

## 2. toc_processor (목차/요약)

| 항목 | 임베딩_기반 | 유니로드 | 발생 가능 문제 |
|------|-------------|----------|----------------|
| **config** | `import config` (settings.py) | `from config import embedding_settings as config` | 동일한 이름의 config로 접근. GOOGLE_API_KEY는 둘 다 설정에서 세팅. |
| **streamlit** | `import streamlit as st` 사용, `st.warning(...)` (JSON 파싱 오류 시) | 없음 (logger 등으로 대체) | 유니로드에는 영향 없음. |
| **generate_document_summary** | 전체 페이지 텍스트 사용. **try/except 있음** → 실패 시 `""` 반환. | 최대 50페이지·10만 자 제한 + try/except → 실패 시 `""` | 유니로드가 입력 길이 제한으로 토큰 초과 가능성은 더 낮음. |
| **detect_toc_pages / parse_toc_structure** | 구조·로직 동일 | 구조·로직 동일 | 차이 없음. |

**점검 권장:**  
- 요약 단계에서 빈 문자열이 나와도, 목차 감지·요약 기반 목차 생성으로 이어지므로, 실패 원인은 **목차 없음 + 요약 실패** 동시 발생 여부 확인.

---

## 3. vision_processor (PDF → 이미지 → Markdown)

| 항목 | 임베딩_기반 | 유니로드 | 발생 가능 문제 |
|------|-------------|----------|----------------|
| **config** | `import config` | `from config import embedding_settings as config` | 동일. |
| **Vision 모델** | 하드코딩 `"gemini-2.0-flash-exp"` (인자로 model_name 넘기면 그대로 사용) | `os.getenv("GEMINI_VISION_MODEL", "gemini-3-flash-preview")` (인자 없을 때만) | SectionPreprocessor가 model_name을 넘기므로, **실제로는 둘 다 DEFAULT_LLM_MODEL(gemini-3-flash-preview) 사용.** 동일. |
| **API 키** | `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY` 없으면 `ValueError` | 동일 | **키 없으면** VisionProcessor 생성 시점(SectionPreprocessor 생성 시)에 바로 예외. process_pdf 진입 전에 실패. |

**점검 권장:**  
- 500이 “모델 초기화” 직후에 나온다면, **GEMINI_API_KEY / GOOGLE_API_KEY** 미설정 또는 `.env` 미로딩 가능성 우선 확인.

---

## 4. preprocessor (섹션 전처리, 청킹, 메타데이터)

| 항목 | 임베딩_기반 | 유니로드 | 발생 가능 문제 |
|------|-------------|----------|----------------|
| **TOC_SECTIONS_DIR** | `config.TOC_SECTIONS_DIR` (CWD 기준 .cache) | `config.TOC_SECTIONS_DIR` (backend/.cache) | 유니로드는 경로가 고정. 쓰기 권한만 있으면 됨. |
| **청크 메타데이터** | `section_title`, `section_start`, `section_end` 등 | 동일 | Supabase 쪽에서 쓰는 키와 호환. |
| **DEFAULT_EMBEDDING_MODEL** | embedding으로 FAISS/벡터스토어 생성 시 사용 | 동일하게 config에서 참조 | **임베딩 모델이 다르면** (gemini-embedding-001 vs text-embedding-004) 차원·성능 차이 가능. 768 맞는지 확인 필요. |

**점검 권장:**  
- 청크 메타데이터는 양쪽 동일. 문제 시 **chunker 출력**(type, chunk_type 등)과 Supabase `_insert_chunks` 기대값만 맞으면 됨.

---

## 5. Supabase 업로드 (upload_to_supabase, SupabaseUploader)

| 항목 | 임베딩_기반 | 유니로드 | 발생 가능 문제 |
|------|-------------|----------|----------------|
| **진입점** | `database.supabase_client.upload_to_supabase()` (함수) | `services.pdf_processor.upload_to_supabase_with_file()` → `SupabaseUploader().upload_to_supabase()` | 역할은 동일. |
| **Supabase 인증** | `os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY")` + 같은 파일에서 `load_dotenv(override=True)` | `os.getenv(...) or settings.SUPABASE_URL/KEY` (config.Settings) | **유니로드는 Settings 로딩 실패 시** (예: backend/.env 없음) Supabase 접근 전에 앱이 죽을 수 있음. |
| **section_map 키** | `{ section_name: section_id }` (제목 기준) | `{ "page_start_page_end": section_id }` (페이지 범위 기준) | 유니로드가 페이지 범위로 매핑해 **동일 제목 섹션**에도 안전. |
| **embedding_summary** | 리스트 그대로 전달 `summary_embedding` | 문자열 `"[" + ",".join(...) + "]"` 로 전달 | **pgvector 컬럼 타입과 Supabase 클라이언트 규약**에 따라 다름. 유니로드가 문자열로 보내는 것이 해당 마이그레이션/클라이언트와 맞는지 확인 필요. (맞지 않으면 documents 삽입 시 오류.) |
| **document_chunks.embedding** | `"embedding": embedding` (리스트) | `"embedding": embedding_str` (문자열) | 위와 동일. **Supabase Python 클라이언트가 vector(768)에 문자열을 받는지** 확인. |
| **테이블/스키마** | `documents`, `document_sections`, `document_chunks` | `09_create_documents_tables.sql` 과 동일 구조 | 마이그레이션 적용 여부가 중요. **09 미적용이면** 테이블/함수 없어서 삽입·RPC 실패. |

**점검 권장:**  
- **09_create_documents_tables.sql** 적용 여부(같은 DB에 테이블·RPC 존재 여부).  
- **embedding_summary / embedding** 포맷(리스트 vs 문자열)이 사용 중인 Supabase/드라이버와 일치하는지.  
- SUPABASE_URL, SUPABASE_KEY가 실제로 로드되는지(환경 변수 또는 Settings).

---

## 6. 업로드 진입 흐름 (API vs Streamlit)

| 항목 | 임베딩_기반 | 유니로드 | 발생 가능 문제 |
|------|-------------|----------|----------------|
| **진입** | Streamlit UI → `upload_component.process_pdf()` → `upload_to_supabase()` | FastAPI `POST /api/upload/` → `process_pdf()` → `upload_to_supabase_with_file()` | 유니로드는 **비동기 + asyncio.to_thread**. 동기 코드가 블로킹 없이 실행되는지만 확인하면 됨. |
| **on_progress** | Streamlit에서 콜백 전달 가능 | `None` 전달 → 로그는 터미널/print만 | 진행 로그는 서버 로그로만 확인. |
| **임시 파일** | 컴포넌트/스크립트에서 경로 관리 | `tempfile.NamedTemporaryFile(delete=False)` 후 `finally`에서 `os.unlink` | 정리 로직은 유니로드가 명시적. 문제 가능성 낮음. |
| **에러 시** | process_pdf가 None 반환 → UI에서 실패 처리 | None 반환 → `Exception("PDF 처리 결과가 비어있습니다.")` 등 → 500 + detail | 프론트에서 500과 detail을 받도록 이미 수정된 상태면, 동작 차이는 없음. |

**점검 권장:**  
- 500이 나올 때 **백엔드 터미널**에 찍힌 `[process_pdf]` / 전역 예외 로그로, process_pdf 단계에서 None이 나온 건지, Supabase 단계에서 실패한 건지 구분.

---

## 7. 발생 가능 문제 요약 (우선순위)

1. **환경 변수 / .env**
   - **GEMINI_API_KEY**(또는 GOOGLE_API_KEY): 없으면 VisionProcessor 생성 시 ValueError → 즉시 500.
   - **SUPABASE_URL, SUPABASE_KEY**: 유니로드는 `config.Settings`에서도 사용. backend/.env 또는 CWD .env에 없으면 기동 실패 또는 업로드 직후 실패.
   - **.env 위치**: uvicorn 실행 디렉터리가 backend/이면 `config.Settings`는 backend/.env를 찾음. 루트에만 두었다면 backend/.env 복사 또는 루트에서 실행해 CWD 맞추기.

2. **Supabase 스키마**
   - **09_create_documents_tables.sql** 미적용 시 `documents` / `document_sections` / `document_chunks` 또는 `match_document_chunks` 없음 → 삽입/검색 시 오류.

3. **임베딩 모델·차원**
   - 유니로드 `DEFAULT_EMBEDDING_MODEL = "models/text-embedding-004"`, 임베딩_기반은 `"models/gemini-embedding-001"`. 모델별 차원이 768인지, Supabase vector(768)와 일치하는지 확인.

4. **embedding 포맷 (pgvector)**
   - 유니로드는 `embedding_summary` / `embedding`을 **문자열**로 넣음. Supabase 클라이언트/DB가 문자열을 vector로 받는지 확인. 안 되면 삽입 단계에서 예외.

5. **모델명**
   - 둘 다 `gemini-3-flash-preview` 사용하도록 맞춰두면, 지역/할당량/정책만 동일하면 동작은 비슷. 한쪽만 실패하면 키/쿼터/지역 제한 가능성.

6. **section_map / chunk 메타데이터**
   - 유니로드는 페이지 범위로 section_id 매핑, 청크 메타데이터에 section_start/section_end 있음. 구조는 호환. 같은 섹션 제목이 여러 번 나와도 유니로드 방식이 더 안전.

---

## 8. 점검 체크리스트

- [x] `backend/.env` 또는 (uvicorn CWD 기준) `.env`에 `GEMINI_API_KEY` 또는 `GOOGLE_API_KEY` 존재
- [x] 동일 .env에 `SUPABASE_URL`, `SUPABASE_KEY` 존재
- [x] `09_create_documents_tables.sql`이 업로드에 사용하는 Supabase 프로젝트에 적용됨
- [x] 사용 중인 임베딩 모델 출력 차원이 768인지 확인
- [x] Supabase에 embedding을 문자열로 넣는 방식이 현재 스키마/클라이언트와 호환되는지 확인
- [x] 500 발생 시 백엔드 로그에서 `[process_pdf]` 또는 전역 예외 메시지로 실패 단계(요약/목차/Vision/Supabase) 확인

이 문서는 코드 변경 없이 비교·점검 결과만 담았습니다. 수정이 필요하면 위 항목을 기준으로 해당 파일만 바꾸면 됩니다.

---

## 9. 점검 결과 (실행 일자 기준)

### 1) GEMINI_API_KEY / GOOGLE_API_KEY

| 항목 | 결과 |
|------|------|
| **backend/.env 존재** | ✅ 존재함 |
| **루트 .env** | ❌ 없음 (backend/.env만 사용) |
| **backend/.env 내 키 이름** | `GEMINI_API_KEY` 존재. `embedding_settings.py` 로드 시 `GOOGLE_API_KEY`로 복사되므로 LangChain/Gemini 호출에 사용됨. |

**결과:** ✅ 통과. (값 내용은 보안상 확인하지 않음.)

---

### 2) SUPABASE_URL, SUPABASE_KEY

| 항목 | 결과 |
|------|------|
| **동일 .env 내 키** | `SUPABASE_URL`, `SUPABASE_KEY` 둘 다 backend/.env에 정의됨. |

**결과:** ✅ 통과.

---

### 3) 09_create_documents_tables.sql 적용 여부

| 항목 | 결과 |
|------|------|
| **로컬 파일** | ✅ `backend/migrations/09_create_documents_tables.sql` 존재. |
| **Supabase 적용** | ✅ `check_migration_09.py` 실행 결과, `documents`, `document_sections`, `document_chunks` 테이블 모두 존재. |
| **확인 방법** | 아래 "3번 확인 방법" 참고. |

**결과:** ✅ 통과. (업로드에 사용하는 Supabase 프로젝트에 09 마이그레이션 적용됨.)

---

### 4) 임베딩 모델 출력 차원 768

| 항목 | 결과 |
|------|------|
| **설정** | `embedding_settings.DEFAULT_EMBEDDING_MODEL = "models/text-embedding-004"` |
| **문서/검색** | Google Gemini API 문서 및 LangChain 문서 기준, `text-embedding-004`(embedding-001 계열)는 **768차원** 출력. |
| **마이그레이션** | `09_create_documents_tables.sql`에서 `embedding_summary vector(768)`, `embedding vector(768)` 사용. |

**결과:** ✅ 통과. (모델 차원과 스키마 일치.)

---

### 5) Supabase embedding 문자열 형식 호환

| 항목 | 결과 |
|------|------|
| **코드** | `SupabaseUploader._insert_document`에서 `embedding_summary`를 `"[" + ",".join(map(str, summary_embedding)) + "]"` 형태로 전달. `_insert_chunks`에서 `embedding`도 동일한 문자열 형식. |
| **DB** | `vector(768)` 컬럼. PostgreSQL pgvector 확장은 `'[0.1,0.2,...]'` 형태 문자열을 vector로 캐스팅 지원. Supabase Python 클라이언트도 해당 형식을 vector 컬럼에 넣을 수 있음. |

**결과:** ✅ 코드·스키마 기준 호환. (실제 삽입 시 오류가 나면 Supabase 대시보드/로그에서 예외 메시지 확인.)

---

### 6) 500 시 로그로 실패 단계 확인

| 항목 | 결과 |
|------|------|
| **process_pdf 내부** | `services/pdf_processor.py` except 블록에서 `print(f"\n❌ [process_pdf] 오류: {e}\n{tb}\n")` 출력. |
| **전역 예외** | `main.py`에 `@app.exception_handler(Exception)` 등록, `print(f"\n❌ [전역 예외] {exc}\n{traceback.format_exc()}\n")` 출력. |
| **upload 라우터** | `routers/upload.py` except에서 `traceback.print_exc()` 호출. |

**결과:** ✅ 500 발생 시 백엔드 터미널에서 `[process_pdf]` 또는 `[전역 예외]`로 단계 구분 가능.

---

### 점검 요약

| # | 항목 | 상태 |
|---|------|------|
| 1 | GEMINI_API_KEY / GOOGLE_API_KEY | ✅ 통과 |
| 2 | SUPABASE_URL, SUPABASE_KEY | ✅ 통과 |
| 3 | 09 마이그레이션 적용 | ✅ 통과 |
| 4 | 임베딩 768차원 | ✅ 통과 |
| 5 | embedding 문자열 호환 | ✅ 통과 |
| 6 | 500 시 로그 | ✅ 통과 |

**남은 조치:** 없음. (3번은 `check_migration_09.py` 실행으로 확인 완료.)

---

### 3번 확인 방법 (다시 확인할 때)

1. **스크립트로 확인 (권장)**  
   `backend/.env`에 `SUPABASE_URL`, `SUPABASE_KEY`가 있으면:
   ```bash
   cd backend && python3 check_migration_09.py
   ```
   - `documents`, `document_sections`, `document_chunks` 세 테이블이 모두 있으면 "09 마이그레이션 적용된 것으로 보입니다" 출력 후 종료 코드 0.
   - 하나라도 없으면 해당 테이블 이름과 에러 메시지 출력 후 종료 코드 1.

2. **Supabase 대시보드**  
   Supabase → SQL Editor에서 다음 실행:
   ```sql
   SELECT 1 FROM documents LIMIT 1;
   SELECT 1 FROM document_sections LIMIT 1;
   SELECT 1 FROM document_chunks LIMIT 1;
   ```
   세 개 모두 에러 없이 실행되면 적용된 것.

3. **마이그레이션 미적용 시**  
   `backend/run_migration_09.py`에 `DATABASE_URL`(Supabase Connection string) 넣고 실행.  
   Supabase 대시보드 → Project Settings → Database → Connection string (URI) 에서 확인.
