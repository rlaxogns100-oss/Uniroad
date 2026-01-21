# Orchestration Agent Test Server

기존 UniZ 프로젝트와 **완전히 분리된** Orchestration Agent 테스트 서버입니다.

## 구조

```
orchestration-agent-test/
├── backend/
│   └── main.py          # FastAPI 서버 + Orchestration Agent
├── frontend/
│   └── index.html       # 테스트 UI (채팅 + 결과 표시)
├── requirements.txt
└── README.md
```

## 실행 방법

### 1. 의존성 설치

```bash
cd /Users/rlaxogns100/Desktop/Projects/UniZ/orchestration-agent-test
pip install -r requirements.txt
```

### 2. 서버 실행

```bash
python backend/main.py
```

### 3. 브라우저에서 접속

```
http://localhost:8080
```

## 기능

### 화면 구성
- **왼쪽 패널**: Orchestration Agent 결과 (Execution Plan + Answer Structure)
- **오른쪽 패널**: 채팅창

### API Endpoints

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/chat` | 질문 전송 → Orchestration 결과 반환 |
| GET | `/api/agents` | 등록된 Sub Agent 목록 조회 |
| POST | `/api/agents` | 새 Sub Agent 추가 |
| DELETE | `/api/agents/{id}` | Sub Agent 삭제 |
| DELETE | `/api/history/{session_id}` | 대화 이력 초기화 |

### 기본 등록된 Sub Agents

1. **UniversityAgent**: 대학 입시 정보 조회
2. **ConsultantAgent**: 성적 분석 및 합격 가능성 평가
3. **TrendAgent**: 입시 트렌드 분석
4. **ComparisonAgent**: 대학/전형 비교

## Sub Agent 추가 방법

### UI에서 추가
1. 왼쪽 하단 "등록된 Sub Agents" → "+ 추가" 버튼 클릭
2. 필수 정보 입력:
   - **Agent ID**: 영문 snake_case (예: `schedule_agent`)
   - **Agent Name**: PascalCase (예: `ScheduleAgent`)
   - **Description**: 에이전트 역할 설명
   - **Capabilities**: 가능한 기능들 (쉼표 구분)
   - **Required Params**: 필수 파라미터 (쉼표 구분)

### API로 추가

```bash
curl -X POST http://localhost:8080/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "id": "schedule_agent",
    "name": "ScheduleAgent",
    "description": "학습 일정을 관리하고 추천하는 에이전트",
    "capabilities": ["일정 조회", "일정 추천", "D-day 계산"],
    "required_params": ["user_id"],
    "optional_params": ["date_range"]
  }'
```

## Orchestration Agent 출력 예시

```json
{
  "plan_id": "consulting_plan_001",
  "user_intent": "내신 2.5등급 학생이 서울대 진학 가능성 문의",
  "execution_plan": [
    {
      "step": 1,
      "agent": "university_agent",
      "target": "서울대",
      "query": "2025년 입결 및 2026년 모집요강",
      "params": { "year": "2025-2026" }
    },
    {
      "step": 2,
      "agent": "consultant_agent",
      "query": "내신 2.5등급과 서울대 입결 비교 분석",
      "params": { "student_grades": "2.5" }
    }
  ],
  "answer_structure": [
    {
      "section": 1,
      "type": "empathy",
      "source_from": null,
      "instruction": "서울대를 목표로 하는 학생의 마음에 공감 (1-2문장)"
    },
    {
      "section": 2,
      "type": "fact_check",
      "source_from": "Step1_Result",
      "instruction": "서울대 최근 입결 데이터 요약 (정량적)"
    },
    {
      "section": 3,
      "type": "analysis",
      "source_from": "Step2_Result",
      "instruction": "학생 성적과 입결 비교 결과, 현실적 진단"
    },
    {
      "section": 4,
      "type": "next_step",
      "source_from": null,
      "instruction": "다음 단계 제안 (다른 대학 비교, 전형 추천 등)"
    }
  ],
  "notes": "학생이 불안해할 수 있으니 희망을 잃지 않도록 격려도 포함할 것"
}
```

## 다음 단계 (구현 예정)

1. **Sub Agents 실제 구현**: 각 에이전트가 실제 데이터를 가져오도록
2. **Final Response Agent**: answer_structure에 따라 최종 답변 생성
3. **기존 프로젝트 연동**: 검증 완료 후 메인 프로젝트에 통합
