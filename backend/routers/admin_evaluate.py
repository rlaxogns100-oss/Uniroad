"""
Admin Evaluate Router
- Admin Agent를 통한 Router 출력 평가 API
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
import sys
import os

# 루트의 multi_agent 폴더를 import 경로에 추가
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from multi_agent.admin_agent import evaluate_router_output

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
