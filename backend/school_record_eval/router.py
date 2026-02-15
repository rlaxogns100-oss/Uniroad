"""
생기부 평가 API 라우터

- prefix: /api/school-record (main.py에서 지정)
- 기존 라우터와 경로/이름 충돌 없음
"""
from fastapi import APIRouter, HTTPException

from .models import SchoolRecordEvaluateRequest, SchoolRecordEvaluateResponse
from .service import evaluate_school_record

router = APIRouter()


@router.get("/health")
async def health():
    """생기부 평가 모듈 헬스 체크"""
    return {"status": "ok", "module": "school_record_eval"}


@router.post("/evaluate", response_model=SchoolRecordEvaluateResponse)
async def evaluate(request: SchoolRecordEvaluateRequest):
    """
    생기부 텍스트를 평가합니다.

    - content: 평가할 생기부 원문 또는 구조화 데이터
    - options: 평가 옵션 (대학/전형 등)
    """
    try:
        result = await evaluate_school_record(request)
        return SchoolRecordEvaluateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"생기부 평가 처리 중 오류: {str(e)}")
