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
from utils.token_logger import log_token_usage

load_dotenv()

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 대학 목록 (26개)
UNIVERSITY_LIST = [
    # 기존 5개 대학
    "서울대", "연세대", "고려대", "성균관대", "경희대",
    # 주요 사립대
    "한양대", "서강대", "중앙대", "이화여대", "건국대", 
    "동국대", "홍익대", "아주대", "인하대",
    # 특수목적대
    "한국외대", "숭실대", "서울시립대", "경북대", "부산대",
    # 과학기술원
    "KAIST", "POSTECH", "GIST", "DGIST",
    "카이스트", "포스텍", "지스트"
]

# 가용 에이전트 목록 (26개 대학 + 컨설팅 + 선생님)
# 각 대학 agent: "{대학명} agent" 형태로 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색
AVAILABLE_AGENTS = [
    *[{
        "name": f"{univ} agent",
        "description": f"{univ} 입시 정보(모집요강, 전형별 정보)를 Supabase에서 검색하는 에이전트"
    } for univ in UNIVERSITY_LIST],
    {
        "name": "컨설팅 agent",
        "description": "주요 대학 합격 데이터 비교 분석, 학생 성적 기반 합격 가능성 평가 및 대학 추천, 정시 점수 환산 (서울대/연세대/고려대/경희대/서강대 점수 환산 지원)"
    },
    {
        "name": "선생님 agent",
        "description": "현실적인 목표 설정 및 공부 계획 수립, 멘탈 관리 조언, 학습 전략"
    },
]

