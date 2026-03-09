# 유니로드 develop_7 설정 가이드

이 폴더는 [Uniroad develop_7](https://github.com/rlaxogns100-oss/Uniroad/tree/develop_7) 브랜치 기준입니다.

## 1. 백엔드

### 의존성 설치

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 환경 변수

- `backend/.env.example`을 복사해 `backend/.env`를 만들고 값을 채웁니다.
- 필수: `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_JWT_SECRET`

**참고:** 현재 develop_7 백엔드는 `routers`만 포함되어 있습니다. 실제 서버를 띄우려면 `config`, `services`, `middleware`, `utils` 등이 필요하므로, 전체 백엔드가 있는 프로젝트(예: `유니로드_배포/backend`)에서 이 라우터를 포함해 실행하는 방식을 권장합니다.

---

## 2. 프론트엔드

### 의존성 설치

```bash
cd frontend
npm install
```

### 환경 변수

- **로컬 개발:** `frontend/.env.example`을 복사해 `frontend/.env`를 만든 뒤, Supabase·API URL 등을 입력합니다.
- **배포용:** 이미 `frontend/.env.production`이 있으면 해당 값을 사용합니다.

주요 변수:

| 변수 | 설명 |
|------|------|
| `VITE_API_BASE_URL` / `VITE_API_URL` | 백엔드 API 주소 (로컬: `http://localhost:8000`) |
| `VITE_SUPABASE_URL` | Supabase 프로젝트 URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anon key |
| `VITE_PRE_DEPLOY` | 로컬/모바일 개발 시 `true` |

### 실행

```bash
cd frontend
npm run dev
```

---

## 3. 요약

| 항목 | 경로 | 비고 |
|------|------|------|
| 백엔드 의존성 | `backend/requirements.txt` | `pip install -r requirements.txt` |
| 백엔드 env 템플릿 | `backend/.env.example` | 복사 후 `backend/.env`로 저장 후 값 입력 |
| 프론트엔드 의존성 | `frontend/package.json` | `npm install` |
| 프론트엔드 env 템플릿 | `frontend/.env.example` | 복사 후 `frontend/.env`로 저장 후 값 입력 |
