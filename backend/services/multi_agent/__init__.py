"""
Multi-Agent 호환 레이어
- 루트의 multi_agent/router_agent.py를 사용
- chat.py의 기존 인터페이스 유지
"""

import sys
import os
import json
from typing import Dict, Any, List

# 루트의 multi_agent 폴더를 import 경로에 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, ROOT_DIR)

from multi_agent.router_agent import route_query, RouterAgent

# chat.py에서 사용하는 상수
AVAILABLE_AGENTS = [
    {"name": "router_agent", "description": "질문을 분석하여 적절한 함수 호출을 결정하는 에이전트"}
]


async def run_orchestration_agent(
    message: str,
    history: List[Dict] = None,
    timing_logger=None
) -> Dict[str, Any]:
    """
    Orchestration Agent 대체
    - router_agent를 호출하고 결과를 direct_response로 반환
    - chat.py가 Sub Agents와 Final Agent를 건너뛰고 즉시 응답
    """
    try:
        # router_agent 호출
        result = await route_query(message, history)
        
        # function_calls만 추출 (토큰 정보 제외)
        function_calls = result.get("function_calls", [])
        
        # 보기 좋게 포맷팅
        if function_calls:
            formatted_output = json.dumps(
                {"function_calls": function_calls},
                ensure_ascii=False,
                indent=2
            )
        else:
            formatted_output = "함수 호출 없음"
        
        # 에러가 있으면 표시
        if "error" in result:
            formatted_output = f"오류: {result['error']}\n\n{formatted_output}"
        
        return {
            "user_intent": "router_agent 테스트",
            "execution_plan": [],
            "answer_structure": [],
            "direct_response": formatted_output,  # 즉시 응답으로 처리
            "extracted_scores": {},
            "router_result": result  # 디버깅용 원본
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "user_intent": "오류 발생",
            "execution_plan": [],
            "answer_structure": [],
            "direct_response": f"Router Agent 오류: {str(e)}"
        }


async def execute_sub_agents(
    execution_plan: List[Dict],
    extracted_scores: Dict = None,
    user_message: str = "",
    timing_logger=None
) -> Dict[str, Any]:
    """
    Sub Agents 실행 (현재는 스킵)
    - direct_response 모드에서는 호출되지 않음
    """
    return {}


async def generate_final_answer(
    user_question: str,
    answer_structure: List[Dict],
    sub_agent_results: Dict[str, Any],
    history: List[Dict] = None,
    timing_logger=None
) -> Dict[str, Any]:
    """
    Final Agent 실행 (현재는 스킵)
    - direct_response 모드에서는 호출되지 않음
    """
    return {
        "final_answer": "",
        "raw_answer": "",
        "sources": [],
        "source_urls": [],
        "used_chunks": [],
        "metadata": {}
    }


def get_agent(name: str):
    """에이전트 조회 (호환성용)"""
    return None


__all__ = [
    "run_orchestration_agent",
    "execute_sub_agents",
    "get_agent",
    "generate_final_answer",
    "AVAILABLE_AGENTS",
]
