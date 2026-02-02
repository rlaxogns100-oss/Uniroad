"""
Functions API 라우터
- execute_function_calls: RAG 함수 실행 (univ, consult)
- route_query: Router Agent를 통한 질문 라우팅
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from services.multi_agent.functions import execute_function_calls
from services.multi_agent.router_agent import route_query

router = APIRouter()


class FunctionCall(BaseModel):
    function: str
    params: Dict[str, Any]


class ExecuteRequest(BaseModel):
    """execute_function_calls 요청 모델"""
    function_calls: List[FunctionCall]


class RouteRequest(BaseModel):
    """route_query 요청 모델"""
    message: str
    history: Optional[List[Dict[str, Any]]] = None


class ExecuteResponse(BaseModel):
    """execute_function_calls 응답 모델"""
    results: Dict[str, Any]
    success: bool
    error: Optional[str] = None


class RouteResponse(BaseModel):
    """route_query 응답 모델"""
    function_calls: List[Dict[str, Any]]
    raw_response: Optional[str] = None
    tokens: Optional[Dict[str, int]] = None
    error: Optional[str] = None


@router.post("/execute", response_model=ExecuteResponse)
async def execute_functions(request: ExecuteRequest):
    """
    RAG 함수 실행 API
    
    - univ: 대학 입시 정보 검색
    - consult: 성적 기반 합격 가능성 분석
    
    Example Request:
    ```json
    {
        "function_calls": [
            {"function": "univ", "params": {"university": "서울대학교", "query": "2026 정시"}}
        ]
    }
    ```
    
    Example Response:
    ```json
    {
        "results": {
            "univ_0": {
                "chunks": [...],
                "count": 10,
                "university": "서울대학교",
                "query": "2026 정시"
            }
        },
        "success": true
    }
    ```
    """
    try:
        # Pydantic 모델을 dict로 변환
        function_calls = [call.model_dump() for call in request.function_calls]
        
        # 함수 실행
        results = await execute_function_calls(function_calls)
        
        return ExecuteResponse(
            results=results,
            success=True
        )
    
    except Exception as e:
        print(f"❌ execute_functions 오류: {e}")
        import traceback
        traceback.print_exc()
        return ExecuteResponse(
            results={},
            success=False,
            error=str(e)
        )


@router.post("/route", response_model=RouteResponse)
async def route_message(request: RouteRequest):
    """
    Router Agent를 통한 질문 라우팅 API
    
    사용자 질문을 분석하여 적절한 함수 호출을 결정합니다.
    
    Example Request:
    ```json
    {
        "message": "서울대 기계공학과 정시 전형 알려줘",
        "history": []
    }
    ```
    
    Example Response:
    ```json
    {
        "function_calls": [
            {"function": "univ", "params": {"university": "서울대학교", "query": "2026 기계공학부 정시"}}
        ],
        "tokens": {"in": 500, "out": 100, "total": 600}
    }
    ```
    """
    try:
        result = await route_query(
            message=request.message,
            history=request.history
        )
        
        return RouteResponse(
            function_calls=result.get("function_calls", []),
            raw_response=result.get("raw_response"),
            tokens=result.get("tokens"),
            error=result.get("error")
        )
    
    except Exception as e:
        print(f"❌ route_message 오류: {e}")
        import traceback
        traceback.print_exc()
        return RouteResponse(
            function_calls=[],
            error=str(e)
        )


@router.post("/pipeline")
async def run_pipeline(request: RouteRequest):
    """
    전체 파이프라인 실행 API (route + execute 통합)
    
    1. Router Agent로 함수 호출 결정
    2. 결정된 함수 실행
    3. 결과 반환
    
    Example Request:
    ```json
    {
        "message": "서울대 기계공학과 정시 전형 알려줘",
        "history": []
    }
    ```
    """
    try:
        # 1. Router Agent 실행
        route_result = await route_query(
            message=request.message,
            history=request.history
        )
        
        function_calls = route_result.get("function_calls", [])
        
        if not function_calls:
            return {
                "success": True,
                "router_output": route_result,
                "function_results": {},
                "message": "함수 호출이 필요하지 않습니다."
            }
        
        # 2. 함수 실행
        function_results = await execute_function_calls(function_calls)
        
        return {
            "success": True,
            "router_output": route_result,
            "function_results": function_results
        }
    
    except Exception as e:
        print(f"❌ run_pipeline 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, str(e))
