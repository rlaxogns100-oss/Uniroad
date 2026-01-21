"""
Orchestration Agent
- 사용자 질문 분석
- 어떤 Sub Agent를 호출할지 결정 (Execution Plan)
- 최종 답변의 구조 설계 (Answer Structure)
"""

import google.generativeai as genai
from typing import Dict, Any, List
import json
import os
from dotenv import load_dotenv
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from token_logger import log_token_usage

load_dotenv()

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

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

## 역할
학생의 질문을 분석하여 두 가지를 결정합니다:
1. **Execution Plan**: 어떤 Sub Agent를 어떤 순서로 호출할지
2. **Answer Structure**: 최종 답변이 어떤 구조로 구성될지 (목차/템플릿)

## 가용 에이전트 목록
{agents}

## 답변 구조 섹션 타입
- `empathy`: 학생의 마음에 공감하는 따뜻한 위로 (1-2문장)
- `fact_check`: 정량적 데이터/팩트 제공 (입결, 경쟁률 등) - 출처 필요
- `analysis`: 학생 상황과 데이터 비교 분석 - 출처 필요
- `recommendation`: 구체적인 추천/제안
- `next_step`: 추가 질문 유도 또는 다음 단계 안내
- `warning`: 주의사항이나 리스크 안내
- `encouragement`: 격려와 응원 (1-2문장)

## 출력 형식
반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.

```json
{{
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
  ]
}}
```

## 규칙
1. 모호한 질문이라도 최선의 계획을 세우세요
2. answer_structure는 최소 2개, 최대 5개 섹션으로 구성
3. empathy 섹션은 항상 첫 번째에 배치
4. fact_check나 analysis가 있으면 반드시 해당 데이터를 가져올 execution_plan이 있어야 함
5. source_from은 execution_plan의 step 번호와 매칭되어야 함 (예: "Step1_Result")
6. agent 필드에는 가용 에이전트 목록에 있는 에이전트 이름만 사용

## 간결성 원칙 (매우 중요!)
- **불필요한 agent 호출 금지**: 간단한 질문에 여러 agent를 호출하지 마세요. 질문의 복잡도에 비례하여 최소한의 agent만 호출하세요.
- **불필요한 섹션 생성 금지**: 단순 인사나 가벼운 질문에 5개 섹션을 모두 채우지 마세요. 필요한 섹션만 간결하게 구성하세요.
- 간단한 질문 = 1~2개 agent, 2~3개 섹션
- 복잡한 비교/분석 질문 = 2개 이상 agent, 3~4개 섹션

## 대학 매칭 규칙
- 특정 대학이 언급되면 해당 대학 agent 호출
- "서울대 연대 고대 비교" 같은 경우 여러 대학 agent 호출
- 합격 가능성, 대학 추천, 점수 환산 질문은 컨설팅 agent 호출
- 공부 계획, 멘탈 관리 질문은 선생님 agent 호출
"""


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


# 로그 콜백 (실시간 스트리밍용)
_log_callback = None

def set_log_callback(callback):
    """로그 콜백 설정"""
    global _log_callback
    _log_callback = callback

def _log(msg: str):
    """로그 출력 및 콜백 호출"""
    if _log_callback:
        _log_callback(msg)
    else:
        print(msg)

async def run_orchestration_agent_with_prompt(
    message: str, 
    history: List[Dict] = None,
    custom_system_prompt: str = None
) -> Dict[str, Any]:
    """
    커스텀 시스템 프롬프트를 사용한 Orchestration Agent 실행
    
    Args:
        message: 사용자 질문
        history: 대화 히스토리 (선택)
        custom_system_prompt: 커스텀 시스템 프롬프트 (선택)
        
    Returns:
        {
            "user_intent": str,
            "execution_plan": List[Dict],
            "answer_structure": List[Dict]
        }
    """
    
    if custom_system_prompt:
        system_prompt = custom_system_prompt.format(
            agents=format_agents_for_prompt()
        )
        print(f"🎨 Using custom system prompt for orchestration")
    else:
        system_prompt = ORCHESTRATION_SYSTEM_PROMPT.format(
            agents=format_agents_for_prompt()
        )
    
    model = genai.GenerativeModel(
        model_name="gemini-3-flash-preview",
        system_instruction=system_prompt
    )

    # 대화 이력 구성
    gemini_history = []
    if history:
        for msg in history:
            role = "user" if msg.get("role") == "user" else "model"
            content = msg.get("content") or msg.get("parts", [""])[0]
            if isinstance(content, list):
                content = content[0] if content else ""
            gemini_history.append({
                "role": role,
                "parts": [content]
            })

    chat = model.start_chat(history=gemini_history)
    response = await chat.send_message_async(message)
    
    # 토큰 사용량 기록
    if hasattr(response, 'usage_metadata'):
        usage = response.usage_metadata
        print(f"💰 토큰 사용량 (orchestration): {usage}")
        
        log_token_usage(
            operation="오케스트레이션",
            prompt_tokens=getattr(usage, 'prompt_token_count', 0),
            output_tokens=getattr(usage, 'candidates_token_count', 0),
            total_tokens=getattr(usage, 'total_token_count', 0),
            model="gemini-3-flash-preview",
            details="실행계획 수립"
        )
    
    result_text = response.text.strip()

    result = parse_orchestration_response(result_text)
    return result


async def run_orchestration_agent(
    message: str, 
    history: List[Dict] = None
) -> Dict[str, Any]:
    """
    Orchestration Agent 실행 (기본 프롬프트 사용)
    
    Args:
        message: 사용자 질문
        history: 대화 히스토리 (선택)
        
    Returns:
        {
            "user_intent": str,
            "execution_plan": List[Dict],
            "answer_structure": List[Dict]
        }
    """
    
    system_prompt = ORCHESTRATION_SYSTEM_PROMPT.format(
        agents=format_agents_for_prompt()
    )

    model = genai.GenerativeModel(
        model_name="gemini-3-flash-preview",
        system_instruction=system_prompt
    )

    # 대화 이력 구성
    gemini_history = []
    if history:
        for msg in history:
            role = "user" if msg.get("role") == "user" else "model"
            content = msg.get("content") or msg.get("parts", [""])[0]
            if isinstance(content, list):
                content = content[0] if content else ""
            gemini_history.append({
                "role": role,
                "parts": [content]
            })

    chat_session = model.start_chat(history=gemini_history)
    
    response = chat_session.send_message(
        message, 
        request_options=genai.types.RequestOptions(
            retry=None,
            timeout=120.0  # 멀티에이전트 파이프라인을 위해 120초로 증가
        )
    )
    
    # 토큰 사용량 기록
    if hasattr(response, 'usage_metadata'):
        usage = response.usage_metadata
        print(f"💰 토큰 사용량 (orchestration_plan): {usage}")
        
        log_token_usage(
            operation="오케스트레이션_계획",
            prompt_tokens=getattr(usage, 'prompt_token_count', 0),
            output_tokens=getattr(usage, 'candidates_token_count', 0),
            total_tokens=getattr(usage, 'total_token_count', 0),
            model="gemini-3-flash-preview",
            details="실행계획 수립"
        )
    
    result = parse_orchestration_response(response.text)
    
    _log("")
    _log(f"📋 Orchestration 결과:")
    _log(f"   사용자 의도: {result.get('user_intent', 'N/A')}")
    _log(f"   실행 계획: {len(result.get('execution_plan', []))}개 step")
    _log(f"   답변 구조: {len(result.get('answer_structure', []))}개 섹션")
    _log("="*80)
    
    return result
