"""
사용자별 채팅 세션 관리 API
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from services.supabase_client import supabase_service
from middleware.auth import get_current_user

router = APIRouter()


class CreateSessionRequest(BaseModel):
    title: Optional[str] = "새 대화"


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
    사용자의 모든 채팅 세션 목록
    """
    try:
        # 세션 목록 가져오기
        response = supabase_service.client.table("chat_sessions")\
            .select("*, chat_messages(count)")\
            .eq("user_id", user["user_id"])\
            .order("updated_at", desc=True)\
            .execute()
        
        sessions = []
        for session in response.data:
            sessions.append({
                "id": session["id"],
                "user_id": session["user_id"],
                "title": session["title"],
                "created_at": session["created_at"],
                "updated_at": session["updated_at"],
                "message_count": len(session.get("chat_messages", [])),
            })
        
        return sessions
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 목록 조회 실패: {str(e)}")


@router.post("/", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    user: dict = Depends(get_current_user)
):
    """
    새 채팅 세션 생성
    """
    try:
        # 세션 생성 시 에러 로깅 추가
        print(f"🆕 새 세션 생성 시도: user_id={user['user_id']}, title={request.title}")
        
        response = supabase_service.client.table("chat_sessions")\
            .insert({
                "user_id": user["user_id"],
                "title": request.title,
            })\
            .execute()
        
        if not response.data:
            print("❌ 세션 생성 실패: 응답 데이터 없음")
            raise HTTPException(status_code=500, detail="세션 생성 실패: 응답 데이터 없음")
        
        session = response.data[0]
        print(f"✅ 세션 생성 성공: session_id={session['id']}")
        
        return {
            "id": session["id"],
            "user_id": session["user_id"],
            "title": session["title"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "message_count": 0,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"❌ 세션 생성 실패: {error_msg}")
        # 에러 메시지에서 chat_logs 관련 에러 확인
        if "chat_logs" in error_msg.lower():
            print("⚠️ chat_logs 테이블 관련 에러 - 이는 무시해도 됩니다")
        raise HTTPException(status_code=500, detail=f"세션 생성 실패: {error_msg}")


@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """
    특정 세션의 메시지 목록
    """
    try:
        # 세션 소유권 확인
        session_response = supabase_service.client.table("chat_sessions")\
            .select("*")\
            .eq("id", session_id)\
            .eq("user_id", user["user_id"])\
            .execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # 메시지 가져오기
        messages_response = supabase_service.client.table("chat_messages")\
            .select("*")\
            .eq("session_id", session_id)\
            .order("created_at")\
            .execute()
        
        return messages_response.data
    
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
    세션 제목 수정
    """
    try:
        response = supabase_service.client.table("chat_sessions")\
            .update({"title": request.title})\
            .eq("id", session_id)\
            .eq("user_id", user["user_id"])\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        session = response.data[0]
        
        # 메시지 개수 가져오기
        count_response = supabase_service.client.table("chat_messages")\
            .select("id", count="exact")\
            .eq("session_id", session_id)\
            .execute()
        
        return {
            "id": session["id"],
            "user_id": session["user_id"],
            "title": session["title"],
            "created_at": session["created_at"],
            "updated_at": session["updated_at"],
            "message_count": count_response.count or 0,
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
    세션 삭제
    """
    try:
        response = supabase_service.client.table("chat_sessions")\
            .delete()\
            .eq("id", session_id)\
            .eq("user_id", user["user_id"])\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        return {"message": "세션이 삭제되었습니다"}
    
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
    세션의 대화 컨텍스트 가져오기 (AI 메모리)
    """
    try:
        # 세션 소유권 확인
        session_response = supabase_service.client.table("chat_sessions")\
            .select("*")\
            .eq("id", session_id)\
            .eq("user_id", user["user_id"])\
            .execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # 컨텍스트 가져오기
        context_response = supabase_service.client.table("conversation_context")\
            .select("*")\
            .eq("session_id", session_id)\
            .execute()
        
        if context_response.data:
            return context_response.data[0]["context"]
        else:
            return []
    
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
    세션의 대화 컨텍스트 저장
    """
    try:
        # 세션 소유권 확인
        session_response = supabase_service.client.table("chat_sessions")\
            .select("*")\
            .eq("id", session_id)\
            .eq("user_id", user["user_id"])\
            .execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # 컨텍스트 저장 (upsert)
        response = supabase_service.client.table("conversation_context")\
            .upsert({
                "session_id": session_id,
                "context": context,
            })\
            .execute()
        
        return {"message": "컨텍스트가 저장되었습니다"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"컨텍스트 저장 실패: {str(e)}")

