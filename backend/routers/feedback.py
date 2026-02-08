from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from services.supabase_client import SupabaseService

router = APIRouter()


class FeedbackCreate(BaseModel):
    content: str
    user_id: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    content: str
    user_id: Optional[str]
    created_at: datetime


@router.post("/api/feedback", response_model=dict)
async def submit_feedback(feedback: FeedbackCreate):
    """
    사용자 피드백 저장
    """
    try:
        client = SupabaseService.get_client()
        
        # feedback 테이블에 저장
        response = client.table('feedback').insert({
            'user_id': feedback.user_id,
            'content': feedback.content
        }).execute()
        
        return {"success": True, "message": "피드백이 전송되었습니다."}
        
    except Exception as e:
        print(f"피드백 저장 오류: {e}")
        raise HTTPException(status_code=500, detail="피드백 저장 실패")


@router.get("/api/feedback", response_model=list)
async def get_feedbacks(limit: int = 100, offset: int = 0):
    """
    관리자용: 피드백 목록 조회
    """
    try:
        client = SupabaseService.get_client()
        
        # feedback과 users를 조인해서 조회
        response = client.table('feedback')\
            .select('id, user_id, content, created_at')\
            .order('created_at', desc=True)\
            .range(offset, offset + limit - 1)\
            .execute()
        
        feedbacks = []
        for feedback in response.data:
            feedback_data = {
                'id': feedback['id'],
                'user_id': feedback.get('user_id'),
                'content': feedback['content'],
                'created_at': feedback['created_at'],
                'user_name': None,
                'user_email': None
            }
            
            # user_id가 있으면 users 테이블에서 정보 조회
            if feedback.get('user_id'):
                try:
                    user_response = client.table('users')\
                        .select('username, email')\
                        .eq('id', feedback['user_id'])\
                        .execute()
                    
                    if user_response.data:
                        feedback_data['user_name'] = user_response.data[0].get('username')
                        feedback_data['user_email'] = user_response.data[0].get('email')
                except:
                    pass
            
            feedbacks.append(feedback_data)
        
        return feedbacks
        
    except Exception as e:
        print(f"피드백 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="피드백 조회 실패")


@router.delete("/api/feedback/{feedback_id}")
async def delete_feedback(feedback_id: int):
    """
    관리자용: 피드백 삭제
    """
    try:
        client = SupabaseService.get_client()
        
        response = client.table('feedback')\
            .delete()\
            .eq('id', feedback_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="피드백을 찾을 수 없습니다")
        
        return {"success": True, "message": "피드백이 삭제되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"피드백 삭제 오류: {e}")
        raise HTTPException(status_code=500, detail="피드백 삭제 실패")

