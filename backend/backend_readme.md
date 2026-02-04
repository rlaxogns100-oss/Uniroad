# 유니로드 Backend 기술 문서

> **버전:** 2.0.0  
> **프레임워크:** FastAPI  
> **서비스:** 대학 입시 상담 AI 백엔드

---

## 목차

1. [개요](#1-개요)
2. [프로젝트 구조](#2-프로젝트-구조)
3. [핵심 아키텍처](#3-핵심-아키텍처)
4. [API 엔드포인트](#4-api-엔드포인트)
5. [멀티에이전트 시스템](#5-멀티에이전트-시스템)
6. [서비스 모듈](#6-서비스-모듈)
7. [데이터베이스](#7-데이터베이스)
8. [환경 설정](#8-환경-설정)
9. [실행 방법](#9-실행-방법)

---

## 1. 개요

유니로드 백엔드는 대학 입시 상담을 위한 AI 기반 챗봇 시스템입니다. 주요 특징:

- **멀티에이전트 파이프라인**: Router Agent → Functions → Main Agent
- **RAG (Retrieval-Augmented Generation)**: 벡터 검색 기반 문서 검색
- **성적 환산 시스템**: 대학별 정시 환산점수 계산
- **실시간 스트리밍**: SSE 기반 응답 스트리밍
- **문서 관리**: PDF 업로드, 파싱, 임베딩 생성

### 기술 스택

| 구분 | 기술 |
|------|------|
| 웹 프레임워크 | FastAPI 0.109.0 |
| AI 모델 | Google Gemini (3-flash-preview, 2.5-flash-lite) |
| 데이터베이스 | Supabase (PostgreSQL + pgvector) |
| 인증 | Supabase Auth + JWT |
| 텍스트 처리 | LangChain Text Splitters |

---

## 2. 프로젝트 구조

```
backend/
├── main.py                    # FastAPI 앱 엔트리포인트
├── requirements.txt           # Python 의존성
│
├── config/                    # 설정 모듈
│   ├── __init__.py
│   ├── config.py              # 환경 변수 설정 (Pydantic Settings)
│   ├── constants.py           # 상수 정의 (모델명, 청킹 설정 등)
│   └── logging_config.py      # 로깅 설정
│
├── middleware/                # 미들웨어
│   └── auth.py                # JWT 인증 (Supabase Auth)
│
├── models/                    # Pydantic 모델
│   └── rag_models.py          # RAG 관련 데이터 모델
│
├── routers/                   # API 라우터
│   ├── auth.py                # 인증 API (회원가입, 로그인)
│   ├── chat.py                # 채팅 API (핵심)
│   ├── sessions.py            # 채팅 세션 관리
│   ├── upload.py              # PDF 업로드
│   ├── documents.py           # 문서 CRUD
│   ├── announcements.py       # 공지사항
│   ├── admin_evaluate.py      # 관리자 평가 API
│   ├── admin_logs.py          # 실행 로그 관리
│   └── agent_admin.py         # 에이전트 관리 (비활성화)
│
├── services/                  # 비즈니스 로직
│   ├── supabase_client.py     # Supabase 클라이언트
│   ├── gemini_service.py      # Gemini API 통합
│   │
│   ├── documents/             # 문서 처리 서비스
│   │   ├── __init__.py
│   │   ├── gemini_pdf_service.py    # PDF → Markdown 변환
│   │   ├── classifier_service.py    # 문서 분류/요약
│   │   └── embedding_service.py     # 임베딩 생성/청킹
│   │
│   ├── multi_agent/           # 멀티에이전트 시스템 (핵심)
│   │   ├── __init__.py        # 파이프라인 오케스트레이션
│   │   ├── router_agent.py    # 질문 분석 → 함수 호출 결정
│   │   ├── main_agent.py      # 최종 답변 생성
│   │   ├── functions.py       # RAG 검색 함수
│   │   ├── admin_agent.py     # 품질 평가 에이전트
│   │   ├── agent_prompts.py   # 프롬프트 정의
│   │   └── score_system/      # 성적 환산 시스템
│   │       ├── __init__.py
│   │       ├── converter.py   # 등급/표준점수/백분위 변환
│   │       ├── processor.py   # 성적 정규화
│   │       ├── search_engine.py  # 리버스 서치 (대학 추천)
│   │       ├── calculators/   # 대학별 환산점수 계산기
│   │       │   ├── snu.py     # 서울대
│   │       │   ├── yonsei.py  # 연세대
│   │       │   ├── korea.py   # 고려대
│   │       │   ├── sogang.py  # 서강대
│   │       │   └── khu.py     # 경희대
│   │       └── data/          # 입시 결과 데이터
│   │           └── admission_results/
│   │
│   └── scoring/               # (레거시) 점수 계산 모듈
│
├── utils/                     # 유틸리티
│   ├── __init__.py
│   ├── document_cache.py      # 문서 캐시
│   ├── timing_logger.py       # 상세 타이밍 측정
│   └── token_logger.py        # 토큰 사용량 로깅
│
├── data/                      # 데이터 파일
│   └── prompts/               # 프롬프트 버전 관리
│
└── migrations/                # DB 마이그레이션 SQL
```

---

## 3. 핵심 아키텍처

### 3.1 멀티에이전트 파이프라인

```
┌─────────────────────────────────────────────────────────────┐
│                    사용자 질문 입력                           │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  1️⃣ Router Agent (gemini-2.5-flash-lite)                    │
│  ────────────────────────────────────────────────────────── │
│  • 질문 분석 및 의도 파악                                     │
│  • 함수 호출 결정 (univ, consult)                            │
│  • JSON 형식으로 function_calls 반환                         │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  2️⃣ Functions 실행                                          │
│  ────────────────────────────────────────────────────────── │
│  • univ(): 대학별 입시 정보 RAG 검색                          │
│  • consult(): 성적 환산 및 합격 가능성 분석                    │
│  • Supabase pgvector 벡터 검색                               │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  3️⃣ Main Agent (gemini-3-flash-preview)                     │
│  ────────────────────────────────────────────────────────── │
│  • 검색 결과 + 사용자 질문 기반 최종 답변 생성                  │
│  • 출처 인용 (cite 태그)                                     │
│  • 섹션 구조화 (empathy, analysis, recommendation 등)        │
└─────────────────────────┬───────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    최종 응답 반환                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 사용 가능한 함수

| 함수명 | 설명 | 파라미터 |
|--------|------|----------|
| `univ` | 대학 입시 정보 검색 | `university`, `query` |
| `consult` | 성적 분석 및 합격 가능성 평가 | `scores`, `target_univ`, `target_major`, `target_range` |

### 3.3 Gemini 모델 사용

| 용도 | 모델 | 설명 |
|------|------|------|
| 대화/판단 | `gemini-3-flash-preview` | 고품질 응답 생성 |
| 문서 처리 | `gemini-2.5-flash-lite` | 고속 처리 (Router Agent) |
| 임베딩 | `text-embedding-004` | 768차원 벡터 생성 |

---

## 4. API 엔드포인트

### 4.1 인증 API (`/api/auth`)

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| POST | `/signup` | 회원가입 | - |
| POST | `/signin` | 로그인 | - |
| POST | `/signout` | 로그아웃 | ✅ |
| GET | `/me` | 현재 사용자 정보 | ✅ |
| POST | `/refresh` | 토큰 갱신 | - |

### 4.2 채팅 API (`/api/chat`)

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| POST | `/` | 채팅 메시지 처리 (동기) | - |
| POST | `/v2/stream` | 스트리밍 채팅 | - |
| POST | `/v2/stream/with-image` | 이미지 포함 스트리밍 채팅 | - |
| POST | `/stream` | 스트리밍 채팅 (레거시) | - |
| POST | `/reset` | 세션 히스토리 초기화 | - |
| GET | `/agents` | 가용 에이전트 목록 | - |

**스트리밍 응답 형식 (SSE):**
```json
{"type": "status", "step": "router", "message": "..."}
{"type": "chunk", "text": "응답 텍스트 조각"}
{"type": "done", "response": "전체 응답", "timing": {...}}
```

### 4.3 세션 관리 API (`/api/sessions`)

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| GET | `/` | 세션 목록 | ✅ |
| POST | `/` | 새 세션 생성 | ✅ |
| GET | `/{session_id}/messages` | 메시지 목록 | ✅ |
| PATCH | `/{session_id}` | 세션 제목 수정 | ✅ |
| DELETE | `/{session_id}` | 세션 삭제 | ✅ |

### 4.4 문서 관리 API

**업로드 (`/api/upload`)**
| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/` | PDF 업로드 및 처리 |

**문서 CRUD (`/api/documents`)**
| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/` | 문서 목록 조회 |
| PATCH | `/{document_id}` | 문서 수정 |
| DELETE | `/{document_id}` | 문서 삭제 |

### 4.5 공지사항 API (`/api/announcements`)

| Method | Endpoint | 설명 | 권한 |
|--------|----------|------|------|
| GET | `/` | 공지사항 목록 | 공개 |
| GET | `/{id}` | 공지사항 상세 | 공개 |
| POST | `/` | 공지사항 작성 | 관리자 |
| PUT | `/{id}` | 공지사항 수정 | 관리자 |
| DELETE | `/{id}` | 공지사항 삭제 | 관리자 |

### 4.6 관리자 API (`/api/admin`)

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/evaluate` | Router 출력 평가 |
| POST | `/evaluate-function` | Function 결과 평가 |
| POST | `/evaluate-final` | 최종 답변 평가 |
| GET | `/logs` | 실행 로그 조회 |
| POST | `/logs` | 로그 생성 |
| DELETE | `/logs/{id}` | 로그 삭제 |

---

## 5. 멀티에이전트 시스템

### 5.1 Router Agent (`router_agent.py`)

**역할:** 사용자 질문을 분석하여 적절한 함수 호출을 결정

**입력:**
```
"서울대 기계공학과 정시 어떻게 해?"
```

**출력:**
```json
{
  "function_calls": [
    {
      "function": "univ",
      "params": {
        "university": "서울대학교",
        "query": "2026학년도 기계공학부 정시 모집요강"
      }
    }
  ]
}
```

**성적 분석 예시:**
```json
{
  "function_calls": [
    {
      "function": "consult",
      "params": {
        "scores": {
          "국어": {"type": "등급", "value": 1},
          "수학": {"type": "표준점수", "value": 140},
          "영어": {"type": "등급", "value": 2}
        },
        "target_univ": ["경희대학교"],
        "target_major": [],
        "target_range": ["적정", "안정"]
      }
    }
  ]
}
```

### 5.2 Functions (`functions.py`)

**RAG 검색 프로세스:**
1. 쿼리 임베딩 생성 (Gemini text-embedding-004)
2. Supabase RPC로 벡터 검색 (pgvector)
3. 문서 요약 유사도 계산 (가중 평균)
4. 토큰 기반 청크 선택 (6,000 토큰 한도)

**univ 함수:**
```python
async def univ(university: str, query: str) -> Dict:
    # 1. 벡터 검색 (30개)
    # 2. 문서 정보 조회 (summary, title, URL)
    # 3. 가중 평균 유사도 계산
    # 4. 토큰 기반 필터링
    return {"chunks": [...], "count": 10, "university": "...", "query": "..."}
```

**consult 함수:**
```python
async def consult(scores, target_univ, target_major, target_range) -> Dict:
    # 1. 성적 정규화 (등급/표준점수/백분위 통합)
    # 2. 대학별 환산점수 계산
    # 3. 리버스 서치 (지원 가능 대학 분석)
    return {"chunks": [...], "target_univ": [...], "target_major": [...]}
```

### 5.3 Main Agent (`main_agent.py`)

**역할:** 검색 결과와 사용자 질문을 기반으로 최종 답변 생성

**응답 구조 (섹션 타입):**
- `empathy`: 공감 및 인사
- `fact_check`: 데이터/수치 제공
- `analysis`: 비교/유불리 분석
- `recommendation`: 전략 추천
- `warning`: 리스크 안내
- `encouragement`: 격려
- `next_step`: 다음 행동 지침

**출력 형식:**
```
===SECTION_START:empathy===
지금 성적 때문에 고민이 많으시군요...
===SECTION_END===
===SECTION_START:analysis===
【고려대 경영학과 환산점수 분석】
<cite data-source="2025 고려대 입시결과 12p" data-url="...">작년 컷: 680점</cite>
===SECTION_END===
```

### 5.4 Score System (`score_system/`)

**지원 대학:**
- 서울대학교 (snu.py)
- 연세대학교 (yonsei.py)
- 고려대학교 (korea.py)
- 서강대학교 (sogang.py)
- 경희대학교 (khu.py)

**성적 정규화:**
```python
# 등급 → 백분위 변환
# 표준점수 → 백분위 변환
# 과목별 반영비율 적용
normalize_scores_from_extracted(scores) -> NormalizedScores
```

**환산점수 계산:**
```python
# 대학별 반영비율에 따른 환산
get_univ_converted_sections(scores, target_univ) -> str
```

**리버스 서치:**
```python
# 입결 데이터 기반 지원 가능 대학 추천
run_reverse_search(scores, target_range) -> List[Dict]
```

---

## 6. 서비스 모듈

### 6.1 Supabase Client (`supabase_client.py`)

**주요 기능:**
- 싱글톤 패턴 클라이언트 관리
- PDF Storage 업로드
- 문서 메타데이터 CRUD
- 채팅 로그 저장
- 벡터 검색 (RPC)

```python
class SupabaseService:
    @classmethod
    def get_client(cls) -> Client
    
    @classmethod
    def upload_pdf_to_storage(cls, file_bytes, file_name) -> tuple
    
    @classmethod
    async def insert_document_metadata(cls, ...) -> bool
    
    @classmethod
    async def insert_document_chunk(cls, content, embedding, metadata) -> bool
```

### 6.2 Gemini Service (`gemini_service.py`)

**주요 기능:**
- 텍스트 생성 (Retry 로직 포함)
- Tool 기반 대화
- 이미지 분석 (멀티모달)
- 문서 정보 추출

```python
class GeminiService:
    async def generate(prompt, system_instruction) -> str
    async def chat_with_tools(messages, tools) -> Dict
    async def generate_with_image(prompt, image_data, mime_type) -> str
    async def extract_info_from_documents(query, documents) -> str
```

### 6.3 Document Services (`services/documents/`)

**GeminiPDFService:**
- PDF → Markdown 변환
- 페이지별 처리

**ClassifierService:**
- 문서 요약 생성
- 출처 자동 추출
- 해시태그 추출

**EmbeddingService:**
- 텍스트 청킹 (RecursiveCharacterTextSplitter)
- Gemini 임베딩 생성 (병렬 처리)

```python
# 청킹 설정
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
EMBEDDING_DIMENSION = 768
```

---

## 7. 데이터베이스

### 7.1 테이블 구조

**documents_metadata**
| 컬럼 | 타입 | 설명 |
|------|------|------|
| file_name | TEXT | 원본 파일명 (PK) |
| storage_file_name | TEXT | Storage UUID 파일명 |
| title | TEXT | 문서 제목 |
| source | TEXT | 출처 |
| summary | TEXT | 요약 |
| total_pages | INT | 총 페이지 |
| total_chunks | INT | 총 청크 수 |
| file_url | TEXT | Storage URL |
| hashtags | TEXT[] | 해시태그 배열 |
| created_at | TIMESTAMP | 생성일시 |

**policy_documents (청크)**
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | SERIAL | PK |
| content | TEXT | 청크 내용 |
| embedding | VECTOR(768) | 임베딩 벡터 |
| metadata | JSONB | 메타데이터 |

**chat_sessions**
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| user_id | UUID | FK (auth.users) |
| title | TEXT | 세션 제목 |
| created_at | TIMESTAMP | 생성일시 |
| updated_at | TIMESTAMP | 수정일시 |

**chat_messages**
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| session_id | UUID | FK (chat_sessions) |
| role | TEXT | user / assistant |
| content | TEXT | 메시지 내용 |
| created_at | TIMESTAMP | 생성일시 |

**announcements**
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | UUID | PK |
| title | TEXT | 제목 |
| content | TEXT | 내용 |
| author_email | TEXT | 작성자 |
| is_pinned | BOOL | 고정 여부 |
| created_at | TIMESTAMP | 생성일시 |

### 7.2 RPC 함수

**match_document_chunks:**
```sql
CREATE FUNCTION match_document_chunks(
  filter_school_name TEXT,
  filter_section_id TEXT,
  match_count INT,
  match_threshold FLOAT,
  query_embedding VECTOR(768)
) RETURNS TABLE(...)
```

---

## 8. 환경 설정

### 8.1 환경 변수 (.env)

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_KEY=your-supabase-anon-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Google Gemini
GEMINI_API_KEY=your-gemini-api-key

# Server
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:5173

# Documents (선택)
SCORE_CONVERSION_GUIDE_URL=https://...
```

### 8.2 상수 설정 (`config/constants.py`)

```python
# 파일 업로드
MAX_FILE_SIZE_MB = 50

# 텍스트 청킹
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

# 임베딩
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMENSION = 768
BATCH_SIZE = 5

# Gemini 모델
GEMINI_FLASH_MODEL = "gemini-3-flash-preview"
GEMINI_LITE_MODEL = "gemini-2.5-flash-lite"
```

---

## 9. 실행 방법

### 9.1 의존성 설치

```bash
cd backend
pip install -r requirements.txt
```

### 9.2 환경 변수 설정

```bash
cp .env.example .env
# .env 파일 편집
```

### 9.3 서버 실행

**개발 모드:**
```bash
python main.py
# 또는
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**프로덕션:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 9.4 서버 시작 시 초기화

서버 시작 시 자동으로 다음 항목이 초기화됩니다:
1. Supabase 연결 Warm-up
2. RAGFunctions 싱글톤 초기화
3. RouterAgent 초기화
4. MainAgent 초기화

### 9.5 API 문서

서버 실행 후 접속:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## 부록: 파일별 상세 설명

### A. 라우터 파일

| 파일 | 줄 수 | 핵심 기능 |
|------|-------|----------|
| `chat.py` | ~1,400 | 채팅 API, 스트리밍, 이미지 분석 |
| `auth.py` | ~160 | 회원가입/로그인/JWT |
| `sessions.py` | ~300 | 채팅 세션 CRUD |
| `upload.py` | ~200 | PDF 업로드/처리 파이프라인 |
| `documents.py` | ~60 | 문서 메타데이터 CRUD |
| `announcements.py` | ~170 | 공지사항 CRUD |
| `admin_evaluate.py` | ~140 | LLM 평가 API |
| `admin_logs.py` | ~350 | 실행 로그 CRUD |

### B. 서비스 파일

| 파일 | 핵심 기능 |
|------|----------|
| `supabase_client.py` | DB 클라이언트, Storage, CRUD |
| `gemini_service.py` | Gemini API 통합, 멀티모달 |
| `multi_agent/__init__.py` | 파이프라인 오케스트레이션 |
| `multi_agent/router_agent.py` | 질문 분석, 함수 결정 |
| `multi_agent/main_agent.py` | 최종 답변 생성 |
| `multi_agent/functions.py` | RAG 검색, 성적 분석 |
| `multi_agent/admin_agent.py` | 품질 평가 |

### C. 유틸리티

| 파일 | 기능 |
|------|------|
| `timing_logger.py` | 초상세 타이밍 측정 |
| `token_logger.py` | 토큰 사용량 추적 |
| `document_cache.py` | 문서 캐싱 |

---

*문서 최종 업데이트: 2026년 1월*
