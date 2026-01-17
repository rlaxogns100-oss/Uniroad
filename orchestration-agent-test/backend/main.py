"""
Orchestration Agent Test Server
- 기존 프로젝트와 완전히 분리된 독립 서버
- Sub Agent와 Final Agent는 구현하지 않고, Orchestration Agent만 테스트
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import google.generativeai as genai
import json
import os
from pathlib import Path

# Gemini API 키 설정 (기존 프로젝트의 키 사용)
GEMINI_API_KEY = "AIzaSyCyTP7xvK-XLaJXUOxRbu5MpkgxlRGNpkQ"
genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Orchestration Agent Test Server")

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

# 가용 에이전트 목록 (Sub Agent 정의 - 이름과 설명만)
AVAILABLE_AGENTS = [
    {
        "name": "서울대 agent",
        "description": "서울대학교 입시 정보(입결, 모집요강, 전형별 정보)를 조회하는 에이전트"
    },
    {
        "name": "고려대 agent",
        "description": "고려대학교 입시 정보(입결, 모집요강, 전형별 정보)를 조회하는 에이전트"
    },
    {
        "name": "연세대 agent",
        "description": "연세대학교 입시 정보(입결, 모집요강, 전형별 정보)를 조회하는 에이전트"
    },
    {
        "name": "컨설팅 agent",
        "description": "여러 대학/전형을 비교 분석, 학생에게 적절한 대학 추천 및 학생 성적대로 합격 가능성 평가"
    },
    {
        "name": "선생님 agent",
        "description": "현실적인 목표 설정 및 공부 계획 수립"
    },
]

# Orchestration Agent 시스템 프롬프트
ORCHESTRATION_SYSTEM_PROMPT = """당신은 대학 입시 상담 시스템의 **Orchestration Agent (총괄 설계자 & PD)**입니다.

## 역할
학생의 질문을 분석하여 두 가지를 결정합니다:
1. **Execution Plan**: 어떤 Sub Agent를 어떤 순서로 호출할지
2. **Answer Structure**: 최종 답변이 어떤 구조로 구성될지 (목차/템플릿)

## 가용 에이전트 목록
{agents}

## 답변 구조 섹션 타입
- `empathy`: 학생의 마음에 공감하는 따뜻한 위로
- `fact_check`: 정량적 데이터/팩트 제공 (입결, 경쟁률 등)
- `analysis`: 학생 상황과 데이터 비교 분석
- `recommendation`: 구체적인 추천/제안
- `next_step`: 추가 질문 유도 또는 다음 단계 안내
- `warning`: 주의사항이나 리스크 안내
- `encouragement`: 격려와 응원

## 출력 형식
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

```json
{{
  "plan_id": "unique_plan_id",
  "user_intent": "사용자 의도 요약",
  "execution_plan": [
    {{
      "step": 1,
      "agent": "에이전트 이름",
      "query": "에이전트에게 전달할 구체적 쿼리"
    }}
  ],
  "answer_structure": [
    {{
      "section": 1,
      "type": "섹션 타입",
      "source_from": "Step{{N}}_Result 또는 null",
      "instruction": "이 섹션에서 다룰 내용에 대한 구체적 지시"
    }}
  ],
  "notes": "Final Agent에게 전달할 추가 지시사항"
}}
```

## 규칙
1. 모호한 질문이라도 최선의 계획을 세우세요
2. answer_structure는 최소 2개, 최대 5개 섹션으로 구성
3. empathy 섹션은 항상 첫 번째에 배치
4. fact_check나 analysis가 있으면 반드시 해당 데이터를 가져올 execution_plan이 있어야 함
5. source_from은 execution_plan의 step 번호와 매칭되어야 함 (예: "Step1_Result")
6. agent 필드에는 가용 에이전트 목록에 있는 에이전트 이름만 사용
"""


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    orchestration_result: Dict[str, Any]
    raw_response: str


def format_agents_for_prompt() -> str:
    """에이전트 목록을 프롬프트용 문자열로 포맷"""
    result = []
    for agent in AVAILABLE_AGENTS:
        result.append(f"- **{agent['name']}**: {agent['description']}")
    return "\n".join(result)


def parse_orchestration_response(response_text: str) -> Dict[str, Any]:
    """Gemini 응답에서 JSON 추출 및 파싱"""
    try:
        # JSON 블록 추출 시도
        if "```json" in response_text:
            json_start = response_text.find("```json") + 7
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        elif "```" in response_text:
            json_start = response_text.find("```") + 3
            json_end = response_text.find("```", json_start)
            json_str = response_text[json_start:json_end].strip()
        else:
            # JSON 직접 파싱 시도
            json_str = response_text.strip()

        return json.loads(json_str)
    except json.JSONDecodeError as e:
        return {
            "error": "JSON 파싱 실패",
            "raw_response": response_text,
            "parse_error": str(e)
        }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Orchestration Agent와 대화"""

    try:
        # 세션 이력 초기화
        if request.session_id not in conversation_history:
            conversation_history[request.session_id] = []

        # Gemini 모델 초기화 (매 요청마다 새로 생성)
        system_prompt = ORCHESTRATION_SYSTEM_PROMPT.format(
            agents=format_agents_for_prompt()
        )

        model = genai.GenerativeModel(
            model_name="gemini-3-flash-preview",
            system_instruction=system_prompt
        )

        # 대화 이력을 Gemini 형식으로 변환
        history = []
        for msg in conversation_history[request.session_id]:
            history.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [msg["content"]]
            })

        # 채팅 시작
        chat_session = model.start_chat(history=history)

        # 메시지 전송
        response = chat_session.send_message(request.message)
        response_text = response.text

        # 대화 이력에 추가
        conversation_history[request.session_id].append({
            "role": "user",
            "content": request.message
        })
        conversation_history[request.session_id].append({
            "role": "assistant",
            "content": response_text
        })

        # 응답 파싱
        orchestration_result = parse_orchestration_response(response_text)

        return {
            "orchestration_result": orchestration_result,
            "raw_response": response_text
        }

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"Error: {error_detail}")
        return {
            "orchestration_result": {
                "error": str(e),
                "detail": error_detail
            },
            "raw_response": f"Error: {str(e)}"
        }


@app.get("/api/agents")
async def get_agents():
    """가용 에이전트 목록 조회"""
    return {"agents": AVAILABLE_AGENTS}


@app.post("/api/agents")
async def add_agent(agent: Dict[str, Any]):
    """새 Sub Agent 추가 (이름과 설명만)"""
    if "name" not in agent or "description" not in agent:
        raise HTTPException(status_code=400, detail="name과 description은 필수입니다")

    # 중복 체크
    if any(a["name"] == agent["name"] for a in AVAILABLE_AGENTS):
        raise HTTPException(status_code=400, detail=f"이미 존재하는 에이전트: {agent['name']}")

    new_agent = {
        "name": agent["name"],
        "description": agent["description"]
    }
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


# 프론트엔드 정적 파일 서빙
frontend_path = Path(__file__).parent.parent / "frontend"


@app.get("/")
async def serve_frontend():
    """프론트엔드 HTML 서빙"""
    return FileResponse(frontend_path / "index.html")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*60)
    print("🚀 Orchestration Agent Test Server")
    print("="*60)
    print(f"📍 Server: http://localhost:8080")
    print(f"📍 API Docs: http://localhost:8080/docs")
    print("="*60 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8080)
