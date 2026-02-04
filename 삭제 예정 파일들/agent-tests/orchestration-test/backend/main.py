"""
Multi-Agent 입시 상담 시스템
전체 파이프라인: Orchestration Agent → Sub Agents → Final Agent → 최종 답변
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import google.generativeai as genai
import json
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Sub Agents와 Final Agent import
from sub_agents import (
    execute_sub_agents, 
    get_agent,
    set_agent_model,
    get_agent_model_config,
    get_available_models
)
from final_agent import generate_final_answer

# Gemini API 키 설정 (환경 변수에서 로드)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY 환경 변수를 설정해주세요.")
genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Multi-Agent 입시 상담 시스템")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 대화 이력 저장 (메모리)
conversation_history: Dict[str, List[Dict]] = {}

# 가용 에이전트 목록 (5개 대학 + 컨설팅 + 선생님)
AVAILABLE_AGENTS = [
    {
        "name": "서울대 agent",
        "description": "서울대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "연세대 agent",
        "description": "연세대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "고려대 agent",
        "description": "고려대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "성균관대 agent",
        "description": "성균관대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "경희대 agent",
        "description": "경희대학교 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    },
    {
        "name": "컨설팅 agent",
        "description": "5개 대학(서울대/연세대/고려대/성균관대/경희대) 합격 데이터 비교 분석, 학생 성적 기반 합격 가능성 평가 및 대학 추천, 정시 점수 환산"
    },
    {
        "name": "선생님 agent",
        "description": "현실적인 목표 설정 및 공부 계획 수립, 멘탈 관리 조언, 학습 전략"
    },
]

# Orchestration Agent 시스템 프롬프트
ORCHESTRATION_SYSTEM_PROMPT = """당신은 대학 입시 상담 시스템의 **Orchestration Agent (총괄 설계자 & PD)**입니다.

## 기본 설정
- **현재 시점:** 2026년 1월 (2026학년도 정시 진행 중)
- **검색 기준:** 사용자가 "작년 입결/결과"를 물으면 반드시 **[2025학년도]** 키워드로 쿼리를 생성하세요. (2026학년도는 결과 미확정, 2024학년도는 재작년임)

## 즉시 처리 규칙 (Immediate Processing)
아래 상황에서는 하위 Agent를 호출하지 않고, **당신이 직접 JSON의 'direct_response' 필드에 답변을 작성**하여 즉시 응답합니다.

1. **간단한 인사 및 잡담**:
   - 예: "안녕", "반가워", "너 누구야?"
   - 대응: 2026학년도 입시 파트너로서 친절하게 인사하고 성적 입력을 유도.

2. **정보가 심각하게 부족한 상담 요청**:
   - 기준: **국어, 수학, 영어, 탐구** 중 언급된 과목이 **2개 이하**인 경우.
   - 상황: "국어 1등급인데 대학 어디 가?", "나 수학 96점이야"
   - 대응: **"추가 정보 요청"**. 합격 예측을 위해서는 최소한 국/수/영/탐 등급이 필요함을 설명하고 입력을 유도.

## 역할
학생의 질문을 분석하여 세 가지를 결정합니다:
1. **Execution Plan**: 어떤 Sub Agent를 어떤 순서로 호출할지
2. **Answer Structure**: 최종 답변이 어떤 구조로 구성될지
3. **Extracted Scores**: 컨설팅 agent 호출 시 성적 정보 구조화 (조건부)

## 가용 에이전트 목록
{agents}

## 에이전트 역할
- 특정 대학이 언급되면 해당 대학 agent 호출
- 공부 계획, 멘탈 관리 질문은 선생님 agent 호출
- 합격 가능성, 대학 추천, 점수 환산 질문은 컨설팅 agent 호출

## 학생의 입력 성적 처리 규칙

학생이 성적을 축약 형식으로 입력하는 경우 (예: "나 112320야", "13425"), 반드시 아래 규칙에 따라 풀어서 표현하세요:

1. **숫자 순서 해석**:
   - 첫 번째 숫자: 국어 등급
   - 두 번째 숫자: 수학 등급
   - 세 번째 숫자: 영어 등급
   - 네 번째 숫자: 탐구1 등급
   - 다섯 번째 숫자: 탐구2 등급

