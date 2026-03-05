"""
사용자별 채팅 세션 관리 API
- session_chat_messages 테이블 기반 (user_session = 세션 식별자)
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from services.supabase_client import supabase_service
from middleware.auth import get_current_user
from utils.admin_filter import is_admin_account

router = APIRouter()


def _safe_iso(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return value
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_auth_user_name(auth_user: Any) -> str:
    metadata = getattr(auth_user, "user_metadata", None) or {}
    if isinstance(metadata, dict):
        name = _to_str(metadata.get("name")) or _to_str(metadata.get("full_name"))
        if name:
            return name
    email = _to_str(getattr(auth_user, "email", None))
    return email.split("@")[0] if "@" in email else ""


def _load_auth_users(client) -> Dict[str, Dict[str, str]]:
    """
    auth.users 기반 이름/이메일 조회 (가능한 경우에만 사용).
    service role 키가 없으면 실패할 수 있으므로 호출부에서 예외를 무시한다.
    """
    by_user: Dict[str, Dict[str, str]] = {}
    page = 1
    per_page = 1000
    while True:
        batch = client.auth.admin.list_users(page=page, per_page=per_page) or []
        if not batch:
            break
        for auth_user in batch:
            uid = _to_str(getattr(auth_user, "id", None))
            if not uid:
                continue
            by_user[uid] = {
                "name": _extract_auth_user_name(auth_user),
                "email": _to_str(getattr(auth_user, "email", None)),
            }
        if len(batch) < per_page:
            break
        page += 1
    return by_user


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


class MigrateMessageItem(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str
    sources: Optional[List[str]] = None
    source_urls: Optional[List[str]] = None


class MigrateMessagesRequest(BaseModel):
    messages: List[MigrateMessageItem]
    browser_session_id: str  # 기존 브라우저 세션 ID


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


class UpdateAdminReviewMetaRequest(BaseModel):
    bookmark: Optional[bool] = None
    comment: Optional[str] = None


ADMIN_CHAT_REVIEW_SETTINGS_KEY = "admin_chat_review_notes"


def _load_admin_chat_review_notes(client) -> Dict[str, Dict[str, Any]]:
    try:
        resp = (
            client.table("admin_settings")
            .select("value")
            .eq("key", ADMIN_CHAT_REVIEW_SETTINGS_KEY)
            .limit(1)
            .execute()
        )
        if not resp.data:
            return {}
        raw = (resp.data[0] or {}).get("value") or {}
        if not isinstance(raw, dict):
            return {}
        notes: Dict[str, Dict[str, Any]] = {}
        for k, v in raw.items():
            if not isinstance(v, dict):
                continue
            notes[str(k)] = {
                "bookmark": bool(v.get("bookmark", False)),
                "comment": str(v.get("comment") or ""),
                "updated_at": _safe_iso(v.get("updated_at")),
                "updated_by": str(v.get("updated_by") or ""),
            }
        return notes
    except Exception:
        return {}


def _save_admin_chat_review_notes(client, notes: Dict[str, Dict[str, Any]]) -> None:
    client.table("admin_settings").upsert(
        {"key": ADMIN_CHAT_REVIEW_SETTINGS_KEY, "value": notes},
        on_conflict="key",
    ).execute()


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
    
    주의: 매번 새로운 UUID를 생성해야 함. browser_session_id는 트래킹용으로만 사용.
    """
    try:
        now = datetime.now().isoformat()
        # 항상 새로운 UUID 생성 (browser_session_id는 트래킹 참조용으로만 저장)
        session_id = str(uuid.uuid4())
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


