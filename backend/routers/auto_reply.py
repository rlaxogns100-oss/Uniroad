"""
자동 댓글 봇 관리 API 라우터
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services.bot_manager import get_bot_manager

router = APIRouter()


class BotConfigUpdate(BaseModel):
    """봇 설정 업데이트 요청"""
    min_delay_seconds: Optional[int] = None
    comments_per_hour_min: Optional[int] = None
    comments_per_hour_max: Optional[int] = None
    rest_minutes: Optional[int] = None


class BotActionResponse(BaseModel):
    """봇 액션 응답"""
    success: bool
    message: str
    pid: Optional[int] = None


@router.get("/status")
async def get_bot_status():
    """
    봇 상태 조회
    
    Returns:
        running: 실행 중 여부
        pid: 프로세스 ID
        cookie_exists: 쿠키 파일 존재 여부
        config: 현재 설정
    """
    manager = get_bot_manager()
    return manager.get_status()


@router.post("/start", response_model=BotActionResponse)
async def start_bot():
    """
    봇 시작
    
    쿠키 파일이 존재해야 시작 가능합니다.
    """
    manager = get_bot_manager()
    result = manager.start()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/stop", response_model=BotActionResponse)
async def stop_bot():
    """
    봇 중지
    
    Graceful shutdown을 시도합니다.
    """
    manager = get_bot_manager()
    result = manager.stop()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.get("/config")
async def get_bot_config():
    """
    봇 설정 조회
    """
    manager = get_bot_manager()
    return manager.get_config()


@router.post("/config")
async def update_bot_config(config: BotConfigUpdate):
    """
    봇 설정 업데이트
    
    실행 중인 봇에도 다음 사이클에 적용됩니다.
    """
    manager = get_bot_manager()
    
    # None이 아닌 값만 업데이트
    update_data = {k: v for k, v in config.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="업데이트할 설정이 없습니다.")
    
    result = manager.update_config(update_data)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result


@router.get("/comments")
async def get_comments(limit: int = 100, offset: int = 0):
    """
    댓글 기록 조회
    
    Args:
        limit: 조회할 최대 개수 (기본 100)
        offset: 시작 위치 (기본 0)
    
    Returns:
        comments: 댓글 기록 리스트 (원글/쿼리/함수결과 포함)
        total: 전체 개수
    """
    if limit > 500:
        limit = 500
    if limit < 1:
        limit = 1
    if offset < 0:
        offset = 0
    
    manager = get_bot_manager()
    return manager.get_comments(limit=limit, offset=offset)


class PromptsUpdate(BaseModel):
    """프롬프트 업데이트 요청"""
    query_prompt: Optional[str] = None
    answer_prompt: Optional[str] = None


@router.get("/prompts")
async def get_prompts():
    """
    봇 Query/Answer Agent 프롬프트 조회.
    bot_prompts.json에 저장된 값 반환. 없으면 빈 문자열.
    """
    manager = get_bot_manager()
    return manager.get_prompts()


@router.post("/prompts")
async def update_prompts(body: PromptsUpdate):
    """
    봇 Query/Answer Agent 프롬프트 저장.
    다음 사이클부터 봇이 이 프롬프트를 사용합니다.
    """
    manager = get_bot_manager()
    result = manager.update_prompts(body.model_dump(exclude_none=True))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "저장 실패"))
    return result
