"""
Multi-Agent Pipeline v2
Router → Functions → Main Agent 구조
- backend/services/multi_agent/ 로 통합됨
"""

import json
import time
from typing import Dict, Any, List

from .router_agent import RouterAgent, route_query
from .admin_agent import AdminAgent, evaluate_router_output, evaluate_function_result
from .functions import execute_function_calls, RAGFunctions
from .main_agent import MainAgent, generate_response as main_agent_generate, generate_response_stream as main_agent_generate_stream

# 기존 chat.py 호환용
AVAILABLE_AGENTS = [
    {"name": "router_agent", "description": "질문을 분석하여 적절한 함수 호출을 결정하는 에이전트"}
]


async def run_orchestration_agent(
    message: str,
    history: List[Dict] = None,
    timing_logger=None,
    user_id: str = None,
    score_id: str = None,
) -> Dict[str, Any]:
    """
    Orchestration Agent 실행 (router_agent 래퍼)
    - 기존 chat.py 호환 유지
    - Router → Functions → Main Agent 파이프라인 실행
    
    Args:
        message: 사용자 질문
        history: 대화 히스토리
        timing_logger: 타이밍 로거 (optional)
        user_id: 사용자 ID (프로필 점수 자동 보완용, optional)
    """
    timing = {"router": 0, "function": 0, "main_agent": 0}
    
    try:
        # 1. router_agent 호출 (user_id 전달)
        print("🔄 [1/3] Router Agent 호출 중...")
        router_start = time.time()
        result = await route_query(message, history, user_id=user_id)
        timing["router"] = round((time.time() - router_start) * 1000)  # ms
        
        # function_calls 추출
        function_calls = result.get("function_calls", [])
        if score_id:
            for call in function_calls:
                if call.get("function") == "consult_jungsi":
                    params = call.setdefault("params", {})
                    params.pop("j_scores", None)
                    params["score_id"] = score_id
        print(f"   ✅ Router 완료: {len(function_calls)}개 함수 호출 ({timing['router']}ms)")
        
        # 2. function_calls 실행 (RAG 검색)
        print("🔄 [2/3] Functions 실행 중...")
        function_results = {}
        func_start = time.time()
        if function_calls:
            try:
                function_results = await execute_function_calls(function_calls, user_id=user_id)
                timing["function"] = round((time.time() - func_start) * 1000)
                print(f"   ✅ Functions 완료: {len(function_results)}개 결과 ({timing['function']}ms)")
            except Exception as func_error:
                timing["function"] = round((time.time() - func_start) * 1000)
                print(f"   ⚠️ Function 실행 오류: {func_error}")
                function_results = {"error": str(func_error)}
        else:
            print("   ℹ️ 함수 호출 없음")
        
        # 3. main_agent 호출 (함수 결과 없어도 일반 대화 처리)
        print("🔄 [3/3] Main Agent 호출 중...")
        main_response = ""
        main_result = {}
        main_start = time.time()
        
        # 함수 결과에 에러가 없으면 main_agent 호출 (빈 결과도 OK - 일반 대화 처리)
        if "error" not in function_results:
            try:
                main_result = await main_agent_generate(message, history, function_results)
                main_response = main_result.get("response", "")
                timing["main_agent"] = round((time.time() - main_start) * 1000)
                print(f"   ✅ Main Agent 완료: {len(main_response)}자 ({timing['main_agent']}ms)")
            except Exception as main_error:
                timing["main_agent"] = round((time.time() - main_start) * 1000)
                print(f"   ⚠️ Main Agent 오류: {main_error}")
                # 폴백: 청크 텍스트 사용
                main_response = _format_chunks_response(function_results)
        else:
            # 에러가 있는 경우만 폴백
            main_response = _format_chunks_response(function_results)
            print(f"   ℹ️ 폴백 사용 (에러 발생)")
        
        # 에러가 있으면 추가
        if "error" in result:
            main_response = f"오류: {result['error']}\n\n{main_response}"
        
        return {
            "router_output": result,  # Router 출력 (function_calls, raw_response, tokens)
            "function_results": function_results,  # 함수 실행 결과
            "main_agent_result": main_result,  # Main Agent 결과 (tokens, citations)
            "direct_response": main_response,  # Main Agent 응답 (채팅창 표시용)
            "timing": timing,  # 단계별 시간 측정 (ms)
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
            "timing": timing,
            # 하위 호환용
            "user_intent": "오류 발생",
            "execution_plan": [],
            "answer_structure": []
        }


