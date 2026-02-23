# Profile Agent (Sandbox)

`uniroad` 실서비스와 분리된 성적 추출용 멀티 에이전트 샌드박스입니다.

기능:
- 학생 채팅에서 성적 정보 추출 (등급/표준점수/백분위, 11232/211332 축약형 포함)
- 누락 과목 자동 보완/추정 (평균 백분위 기반)
- `adiga2/input/profiles_5sets.json` 형식에 맞춘 payload 생성
- 로컬 SQLite `user_profile` 테이블에 upsert 저장
- 프론트에서 구조화 결과(Extracted/Completed/adiga2 Input) 즉시 표시

## 구조

```
profile-agent/
  backend/
    app/
      agents/
      services/
      core/
      main.py
    requirements.txt
  frontend/
    index.html
    app.js
    styles.css
```

## 실행

1) 백엔드 의존성 설치

```bash
cd /Users/rlaxogns100/Desktop/Projects/uniroad/profile-agent/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) 서버 실행

```bash
uvicorn app.main:app --reload --port 8100
```

3) 브라우저 접속

- [http://localhost:8100](http://localhost:8100)

## API

### POST `/api/chat`

```json
{
  "user_id": "demo-student-001",
  "message": "나 11232인데 수학은 미적, 생윤 2등급 사문 3등급이야"
}
```

응답:
- `extracted_scores`: 채팅에서 직접 읽은 값
- `completed_scores`: 보완/추정이 반영된 과목별 점수
- `adiga_input`: adiga2 계산기 입력 스키마
- `estimated_subjects`: 추정된 과목 리스트
- `db_record`: `user_profile` 업데이트 정보

### GET `/api/profile/{user_id}`

마지막 저장된 구조화 프로필 조회.

