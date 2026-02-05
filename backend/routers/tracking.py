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
    """페이지 뷰 추적 — events 테이블에만 기록"""
    try:
        user_data = await optional_auth(authorization)
        user_id = user_data.get("user_id") if user_data else None

        if user_id and is_admin_account(user_id=user_id):
            return {"success": True, "message": "Admin tracking skipped"}

        client = supabase_service.get_client()

        # 이벤트 유형: landing / chat_page 만 기록 (auth 등은 선택적)
        event_type = None
        if request.page_type == "landing":
            event_type = "landing"
        elif request.page_type == "chat":
            event_type = "chat_page"
        if event_type is None:
            return {"success": True, "session_id": request.session_id}

        # 디바이스 정보 (User-Agent 파싱, migration 15 적용 시 events에 저장)
        ua_string = http_request.headers.get("User-Agent") or ""
        device_info = parse_user_agent(ua_string) if ua_string else {}
        event_data = {
            "event_time": datetime.now().isoformat(),
            "event_type": event_type,
            "utm_source": request.utm_source,
            "utm_medium": request.utm_medium,
            "utm_campaign": request.utm_campaign,
            "utm_content": request.utm_content,
            "utm_term": request.utm_term,
            "user_id": user_id,
            "user_session": request.session_id,
        }
        # device 컬럼이 있으면 포함 (migration 15 미적용 시 컬럼 없음 → 제외하고 재시도)
        event_data_with_device = {**event_data, "device_type": device_info.get("device_type"), "browser": device_info.get("browser"), "os": device_info.get("os")}
        try:
            client.table("events").insert(event_data_with_device).execute()
        except Exception as insert_err:
            if "device_type" in str(insert_err) or "column" in str(insert_err).lower():
                client.table("events").insert(event_data).execute()
            else:
                raise

        # 로그인 시 해당 세션에 login 이벤트가 없으면 1건 추가
        if user_id:
            existing = client.table("events").select("id").eq("user_session", request.session_id).eq("event_type", "login").limit(1).execute()
            if not existing.data:
                login_event = {
                    "event_time": datetime.now().isoformat(),
                    "event_type": "login",
                    "utm_source": request.utm_source,
                    "utm_medium": request.utm_medium,
                    "utm_campaign": request.utm_campaign,
                    "utm_content": request.utm_content,
                    "utm_term": request.utm_term,
                    "user_id": user_id,
                    "user_session": request.session_id,
                }
                client.table("events").insert(login_event).execute()

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
    """사용자 행동 추적 — 질문 전송 시 events 테이블에 question_sent 기록"""
    try:
        user_data = await optional_auth(authorization)
        user_id = user_data.get("user_id") if user_data else None

        if user_id and is_admin_account(user_id=user_id):
            return {"success": True, "message": "Admin tracking skipped"}

        client = supabase_service.get_client()

        if request.action_name == "send_message":
            # 같은 세션의 기존 이벤트에서 UTM 가져오기 (없으면 null)
            utm_row = (
                client.table("events")
                .select("utm_source, utm_medium, utm_campaign, utm_content, utm_term")
                .eq("user_session", request.session_id)
                .order("event_time", desc=False)
                .limit(1)
                .execute()
            )
            utm = utm_row.data[0] if utm_row.data else {}
            event_data = {
                "event_time": datetime.now().isoformat(),
                "event_type": "question_sent",
                "utm_source": utm.get("utm_source"),
                "utm_medium": utm.get("utm_medium"),
                "utm_campaign": utm.get("utm_campaign"),
                "utm_content": utm.get("utm_content"),
                "utm_term": utm.get("utm_term"),
                "user_id": user_id,
                "user_session": request.session_id,
            }
            client.table("events").insert(event_data).execute()

        return {"success": True}

    except Exception as e:
        print(f"❌ 사용자 행동 추적 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/tracking/session/{session_id}")
async def get_session_info(session_id: str):
    """세션 정보 조회 — events 기반 요약"""
    try:
        client = supabase_service.get_client()
        response = (
            client.table("events")
            .select("event_type, event_time, user_id, utm_source, utm_medium")
            .eq("user_session", session_id)
            .order("event_time", desc=False)
            .execute()
        )
        if not response.data:
            return {"error": "Session not found"}
        events = response.data
        types = {e["event_type"] for e in events}
        first = events[0]
        return {
            "user_session": session_id,
            "user_id": first.get("user_id"),
            "utm_source": first.get("utm_source"),
            "utm_medium": first.get("utm_medium"),
            "visited_landing": "landing" in types,
            "visited_chat": "chat_page" in types,
            "logged_in": "login" in types,
            "asked_question": "question_sent" in types,
            "event_count": len(events),
        }
    except Exception as e:
        print(f"❌ 세션 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))