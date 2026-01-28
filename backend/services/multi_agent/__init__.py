"""
Multi-Agent Pipeline v2
Router → Functions → Main Agent 구조
- backend/services/multi_agent/ 로 통합됨
"""

import json
from typing import Dict, Any, List

from .router_agent import RouterAgent, route_query
from .admin_agent import AdminAgent, evaluate_router_output, evaluate_function_result
from .functions import execute_function_calls, RAGFunctions

# 기존 chat.py 호환용
AVAILABLE_AGENTS = [
    {"name": "router_agent", "description": "질문을 분석하여 적절한 함수 호출을 결정하는 에이전트"}
]


async def run_orchestration_agent(message: str, history: List[Dict] = None, timing_logger=None) -> Dict[str, Any]:
    """
    Orchestration Agent 실행 (router_agent 래퍼)
    - 기존 chat.py 호환 유지
    - function_calls 실행 후 청크 데이터를 direct_response로 반환
    """
    try:
        # 1. router_agent 호출
        result = await route_query(message, history)
        
        # function_calls 추출
        function_calls = result.get("function_calls", [])
        
        # 2. function_calls 실행 (RAG 검색)
        function_results = {}
        if function_calls:
            try:
                function_results = await execute_function_calls(function_calls)
            except Exception as func_error:
                print(f"⚠️ Function 실행 오류: {func_error}")
                function_results = {"error": str(func_error)}
        
        # 3. 청크 데이터를 direct_response로 포맷팅
        chunks_text = _format_chunks_response(function_results)
        
        # 에러가 있으면 추가
        if "error" in result:
            chunks_text = f"오류: {result['error']}\n\n{chunks_text}"
        
        return {
            "user_intent": "router_agent 테스트",
            "execution_plan": [],
            "answer_structure": [],
            "direct_response": chunks_text,  # 청크 데이터로 변경
            "extracted_scores": {},
            "router_result": result,  # 원본 결과
            "function_results": function_results  # 함수 실행 결과 추가
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "user_intent": "오류 발생",
            "execution_plan": [],
            "answer_structure": [],
            "direct_response": f"Router Agent 오류: {str(e)}",
            "function_results": {}
        }


def _format_chunks_response(function_results: Dict[str, Any]) -> str:
    """
    function_results를 읽기 쉬운 텍스트로 포맷팅
    """
    if not function_results:
        return "검색 결과가 없습니다."
    
    if "error" in function_results:
        return f"검색 오류: {function_results['error']}"
    
    output_lines = []
    
    for key, result in function_results.items():
        if isinstance(result, dict) and "chunks" in result:
            university = result.get("university", "")
            query = result.get("query", "")
            count = result.get("count", 0)
            
            output_lines.append(f"## {university} 검색 결과 ({count}개)")
            output_lines.append(f"검색어: {query}\n")
            
            for i, chunk in enumerate(result.get("chunks", []), 1):
                page = chunk.get("page_number", "?")
                score = chunk.get("score", 0)
                content = chunk.get("content", "")
                
                # 청크 내용 표시 (최대 500자)
                content_preview = content[:500] + "..." if len(content) > 500 else content
                
                output_lines.append(f"### [{i}] 페이지 {page} (유사도: {score:.3f})")
                output_lines.append(content_preview)
                output_lines.append("")
        
        elif isinstance(result, dict) and result.get("status") == "not_implemented":
            output_lines.append(f"## {key}: 미구현 함수")
        
        elif isinstance(result, dict) and "error" in result:
            output_lines.append(f"## {key}: 오류 - {result['error']}")
    
    return "\n".join(output_lines) if output_lines else "검색 결과가 없습니다."


async def execute_sub_agents(execution_plan, context, timing_logger=None) -> Dict[str, Any]:
    """Sub Agents 실행 (router_agent 모드에서는 사용하지 않음)"""
    return {}


async def generate_final_answer(
    message: str,
    orchestration_result: Dict,
    sub_agent_results: Dict,
    history: List[Dict] = None,
    timing_logger=None
) -> Dict[str, Any]:
    """Final Answer 생성 (router_agent 모드에서는 direct_response 사용)"""
    return {
        "final_answer": "",
        "raw_answer": "",
        "sources": [],
        "source_urls": [],
        "used_chunks": [],
        "metadata": {}
    }


def get_agent(name: str):
    """에이전트 가져오기"""
    return None


# ============================================================
# 더미 모듈 객체 (chat.py 호환용)
# - chat.py에서 orchestration_agent.set_log_callback() 등 호출
# - router_agent 모드에서는 실제로 사용하지 않음
# ============================================================
class _DummyModule:
    """set_log_callback 호출을 무시하는 더미 모듈"""
    def set_log_callback(self, callback):
        pass

orchestration_agent = _DummyModule()
sub_agents = _DummyModule()
final_agent = _DummyModule()


__all__ = [
    "RouterAgent",
    "route_query",
    "AdminAgent",
    "evaluate_router_output",
    "evaluate_function_result",
    "AVAILABLE_AGENTS",
    "run_orchestration_agent",
    "execute_sub_agents",
    "generate_final_answer",
    "get_agent",
    "orchestration_agent",
    "sub_agents",
    "final_agent",
    "execute_function_calls",
    "RAGFunctions",
]
