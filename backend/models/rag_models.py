"""
RAG 관련 Pydantic 모델
"""
from pydantic import BaseModel, Field
from typing import List


class ClassificationResult(BaseModel):
    """문서 분류 결과"""
    category: str = Field(description="문서 카테고리")
    confidence: float = Field(ge=0.0, le=1.0, description="신뢰도 (0~1)")
    reason: str = Field(description="분류 이유")
    keywords: List[str] = Field(default_factory=list, description="키워드 목록")
