"""
Admin Evaluate Router
- Admin Agent를 통한 Router 출력 평가 API
- Function 실행 결과 평가 API
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from services.multi_agent.admin_agent import evaluate_router_output, evaluate_function_result

router = APIRouter()


class EvaluateRequest(BaseModel):
    user_question: str
    router_output: str  # JSON 문자열로 받음


class EvaluateResponse(BaseModel):
    status: str
    format_check: Dict[str, Any]
    function_check: Dict[str, Any]
    params_check: Dict[str, Any]
    overall_comment: str


class EvaluateFunctionRequest(BaseModel):
    user_question: str
    function_calls: List[Dict[str, Any]]
    function_results: Dict[str, Any]


class EvaluateFunctionResponse(BaseModel):
    status: str
    comment: str
    details: Dict[str, Any]
    total_chunks: int


@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate(request: EvaluateRequest):
    """
    Router 출력 평가
    
    Admin Agent가 Router 출력을 평가하여 품질 점검 결과를 반환합니다.
    """
    result = await evaluate_router_output(
        user_question=request.user_question,
        router_output=request.router_output
    )
    
    return EvaluateResponse(
        status=result.get("status", "error"),
        format_check=result.get("format_check", {"valid": False, "comment": "평가 실패"}),
        function_check=result.get("function_check", {"valid": False, "comment": "평가 실패"}),
        params_check=result.get("params_check", {"valid": False, "comment": "평가 실패"}),
        overall_comment=result.get("overall_comment", "평가 실패")
    )


@router.post("/evaluate-function", response_model=EvaluateFunctionResponse)
async def evaluate_function(request: EvaluateFunctionRequest):
    """
    Function 실행 결과 평가
    
    function_calls 실행 결과를 평가하여 품질 점검 결과를 반환합니다.
    """
    result = await evaluate_function_result(
        user_question=request.user_question,
        function_calls=request.function_calls,
        function_results=request.function_results
    )
    
    return EvaluateFunctionResponse(
        status=result.get("status", "error"),
        comment=result.get("comment", "평가 실패"),
        details=result.get("details", {}),
        total_chunks=result.get("total_chunks", 0)
    )
