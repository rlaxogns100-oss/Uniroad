# Agent Tests

UniZ 프로젝트의 에이전트 테스트 환경 모음입니다.

## 구조

```
agent-tests/
├── README.md                    # 이 파일
├── orchestration-test/          # Orchestration Agent 테스트
│   ├── backend/
│   │   ├── main.py
│   │   ├── final_agent.py
│   │   ├── sub_agents.py
│   │   └── mock_database.py
│   ├── frontend/
│   │   └── index.html
│   ├── requirements.txt
│   └── README.md
└── final-agent-test/            # Final Agent 전용 테스트
    ├── backend/
    │   └── main.py
    ├── index.html
    ├── requirements.txt
    └── README.md
```

## 테스트 환경 목록

### 1. Orchestration Test

전체 Multi-Agent 파이프라인 테스트:
- Orchestration Agent → Sub Agents → Final Agent

```bash
cd orchestration-test/backend
python main.py
```

### 2. Final Agent Test

Final Agent만 단독 테스트:
- 프롬프트 최적화에 집중
- 직접 입력 데이터로 테스트

```bash
cd final-agent-test/backend
python main.py
```

## 공통 설정

`.env` 파일이 프로젝트 루트에 있어야 합니다:

```
GEMINI_API_KEY=your-api-key-here
```

## 포트 정보

| 테스트 환경 | 백엔드 포트 | 프론트엔드 |
|------------|------------|-----------|
| Orchestration Test | 8080 | frontend/index.html |
| Final Agent Test | 8090 | index.html |
