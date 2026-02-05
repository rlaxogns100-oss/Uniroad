"""
사용자별 채팅 세션 관리 API
- session_chat_messages 테이블 기반 (user_session = 세션 식별자)
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
from services.supabase_client import supabase_service
from middleware.auth import get_current_user

router = APIRouter()


class CreateSessionRequest(BaseModel):
    title: Optional[str] = "새 대화"
    browser_session_id: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    referrer: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    sources: Optional[List[str]] = []
    source_urls: Optional[List[str]] = []
    created_at: datetime


@router.get("/", response_model=List[SessionResponse])
async def get_sessions(user: dict = Depends(get_current_user)):
    """
    사용자의 모든 채팅 세션 목록 (session_chat_messages에서 user_session별 집계)
    """
    try:
        response = supabase_service.client.table("session_chat_messages")\
            .select("user_session, content, role, created_at")\
            .eq("user_id", user["user_id"])\
            .order("created_at", desc=False)\
            .execute()
        if not response.data:
            return []
        # user_session별로 그룹화
        by_session = {}
        for row in response.data:
            us = row["user_session"]
            if us not in by_session:
                by_session[us] = {"created_at": row["created_at"], "updated_at": row["created_at"], "count": 0, "first_user_content": None}
            by_session[us]["updated_at"] = row["created_at"]
            by_session[us]["count"] += 1
            if row["role"] == "user" and by_session[us]["first_user_content"] is None:
                by_session[us]["first_user_content"] = (row["content"] or "")[:50]
        sessions = [
            {
                "id": us,
                "user_id": user["user_id"],
                "title": meta["first_user_content"] or "새 대화",
                "created_at": meta["created_at"],
                "updated_at": meta["updated_at"],
                "message_count": meta["count"],
            }
            for us, meta in by_session.items()
        ]
        sessions.sort(key=lambda s: s["updated_at"], reverse=True)
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 목록 조회 실패: {str(e)}")


@router.post("/", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    user: dict = Depends(get_current_user)
):
    """
    새 채팅 세션 생성 (DB insert 없이 id만 반환, 첫 메시지 시 session_chat_messages에 기록)
    """
    try:
        now = datetime.now().isoformat()
        session_id = request.browser_session_id or str(uuid.uuid4())
        return {
            "id": session_id,
            "user_id": user["user_id"],
            "title": request.title or "새 대화",
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 생성 실패: {str(e)}")


@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """
    특정 세션의 메시지 목록 (session_chat_messages)
    """
    try:
        messages_response = supabase_service.client.table("session_chat_messages")\
            .select("message_id, user_session, role, content, sources, source_urls, created_at")\
            .eq("user_session", session_id)\
            .eq("user_id", user["user_id"])\
            .order("created_at")\
            .execute()
        if not messages_response.data:
            return []
        return [
            {
                "id": row["message_id"],
                "session_id": row["user_session"],
                "role": row["role"],
                "content": row["content"],
                "sources": row.get("sources") or [],
                "source_urls": row.get("source_urls") or [],
                "created_at": row["created_at"],
            }
            for row in messages_response.data
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"메시지 조회 실패: {str(e)}")


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    user: dict = Depends(get_current_user)
):
    """
    세션 제목 수정 (session_chat_messages에는 title 없음, 동일 응답 형태만 반환)
    """
    try:
        rows = supabase_service.client.table("session_chat_messages")\
            .select("created_at")\
            .eq("user_session", session_id)\
            .eq("user_id", user["user_id"])\
            .order("created_at")\
            .execute()
        if not rows.data:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        created = rows.data[0]["created_at"]
        updated = rows.data[-1]["created_at"]
        return {
            "id": session_id,
            "user_id": user["user_id"],
            "title": request.title,
            "created_at": created,
            "updated_at": updated,
            "message_count": len(rows.data),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 수정 실패: {str(e)}")


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """
    세션 삭제 (session_chat_messages에서 해당 user_session 행 삭제)
    """
    try:
        result = supabase_service.client.table("session_chat_messages")\
            .delete()\
            .eq("user_session", session_id)\
            .eq("user_id", user["user_id"])\
            .execute()
        return {"message": "세션과 메시지가 삭제되었습니다"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 삭제 실패: {str(e)}")


@router.get("/{session_id}/context")
async def get_context(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """
    세션의 대화 컨텍스트 (session_chat_messages에서 최근 메시지로 구성)
    """
    try:
        rows = supabase_service.client.table("session_chat_messages")\
            .select("role, content")\
            .eq("user_session", session_id)\
            .eq("user_id", user["user_id"])\
            .order("created_at")\
            .limit(20)\
            .execute()
        if not rows.data:
            return []
        return [{"role": r["role"], "content": r.get("content", "")} for r in rows.data]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨텍스트 조회 실패: {str(e)}")


@router.post("/{session_id}/context")
async def save_context(
    session_id: str,
    context: List[dict],
    user: dict = Depends(get_current_user)
):
    """
    세션의 대화 컨텍스트 저장 (session_chat_messages 기반이므로 no-op, 컨텍스트는 메시지에서 유도)
    """
    return {"message": "컨텍스트가 저장되었습니다"}

