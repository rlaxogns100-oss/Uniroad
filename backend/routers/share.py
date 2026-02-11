"""
채팅 공유 API
- 특정 질문/답변을 공유 링크로 생성
- 공유된 채팅 조회
- 핵심 요약 생성
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import secrets
import string
from services.supabase_client import supabase_service
from services.multi_agent.summary_agent import generate_summary
from config.config import settings

router = APIRouter()


def generate_share_id(length: int = 10) -> str:
    """짧은 고유 공유 ID 생성 (영숫자 조합)"""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class CreateShareRequest(BaseModel):
    user_query: str  # 사용자 질문
    assistant_response: str  # AI 답변
    sources: Optional[List[str]] = None  # 출처 목록
    source_urls: Optional[List[str]] = None  # 출처 URL


class ShareResponse(BaseModel):
    share_id: str
    share_url: str


class SummaryRequest(BaseModel):
    user_query: str
    assistant_response: str


class SummaryResponse(BaseModel):
    summary: str


class SharedChatResponse(BaseModel):
    share_id: str
    user_query: str
    assistant_response: str
    sources: Optional[List[str]] = None
    source_urls: Optional[List[str]] = None
    created_at: datetime
    view_count: int


@router.post("/", response_model=ShareResponse)
async def create_share(request: CreateShareRequest, req: Request):
    """
    채팅 공유 링크 생성
    
    - 질문과 답변을 저장하고 고유 share_id 반환
    - 누구나 생성 가능 (로그인 불필요)
    """
    try:
        # 고유 share_id 생성 (충돌 방지를 위해 최대 5회 시도)
        for _ in range(5):
            share_id = generate_share_id()
            
            # 중복 확인
            existing = supabase_service.client.table("shared_chats")\
                .select("share_id")\
                .eq("share_id", share_id)\
                .execute()
            
            if not existing.data:
                break
        else:
            raise HTTPException(status_code=500, detail="공유 ID 생성 실패")
        
        # 데이터 저장
        insert_data = {
            "share_id": share_id,
            "user_query": request.user_query,
            "assistant_response": request.assistant_response,
            "sources": request.sources or [],
            "source_urls": request.source_urls or [],
            "view_count": 0,
        }
        
        supabase_service.client.table("shared_chats").insert(insert_data).execute()
        
        # 공유 URL 생성 - 요청 origin에서 프론트엔드 URL 추출
        origin = req.headers.get("origin", "")
        referer = req.headers.get("referer", "")
        
        if origin and ("localhost" in origin or "127.0.0.1" in origin):
            # 로컬 환경: origin 그대로 사용 (포트 포함)
            share_url = f"{origin}/s/{share_id}"
        elif referer and ("localhost" in referer or "127.0.0.1" in referer):
            # referer에서 base URL 추출
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            share_url = f"{base_url}/s/{share_id}"
        else:
            # 프로덕션 환경
            share_url = f"https://uni2road.com/s/{share_id}"
        
        return ShareResponse(share_id=share_id, share_url=share_url)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 공유 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"공유 생성 실패: {str(e)}")


@router.get("/{share_id}", response_model=SharedChatResponse)
async def get_shared_chat(share_id: str):
    """
    공유된 채팅 조회
    
    - share_id로 저장된 질문/답변 조회
    - 조회 시 view_count 증가
    - 누구나 조회 가능 (로그인 불필요)
    """
    try:
        # 공유 데이터 조회
        response = supabase_service.client.table("shared_chats")\
            .select("*")\
            .eq("share_id", share_id)\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="공유된 채팅을 찾을 수 없습니다")
        
        shared_chat = response.data[0]
        
        # 조회수 증가 (비동기로 처리, 실패해도 무시)
        try:
            supabase_service.client.table("shared_chats")\
                .update({"view_count": shared_chat["view_count"] + 1})\
                .eq("share_id", share_id)\
                .execute()
        except Exception:
            pass  # 조회수 업데이트 실패는 무시
        
        return SharedChatResponse(
            share_id=shared_chat["share_id"],
            user_query=shared_chat["user_query"],
            assistant_response=shared_chat["assistant_response"],
            sources=shared_chat.get("sources") or [],
            source_urls=shared_chat.get("source_urls") or [],
            created_at=shared_chat["created_at"],
            view_count=shared_chat["view_count"],
        )
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 공유 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"공유 조회 실패: {str(e)}")


@router.post("/summary", response_model=SummaryResponse)
async def create_summary(request: SummaryRequest):
    """
    채팅 내용 핵심 요약 생성
    
    - 질문과 답변을 받아 3-5줄 요약 반환
    - GPT-4.1-mini 사용
    """
    try:
        summary = await generate_summary(request.user_query, request.assistant_response)
        return SummaryResponse(summary=summary)
    
    except Exception as e:
        print(f"❌ 요약 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"요약 생성 실패: {str(e)}")