# Orchestration Agent 시스템 프롬프트
ORCHESTRATION_SYSTEM_PROMPT = """당신은 대학 입시 상담 시스템의 **Orchestration Agent (총괄 설계자 & PD)**입니다.

## 기본 설정
- **현재 시점:** 2026년 1월 (2026학년도 입시 진행 중)
- **검색 기준:** 사용자가 "작년 입결/결과"를 물으면 반드시 **[2025학년도]** 키워드로 쿼리를 생성하세요. (2026학년도는 결과 미확정, 2024학년도는 재작년임)

## 역할
학생의 질문을 분석하여 세 가지를 결정합니다:
1. **Execution Plan**: 어떤 Sub Agent를 어떤 순서로 호출할지
2. **Answer Structure**: 최종 답변이 어떤 구조로 구성될지 (목차/템플릿)
3. **Extracted Scores**: 컨설팅 agent 호출 시 성적 정보 구조화 (조건부)

## 가용 에이전트 목록
{agents}

## 에이전트 역할
- 특정 대학이 언급되면 해당 대학 agent 호출
- 공부 계획, 멘탈 관리 질문은 선생님 agent 호출
- 합격 가능성, 대학 추천, 점수 환산 질문은 컨설팅 agent 호출
- '어디 갈까?', '최저 없는 대학 알려줘'같은 막연한 질문에 대학 Agent를 호출하거나, 에이전트 목록 중에서 고르지 말고 전적으로 컨설팅 Agent 에 맡길 것.


## 성적 정보 추출 규칙 (매우 중요!)
**컨설팅 agent를 호출할 계획이고, 사용자 질문에 성적 정보가 포함된 경우에만** `extracted_scores` 필드를 생성하세요.

### 생성 조건
- ✅ 컨설팅 agent 호출 예정 + 성적 정보 있음 → extracted_scores 생성
- ❌ 선생님/대학 agent만 호출 → extracted_scores 생성하지 않음
- ❌ 성적 정보 없음 → extracted_scores 생성하지 않음

### 지원 입력 형식
- 축약형: "나 11232야" → 순서: 국어/수학/영어/탐구1/탐구2 등급
- 등급: "국어 1등급", "수학 2등급"
- 표준점수: "국어 표준점수 140", "수학 140점" (100 이상은 표준점수)
- 백분위: "국어 백분위 98"
- 원점수: "국어 92점" (100점 만점, 100 미만)
- 자연어: "국어가 1등급이고 수학도 1등급인데요"
- 예외: "나 211332"야 -> 6개 숫자가 제시된 경우 한국사/국어/수학/영어/탐구1/탐구2

### 과목명 규칙
- **주요 과목**: 국어, 수학, 영어, 한국사
- **선택과목**: 선택과목이 언급되면 포함 (화법과작문, 언어와매체, 확률과통계, 미적분, 기하), 언급되지 않은 경우 국어는 '화법과작문', 수학은 '확률과통계'로 간주.
- **탐구 과목**: 반드시 구체적 과목명으로 추출
  - 사회탐구: 생활과윤리, 윤리와사상, 한국지리, 세계지리, 동아시아사, 세계사, 경제, 정치와법, 사회문화
  - 과학탐구: 물리학1, 물리학2, 화학1, 화학2, 생명과학1, 생명과학2, 지구과학1, 지구과학2

### 탐구 과목 추론 규칙
사용자가 구체적 탐구 과목을 말하지 않은 경우:
- 수학 선택과목이 "확률과통계"면 → 인문계로 추론 (생활과윤리, 사회문화)
- 수학 선택과목이 "미적분" 또는 "기하"면 → 자연계로 추론 (생명과학1, 지구과학1)
- 수학 선택과목 정보 없으면 → 인문계 기본값 (생활과윤리, 사회문화)

### 출력 형식
```json
"extracted_scores": {{
  "국어": {{"type": "등급", "value": 1, "선택과목": "화법과작문"}},
  "수학": {{"type": "표준점수", "value": 140, "선택과목": "미적분"}},
  "영어": {{"type": "등급", "value": 2}},
  "생명과학1": {{"type": "등급", "value": 3}},
  "지구과학1": {{"type": "등급", "value": 2}}
}}
```
- type: "등급", "표준점수", "백분위", "원점수" 중 하나
- value: 숫자 (등급은 1-9, 표준점수는 50-150, 백분위는 0-100)
- 선택과목: 국어/수학만 해당, 없으면 생략

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

### 컨설팅 agent 호출 시 (성적 포함) - 매우 중요!
**컨설팅 agent 쿼리에는 성적 정보를 포함하지 마세요! 성적은 extracted_scores로 별도 전달됩니다.**

```json
{{
  "user_intent": "사용자 의도 요약",
  "extracted_scores": {{
    "국어": {{"type": "등급", "value": 1, "선택과목": "화법과작문"}},
    "수학": {{"type": "등급", "value": 1, "선택과목": "확률과통계"}},
    "영어": {{"type": "등급", "value": 2}},
    "생활과윤리": {{"type": "등급", "value": 3}},
    "사회문화": {{"type": "등급", "value": 2}}
  }},
  "execution_plan": [
    {{
      "step": 1,
      "agent": "경희대 agent",
      "query": "2026학년도 정시 모집요강 및 수능 반영 비율"
    }},
    {{
      "step": 2,
      "agent": "컨설팅 agent",
      "query": "주어진 성적 기반 2025학년도 입결 기준 경희대 합격 가능성 분석 및 유리한 전형 추천"
    }}
  ],
  "answer_structure": [
    {{
      "section": 1,
      "type": "empathy",
      "source_from": null,
      "instruction": "주어진 성적으로 경희대 진학을 고민하는 학생에게 공감하는 따뜻한 멘트 (1-2문장)"
    }},
    {{
      "section": 2,
      "type": "fact_check",
      "source_from": "Step1_Result",
      "instruction": "경희대 2026학년도 정시 모집요강과 2025학년도 입결 데이터 제시 (최저등급, 경쟁률)"
    }},
    {{
      "section": 3,
      "type": "analysis",
      "source_from": "Step2_Result",
      "instruction": "학생의 성적으로 환산한 점수와 경희대 입결 비교하여 합격 가능성 분석"
    }},
    {{
      "section": 4,
      "type": "recommendation",
      "source_from": "Step2_Result",
      "instruction": "경희대 내에서 유리한 전형/모집단위 추천 및 지원 전략"
    }},
    {{
      "section": 5,
      "type": "next_step",
      "source_from": null,
      "instruction": "추가 대학 비교나 세부 전략 상담 유도"
    }}
  ]
}}
```
- ✅ 올바른 쿼리: "주어진 성적 기반 서울대 합격 가능성 분석"
- ❌ 틀린 쿼리: "국어 1등급, 수학 1등급... 서울대 합격 가능성 분석" (성적을 쿼리에 포함하지 마세요!)
- ✅ 올바른 쿼리: "주어진 성적 기반 합격 가능성 높은 대학교 추천"
- ❌ 틀린 쿼리: "주어진 성적 기반 서울대, 연세대, 고려대, 성균관대, 경희대 2025학년도 입결 기준 합격 가능성 분석" (에이전트 목록을 쿼리에 포함하지 마세요!)
**instruction 필드는 필수입니다!** Final Agent가 이 지시를 기반으로 답변을 생성합니다.

### 다른 agent 호출 시 (성적 없음)
```json
{{
  "user_intent": "사용자 의도 요약",
  "execution_plan": [
    {{
      "step": 1,
      "agent": "서울대 agent",
      "query": "2026학년도 정시 모집요강 정보"
    }}
  ],
  "answer_structure": [
    {{
      "section": 1,
      "type": "empathy",
      "source_from": null,
      "instruction": "서울대 정시 모집요강에 관심 있는 학생에게 공감하는 멘트 (1-2문장)"
    }},
    {{
      "section": 2,
      "type": "fact_check",
      "source_from": "Step1_Result",
      "instruction": "서울대 2026학년도 정시 모집요강 주요 내용 정리 (모집인원, 전형방법, 수능 반영비율)"
    }},
    {{
      "section": 3,
      "type": "next_step",
      "source_from": null,
      "instruction": "추가 질문 유도 (성적 입력 시 합격 가능성 분석 가능)"
    }}
  ]
}}
```

## 규칙
1. 모호한 질문이라도 최선의 계획을 세우세요
2. answer_structure는 최소 1개, 최대 5개 섹션으로 구성
3. empathy 섹션은 항상 첫 번째에 배치
4. fact_check나 analysis가 있으면 반드시 해당 데이터를 가져올 execution_plan이 있어야 함
5. source_from은 execution_plan의 step 번호와 매칭되어야 함 (예: "Step1_Result")
6. agent 필드에는 가용 에이전트 목록에 있는 에이전트 이름만 사용
7. **extracted_scores는 컨설팅 agent 호출 시에만 생성** (다른 경우 필드 자체를 생략)

## 간결성 원칙 (매우 중요!)
- **불필요한 agent 호출 금지**: 간단한 질문에 여러 agent를 호출하지 마세요. 질문의 복잡도에 비례하여 최소한의 agent만 호출하세요.
- **불필요한 섹션 생성 금지**: 단순 인사나 가벼운 질문에 5개 섹션을 모두 채우지 마세요. 필요한 섹션만 간결하게 구성하세요.
- 간단한 질문 = 1~2개 agent, 2~3개 섹션
- 복잡한 비교/분석 질문 = 2개 이상 agent, 3~4개 섹션
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
        model_name="gemini-2.5-flash-lite",
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
            model="gemini-2.5-flash-lite",
            details="실행계획 수립"
        )
    
    result_text = response.text.strip()

    result = parse_orchestration_response(result_text)
    return result


async def run_orchestration_agent(
    message: str, 
    history: List[Dict] = None,
    timing_logger = None
) -> Dict[str, Any]:
    """
    Orchestration Agent 실행 (기본 프롬프트 사용)
    
    Args:
        message: 사용자 질문
        history: 대화 히스토리 (선택)
        timing_logger: 타이밍 로거 (선택)
        
    Returns:
        {
            "user_intent": str,
            "execution_plan": List[Dict],
            "answer_structure": List[Dict]
        }
    """
    import time
    
    # 초상세 타이밍: Orchestration Agent 시작
    orch_timing = None
    llm_call = None
    if timing_logger:
        orch_timing = timing_logger.start_orchestration()
        llm_call = orch_timing.start_llm_call("orch_main", "gemini-2.5-flash-lite")
    
    system_prompt = ORCHESTRATION_SYSTEM_PROMPT.format(
        agents=format_agents_for_prompt()
    )
    
    if timing_logger:
        timing_logger.mark("orch_prompt_ready")
    if llm_call:
        llm_call.mark("prompt_ready")
        llm_call.set_metadata("prompt_length", len(system_prompt) + len(message))

    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",
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
    
    if timing_logger:
        timing_logger.mark("orch_api_sent")
    if llm_call:
        llm_call.mark("api_request_sent")
    
    response = chat_session.send_message(
        message, 
        request_options=genai.types.RequestOptions(
            retry=None,
            timeout=120.0  # 멀티에이전트 파이프라인을 위해 120초로 증가
        )
    )
    
    if timing_logger:
        timing_logger.mark("orch_api_received")
    if llm_call:
        llm_call.mark("api_response_received")
        llm_call.set_metadata("response_length", len(response.text))
    
    # 토큰 사용량 기록
    if hasattr(response, 'usage_metadata'):
        usage = response.usage_metadata
        print(f"💰 토큰 사용량 (orchestration_plan): {usage}")
        
        if llm_call:
            llm_call.set_metadata("token_count", getattr(usage, 'total_token_count', 0))
        
        log_token_usage(
            operation="오케스트레이션_계획",
            prompt_tokens=getattr(usage, 'prompt_token_count', 0),
            output_tokens=getattr(usage, 'candidates_token_count', 0),
            total_tokens=getattr(usage, 'total_token_count', 0),
            model="gemini-2.5-flash-lite",
            details="실행계획 수립"
        )
    
    if llm_call:
        llm_call.mark("response_parsed")
    
    result = parse_orchestration_response(response.text)
    
    if timing_logger:
        timing_logger.mark("orch_parsed")
    if llm_call:
        llm_call.mark("call_complete")
    if orch_timing:
        orch_timing.complete()
    
    # 로그는 호출부(chat.py)에서 출력하므로 여기서는 생략
    
    return result
