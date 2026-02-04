"""
페이지 뷰 추적 API
- UTM 파라미터 기반 사용자 여정 추적
- 페이지 뷰, 사용자 행동 기록
"""

from fastapi import APIRouter, HTTPException, Request, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import user_agents

from services.supabase_client import supabase_service
from utils.admin_filter import is_admin_account
from middleware.auth import optional_auth

router = APIRouter()


class PageViewRequest(BaseModel):
    session_id: str
    page_type: str  # 'landing', 'chat', 'auth', 'admin'
    page_path: str
    page_title: Optional[str] = None
    
    # UTM 파라미터
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    
    # 추가 정보
    referrer: Optional[str] = None
    time_on_page: Optional[int] = None  # 이전 페이지 체류시간


class UserActionRequest(BaseModel):
    session_id: str
    action_type: str  # 'click', 'scroll', 'submit'
    action_name: str  # 'cta_button', 'chat_start'
    action_category: Optional[str] = None
    element_id: Optional[str] = None
    element_text: Optional[str] = None


def parse_user_agent(user_agent_string: str) -> Dict[str, str]:
    """User-Agent 파싱"""
    ua = user_agents.parse(user_agent_string)
    
    # 디바이스 타입
    if ua.is_mobile:
        device_type = "mobile"
    elif ua.is_tablet:
        device_type = "tablet"
    else:
        device_type = "desktop"
    
    return {
        "device_type": device_type,
        "browser": ua.browser.family if ua.browser.family else "unknown",
        "os": ua.os.family if ua.os.family else "unknown"
    }


def get_client_ip(request: Request) -> str:
    """클라이언트 IP 추출"""
    # Nginx 프록시 헤더 확인
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


@router.post("/api/tracking/page-view")
async def track_page_view(
    request: PageViewRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None)
):
    """페이지 뷰 추적"""
    try:
        # 사용자 정보 (옵션)
        user_data = await optional_auth(authorization)
        user_id = user_data.get("user_id") if user_data else None
        
        # 관리자 계정 확인
        if user_id and is_admin_account(user_id=user_id):
            return {"success": True, "message": "Admin tracking skipped"}
        
        client = supabase_service.get_client()
        
        # User-Agent 파싱
        user_agent_string = http_request.headers.get("User-Agent", "")
        ua_info = parse_user_agent(user_agent_string)
        
        # IP 주소
        ip_address = get_client_ip(http_request)
        
        # 1. page_views 테이블에 기록
        page_view_data = {
            "session_id": request.session_id,
            "user_id": user_id,
            "page_type": request.page_type,
            "page_path": request.page_path,
            "page_title": request.page_title,
            "utm_source": request.utm_source,
            "utm_medium": request.utm_medium,
            "utm_campaign": request.utm_campaign,
            "utm_content": request.utm_content,
            "utm_term": request.utm_term,
            "referrer": request.referrer,
            "referrer_domain": request.referrer.split('/')[2] if request.referrer and '://' in request.referrer else None,
            "user_agent": user_agent_string,
            "device_type": ua_info["device_type"],
            "browser": ua_info["browser"],
            "os": ua_info["os"],
            "ip_address": ip_address,
            "time_on_page": request.time_on_page
        }
        
        client.table("page_views").insert(page_view_data).execute()
        
        # 2. user_journeys 업데이트 또는 생성
        journey_response = client.table("user_journeys")\
            .select("*")\
            .eq("session_id", request.session_id)\
            .execute()
        
        if journey_response.data:
            # 기존 여정 업데이트
            journey = journey_response.data[0]
            update_data = {
                "last_visit_at": datetime.now().isoformat(),
                "page_views_count": journey["page_views_count"] + 1
            }
            
            # 페이지별 방문 기록
            if request.page_type == "landing" and not journey["visited_landing"]:
                update_data["visited_landing"] = True
                update_data["landing_visit_at"] = datetime.now().isoformat()
            elif request.page_type == "chat" and not journey["visited_chat"]:
                update_data["visited_chat"] = True
                update_data["chat_visit_at"] = datetime.now().isoformat()
                update_data["funnel_stage"] = "chat"
            elif request.page_type == "auth" and not journey["visited_auth"]:
                update_data["visited_auth"] = True
            
            # 로그인 확인
            if user_id and not journey["logged_in"]:
                update_data["logged_in"] = True
                update_data["login_at"] = datetime.now().isoformat()
                update_data["funnel_stage"] = "login"
                update_data["user_id"] = user_id
                
                # 사용자 정보 가져오기
                if user_data:
                    update_data["user_email"] = user_data.get("email")
                    update_data["user_name"] = user_data.get("name")
            
            client.table("user_journeys")\
                .update(update_data)\
                .eq("session_id", request.session_id)\
                .execute()
        else:
            # 새 여정 생성
            journey_data = {
                "session_id": request.session_id,
                "first_utm_source": request.utm_source,
                "first_utm_medium": request.utm_medium,
                "first_utm_campaign": request.utm_campaign,
                "first_utm_content": request.utm_content,
                "first_utm_term": request.utm_term,
                "first_referrer": request.referrer,
                "visited_landing": request.page_type == "landing",
                "visited_chat": request.page_type == "chat",
                "visited_auth": request.page_type == "auth",
                "landing_visit_at": datetime.now().isoformat() if request.page_type == "landing" else None,
                "chat_visit_at": datetime.now().isoformat() if request.page_type == "chat" else None,
                "funnel_stage": "chat" if request.page_type == "chat" else "landing",
                "page_views_count": 1,
                "device_type": ua_info["device_type"],
                "browser": ua_info["browser"],
                "os": ua_info["os"],
                "ip_address": ip_address,
                "user_id": user_id,
                "user_email": user_data.get("email") if user_data else None,
                "user_name": user_data.get("name") if user_data else None
            }
            
            client.table("user_journeys").insert(journey_data).execute()
        
        return {"success": True, "session_id": request.session_id}
        
    except Exception as e:
        print(f"❌ 페이지 뷰 추적 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/tracking/user-action")
