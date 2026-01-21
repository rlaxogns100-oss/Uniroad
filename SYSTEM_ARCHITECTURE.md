# 🏗️ UniZ (유니로드) 시스템 아키텍처

**대학 입시 상담 Multi-Agent AI 시스템**  
Version 2.0.0 | 최종 업데이트: 2026-01-20

---

## 📋 목차

1. [시스템 개요](#시스템-개요)
2. [핵심 아키텍처](#핵심-아키텍처)
3. [Multi-Agent 시스템](#multi-agent-시스템)
4. [데이터 플로우](#데이터-플로우)
5. [기술 스택](#기술-스택)
6. [컴포넌트 상세](#컴포넌트-상세)
7. [배포 아키텍처](#배포-아키텍처)

---

## 🎯 시스템 개요

### 프로젝트 이름
**UniZ (유니로드)** - 대학 입시 상담 AI 챗봇

### 핵심 목적
- **정확한 정보 제공**: 공식 대학 문서 기반 RAG 시스템
- **개인화된 상담**: Multi-Agent 시스템으로 맞춤형 답변
- **실시간 분석**: 학생 성적 기반 합격 가능성 분석

### 주요 특징
- ✅ **7개 전문 AI Agent** 협업 시스템
- ✅ **RAG 기반** 정확한 정보 검색
- ✅ **Gemini 2.0 Flash** 최신 AI 모델
- ✅ **실시간 스트리밍** 답변 생성
- ✅ **Supabase** 벡터 데이터베이스

---

## 🏗️ 핵심 아키텍처

### 전체 시스템 다이어그램

```
┌─────────────────────────────────────────────────────────────────┐
│                          사용자 (학생/학부모)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (React + TypeScript)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  ChatPage    │  │  AdminPage   │  │ AgentAdmin   │          │
│  │  (실시간채팅)  │  │ (문서관리)    │  │ (프롬프트관리)│          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                   │
│  - Vite Build System                                             │
│  - TailwindCSS Styling                                           │
│  - Axios API Client                                              │
│  - React Router                                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP/WebSocket
                             │ (CORS 설정)
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                            │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    API Routers                           │   │
│  │  - /api/chat        (멀티에이전트 파이프라인)             │   │
│  │  - /api/upload      (문서 업로드 & 처리)                 │   │
│  │  - /api/documents   (문서 조회/삭제)                     │   │
│  │  - /api/agent       (Agent 프롬프트 관리)                │   │
│  └─────────────────────────────────────────────────────────┘   │
│                             ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │            Multi-Agent Orchestration System              │   │
│  │                                                           │   │
│  │   ┌──────────────────────────────────────────────┐      │   │
│  │   │   🎯 Orchestration Agent (지휘자)            │      │   │
│  │   │   - 질문 분석 및 의도 파악                   │      │   │
│  │   │   - Sub Agent 선택 (Execution Plan)         │      │   │
│  │   │   - 답변 구조 설계 (Answer Structure)       │      │   │
│  │   │   - 대화 히스토리 관리                       │      │   │
│  │   └──────────────────────────────────────────────┘      │   │
│  │                             ↓                             │   │
│  │   ┌──────────────────────────────────────────────┐      │   │
│  │   │         Sub Agents (전문 실행자들)            │      │   │
│  │   │                                               │      │   │
│  │   │  🏫 대학별 Agent (5개)                       │      │   │
│  │   │     - 서울대 Agent                           │      │   │
│  │   │     - 연세대 Agent                           │      │   │
│  │   │     - 고려대 Agent                           │      │   │
│  │   │     - 성균관대 Agent                         │      │   │
│  │   │     - 경희대 Agent                           │      │   │
│  │   │                                               │      │   │
│  │   │  💼 컨설팅 Agent                             │      │   │
│  │   │     - 합격 데이터 분석                       │      │   │
│  │   │     - 입결 비교                              │      │   │
│  │   │     - 점수 환산                              │      │   │
│  │   │     - 대학 추천                              │      │   │
│  │   │                                               │      │   │
│  │   │  👨‍🏫 선생님 Agent                             │      │   │
│  │   │     - 학습 계획 수립                         │      │   │
│  │   │     - 멘탈 관리 조언                         │      │   │
│  │   │     - 목표 설정                              │      │   │
│  │   └──────────────────────────────────────────────┘      │   │
│  │                             ↓                             │   │
│  │   ┌──────────────────────────────────────────────┐      │   │
│  │   │   ✅ Final Agent (조립자)                    │      │   │
│  │   │   - Sub Agent 결과 통합                     │      │   │
│  │   │   - 최종 답변 생성                          │      │   │
│  │   │   - 출처 표시 (<cite> 태그)                │      │   │
│  │   │   - 마크다운 포맷팅                         │      │   │
│  │   └──────────────────────────────────────────────┘      │   │
│  └─────────────────────────────────────────────────────────┘   │
│                             ↓                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                      Services Layer                       │   │
│  │                                                           │   │
│  │  📚 RAG Service                                          │   │
│  │     - 벡터 검색 (Supabase pgvector)                     │   │
│  │     - 문서 필터링 & 랭킹                                │   │
│  │     - 키워드 매칭                                        │   │
│  │                                                           │   │
│  │  🤖 Gemini Service                                       │   │
│  │     - Gemini 2.0 Flash API                              │   │
│  │     - Gemini 1.5 Pro (PDF 분석)                         │   │
│  │     - 스트리밍 응답                                      │   │
│  │                                                           │   │
│  │  📄 PDF Service                                          │   │
│  │     - PDF → Markdown 변환                               │   │
│  │     - 문서 자동 분류                                     │   │
│  │     - 해시태그 추출                                      │   │
│  │                                                           │   │
│  │  🔐 Supabase Client                                      │   │
│  │     - PostgreSQL 연결                                   │   │
│  │     - 벡터 검색 (match_documents)                       │   │
│  │     - 문서 CRUD                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────────┬────────────────────────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Gemini API  │    │  Supabase    │    │   Storage    │
│  (Google)    │    │  (PostgreSQL │    │   (S3/       │
│              │    │  + pgvector) │    │   Supabase)  │
│ - 2.0 Flash  │    │              │    │              │
│ - 1.5 Pro    │    │ - RAG DB     │    │ - PDF Files  │
└──────────────┘    │ - Metadata   │    └──────────────┘
                    │ - Chat Logs  │
                    └──────────────┘
```

---

## 🤖 Multi-Agent 시스템

### Agent 협업 파이프라인

```
사용자 질문
    ↓
┌─────────────────────────────────────────────────────────────┐
│  1️⃣ Orchestration Agent (지휘자)                            │
│                                                              │
│  입력: 사용자 질문 + 대화 히스토리                           │
│  처리:                                                       │
│   - 질문 의도 분석                                          │
│   - 필요한 정보 유형 파악                                   │
│   - 적절한 Sub Agent 선택                                   │
│                                                              │
│  출력:                                                       │
│   - Execution Plan (어떤 Agent를 호출할지)                 │
│   - Answer Structure (답변 구조 설계도)                    │
│                                                              │
│  예시:                                                       │
│  {                                                           │
│    "execution_plan": {                                       │
│      "agents": ["서울대 agent", "컨설팅 agent"],            │
│      "order": "parallel",                                    │
│      "queries": {                                            │
│        "서울대 agent": "2025학년도 정시 모집요강...",       │
│        "컨설팅 agent": "수학 4등급으로 합격 가능성..."     │
│      }                                                        │
│    },                                                         │
│    "answer_structure": {                                     │
│      "sections": [                                           │
│        "1. 서울대 정시 전형 정보",                          │
│        "2. 수학 4등급 합격 가능성 분석",                    │
│        "3. 보완 방법 제안"                                  │
│      ]                                                        │
│    }                                                          │
│  }                                                            │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  2️⃣ Sub Agents 병렬 실행                                     │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                │
│  │ 서울대 Agent     │  │ 컨설팅 Agent     │                │
│  │                  │  │                  │                │
│  │ 🔍 Supabase 검색 │  │ 📊 입결 데이터   │                │
│  │ - #서울대 해시태그│  │ - Mock DB 조회   │                │
│  │ - 요약 필터링    │  │ - 합격선 계산    │                │
│  │ - 전체 내용 로드 │  │ - 확률 분석      │                │
│  │ - Gemini 분석    │  │ - Gemini 해석    │                │
│  │                  │  │                  │                │
│  │ 📤 출력:         │  │ 📤 출력:         │                │
│  │ {                │  │ {                │                │
│  │   "answer": "...",│  │   "answer": "...",│                │
│  │   "sources": [...],│  │   "data": {...}   │                │
│  │   "raw_documents":│  │ }                │                │
│  │      [...]        │  │                  │                │
│  │ }                │  │                  │                │
│  └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────────┐
│  3️⃣ Final Agent (조립자)                                     │
│                                                              │
│  입력:                                                       │
│   - Answer Structure (설계도)                               │
│   - Sub Agent Results (재료들)                              │
│   - 사용자 질문                                             │
│                                                              │
│  처리:                                                       │
│   1. Answer Structure 각 섹션별로 적절한 재료 선택         │
│   2. 섹션별로 답변 생성                                     │
│   3. 출처 표시 (<cite> 태그)                               │
│   4. 마크다운 포맷팅 (【】 볼드)                            │
│   5. 전체 답변 통합                                         │
│                                                              │
│  출력:                                                       │
│  【서울대 정시 전형 정보】                                   │
│  2025학년도 서울대학교 정시모집은...<cite>서울대모집요강</cite>│
│                                                              │
│  【수학 4등급 합격 가능성】                                  │
│  현재 수학 4등급으로는...<cite>입시결과</cite>              │
│                                                              │
│  【보완 방법 제안】                                          │
│  추천드리는 전략은...                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
사용자에게 최종 답변 전달 (스트리밍)
```

### Agent별 역할 상세

#### 🎯 Orchestration Agent
- **역할**: 전체 파이프라인 지휘자
- **모델**: Gemini 2.0 Flash
- **입력**: 사용자 질문 + 대화 히스토리
- **출력**: 
  - `execution_plan`: 어떤 Agent를 호출할지
  - `answer_structure`: 답변을 어떻게 구성할지
- **특징**:
  - 프롬프트 동적 수정 가능 (Agent Admin 페이지)
  - 대화 컨텍스트 관리
  - 병렬/순차 실행 결정

#### 🏫 University Agents (5개)
- **역할**: 각 대학별 입시 정보 검색
- **대학**: 서울대, 연세대, 고려대, 성균관대, 경희대
- **검색 로직**:
  ```
  1. Supabase에서 #{대학명} 해시태그로 문서 검색
  2. 요약본(500자) 분석으로 관련성 평가
  3. 적합한 문서의 전체 내용 로드
  4. Gemini로 정보 추출
  5. 출처와 함께 반환
  ```
- **출력**:
  ```json
  {
    "answer": "검색된 정보",
    "sources": ["문서 제목1", "문서 제목2"],
    "raw_documents": [
      {"title": "...", "content": "...", "url": "..."}
    ]
  }
  ```

#### 💼 Consulting Agent
- **역할**: 입시 데이터 분석 및 컨설팅
- **기능**:
  - 5개 대학 입시 결과 비교
  - 학생 성적 기반 합격 가능성 평가
  - 정시 점수 환산 (표준점수/백분위)
  - 대학 추천
- **데이터 소스**: Mock Database (추후 실제 DB 연동)
- **분석 항목**:
  - 수시 입결: 내신 등급 기반
  - 정시 입결: 백분위 기반
  - 학과별 경쟁률
  - 합격선 예측

#### 👨‍🏫 Teacher Agent
- **역할**: 학습 전략 및 멘탈 관리
- **기능**:
  - 현실적 목표 설정
  - 공부 계획 수립
  - 과목별 학습 전략
  - 멘탈 관리 조언
  - 동기 부여
- **특징**: 데이터 조회 없이 Gemini의 일반 지식 활용

#### ✅ Final Agent
- **역할**: 최종 답변 조립
- **입력**:
  - Answer Structure (설계도)
  - Sub Agent Results (재료)
- **처리**:
  1. 섹션별로 적절한 재료 선택
  2. 자연스러운 답변 생성
  3. 출처 표시 (`<cite>태그</cite>`)
  4. 마크다운 포맷팅 (`【제목】`)
- **특징**:
  - 중복 제거
  - 일관성 유지
  - 가독성 최적화

---

## 📊 데이터 플로우

### 채팅 요청 처리 흐름

```
1. 사용자가 질문 입력
   ↓
2. Frontend (ChatPage)
   - axios.post('/api/chat', { message, session_id })
   ↓
3. Backend Router (/api/chat)
   - 요청 검증
   - 세션 히스토리 로드
   ↓
4. Orchestration Agent 실행
   - 질문 분석
   - Execution Plan 생성
   - Answer Structure 생성
   ↓
5. Sub Agents 병렬 실행
   - 각 Agent별 쿼리 실행
   - 결과 수집
   ↓
6. Final Agent 실행
   - 결과 통합
   - 최종 답변 생성
   ↓
7. 응답 반환
   - 스트리밍 방식 (실시간)
   - 로그 포함
   ↓
8. Frontend 렌더링
   - 마크다운 파싱
   - 출처 링크 표시
```

### 문서 업로드 처리 흐름

```
1. 관리자가 PDF 업로드 (AdminPage)
   ↓
2. Frontend
   - FormData 생성 (file, title, source)
   - axios.post('/api/upload', formData)
   ↓
3. Backend Router (/api/upload)
   - 파일 검증 (타입, 크기)
   - 임시 저장
   ↓
4. Gemini PDF Service
   - Gemini 1.5 Pro로 PDF 분석
   - Markdown 변환
   - 내용 추출
   ↓
5. AI 문서 분류
   - Gemini로 카테고리 판단
   - 해시태그 추출 (예: #서울대, #정시)
   - 요약 생성 (500자)
   ↓
6. 텍스트 청킹
   - LangChain RecursiveCharacterTextSplitter
   - chunk_size: 1200
   - overlap: 200
   ↓
7. 임베딩 생성
   - OpenAI text-embedding-3-small
   - 1536차원 벡터
   ↓
8. Supabase 저장
   - policy_documents 테이블
   - content, embedding, metadata 저장
   ↓
9. 응답 반환
   - 처리 결과
   - 통계 정보
```

---

## 🛠 기술 스택

### Frontend

| 카테고리 | 기술 | 버전 | 용도 |
|---------|------|------|------|
| **프레임워크** | React | 18.x | UI 라이브러리 |
| **언어** | TypeScript | 5.x | 타입 안정성 |
| **빌드** | Vite | 5.x | 개발 서버 & 빌드 |
| **스타일** | TailwindCSS | 3.x | 유틸리티 CSS |
| **라우팅** | React Router | 6.x | SPA 라우팅 |
| **HTTP** | Axios | 1.x | API 통신 |
| **마크다운** | react-markdown | 9.x | 마크다운 렌더링 |

### Backend

| 카테고리 | 기술 | 버전 | 용도 |
|---------|------|------|------|
| **프레임워크** | FastAPI | 0.109.x | 웹 프레임워크 |
| **언어** | Python | 3.9+ | 백엔드 언어 |
| **서버** | Uvicorn | 0.27.x | ASGI 서버 |
| **AI** | Gemini 2.0 Flash | Latest | 주력 LLM |
| **AI** | Gemini 1.5 Pro | Latest | PDF 분석 |
| **임베딩** | OpenAI | Latest | 벡터 임베딩 |
| **DB** | Supabase | Latest | PostgreSQL + pgvector |
| **PDF** | Gemini Vision | Latest | PDF 처리 |

### Infrastructure

| 카테고리 | 기술 | 용도 |
|---------|------|------|
| **데이터베이스** | PostgreSQL 15 | 메인 DB |
| **벡터 DB** | pgvector | 벡터 검색 |
| **스토리지** | Supabase Storage | 파일 저장 |
| **배포** | AWS EC2 | 서버 호스팅 |
| **프록시** | Nginx | 리버스 프록시 |

---

## 🔧 컴포넌트 상세

### Backend Services

#### 1. Multi-Agent Module (`services/multi_agent/`)

**orchestration_agent.py**
```python
class OrchestrationAgent:
    """질문 분석 및 에이전트 선택"""
    
    def analyze_question(self, question: str, history: List) -> Dict:
        """
        Returns:
        {
            "execution_plan": {
                "agents": ["서울대 agent", ...],
                "queries": {"서울대 agent": "..."} 
            },
            "answer_structure": {
                "sections": ["1. ...", "2. ..."]
            }
        }
        """
```

**sub_agents.py**
```python
class UniversityAgent(SubAgentBase):
    """대학별 정보 검색 Agent"""
    
    async def execute(self, query: str) -> Dict:
        """
        1. 해시태그로 문서 검색
        2. 요약본 필터링
        3. 전체 내용 분석
        4. 결과 반환
        """

class ConsultingAgent(SubAgentBase):
    """입시 데이터 분석 Agent"""
    
    async def execute(self, query: str) -> Dict:
        """
        1. 성적 정보 파싱
        2. DB에서 입결 조회
        3. 합격 가능성 계산
        4. 분석 결과 반환
        """

class TeacherAgent(SubAgentBase):
    """학습 전략 조언 Agent"""
    
    async def execute(self, query: str) -> Dict:
        """
        1. 학생 상황 파악
        2. 학습 계획 수립
        3. 조언 생성
        """
```

**final_agent.py**
```python
class FinalAgent:
    """최종 답변 조립"""
    
    def assemble_answer(
        self, 
        answer_structure: Dict,
        sub_results: Dict,
        question: str
    ) -> str:
        """
        1. 섹션별로 재료 선택
        2. 답변 생성
        3. 출처 표시
        4. 포맷팅
        """
```

#### 2. RAG Service

**supabase_client.py**
```python
class SupabaseService:
    """Supabase 연동"""
    
    def search_documents(
        self,
        query: str,
        filters: Dict = None
    ) -> List[Dict]:
        """벡터 검색"""
        
    def insert_document(
        self,
        content: str,
        embedding: List[float],
        metadata: Dict
    ) -> str:
        """문서 저장"""
```

#### 3. Gemini Service

**gemini_service.py**
```python
class GeminiService:
    """Gemini API 연동"""
    
    def generate(
        self,
        prompt: str,
        system_prompt: str = None,
        stream: bool = False
    ) -> str:
        """텍스트 생성"""
        
    def analyze_pdf(
        self,
        pdf_path: str
    ) -> Dict:
        """PDF 분석 (Vision API)"""
```

### Frontend Components

#### Pages

**ChatPage.tsx**
- 실시간 채팅 인터페이스
- 메시지 스트리밍
- 마크다운 렌더링
- 출처 표시

**AdminPage.tsx**
- PDF 업로드
- 문서 목록 관리
- 처리 상태 표시

**AgentAdminPage.tsx**
- Agent 프롬프트 관리
- 버전 관리
- 실시간 테스트

#### Components

**ChatMessage.tsx**
- 메시지 렌더링
- 마크다운 파싱
- 출처 링크
- 타이밍 표시

**AgentPanel.tsx**
- Agent 상태 표시
- 로그 뷰어
- 디버그 정보

---

## 🌐 배포 아키텍처

### Production 환경

```
                        Internet
                           │
                           ↓
                    ┌──────────────┐
                    │  CloudFlare  │
                    │  (CDN/WAF)   │
                    └──────┬───────┘
                           │
                           ↓
┌──────────────────────────────────────────────────────┐
│              AWS EC2 (Ubuntu 22.04)                   │
│                                                        │
│  ┌──────────────────────────────────────────────┐   │
│  │             Nginx (Reverse Proxy)             │   │
│  │  - SSL 인증서 (Let's Encrypt)                │   │
│  │  - HTTPS 리다이렉트                          │   │
│  │  - Gzip 압축                                 │   │
│  │  - Rate Limiting                             │   │
│  └──────┬─────────────────────┬─────────────────┘   │
│         │                     │                       │
│         ↓                     ↓                       │
│  ┌─────────────┐      ┌─────────────┐               │
│  │  Frontend   │      │  Backend    │               │
│  │  (Static)   │      │  (Uvicorn)  │               │
│  │  Port: 80   │      │  Port: 8000 │               │
│  └─────────────┘      └──────┬──────┘               │
└─────────────────────────────┼────────────────────────┘
                               │
                ┌──────────────┼──────────────┐
                ↓              ↓              ↓
        ┌──────────┐   ┌──────────┐  ┌──────────┐
        │  Gemini  │   │ Supabase │  │  OpenAI  │
        │   API    │   │  (Cloud) │  │   API    │
        └──────────┘   └──────────┘  └──────────┘
```

### Development 환경

```
┌──────────────────────────────────────────────┐
│         Local Machine (macOS/Windows)         │
│                                                │
│  Terminal 1:                                  │
│  cd backend && python main.py                │
│  → http://localhost:8000                     │
│                                                │
│  Terminal 2:                                  │
│  cd frontend && npm run dev                  │
│  → http://localhost:5173                     │
│                                                │
│  Vite Proxy:                                  │
│  /api/* → http://localhost:8000/api/*        │
└──────────────────────────────────────────────┘
```

---

## 📈 성능 지표

### 응답 시간

| 작업 | 평균 시간 | 설명 |
|-----|---------|------|
| **Orchestration** | 2-3초 | 질문 분석 + Plan 생성 |
| **Sub Agent (대학)** | 3-5초 | DB 검색 + 분석 |
| **Sub Agent (컨설팅)** | 2-3초 | 데이터 조회 + 계산 |
| **Final Agent** | 5-8초 | 답변 조립 + 생성 |
| **총 응답 시간** | 10-20초 | 전체 파이프라인 |

### 데이터 처리

| 항목 | 수치 | 설명 |
|-----|------|------|
| **PDF 업로드** | 30-60초 | 10-50페이지 기준 |
| **임베딩 차원** | 1536 | OpenAI embedding |
| **청크 크기** | 1200자 | LangChain 기본 |
| **청크 오버랩** | 200자 | 문맥 유지 |
| **동시 검색** | 병렬 | 여러 Agent 동시 실행 |

---

## 🔐 보안 & 인증

### API 키 관리
```env
# backend/.env
GEMINI_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
SUPABASE_URL=your_url_here
SUPABASE_KEY=your_key_here
```

### CORS 설정
```python
# backend/main.py
allow_origins=[
    "http://localhost:5173",    # 개발
    "http://3.107.178.26",     # 프로덕션
]
```

### 데이터 보호
- PDF 파일은 처리 후 삭제
- 세션 데이터는 메모리에만 저장
- API 키는 환경 변수로 관리
- Supabase RLS (Row Level Security) 활용

---

## 🚀 확장 계획

### Phase 1 (현재)
- ✅ Multi-Agent 시스템 구축
- ✅ 5개 대학 정보 검색
- ✅ 기본 컨설팅 기능
- ✅ 프롬프트 동적 관리

### Phase 2 (진행 중)
- 🔄 실제 입시 데이터 연동
- 🔄 사용자 인증 시스템
- 🔄 대화 히스토리 영구 저장
- 🔄 성능 최적화

### Phase 3 (계획)
- 📋 더 많은 대학 추가
- 📋 모바일 앱 개발
- 📋 실시간 알림 기능
- 📋 대시보드 분석

---

## 📞 기술 지원

### 문서
- [README.md](./README.md) - 빠른 시작 가이드
- [PROJECT-DOCUMENTATION.md](./PROJECT-DOCUMENTATION.md) - 상세 문서
- [CHAT_ALGORITHM_DETAIL.md](./CHAT_ALGORITHM_DETAIL.md) - RAG 알고리즘

### 개발 환경
```bash
# 백엔드 로그
tail -f /tmp/backend_*.log

# API 문서
open http://localhost:8000/docs

# 프론트엔드 개발자 도구
# Chrome DevTools → Network/Console
```

---

## 📝 버전 히스토리

### v2.0.0 (2026-01-20)
- Multi-Agent 시스템 도입
- Orchestration → Sub Agents → Final 파이프라인
- Gemini 2.0 Flash 적용
- Agent 프롬프트 동적 관리

### v1.5.0 (2026-01-13)
- RAG 시스템 개선 (키워드 기반)
- Supabase 벡터 검색
- 문서 자동 분류

### v1.0.0 (2026-01-01)
- 초기 MVP 버전
- 기본 채팅 기능
- PDF 업로드

---

**🎉 UniZ - 대학 입시의 모든 것을 하나로!**

*Made with ❤️ by UniZ Team*
