# 유니로드 (Uniroad) 🎓

**대한민국 최고의 입시 데이터 기반 AI 컨설턴트**

멀티에이전트 RAG(Retrieval-Augmented Generation) 시스템을 기반으로 한 대학 입시 상담 AI 서비스입니다.

---

## 📊 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              사용자 (브라우저)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Frontend (React + TypeScript + Vite)                     │
│                              Port: 5173                                      │
│    ChatPage │ AdminPage │ AgentAdminPage │ AuthPage │ TimingDashboard       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │ /api 프록시
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Backend (FastAPI + Python)                            │
│                              Port: 8000                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Multi-Agent System (핵심)                        │   │
│  │  ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐ │   │
│  │  │   Router   │ → │Orchestration│ → │ Sub Agents │ → │   Final    │ │   │
│  │  │   Agent    │   │   Agent    │   │ (대학별/기능)│   │   Agent    │ │   │
│  │  └────────────┘   └────────────┘   └────────────┘   └────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              Score System (환산점수 계산)                            │   │
│  │  서울대 │ 연세대 │ 고려대 │ 경희대 │ 서강대 점수 환산기              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    External Services (외부 서비스)                           │
│      Supabase (PostgreSQL + Vector Search)  │  Google Gemini (AI 모델)      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔥 핵심 기능

### 1. 멀티에이전트 시스템

사용자 질문을 분석하고 최적의 답변을 생성하는 4단계 파이프라인:

| Agent | 역할 | 모델 |
|-------|------|------|
| **Router Agent** | 질문 라우팅 및 적절한 함수 호출 결정 | gemini-2.5-flash-lite |
| **Orchestration Agent** | 질문 분석, 실행 계획(Execution Plan) 및 답변 구조(Answer Structure) 설계 | gemini-2.5-flash-lite |
| **Sub Agents** | 대학별 정보 검색, 성적 분석, 학습 조언 등 전문 에이전트 실행 | gemini-2.5-flash-lite |
| **Final Agent** | Sub Agent 결과를 종합하여 최종 답변 생성 (출처 인용 포함) | gemini-2.5-flash-lite |

**지원 에이전트:**
- 26개 대학 Agent (서울대, 연세대, 고려대, KAIST, POSTECH 등)
- 컨설팅 Agent (합격 가능성 분석, 환산점수 계산)
- 선생님 Agent (학습 계획, 멘탈 관리 조언)

### 2. 정시 환산점수 자동 계산

5개 주요 대학의 2026학년도 정시 환산점수를 실시간으로 계산:

| 대학 | 환산 방식 | 만점 |
|------|----------|------|
| **서울대** | 표준점수 가중 + 탐구 변환 | 1000점 |
| **연세대** | 표준점수/백분위 가중 | 1000점 |
| **고려대** | 표준점수 가중 + 영어 감점 | 1000점 |
| **경희대** | 백분위 기반 + 영어/한국사 감점 | 600점 |
| **서강대** | 표준점수 가중 (국어/수학 선택) | 1000점 |

**지원 성적 입력 형식:**
- 축약형: `11232` (국어/수학/영어/탐구1/탐구2 등급)
- 등급: `국어 1등급`, `수학 2등급`
- 표준점수: `수학 표준점수 140`, `국어 138점`
- 백분위: `국어 백분위 98`

### 3. RAG 기반 정보 검색

Supabase 벡터 DB를 활용한 검색증강생성:

- **문서 업로드**: PDF → Markdown 변환 → 청킹 → 임베딩
- **해시태그 기반 검색**: `#서울대`, `#2026`, `#정시` 등
- **출처 인용**: `<cite>` 태그로 답변의 근거 문서 표시

### 4. 실시간 스트리밍 채팅

- **SSE (Server-Sent Events)** 기반 실시간 응답
- 처리 단계별 상태 표시 (Router → Orchestration → Sub Agents → Final)
- **이미지 분석 지원**: 성적표, 모집요강 등 이미지 첨부 후 질문 가능

---

## 🚀 빠른 시작

### 서버 시작

```bash
./start.sh
```

자동으로:
- 백엔드 가상환경(venv) 생성 및 의존성 설치
- 프론트엔드 node_modules 설치
- 백엔드/프론트엔드 서버 실행 (각각 별도 터미널)

### 서버 종료

```bash
./stop.sh
```

---

## 📍 접속 주소

| 서비스 | URL |
|--------|-----|
| **프론트엔드** | http://localhost:5173 |
| **백엔드 API** | http://localhost:8000 |
| **API 문서 (Swagger)** | http://localhost:8000/docs |

---

## 🛠️ 수동 실행 (필요시)

### 백엔드

```bash
cd backend
source venv/bin/activate  # venv가 없으면: python3 -m venv venv
pip install -r requirements.txt
python main.py
```