async def track_user_action(
    request: UserActionRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None)
):
    """사용자 행동 추적"""
    try:
        # 사용자 정보 (옵션)
        user_data = await optional_auth(authorization)
        user_id = user_data.get("user_id") if user_data else None
        
        # 관리자 계정 확인
        if user_id and is_admin_account(user_id=user_id):
            return {"success": True, "message": "Admin tracking skipped"}
        
        client = supabase_service.get_client()
        
        # 세션의 UTM 정보 가져오기
        journey_response = client.table("user_journeys")\
            .select("first_utm_source, first_utm_medium, first_utm_campaign")\
            .eq("session_id", request.session_id)\
            .execute()
        
        utm_info = {}
        if journey_response.data:
            journey = journey_response.data[0]
            utm_info = {
                "utm_source": journey.get("first_utm_source"),
                "utm_medium": journey.get("first_utm_medium"),
                "utm_campaign": journey.get("first_utm_campaign")
            }
        
        # user_actions 테이블에 기록
        action_data = {
            "session_id": request.session_id,
            "user_id": user_id,
            "action_type": request.action_type,
            "action_name": request.action_name,
            "action_category": request.action_category,
            "element_id": request.element_id,
            "element_text": request.element_text,
            **utm_info
        }
        
        client.table("user_actions").insert(action_data).execute()
        
        # 특별한 액션 처리 (질문 전송)
        if request.action_name == "send_message" and journey_response.data:
            journey = journey_response.data[0]
            if not journey.get("asked_question"):
                client.table("user_journeys")\
                    .update({
                        "asked_question": True,
                        "first_question_at": datetime.now().isoformat(),
                        "funnel_stage": "active_user"
                    })\
                    .eq("session_id", request.session_id)\
                    .execute()
        
        return {"success": True}
        
    except Exception as e:
        print(f"❌ 사용자 행동 추적 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracking/session/{session_id}")
async def get_session_info(session_id: str):
    """세션 정보 조회"""
    try:
        client = supabase_service.get_client()
        
        response = client.table("user_journeys")\
            .select("*")\
            .eq("session_id", session_id)\
            .execute()
        
        if response.data:
            return response.data[0]
        else:
            return {"error": "Session not found"}
            
    except Exception as e:
        print(f"❌ 세션 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))