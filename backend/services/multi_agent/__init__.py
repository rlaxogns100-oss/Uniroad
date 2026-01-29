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
from .main_agent import MainAgent, generate_response as main_agent_generate

# 기존 chat.py 호환용
AVAILABLE_AGENTS = [
    {"name": "router_agent", "description": "질문을 분석하여 적절한 함수 호출을 결정하는 에이전트"}
]


async def run_orchestration_agent(message: str, history: List[Dict] = None, timing_logger=None) -> Dict[str, Any]:
    """
    Orchestration Agent 실행 (router_agent 래퍼)
    - 기존 chat.py 호환 유지
    - Router → Functions → Main Agent 파이프라인 실행
    """
    try:
        # 1. router_agent 호출
        print("🔄 [1/3] Router Agent 호출 중...")
        result = await route_query(message, history)
        
        # function_calls 추출
        function_calls = result.get("function_calls", [])
        print(f"   ✅ Router 완료: {len(function_calls)}개 함수 호출")
        
        # 2. function_calls 실행 (RAG 검색)
        print("🔄 [2/3] Functions 실행 중...")
        function_results = {}
        if function_calls:
            try:
                function_results = await execute_function_calls(function_calls)
                print(f"   ✅ Functions 완료: {len(function_results)}개 결과")
            except Exception as func_error:
                print(f"   ⚠️ Function 실행 오류: {func_error}")
                function_results = {"error": str(func_error)}
        else:
            print("   ℹ️ 함수 호출 없음")
        
        # 3. main_agent 호출 (NEW!)
        print("🔄 [3/3] Main Agent 호출 중...")
        main_response = ""
        main_result = {}
        
        if function_results and "error" not in function_results:
            try:
                main_result = await main_agent_generate(message, history, function_results)
                main_response = main_result.get("response", "")
                print(f"   ✅ Main Agent 완료: {len(main_response)}자")
            except Exception as main_error:
                print(f"   ⚠️ Main Agent 오류: {main_error}")
                # 폴백: 청크 텍스트 사용
                main_response = _format_chunks_response(function_results)
        else:
            # 함수 결과 없거나 에러 시 폴백
            main_response = _format_chunks_response(function_results)
            print(f"   ℹ️ 폴백 사용 (청크 텍스트)")
        
        # 에러가 있으면 추가
        if "error" in result:
            main_response = f"오류: {result['error']}\n\n{main_response}"
        
        return {
            "router_output": result,  # Router 출력 (function_calls, raw_response, tokens)
            "function_results": function_results,  # 함수 실행 결과
            "main_agent_result": main_result,  # Main Agent 결과 (tokens, citations)
            "direct_response": main_response,  # Main Agent 응답 (채팅창 표시용)
            # 하위 호환용 레거시 필드
            "user_intent": "router_agent",
            "execution_plan": [],
            "answer_structure": [],
            "extracted_scores": {}
        }
        
    except Exception as e:
        print(f"❌ 파이프라인 오류: {e}")
        return {
            "error": str(e),
            "router_output": {"error": str(e)},
            "function_results": {},
            "main_agent_result": {},
            "direct_response": f"파이프라인 오류: {str(e)}",
            # 하위 호환용
            "user_intent": "오류 발생",
            "execution_plan": [],
            "answer_structure": []
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
    "MainAgent",
    "main_agent_generate",
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