@router.post("/migrate")
async def migrate_messages(
    request: MigrateMessagesRequest,
    user: dict = Depends(get_current_user)
):
    """
    비로그인 상태의 채팅 내역을 로그인한 사용자의 세션으로 마이그레이션
    
    - 새 세션 ID 생성
    - 메시지들을 session_chat_messages에 user_id와 함께 저장
    - 저장된 세션 ID 반환
    """
    try:
        if not request.messages:
            raise HTTPException(status_code=400, detail="마이그레이션할 메시지가 없습니다")
        
        # 새 세션 ID 생성
        session_id = str(uuid.uuid4())
        user_id = user["user_id"]
        now = datetime.now()
        
        # 메시지들을 session_chat_messages에 저장
        for idx, msg in enumerate(request.messages):
            message_id = str(uuid.uuid4())
            # 메시지 순서를 보장하기 위해 시간에 인덱스 추가
            created_at = (now.replace(microsecond=idx * 1000)).isoformat()
            
            insert_data = {
                "user_session": session_id,
                "message_id": message_id,
                "role": msg.role,
                "content": msg.content,
                "user_id": user_id,
                "created_at": created_at,
            }
            
            # sources와 source_urls가 있으면 추가
            if msg.sources:
                insert_data["sources"] = msg.sources
            if msg.source_urls:
                insert_data["source_urls"] = msg.source_urls
            
            supabase_service.client.table("session_chat_messages").insert(insert_data).execute()
        
        print(f"✅ 채팅 마이그레이션 완료: user_id={user_id}, session_id={session_id}, messages={len(request.messages)}")
        
        return {
            "session_id": session_id,
            "message_count": len(request.messages),
            "message": "채팅 내역이 성공적으로 마이그레이션되었습니다"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 채팅 마이그레이션 실패: {e}")
        raise HTTPException(status_code=500, detail=f"채팅 마이그레이션 실패: {str(e)}")


@router.get("/admin/review/sessions")
async def get_admin_review_sessions(
    limit: int = 300,
    offset: int = 0,
    user: dict = Depends(get_current_user)
):
    """
    관리자 로그 리뷰용 세션 목록 조회
    - session_chat_messages를 세션 단위로 집계
    - 비회원 세션 포함
    """
    if not is_admin_account(email=user.get("email"), name=user.get("name")):
        raise HTTPException(status_code=403, detail="Admin only")

    limit = min(max(1, limit), 1000)
    offset = max(0, offset)

    try:
        client = supabase_service.get_admin_client()
        review_notes = _load_admin_chat_review_notes(client)
        auth_by_user: Dict[str, Dict[str, str]] = {}
        try:
            auth_by_user = _load_auth_users(client)
        except Exception:
            auth_by_user = {}

        # 최신 메시지 기준으로 충분히 큰 범위를 읽어 세션 집계를 구성
        # (세션 페이지 목적이므로 최신 데이터 위주가 적합)
        rows_resp = (
            client.table("session_chat_messages")
            .select("user_session, user_id, role, created_at")
            .order("created_at", desc=True)
            .limit(50000)
            .execute()
        )
        rows = rows_resp.data or []

        session_map: Dict[str, Dict[str, Any]] = {}
        user_ids = set()

        for row in rows:
            session_id = (row.get("user_session") or "").strip()
            if not session_id:
                continue

            created_at = _safe_iso(row.get("created_at"))
            user_id = row.get("user_id")
            role = (row.get("role") or "").strip()

            if session_id not in session_map:
                session_map[session_id] = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "chat_count": 0,
                    "start_time": created_at,
                    "end_time": created_at,
                }
            meta = session_map[session_id]

            if not meta.get("user_id") and user_id:
                meta["user_id"] = user_id

            if role == "user":
                meta["chat_count"] += 1

            if created_at and (not meta["start_time"] or created_at < meta["start_time"]):
                meta["start_time"] = created_at
            if created_at and (not meta["end_time"] or created_at > meta["end_time"]):
                meta["end_time"] = created_at

            if user_id:
                user_ids.add(str(user_id))

        # 사용자 정보 조회 (이름/요금제)
        # 참고: user_id 개수가 많거나 형식이 섞여 있으면 in() 쿼리가 400을 낼 수 있어
        # admin users 테이블을 배치로 읽어 맵을 구성한다.
        user_info_map: Dict[str, Dict[str, Any]] = {}
        if user_ids:
            start = 0
            batch = 1000
            while True:
                try:
                    users_resp = (
                        client.table("users")
                        .select("id, name, email, is_premium")
                        .range(start, start + batch - 1)
                        .execute()
                    )
                except Exception:
                    try:
                        users_resp = (
                            client.table("users")
                            .select("id, name, is_premium")
                            .range(start, start + batch - 1)
                            .execute()
                        )
                    except Exception:
                        users_resp = (
                            client.table("users")
                            .select("id, is_premium")
                            .range(start, start + batch - 1)
                            .execute()
                        )
                user_rows = users_resp.data or []
                if not user_rows:
                    break

                for u in user_rows:
                    uid = str(u.get("id") or "").strip()
                    if not uid or uid not in user_ids:
                        continue
                    auth_info = auth_by_user.get(uid, {})
                    user_info_map[uid] = {
                        "name": _to_str(auth_info.get("name")) or (u.get("name") or "").strip(),
                        "email": _to_str(auth_info.get("email")) or (u.get("email") or "").strip(),
                        "is_premium": bool(u.get("is_premium")),
                    }

                if len(user_rows) < batch:
                    break
                start += batch

            # users 테이블에 없더라도 auth.users에서 이름/이메일을 얻을 수 있으면 보강
            for uid in user_ids:
                if uid in user_info_map:
                    continue
                auth_info = auth_by_user.get(uid, {})
                if auth_info:
                    user_info_map[uid] = {
                        "name": _to_str(auth_info.get("name")),
                        "email": _to_str(auth_info.get("email")),
                        "is_premium": False,
                    }

        sessions = []
        for _, meta in session_map.items():
            uid = str(meta.get("user_id") or "").strip()
            if not uid:
                user_type = "guest"
                user_name = meta["session_id"]
                user_email = ""
            else:
                info = user_info_map.get(uid, {})
                user_type = "pro" if info.get("is_premium") else "basic"
                user_name = info.get("name") or uid
                user_email = info.get("email") or ""

            sessions.append({
                "session_id": meta["session_id"],
                "user_id": uid or None,
                "user_name": user_name,
                "user_email": user_email or None,
                "user_type": user_type,
                "chat_count": int(meta.get("chat_count") or 0),
                "start_time": meta.get("start_time") or "",
                "end_time": meta.get("end_time") or "",
                "recent_time": meta.get("end_time") or "",
                "bookmark": bool(review_notes.get(meta["session_id"], {}).get("bookmark", False)),
                "comment": str(review_notes.get(meta["session_id"], {}).get("comment") or ""),
            })

        sessions.sort(key=lambda x: x.get("recent_time") or "", reverse=True)
        total = len(sessions)
        paged = sessions[offset: offset + limit]

        return {"sessions": paged, "total": total}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관리자 세션 목록 조회 실패: {str(e)}")