def run_orchestration_agent_stream(
    message: str,
    history: List[Dict] = None,
    timing_logger=None,
    user_id: str = None,
    score_id: str = None,
):
    """
    Orchestration Agent 실행 (스트리밍 버전)
    - Router → Functions 후 Main Agent 응답을 스트리밍
    - Generator를 반환 (각 청크는 dict 형태)
    
    Args:
        message: 사용자 질문
        history: 대화 히스토리
        timing_logger: 타이밍 로거 (optional)
        user_id: 사용자 ID (프로필 점수 자동 보완용, optional)
    
    Yields:
        {"type": "status", "step": str, "message": str, "detail": dict}  # 상태 업데이트
        {"type": "chunk", "text": str}  # Main Agent 응답 청크
        {"type": "done", "timing": dict, "function_results": dict}  # 완료
    """
    import asyncio
    
    timing = {"router": 0, "function": 0, "main_agent": 0}
    
    try:
        # 1. Router Agent 호출 (동기적으로 실행, user_id 전달)
        yield {"type": "status", "step": "router", "message": "🔄 [1/3] Router Agent 호출 중..."}
        
        router_start = time.time()
        # 비동기 함수를 동기적으로 실행
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(route_query(message, history, user_id=user_id))
        finally:
            loop.close()
        
        timing["router"] = round((time.time() - router_start) * 1000)
        
        function_calls = result.get("function_calls", [])
        if score_id:
            for call in function_calls:
                if call.get("function") == "consult_jungsi":
                    params = call.setdefault("params", {})
                    params.pop("j_scores", None)
                    params["score_id"] = score_id
        
        # Router 완료 시 검색 쿼리 상세 정보 포함
        queries_detail = []
        for call in function_calls:
            func_name = call.get("function", "")
            params = call.get("params", {})
            if func_name == "univ":
                queries_detail.append({
                    "type": "univ",
                    "university": params.get("university", ""),
                    "query": params.get("query", "")
                })
            elif func_name == "consult":
                queries_detail.append({
                    "type": "consult",
                    "target_univ": params.get("target_univ", []),
                    "query": "성적 분석"
                })
        
        yield {
            "type": "status", 
            "step": "router_complete", 
            "message": f"✅ Router 완료: {len(function_calls)}개 함수 호출 ({timing['router']}ms)",
            "detail": {
                "function_calls": queries_detail,
                "count": len(function_calls)
            }
        }
        
        # 2. Functions 실행 (RAG 검색)
        yield {"type": "status", "step": "function", "message": "🔄 [2/3] Functions 실행 중..."}
        
        function_results = {}
        func_start = time.time()
        
        if function_calls:
            try:
                # 검색 시작 상세 정보 전송
                for idx, call in enumerate(function_calls):
                    func_name = call.get("function", "")
                    params = call.get("params", {})
                    if func_name == "univ":
                        yield {
                            "type": "status",
                            "step": "search_start",
                            "message": f"🔍 검색 중: {params.get('university', '')}",
                            "detail": {
                                "index": idx,
                                "university": params.get("university", ""),
                                "query": params.get("query", "")
                            }
                        }
                    elif func_name == "consult":
                        yield {
                            "type": "status",
                            "step": "search_start",
                            "message": "📊 성적 분석 중...",
                            "detail": {
                                "index": idx,
                                "type": "consult",
                                "target_univ": params.get("target_univ", [])
                            }
                        }
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    function_results = loop.run_until_complete(
                        execute_function_calls(function_calls, user_id=user_id)
                    )
                finally:
                    loop.close()
                
                timing["function"] = round((time.time() - func_start) * 1000)
                
                # 검색 완료 상세 정보 추출 (찾은 문서 목록)
                search_results_detail = []
                for key, func_result in function_results.items():
                    if isinstance(func_result, dict) and "chunks" in func_result:
                        university = func_result.get("university", "")
                        doc_titles = func_result.get("document_titles", {})
                        doc_count = func_result.get("count", 0)
                        
                        # 중복 제거된 문서 제목 리스트
                        unique_titles = list(set(doc_titles.values())) if doc_titles else []
                        
                        search_results_detail.append({
                            "university": university,
                            "query": func_result.get("query", ""),
                            "doc_count": doc_count,
                            "documents": unique_titles[:5]  # 최대 5개 문서 제목
                        })
                
                yield {
                    "type": "status", 
                    "step": "search_complete", 
                    "message": f"✅ Functions 완료: {len(function_results)}개 결과 ({timing['function']}ms)",
                    "detail": {
                        "results": search_results_detail,
                        "total_count": sum(r.get("doc_count", 0) for r in search_results_detail)
                    }
                }
            except Exception as func_error:
                timing["function"] = round((time.time() - func_start) * 1000)
                yield {"type": "status", "step": "function", "message": f"⚠️ Function 오류: {func_error}"}
                function_results = {"error": str(func_error)}
        else:
            yield {"type": "status", "step": "function", "message": "ℹ️ 함수 호출 없음"}
        
        # 3. Main Agent 스트리밍 호출
        yield {"type": "status", "step": "main_agent", "message": "🔄 [3/3] Main Agent 응답 생성 중..."}
        
        main_start = time.time()
        full_response = ""
        
        if "error" not in function_results:
            try:
                # 스트리밍으로 Main Agent 호출
                for chunk in main_agent_generate_stream(message, history, function_results):
                    full_response += chunk
                    yield {"type": "chunk", "text": chunk}
                
                timing["main_agent"] = round((time.time() - main_start) * 1000)
                yield {"type": "status", "step": "main_agent", "message": f"✅ Main Agent 완료: {len(full_response)}자 ({timing['main_agent']}ms)"}
                
            except Exception as main_error:
                timing["main_agent"] = round((time.time() - main_start) * 1000)
                yield {"type": "status", "step": "main_agent", "message": f"⚠️ Main Agent 오류: {main_error}"}
                full_response = _format_chunks_response(function_results)
                yield {"type": "chunk", "text": full_response}
        else:
            full_response = _format_chunks_response(function_results)
            yield {"type": "chunk", "text": full_response}
        
        # sources 및 source_urls 추출
        sources = []
        source_urls = []
        used_chunks = []
        
        for key, func_result in function_results.items():
            if isinstance(func_result, dict) and "chunks" in func_result:
                doc_titles = func_result.get("document_titles", {})
                doc_urls = func_result.get("document_urls", {})
                
                for chunk in func_result.get("chunks", []):
                    doc_id = chunk.get("document_id")
                    page = chunk.get("page_number", "")
                    title = doc_titles.get(doc_id, f"문서 {doc_id}")
                    url = doc_urls.get(doc_id, "")
                    
                    source_info = f"{title} {page}p" if page else title
                    sources.append(source_info)
                    source_urls.append(url)
                    
                    used_chunks.append({
                        "id": chunk.get("id", ""),
                        "content": chunk.get("content", "")[:200],  # 미리보기
                        "title": title,
                        "source": source_info,
                        "file_url": url
                    })
        
        # 완료
        yield {
            "type": "done",
            "timing": timing,
            "function_results": function_results,
            "router_output": result,
            "response": full_response,
            "sources": sources,
            "source_urls": source_urls,
            "used_chunks": used_chunks
        }
        
    except Exception as e:
        print(f"❌ 스트리밍 파이프라인 오류: {e}")
        yield {"type": "error", "message": str(e)}


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
    "main_agent_generate_stream",
    "AVAILABLE_AGENTS",
    "run_orchestration_agent",
    "run_orchestration_agent_stream",
    "execute_sub_agents",
    "generate_final_answer",
    "get_agent",
    "orchestration_agent",
    "sub_agents",
    "final_agent",
    "execute_function_calls",
    "RAGFunctions",
]
