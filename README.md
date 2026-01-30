# 유니로드 (Uniroad)

대한민국 최고의 입시 데이터 기반 AI 컨설턴트

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

모든 실행 중인 서버를 안전하게 종료합니다.

## 📍 접속 주소

- **프론트엔드**: http://localhost:5173
- **백엔드 API**: http://localhost:8000
- **API 문서**: http://localhost:8000/docs

## 🛠️ 수동 실행 (필요시)

### 백엔드

```bash
cd backend
source venv/bin/activate  # venv가 없으면: python3 -m venv venv
python main.py
```

### 프론트엔드

```bash
cd frontend
npm install  # 처음 한 번만
npm run dev
```

## 📦 기술 스택

### Backend
- FastAPI
- Python 3.10+
- Google Gemini API
- Supabase (Database + Vector Search)

### Frontend
- React + TypeScript
- Vite
- Tailwind CSS

## 🔧 환경 변수 설정

### Backend (`backend/.env`)

```env
GEMINI_API_KEY=your_key
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
```

### Frontend (`frontend/.env`)

```env
VITE_API_URL=http://localhost:8000
```

## 📝 주요 기능

- 🎯 성적 기반 대학 추천
- 📊 환산점수 자동 계산
- 🏫 대학별 입시 정보 검색
- 💬 AI 채팅 상담
- 📈 실시간 합격 가능성 분석

## 🤝 개발자

서울대학교 개발자의 무료 입시상담 프로젝트
