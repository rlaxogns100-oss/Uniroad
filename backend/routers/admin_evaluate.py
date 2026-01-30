"""
Admin Evaluate Router
- Admin Agent를 통한 Router 출력 평가 API
- Function 실행 결과 평가 API
- 최종 답변 평가 API
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from services.multi_agent.admin_agent import (
    evaluate_router_output, 
    evaluate_function_result,
    evaluate_final_response
)

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


# ============================================================
# 최종 답변 평가 API
# ============================================================

class EvaluateFinalRequest(BaseModel):
    user_question: str
    conversation_history: List[str] = []
    function_results: Dict[str, Any]
    final_response: str


class EvaluateFinalResponse(BaseModel):
    status: str
    source_accuracy: Dict[str, Any]
    hallucination_check: Dict[str, Any]
    length_check: Dict[str, Any]
    context_relevance: Dict[str, Any]
    format_check: Dict[str, Any]
    overall_comment: str


@router.post("/evaluate-final", response_model=EvaluateFinalResponse)
async def evaluate_final(request: EvaluateFinalRequest):
    """
    최종 답변 평가
    
    Main Agent가 생성한 최종 답변을 LLM으로 평가합니다.
    - 출처 정확성: Function 결과를 정확히 참고하고 출처를 표기하였는가?
    - 할루시네이션: Function 결과에 없는 정보를 지어내지 않았는가?
    - 답변 길이: 너무 짧거나 길지 않은가?
    - 맥락 적절성: 질문과 대화 내역을 고려한 적절한 답변인가?
    - 형식 검증: 답변 형식이 깨지지 않았는가?
    """
    result = await evaluate_final_response(
        user_question=request.user_question,
        conversation_history=request.conversation_history,
        function_results=request.function_results,
        final_response=request.final_response
    )
    
    return EvaluateFinalResponse(
        status=result.get("status", "error"),
        source_accuracy=result.get("source_accuracy", {"valid": False, "comment": "평가 실패"}),
        hallucination_check=result.get("hallucination_check", {"valid": False, "comment": "평가 실패"}),
        length_check=result.get("length_check", {"valid": False, "comment": "평가 실패"}),
        context_relevance=result.get("context_relevance", {"valid": False, "comment": "평가 실패"}),
        format_check=result.get("format_check", {"valid": False, "comment": "평가 실패"}),
        overall_comment=result.get("overall_comment", "평가 실패")
    )