2. **풀어쓰기 형식** (반드시 "탐구1", "탐구2"로 명시):
   - 예시 1: "나 112320야" → "국어 1등급, 수학 1등급, 영어 2등급, 탐구1 3등급, 탐구2 2등급"
   - 예시 2: "13425" → "국어 1등급, 수학 3등급, 영어 4등급, 탐구1 2등급, 탐구2 5등급"
   - ❌ 틀린 예: "탐구 3등급, 탐구 2등급" (이렇게 쓰면 안 됨!)
   - ✅ 올바른 예: "탐구1 3등급, 탐구2 2등급" (반드시 탐구1, 탐구2로 구분)

3. **컨설팅 agent에게 전달할 쿼리 작성 시**:
   - 반드시 위 형식으로 풀어쓴 성적을 포함하여 쿼리를 작성하세요.
   - 예: "국어 1등급, 수학 1등급, 영어 2등급, 탐구1 3등급, 탐구2 2등급일 때의 예상 표준점수대 산출 및 2025학년도 입결 기준 서울대, 연세대, 고려대, 성균관대, 경희대 합격 가능성 분석"

## 성적 정보 추출 규칙 (매우 중요!)
**컨설팅 agent를 호출할 계획이고, 사용자 질문에 성적이 포함된 경우에만** `extracted_scores` 필드를 생성하세요.

### 생성 조건
- ✅ 컨설팅 agent 호출 + 성적 있음 → extracted_scores 생성
- ❌ 다른 agent만 호출 → extracted_scores 필드 생략
- ❌ 성적 없음 → extracted_scores 필드 생략

### 지원 입력 형식
- 축약형: "나 11232야" → 국어1/수학1/영어2/탐구1=3/탐구2=2
- 등급: "국어 1등급", "수학 2등급"
- 표준점수: "국어 140", "수학 표준점수 130"
- 자연어: "국어가 1등급이고 수학도 1등급인데요"

### 과목명 규칙
- **주요 과목**: 국어, 수학, 영어, 한국사
- **선택과목** (언급 시 포함): 화법과작문, 언어와매체, 확률과통계, 미적분, 기하
- **탐구 과목** (반드시 구체적 과목명):
  - 사회탐구: 생활과윤리, 윤리와사상, 한국지리, 세계지리, 동아시아사, 세계사, 경제, 정치와법, 사회문화
  - 과학탐구: 물리학1, 물리학2, 화학1, 화학2, 생명과학1, 생명과학2, 지구과학1, 지구과학2

### 탐구 과목 추론
사용자가 구체적 탐구 과목을 말하지 않은 경우:
- 수학이 "확률과통계"면 → 인문계 (생활과윤리, 사회문화)
- 수학이 "미적분" 또는 "기하"면 → 자연계 (생명과학1, 지구과학1)
- 정보 없으면 → 인문계 기본값

### 출력 형식
```json
"extracted_scores": {{
  "국어": {{"type": "등급", "value": 1, "선택과목": "화법과작문"}},
  "수학": {{"type": "등급", "value": 1, "선택과목": "확률과통계"}},
  "영어": {{"type": "등급", "value": 2}},
  "생활과윤리": {{"type": "등급", "value": 3}},
  "사회문화": {{"type": "등급", "value": 2}}
}}
```

## 답변 구조 섹션 타입
- `empathy`: 학생의 마음에 공감하는 따뜻한 위로 (1-2문장)
- `fact_check`: 정량적 데이터/팩트 제공 (입결, 경쟁률 등)
- `analysis`: 학생 상황과 데이터 비교 분석
- `recommendation`: 구체적인 추천/제안
- `next_step`: 추가 질문 유도
- `warning`: 주의사항
- `encouragement`: 격려 (1-2문장)

## 출력 형식

### 컨설팅 agent 호출 (성적 포함)
```json
{{
  "user_intent": "서울대 합격 가능성 문의",
  "extracted_scores": {{
    "국어": {{"type": "등급", "value": 1, "선택과목": "화법과작문"}},
    "수학": {{"type": "등급", "value": 1, "선택과목": "확률과통계"}},
    "영어": {{"type": "등급", "value": 2}},
    "생활과윤리": {{"type": "등급", "value": 3}},
    "사회문화": {{"type": "등급", "value": 2}}
  }},
  "execution_plan": [
    {{"step": 1, "agent": "컨설팅 agent", "query": "서울대 합격 가능성 분석"}}
  ],
  "answer_structure": [...]
}}
```