@router.patch("/admin/review/sessions/{session_id}/meta")
async def update_admin_review_session_meta(
    session_id: str,
    request: UpdateAdminReviewMetaRequest,
    user: dict = Depends(get_current_user)
):
    """
    관리자 로그 리뷰용 세션 메타 업데이트
    - bookmark/comment를 admin_settings(JSONB) 키-값에 저장
    """
    if not is_admin_account(email=user.get("email"), name=user.get("name")):
        raise HTTPException(status_code=403, detail="Admin only")

    if request.bookmark is None and request.comment is None:
        raise HTTPException(status_code=400, detail="업데이트할 값이 없습니다.")

    try:
        client = supabase_service.get_admin_client()
        notes = _load_admin_chat_review_notes(client)
        existing = notes.get(session_id, {})

        next_note: Dict[str, Any] = {
            "bookmark": existing.get("bookmark", False),
            "comment": existing.get("comment", ""),
            "updated_at": datetime.utcnow().isoformat(),
            "updated_by": str(user.get("user_id") or user.get("email") or ""),
        }
        if request.bookmark is not None:
            next_note["bookmark"] = bool(request.bookmark)
        if request.comment is not None:
            next_note["comment"] = str(request.comment)

        notes[session_id] = next_note
        _save_admin_chat_review_notes(client, notes)

        return {
            "session_id": session_id,
            "bookmark": bool(next_note.get("bookmark", False)),
            "comment": str(next_note.get("comment") or ""),
            "updated_at": _safe_iso(next_note.get("updated_at")),
            "updated_by": str(next_note.get("updated_by") or ""),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"세션 메타 저장 실패: {str(e)}")


