"""
생기부 평가 API 요청/응답 스키마
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any


class SchoolRecordEvaluateRequest(BaseModel):
    """생기부(세특) 평가 요청"""
    content: str = Field(..., description="세특 초안 (필수)")
    hope_major: Optional[str] = Field(default="", description="희망 전공")
    options: Optional[dict] = Field(default_factory=dict, description="평가 옵션 (추가 기준 등)")


class SchoolRecordEvaluateResponse(BaseModel):
    """생기부 평가 응답"""
    success: bool = True
    message: str = ""
    result: Optional[dict] = None
    scores: Optional[dict] = None