### 다른 경우 (extracted_scores 생략)
```json
{{
  "user_intent": "서울대 모집요강 문의",
  "execution_plan": [
    {{"step": 1, "agent": "서울대 agent", "query": "2026학년도 정시 모집요강"}}
  ],
  "answer_structure": [...]
}}
```

## 규칙
1. answer_structure는 2~5개 섹션
2. empathy 섹션은 첫 번째 배치
3. source_from은 step 번호와 매칭
4. **extracted_scores는 컨설팅 agent 호출 시에만 생성**
5. 간단한 질문 = 1~2개 agent, 2~3개 섹션
6. 복잡한 질문 = 2개 이상 agent, 3~4개 섹션
"""


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


def format_agents_for_prompt() -> str:
    """에이전트 목록을 프롬프트용 문자열로 포맷"""
    result = []
    for agent in AVAILABLE_AGENTS:
        result.append(f"- **{agent['name']}**: {agent['description']}")
    return "\n".join(result)


def parse_orchestration_response(response_text: str) -> Dict[str, Any]:
    """Gemini 응답에서 JSON 추출 및 파싱"""
    try:
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            json_str = response_text.strip()

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return {
            "error": "JSON 파싱 실패",
            "raw_response": response_text,
            "parse_error": str(e)
        }


async def run_orchestration_agent(message: str, session_id: str) -> Dict[str, Any]:
    """Orchestration Agent 실행"""

    system_prompt = ORCHESTRATION_SYSTEM_PROMPT.format(
        agents=format_agents_for_prompt()
    )

    model = genai.GenerativeModel(
        model_name="gemini-3-flash-preview",
        system_instruction=system_prompt
    )

    # 대화 이력
    history = []
    if session_id in conversation_history:
        for msg in conversation_history[session_id]:
            history.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [msg["content"]]
            })

    chat_session = model.start_chat(history=history)
    response = chat_session.send_message(message)

    return parse_orchestration_response(response.text)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    전체 파이프라인 실행:
    1. Orchestration Agent → Execution Plan + Answer Structure
    2. Sub Agents 실행 → 결과 수집
    3. Final Agent → 최종 답변 생성
    """

    try:
        # 세션 이력 초기화
        if request.session_id not in conversation_history:
            conversation_history[request.session_id] = []

        # ========================================
        # 1단계: Orchestration Agent
        # ========================================
        orchestration_result = await run_orchestration_agent(
            request.message, request.session_id
        )

        if "error" in orchestration_result:
            return {
                "stage": "orchestration",
                "error": orchestration_result["error"],
                "orchestration_result": orchestration_result,
                "sub_agent_results": None,
                "final_answer": None
            }

        execution_plan = orchestration_result.get("execution_plan", [])
        answer_structure = orchestration_result.get("answer_structure", [])
        extracted_scores = orchestration_result.get("extracted_scores", {})
        notes = orchestration_result.get("notes", "")

        # ========================================
        # 2단계: Sub Agents 실행 (extracted_scores 전달)
        # ========================================
        sub_agent_results = await execute_sub_agents(
            execution_plan,
            extracted_scores=extracted_scores
        )

        # ========================================
        # 3단계: Final Agent - 최종 답변 생성
        # ========================================
        final_result = await generate_final_answer(
            user_question=request.message,
            answer_structure=answer_structure,
            sub_agent_results=sub_agent_results,
            notes=notes
        )

        final_answer = final_result.get("final_answer", "답변 생성 실패")

        # 대화 이력에 추가
        conversation_history[request.session_id].append({
            "role": "user",
            "content": request.message
        })
        conversation_history[request.session_id].append({
            "role": "assistant",
            "content": final_answer
        })

        return {
            "stage": "complete",
            "orchestration_result": orchestration_result,
            "sub_agent_results": sub_agent_results,
            "final_answer": final_answer,
            "metadata": final_result.get("metadata", {})
        }

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error: {error_detail}")
        return {
            "stage": "error",
            "error": str(e),
            "detail": error_detail,
            "orchestration_result": None,
            "sub_agent_results": None,
            "final_answer": None
        }


