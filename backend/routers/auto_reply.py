"""
자동 댓글 봇 관리 API 라우터
멀티 카페 지원: 각 카페별로 독립된 봇 관리
계정 분리: 탭(카페)과 계정을 분리하여 각 탭에서 계정을 선택 가능
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import asyncio
import os
from services.bot_manager import get_bot_manager, get_supported_cafes, SUPPORTED_CAFES, ACCOUNTS

router = APIRouter()


class BotConfigUpdate(BaseModel):
    """봇 설정 업데이트 요청"""
    min_delay_seconds: Optional[int] = None
    comments_per_hour_min: Optional[int] = None
    comments_per_hour_max: Optional[int] = None
    rest_minutes: Optional[int] = None
    keywords: Optional[List[str]] = None


class BotStartRequest(BaseModel):
    """봇 시작 요청"""
    dry_run: bool = False
    account_id: Optional[str] = None


class BotActionResponse(BaseModel):
    """봇 액션 응답"""
    success: bool
    message: str
    pid: Optional[int] = None


# ==========================================
# 카페 목록 API
# ==========================================

@router.get("/cafes")
async def list_cafes():
    """
    지원하는 카페 목록 조회
    
    Returns:
        cafes: 카페 ID와 이름 목록
    """
    return {"cafes": SUPPORTED_CAFES}


@router.get("/accounts")
async def list_accounts():
    """
    사용 가능한 계정 목록 조회
    
    Returns:
        accounts: 계정 ID와 이름 목록
    """
    # 아무 카페나 선택해서 계정 목록 가져오기 (계정은 공통)
    manager = get_bot_manager("suhui")
    return {"accounts": manager.get_available_accounts()}


# ==========================================
# 카페별 봇 관리 API
# ==========================================

@router.get("/{cafe_id}/status")
async def get_bot_status(cafe_id: str):
    """
    봇 상태 조회
    
    Returns:
        running: 실행 중 여부
        pid: 프로세스 ID
        cookie_exists: 쿠키 파일 존재 여부
        config: 현재 설정
    """
    manager = get_bot_manager(cafe_id)
    return manager.get_status()


@router.post("/{cafe_id}/start", response_model=BotActionResponse)
async def start_bot(cafe_id: str, request: BotStartRequest = BotStartRequest()):
    """
    봇 시작
    
    Args:
        request.dry_run: True면 가실행 모드 (댓글 생성만 하고 실제로 달지 않음)
        request.account_id: 사용할 계정 ID (없으면 현재 선택된 계정 사용)
    
    쿠키 파일이 존재해야 시작 가능합니다.
    """
    manager = get_bot_manager(cafe_id)
    result = manager.start(dry_run=request.dry_run, account_id=request.account_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.post("/{cafe_id}/stop", response_model=BotActionResponse)
async def stop_bot(cafe_id: str):
    """
    봇 중지
    
    Graceful shutdown을 시도합니다.
    """
    manager = get_bot_manager(cafe_id)
    result = manager.stop()
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return result


@router.get("/{cafe_id}/config")
async def get_bot_config(cafe_id: str):
    """
    봇 설정 조회
    """
    manager = get_bot_manager(cafe_id)
    return manager.get_config()


@router.post("/{cafe_id}/config")
async def update_bot_config(cafe_id: str, config: BotConfigUpdate):
    """
    봇 설정 업데이트
    
    실행 중인 봇에도 다음 사이클에 적용됩니다.
    """
    manager = get_bot_manager(cafe_id)
    
    # None이 아닌 값만 업데이트
    update_data = {k: v for k, v in config.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="업데이트할 설정이 없습니다.")
    
    result = manager.update_config(update_data)
    
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result["message"])
    
    return result


@router.get("/{cafe_id}/comments")
async def get_comments(cafe_id: str, limit: int = 100, offset: int = 0):
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
    
    manager = get_bot_manager(cafe_id)
    return manager.get_comments(limit=limit, offset=offset)


class PromptsUpdate(BaseModel):
    """프롬프트 업데이트 요청"""
    query_prompt: Optional[str] = None
    answer_prompt: Optional[str] = None


class TestRequest(BaseModel):
    """테스트 요청"""
    post_content: str


@router.get("/{cafe_id}/prompts")
async def get_prompts(cafe_id: str):
    """
    봇 Query/Answer Agent 프롬프트 조회.
    bot_prompts.json에 저장된 값 반환. 없으면 빈 문자열.
    """
    manager = get_bot_manager(cafe_id)
    return manager.get_prompts()


@router.post("/{cafe_id}/prompts")
async def update_prompts(cafe_id: str, body: PromptsUpdate):
    """
    봇 Query/Answer Agent 프롬프트 저장.
    다음 사이클부터 봇이 이 프롬프트를 사용합니다.
    """
    manager = get_bot_manager(cafe_id)
    result = manager.update_prompts(body.model_dump(exclude_none=True))
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "저장 실패"))
    return result


@router.post("/{cafe_id}/test")
async def test_generate_reply(cafe_id: str, body: TestRequest):
    """
    테스트용 댓글 생성 (Query Agent -> RAG -> Answer Agent 파이프라인)
    
    원글을 입력받아 전체 파이프라인을 실행하고 결과를 반환합니다.
    실제 댓글을 달지 않고 결과만 확인할 수 있습니다.
    
    Args:
        post_content: 테스트할 게시글 내용 (첫 줄: 제목, 나머지: 본문)
    
    Returns:
        query: Query Agent가 생성한 function_calls
        function_result: RAG 검색 결과
        answer: Answer Agent가 생성한 최종 답변
    """
    if not body.post_content or not body.post_content.strip():
        raise HTTPException(status_code=400, detail="게시글 내용을 입력해주세요.")
    
    manager = get_bot_manager(cafe_id)
    result = await manager.test_generate_reply(body.post_content)
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message", "테스트 실행 실패"))
    
    return result


class SkipLinkRequest(BaseModel):
    """스킵 링크 추가/삭제 요청"""
    url: str


@router.get("/{cafe_id}/skip-links")
async def get_skip_links(cafe_id: str):
    """
    수동 스킵 링크 목록 조회
    """
    manager = get_bot_manager(cafe_id)
    return manager.get_skip_links()


@router.post("/{cafe_id}/skip-links")
async def add_skip_link(cafe_id: str, body: SkipLinkRequest):
    """
    수동 스킵 링크 추가 (중복 댓글 방지용)
    
    브라우저 URL 형식도 지원합니다:
    - https://cafe.naver.com/suhui/29429119
    - https://cafe.naver.com/f-e/cafes/10197921/articles/29429119
    """
    if not body.url or not body.url.strip():
        raise HTTPException(status_code=400, detail="URL을 입력해주세요.")
    
    manager = get_bot_manager(cafe_id)
    result = manager.add_skip_link(body.url.strip())
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "추가 실패"))
    
    return result


@router.delete("/{cafe_id}/skip-links")
async def remove_skip_link(cafe_id: str, body: SkipLinkRequest):
    """
    수동 스킵 링크 삭제
    """
    if not body.url or not body.url.strip():
        raise HTTPException(status_code=400, detail="URL을 입력해주세요.")
    
    manager = get_bot_manager(cafe_id)
    result = manager.remove_skip_link(body.url.strip())
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "삭제 실패"))
    
    return result


@router.get("/{cafe_id}/logs/stream")
async def stream_logs(cafe_id: str):
    """
    실시간 로그 스트리밍 (Server-Sent Events)
    
    봇이 실행 중일 때 bot.log 파일의 새로운 내용을 실시간으로 스트리밍합니다.
    
    Returns:
        StreamingResponse: text/event-stream 형식의 실시간 로그
    """
    async def log_generator():
        manager = get_bot_manager(cafe_id)
        bot_log_file = os.path.join(manager.bot_dir, "bot.log")
        last_position = 0
        
        # 파일이 없으면 생성될 때까지 대기
        while not os.path.exists(bot_log_file):
            await asyncio.sleep(1)
        
        # 기존 로그 전체 전송
        try:
            with open(bot_log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                last_position = f.tell()
                for line in lines[-100:]:  # 최근 100줄만
                    yield f"data: {line.rstrip()}\n\n"
        except Exception as e:
            yield f"data: [로그 읽기 오류: {e}]\n\n"
        
        # 새로운 로그 실시간 스트리밍
        while True:
            try:
                if os.path.exists(bot_log_file):
                    with open(bot_log_file, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(last_position)
                        new_lines = f.readlines()
                        last_position = f.tell()
                        
                        for line in new_lines:
                            yield f"data: {line.rstrip()}\n\n"
                
                await asyncio.sleep(0.5)  # 0.5초마다 체크
            except Exception as e:
                yield f"data: [스트리밍 오류: {e}]\n\n"
                await asyncio.sleep(1)
    
    return StreamingResponse(
        log_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # nginx buffering 비활성화
        }
    )


# ==========================================
# 반자동 시스템 API 엔드포인트
# ==========================================

class CommentEditRequest(BaseModel):
    """댓글 수정 요청"""
    new_comment: str

class CommentCancelRequest(BaseModel):
    """댓글 취소 요청"""
    reason: str


@router.post("/{cafe_id}/comments/{comment_id}/approve")
async def approve_comment(cafe_id: str, comment_id: str):
    """
    댓글 승인 - 게시 대기열에 추가
    
    승인된 댓글은 게시 워커가 실행 중일 때 딜레이를 적용하여 자동으로 게시됩니다.
    """
    manager = get_bot_manager(cafe_id)
    result = manager.approve_comment(comment_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "승인 실패"))
    
    return result


@router.post("/{cafe_id}/comments/{comment_id}/cancel")
async def cancel_comment(cafe_id: str, comment_id: str, body: CommentCancelRequest):
    """
    댓글 취소 - 게시하지 않음
    
    취소된 댓글은 기록에 남지만 게시되지 않습니다.
    """
    manager = get_bot_manager(cafe_id)
    result = manager.cancel_comment(comment_id, reason=body.reason)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "취소 실패"))
    
    return result


@router.post("/{cafe_id}/comments/{comment_id}/edit")
async def edit_comment(cafe_id: str, comment_id: str, body: CommentEditRequest):
    """
    댓글 수정
    
    댓글 내용을 수정합니다. 수정 이력이 기록됩니다.
    """
    if not body.new_comment or not body.new_comment.strip():
        raise HTTPException(status_code=400, detail="수정할 댓글 내용을 입력해주세요.")
    
    manager = get_bot_manager(cafe_id)
    result = manager.edit_comment(comment_id, body.new_comment.strip())
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "수정 실패"))
    
    return result


@router.post("/{cafe_id}/comments/{comment_id}/regenerate")
async def regenerate_comment(cafe_id: str, comment_id: str):
    """
    댓글 재생성 - AI 에이전트를 다시 실행
    
    원본 게시글 내용을 기반으로 새로운 댓글을 생성합니다.
    """
    manager = get_bot_manager(cafe_id)
    result = await manager.regenerate_comment(comment_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "재생성 실패"))
    
    return result


@router.post("/{cafe_id}/comments/{comment_id}/revert")
async def revert_comment(cafe_id: str, comment_id: str):
    """
    댓글을 pending 상태로 되돌리기
    
    취소됨, 실패, 승인됨 상태의 댓글을 다시 대기 상태로 되돌립니다.
    """
    manager = get_bot_manager(cafe_id)
    result = manager.revert_to_pending(comment_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "되돌리기 실패"))
    
    return result


# ==========================================
# 게시 워커 API 엔드포인트
# ==========================================

class PosterStartRequest(BaseModel):
    """게시 워커 시작 요청"""
    account_id: Optional[str] = None


@router.post("/{cafe_id}/poster/start")
async def start_poster(cafe_id: str, request: PosterStartRequest = PosterStartRequest()):
    """
    게시 워커 시작
    
    승인된 댓글을 설정된 딜레이에 따라 자동으로 게시합니다.
    """
    manager = get_bot_manager(cafe_id)
    result = manager.start_poster(account_id=request.account_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "시작 실패"))
    
    return result


@router.post("/{cafe_id}/poster/stop")
async def stop_poster(cafe_id: str):
    """
    게시 워커 중지
    """
    manager = get_bot_manager(cafe_id)
    result = manager.stop_poster()
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "중지 실패"))
    
    return result


@router.get("/{cafe_id}/poster/status")
async def get_poster_status(cafe_id: str):
    """
    게시 워커 상태 조회
    
    Returns:
        running: 실행 중 여부
        pid: 프로세스 ID
        approved_count: 승인 대기 중인 댓글 수
    """
    manager = get_bot_manager(cafe_id)
    return manager.get_poster_status()


@router.get("/{cafe_id}/poster/logs")
async def get_poster_logs(cafe_id: str, lines: int = 50):
    """
    게시 워커 로그 조회
    
    Args:
        lines: 가져올 로그 줄 수 (기본 50)
    
    Returns:
        logs: 로그 줄 배열
    """
    manager = get_bot_manager(cafe_id)
    return manager.get_poster_logs(lines)