### 프론트엔드

```bash
cd frontend
npm install  # 처음 한 번만
npm run dev
```

---

## 📦 기술 스택

### Backend
- **FastAPI** - 고성능 비동기 API 프레임워크
- **Python 3.10+**
- **Google Gemini API** - LLM (gemini-2.5-flash-lite)
- **Supabase** - PostgreSQL + pgvector (벡터 검색)

### Frontend
- **React 18** + **TypeScript**
- **Vite** - 빌드 도구
- **Tailwind CSS** - 스타일링

---

## 🔧 환경 변수 설정

### Backend (`backend/.env`)

```env
GEMINI_API_KEY=your_gemini_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key
SUPABASE_JWT_SECRET=your_jwt_secret
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:5173
```

### Frontend (`frontend/.env`)

```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

---

## 📁 프로젝트 구조

```
유니로드/
├── backend/                    # FastAPI 백엔드
│   ├── main.py                 # 진입점
│   ├── config/                 # 설정 (환경변수, 상수)
│   ├── routers/                # API 라우터
│   │   ├── chat.py             # ⭐ 채팅 API (핵심)
│   │   ├── auth.py             # 인증
│   │   ├── sessions.py         # 세션 관리
│   │   ├── upload.py           # 문서 업로드
│   │   └── documents.py        # 문서 관리
│   ├── services/
│   │   ├── multi_agent/        # ⭐ 멀티에이전트 시스템
│   │   │   ├── router_agent.py      # 질문 라우팅
│   │   │   ├── orchestration_agent.py  # 실행 계획 설계
│   │   │   ├── sub_agents.py        # 전문 에이전트들
│   │   │   ├── final_agent.py       # 최종 답변 생성
│   │   │   └── score_system/        # 환산점수 계산기
│   │   ├── scoring/            # ⭐ 점수 계산 모듈
│   │   │   ├── snu_score_calculator.py   # 서울대
│   │   │   ├── yonsei_score_calculator.py # 연세대
│   │   │   ├── korea_score_calculator.py  # 고려대
│   │   │   ├── khu_score_calculator.py    # 경희대
│   │   │   └── sogang_score_calculator.py # 서강대
│   │   ├── gemini_service.py   # Gemini API 통합
│   │   └── supabase_client.py  # Supabase 클라이언트
│   └── migrations/             # DB 마이그레이션
│
├── frontend/                   # React 프론트엔드
│   ├── src/
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx    # ⭐ 메인 채팅 페이지
│   │   │   ├── AdminPage.tsx   # 문서 관리
│   │   │   └── AuthPage.tsx    # 로그인
│   │   ├── components/
│   │   │   ├── ChatMessage.tsx # 메시지 렌더링
│   │   │   └── ThinkingProcess.tsx # 처리 중 표시
│   │   ├── api/client.ts       # API 클라이언트
│   │   └── contexts/AuthContext.tsx # 인증 상태
│   └── vite.config.ts          # Vite 설정
│
├── start.sh                    # 서버 시작 스크립트
├── stop.sh                     # 서버 종료 스크립트
└── README.md
```

---

## 📝 API 주요 엔드포인트

### 채팅 API

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| POST | `/api/chat/v2/stream` | 스트리밍 채팅 (Main Agent) |
| POST | `/api/chat/v2/stream/with-image` | 이미지 첨부 채팅 |
| POST | `/api/chat/stream` | 스트리밍 채팅 (Legacy) |
| POST | `/api/chat/reset` | 대화 히스토리 초기화 |

### 세션 API

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| GET | `/api/sessions/` | 세션 목록 조회 |
| POST | `/api/sessions/` | 새 세션 생성 |
| GET | `/api/sessions/{id}/messages` | 메시지 목록 |
| DELETE | `/api/sessions/{id}` | 세션 삭제 |

### 문서 API

| 메서드 | 엔드포인트 | 설명 |
|--------|-----------|------|
| POST | `/api/upload/` | PDF 업로드 |
| GET | `/api/documents/` | 문서 목록 |
| DELETE | `/api/documents/{id}` | 문서 삭제 |

---

## 🎯 사용 예시

### 기본 질문
```
"서울대 기계공학부 정시 전형 알려줘"
"2026학년도 경희대 모집요강 보여줘"
```

### 성적 기반 분석
```
"나 11232인데 경희대 갈 수 있어?"
"국어 138, 수학 미적 140, 영어 1등급이야. 어디 갈 수 있어?"
"내 성적으로 SKY 중에 어디 가능해?"
```

### 학습 상담
```
"수학 3등급인데 어떻게 올려?"
"입시 스트레스 받는데 어떻게 해야 해?"
```

---

## 🤝 개발자

서울대학교 개발자의 무료 입시상담 프로젝트

---

## 📄 라이선스

This project is for educational purposes.