@router.get("/admin/review/sessions/{session_id}/messages")
async def get_admin_review_session_messages(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """
    관리자 로그 리뷰용 세션 메시지 조회
    - user_id 제약 없이 특정 session_id의 전체 메시지 반환
    """
    if not is_admin_account(email=user.get("email"), name=user.get("name")):
        raise HTTPException(status_code=403, detail="Admin only")

    try:
        client = supabase_service.get_admin_client()
        def _norm_text(v: Any) -> str:
            s = str(v or "")
            return " ".join(s.split()).strip()

        def _to_dt(v: Any) -> Optional[datetime]:
            if not v:
                return None
            if isinstance(v, datetime):
                return v
            s = str(v)
            try:
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                return datetime.fromisoformat(s)
            except Exception:
                return None

        messages_resp = (
            client.table("session_chat_messages")
            .select("message_id, user_session, user_id, role, content, sources, source_urls, created_at")
            .eq("user_session", session_id)
            .order("created_at", desc=False)
            .execute()
        )
        raw_messages = messages_resp.data or []

        # assistant 메시지에 대응하는 admin_logs(턴 디버그) 매핑 시도
        # session_id 컬럼이 admin_logs에 없어 user_question/final_answer 매칭 기반으로 보강
        messages = []
        for idx, row in enumerate(raw_messages):
            role = row.get("role")
            content = row.get("content") or ""
            row_user_id = row.get("user_id")
            router_output = None
            function_result = None
            timing = None
            elapsed_time = 0

            if role == "assistant" and idx > 0:
                prev_row = raw_messages[idx - 1]
                prev_role = prev_row.get("role")
                prev_user_question = prev_row.get("content") or ""
                if prev_role == "user" and prev_user_question:
                    try:
                        q = (
                            client.table("admin_logs")
                            .select("router_output, function_result, timing_router, timing_function, timing_main_agent, elapsed_time, timestamp, final_answer")
                            .eq("user_question", prev_user_question)
                            .order("timestamp", desc=True)
                            .limit(30)
                        )
                        if row_user_id:
                            q = q.eq("user_id", row_user_id)
                        else:
                            q = q.is_("user_id", "null")
                        log_resp = q.execute()
                        if log_resp.data and len(log_resp.data) > 0:
                            normalized_content = _norm_text(content)
                            msg_dt = _to_dt(row.get("created_at"))

                            def score_candidate(log_row: Dict[str, Any]) -> float:
                                score = 0.0
                                ans = _norm_text(log_row.get("final_answer"))
                                if ans and normalized_content:
                                    if ans == normalized_content:
                                        score += 1000
                                    elif ans[:140] == normalized_content[:140]:
                                        score += 500
                                    elif ans and normalized_content and (ans in normalized_content or normalized_content in ans):
                                        score += 200
                                log_dt = _to_dt(log_row.get("timestamp"))
                                if msg_dt and log_dt:
                                    delta = abs((msg_dt - log_dt).total_seconds())
                                    score += max(0.0, 120.0 - min(delta, 120.0))
                                return score

                            sorted_logs = sorted(log_resp.data, key=score_candidate, reverse=True)
                            log_row = sorted_logs[0]
                            router_output = log_row.get("router_output")
                            function_result = log_row.get("function_result")
                            timing = {
                                "router": log_row.get("timing_router", 0),
                                "function": log_row.get("timing_function", 0),
                                "main_agent": log_row.get("timing_main_agent", 0),
                            }
                            elapsed_time = log_row.get("elapsed_time", 0)
                    except Exception:
                        # 디버그 보강 실패는 전체 메시지 조회 실패로 이어지지 않도록 무시
                        pass

            messages.append({
                "id": row.get("message_id"),
                "session_id": row.get("user_session"),
                "user_id": row_user_id,
                "role": role,
                "content": content,
                "sources": row.get("sources") or [],
                "source_urls": row.get("source_urls") or [],
                "created_at": _safe_iso(row.get("created_at")),
                "router_output": router_output,
                "function_result": function_result,
                "timing": timing,
                "elapsed_time": elapsed_time,
            })

        return {"session_id": session_id, "messages": messages, "total": len(messages)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"관리자 세션 메시지 조회 실패: {str(e)}")