@app.post("/api/test/final-agent")
async def test_final_agent(request: dict):
    """
    Final Agent 직접 테스트 엔드포인트
    
    Request body:
    {
        "user_question": str,
        "answer_structure": List[Dict],
        "sub_agent_results": Dict[str, Any],
        "notes": str (optional)
    }
    """
    try:
        print("\n" + "="*80)
        print("🧪 Final Agent 테스트 API 호출")
        print("="*80)
        
        user_question = request.get("user_question", "")
        answer_structure = request.get("answer_structure", [])
        sub_agent_results = request.get("sub_agent_results", {})
        notes = request.get("notes", "")
        
        print(f"✅ 받은 데이터:")
        print(f"   user_question: {user_question[:100]}...")
        print(f"   answer_structure: {len(answer_structure)}개 섹션")
        print(f"   sub_agent_results: {list(sub_agent_results.keys())}")
        print(f"   notes: {notes if notes else '(없음)'}")
        
        # Final Agent 실행
        result = await generate_final_answer(
            user_question=user_question,
            answer_structure=answer_structure,
            sub_agent_results=sub_agent_results,
            notes=notes
        )
        
        print(f"✅ Final Agent 실행 완료")
        print("="*80 + "\n")
        
        return {
            "status": "success",
            "result": result,
            "input_data": {
                "user_question": user_question,
                "answer_structure_count": len(answer_structure),
                "sub_agent_results_keys": list(sub_agent_results.keys()),
                "notes": notes
            }
        }
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"❌ Final Agent 테스트 실패: {error_detail}")
        return {
            "status": "error",
            "error": str(e),
            "detail": error_detail
        }


@app.post("/api/chat/orchestration-only")
async def chat_orchestration_only(request: ChatRequest):
    """Orchestration Agent만 실행 (디버깅용)"""
    try:
        result = await run_orchestration_agent(request.message, request.session_id)
        return {"orchestration_result": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/agents")
async def get_agents():
    """가용 에이전트 목록 조회"""
    return {"agents": AVAILABLE_AGENTS}


@app.post("/api/agents")
async def add_agent(agent: Dict[str, Any]):
    """새 Sub Agent 추가"""
    if "name" not in agent or "description" not in agent:
        raise HTTPException(status_code=400, detail="name과 description은 필수입니다")

    if any(a["name"] == agent["name"] for a in AVAILABLE_AGENTS):
        raise HTTPException(status_code=400, detail=f"이미 존재하는 에이전트: {agent['name']}")

    new_agent = {"name": agent["name"], "description": agent["description"]}
    AVAILABLE_AGENTS.append(new_agent)
    return {"message": "에이전트 추가 완료", "agent": new_agent}


@app.delete("/api/agents/{agent_name}")
async def delete_agent(agent_name: str):
    """Sub Agent 삭제"""
    global AVAILABLE_AGENTS
    original_len = len(AVAILABLE_AGENTS)
    AVAILABLE_AGENTS = [a for a in AVAILABLE_AGENTS if a["name"] != agent_name]

    if len(AVAILABLE_AGENTS) == original_len:
        raise HTTPException(status_code=404, detail=f"에이전트를 찾을 수 없음: {agent_name}")

    return {"message": "에이전트 삭제 완료", "agent_name": agent_name}


@app.delete("/api/history/{session_id}")
async def clear_history(session_id: str):
    """대화 이력 초기화"""
    if session_id in conversation_history:
        del conversation_history[session_id]
    return {"message": "대화 이력 초기화 완료"}


@app.get("/api/models")
async def get_models():
    """사용 가능한 LLM 모델 목록 조회"""
    return {
        "models": get_available_models()
    }


@app.get("/api/agents/models")
async def get_agents_models():
    """모든 에이전트의 현재 모델 설정 조회"""
    return {
        "agent_models": get_agent_model_config()
    }


@app.put("/api/agents/{agent_name}/model")
async def update_agent_model(agent_name: str, request: Dict[str, str]):
    """특정 에이전트의 모델 설정 변경"""
    try:
        model_name = request.get("model_name")
        if not model_name:
            raise HTTPException(status_code=400, detail="model_name이 필요합니다")
        
        set_agent_model(agent_name, model_name)
        
        return {
            "message": "모델 설정 완료",
            "agent_name": agent_name,
            "model_name": model_name
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 프론트엔드 정적 파일 서빙
frontend_path = Path(__file__).parent.parent / "frontend"


@app.get("/")
async def serve_frontend():
    """프론트엔드 HTML 서빙"""
    return FileResponse(frontend_path / "index.html")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 Multi-Agent 입시 상담 시스템")
    print("="*60)
    print("📍 Server: http://localhost:8080")
    print("📍 API Docs: http://localhost:8080/docs")
    print("="*60)
    print("\n파이프라인: Orchestration → Sub Agents → Final Agent\n")
    uvicorn.run(app, host="0.0.0.0", port=8080)
