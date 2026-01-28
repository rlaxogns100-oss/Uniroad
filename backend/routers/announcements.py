"""
공지사항 API 라우터
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from services.supabase_client import supabase_service
from middleware.auth import get_current_user

router = APIRouter()

# 관리자 이메일 목록
ADMIN_EMAILS = ["herry0515@naver.com"]


class AnnouncementCreate(BaseModel):
    title: str
    content: str
    is_pinned: bool = False


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_pinned: Optional[bool] = None


class AnnouncementResponse(BaseModel):
    id: str
    title: str
    content: str
    author_email: str
    is_pinned: bool
    created_at: str
    updated_at: str


def is_admin(user: dict) -> bool:
    """관리자 권한 확인"""
    return user.get("email") in ADMIN_EMAILS


@router.get("/", response_model=List[AnnouncementResponse])
async def get_announcements():
    """
    공지사항 목록 조회 (최신순, 고정된 공지사항 우선)
    """
    try:
        response = supabase_service.client.table("announcements").select("*").order("is_pinned", desc=True).order("created_at", desc=True).execute()
        
        return response.data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"공지사항 조회 실패: {str(e)}")


@router.get("/{announcement_id}", response_model=AnnouncementResponse)
async def get_announcement(announcement_id: str):
    """
    특정 공지사항 조회
    """
    try:
        response = supabase_service.client.table("announcements").select("*").eq("id", announcement_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다")
        
        return response.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"공지사항 조회 실패: {str(e)}")


@router.post("/", response_model=AnnouncementResponse)
async def create_announcement(
    announcement: AnnouncementCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    공지사항 작성 (관리자 전용)
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="관리자만 공지사항을 작성할 수 있습니다")
    
    try:
        response = supabase_service.client.table("announcements").insert({
            "title": announcement.title,
            "content": announcement.content,
            "author_email": current_user.get("email"),
            "is_pinned": announcement.is_pinned,
        }).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="공지사항 생성 실패")
        
        return response.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"공지사항 생성 실패: {str(e)}")


@router.put("/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: str,
    announcement: AnnouncementUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    공지사항 수정 (관리자 전용)
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="관리자만 공지사항을 수정할 수 있습니다")
    
    try:
        # 업데이트할 필드만 추출
        update_data = {k: v for k, v in announcement.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="수정할 내용이 없습니다")
        
        response = supabase_service.client.table("announcements").update(update_data).eq("id", announcement_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다")
        
        return response.data[0]
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"공지사항 수정 실패: {str(e)}")


@router.delete("/{announcement_id}")
async def delete_announcement(
    announcement_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    공지사항 삭제 (관리자 전용)
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="관리자만 공지사항을 삭제할 수 있습니다")
    
    try:
        response = supabase_service.client.table("announcements").delete().eq("id", announcement_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="공지사항을 찾을 수 없습니다")
        
        return {"message": "공지사항이 삭제되었습니다", "id": announcement_id}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"공지사항 삭제 실패: {str(e)}")


@router.get("/check-admin/me")
async def check_admin(current_user: dict = Depends(get_current_user)):
    """
    현재 사용자의 관리자 권한 확인
    """
    return {"is_admin": is_admin(current_user), "email": current_user.get("email")}
