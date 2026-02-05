"""
관리자 통계 API
- 누적 가입자 수 (Supabase Auth users 행 수)
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from middleware.auth import get_current_user
from utils.admin_filter import is_admin_account
from services.supabase_client import supabase_service

router = APIRouter()

PATH_EXCEL_KEY = "path_excel"


class PathRowPayload(BaseModel):
    step: str
    sessionSource: str
    activeUsers: int
    completionRate: float
    exits: int
    bounceRate: float


class PathExcelPayload(BaseModel):
    pathData: List[PathRowPayload]
    selectedPathSource: Optional[str] = ""


def _path_row_to_payload(row: dict) -> dict:
    return {
        "step": row.get("step", ""),
        "sessionSource": row.get("sessionSource", row.get("session_source", "")),
        "activeUsers": int(row.get("activeUsers", row.get("active_users", 0))),
        "completionRate": float(row.get("completionRate", row.get("completion_rate", 0))),
        "exits": int(row.get("exits", 0)),
        "bounceRate": float(row.get("bounceRate", row.get("bounce_rate", 0))),
    }


@router.get("/stats/users/count")
async def get_auth_user_count(user: dict = Depends(get_current_user)):
    """
    누적 가입자 수 (auth.users 행 수).
    관리자만 호출 가능.
    """
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")

    try:
        client = supabase_service.get_admin_client()
        result = client.rpc("get_auth_user_count").execute()
        data = result.data
        # RPC 스칼라 반환: 정수, [정수], 또는 [{"get_auth_user_count": n}]
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, int):
                total = first
            elif isinstance(first, dict):
                total = first.get("get_auth_user_count", 0)
            else:
                total = int(first) if first is not None else 0
        elif isinstance(data, int):
            total = data
        else:
            total = int(data) if data is not None else 0
        return {"total_users": total}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get user count: {str(e)}. Run migration 17_get_auth_user_count.sql and set SUPABASE_SERVICE_ROLE_KEY if needed.",
        )


@router.get("/stats/users/cumulative-timeseries")
async def get_auth_user_cumulative_timeseries(user: dict = Depends(get_current_user)):
    """
    Created at 기준 일별 신규 가입자 수 + 누적 가입자 수 시계열.
    관리자만 호출 가능.
    """
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")

    try:
        client = supabase_service.get_admin_client()
        result = client.rpc("get_auth_user_cumulative_timeseries").execute()
        data = result.data or []
        # RPC 테이블 반환: [{"day": "2026-01-24", "new_users": 1, "cumulative_users": 1}, ...]
        rows = []
        for row in data:
            if isinstance(row, dict):
                day = row.get("day")
                new_users = row.get("new_users", 0)
                cumulative_users = row.get("cumulative_users", 0)
            else:
                continue
            rows.append({
                "day": day,
                "new_users": int(new_users) if new_users is not None else 0,
                "cumulative_users": int(cumulative_users) if cumulative_users is not None else 0,
            })
        return {"series": rows}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cumulative timeseries: {str(e)}. Run migration 18_get_auth_user_cumulative_timeseries.sql if needed.",
        )


@router.get("/stats/questions/cumulative-timeseries")
async def get_questions_cumulative_timeseries(user: dict = Depends(get_current_user)):
    """
    admin_logs.created_at 기준 일별 질문 수 + 누적 질문 수 시계열.
    관리자만 호출 가능.
    """
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")

    try:
        client = supabase_service.get_admin_client()
        result = client.rpc("get_admin_logs_question_cumulative_timeseries").execute()
        data = result.data or []
        rows = []
        for row in data:
            if isinstance(row, dict):
                day = row.get("day")
                new_questions = row.get("new_questions", 0)
                cumulative_questions = row.get("cumulative_questions", 0)
            else:
                continue
            rows.append({
                "day": day,
                "new_questions": int(new_questions) if new_questions is not None else 0,
                "cumulative_questions": int(cumulative_questions) if cumulative_questions is not None else 0,
            })
        return {"series": rows}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get question timeseries: {str(e)}. Run migration 20_get_admin_logs_question_cumulative_timeseries.sql if needed.",
        )


@router.get("/stats/behavior/same-person-activity")
async def get_same_person_activity(user: dict = Depends(get_current_user)):
    """
    is_same_person별(user_id가 하나라도 있는 그룹만): 총 질문 횟수, 1시간 구간 재등장 횟수.
    관리자만 호출 가능.
    """
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")

    try:
        client = supabase_service.get_admin_client()
        result = client.rpc("get_admin_logs_same_person_activity").execute()
        data = result.data or []
        rows = []
        for row in data:
            if not isinstance(row, dict):
                continue
            is_same = row.get("is_same_person")
            latest_ts = row.get("latest_ts")
            total_q = row.get("total_questions", 0)
            distinct_hours = row.get("distinct_hour_appearances", 0)
            rows.append({
                "is_same_person": is_same,
                "latest_ts": latest_ts,
                "total_questions": int(total_q) if total_q is not None else 0,
                "distinct_hour_appearances": int(distinct_hours) if distinct_hours is not None else 0,
            })
        count_null = 0
        count_no_user_id = 0
        try:
            summary_result = client.rpc("get_admin_logs_same_person_summary").execute()
            summary_data = (summary_result.data or [{}])[0] if summary_result.data else {}
            count_null = summary_data.get("count_is_same_person_null") or 0
            count_no_user_id = summary_data.get("count_no_user_id_same_person") or 0
        except Exception:
            pass
        return {
            "items": rows,
            "count_is_same_person_null": int(count_null) if count_null is not None else 0,
            "count_no_user_id_same_person": int(count_no_user_id) if count_no_user_id is not None else 0,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get same-person activity: {str(e)}. Run migration 22_get_admin_logs_same_person_activity.sql if needed.",
        )


@router.get("/stats/behavior/latest-conversation")
async def get_latest_conversation_by_same_person(
    is_same_person: str,
    user: dict = Depends(get_current_user),
):
    """
    해당 is_same_person 중 timestamp가 가장 최신인 admin_logs 행의 conversation_history 등 반환.
    관리자만 호출 가능.
    """
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")
    if not is_same_person or not is_same_person.strip():
        raise HTTPException(status_code=400, detail="is_same_person required")

    try:
        client = supabase_service.get_admin_client()
        result = (
            client.table("admin_logs")
            .select("id, timestamp, user_question, final_answer, conversation_history")
            .eq("is_same_person", is_same_person.strip())
            .order("timestamp", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"log": None}
        row = rows[0]
        return {
            "log": {
                "id": row.get("id"),
                "timestamp": row.get("timestamp"),
                "userQuestion": row.get("user_question") or "",
                "finalAnswer": row.get("final_answer") or "",
                "conversationHistory": row.get("conversation_history") or [],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get latest conversation: {str(e)}")


@router.get("/stats/behavior/no-user-id-distribution")
async def get_no_user_id_row_distribution(user: dict = Depends(get_current_user)):
    """
    user_id가 없는 is_same_person 그룹별 행 수 분포.
    반환: [{ rows_per_person: N, num_persons: M }, ...] = 행이 N개인 그룹이 M개.
    관리자만 호출 가능.
    """
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")

    try:
        client = supabase_service.get_admin_client()
        result = client.rpc("get_admin_logs_no_user_id_row_distribution").execute()
        data = result.data or []
        rows = []
        for row in data:
            if not isinstance(row, dict):
                continue
            rpp = row.get("rows_per_person")
            nop = row.get("num_persons")
            rows.append({
                "rows_per_person": int(rpp) if rpp is not None else 0,
                "num_persons": int(nop) if nop is not None else 0,
            })
        return {"distribution": rows}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get distribution: {str(e)}. Run migration 24_get_admin_logs_no_user_id_row_distribution.sql if needed.",
        )


@router.get("/stats/behavior/null-same-person-rows")
async def get_null_same_person_rows(user: dict = Depends(get_current_user)):
    """is_same_person이 null인 admin_logs 행 목록 (표용). 관리자만."""
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        client = supabase_service.get_admin_client()
        result = (
            client.table("admin_logs")
            .select("id, timestamp, user_question")
            .is_("is_same_person", "null")
            .order("timestamp", desc=True)
            .limit(2000)
            .execute()
        )
        rows = []
        for r in result.data or []:
            uq = (r.get("user_question") or "")[:150]
            if len(r.get("user_question") or "") > 150:
                uq += "…"
            rows.append({
                "id": r.get("id"),
                "timestamp": r.get("timestamp"),
                "userQuestionSnippet": uq,
            })
        return {"rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/behavior/no-user-id-same-person-list")
async def get_no_user_id_same_person_list(user: dict = Depends(get_current_user)):
    """user_id가 없는 is_same_person 목록 및 그룹별 행 수 (표용). 관리자만."""
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        client = supabase_service.get_admin_client()
        result = client.rpc("get_admin_logs_no_user_id_same_person_list").execute()
        data = result.data or []
        rows = []
        for row in data:
            if not isinstance(row, dict):
                continue
            rows.append({
                "is_same_person": row.get("is_same_person"),
                "row_count": int(row.get("row_count") or 0),
            })
        return {"rows": rows}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed: {str(e)}. Run migration 25_get_admin_logs_no_user_id_same_person_list.sql if needed.",
        )


@router.get("/stats/behavior/log-by-id")
async def get_log_by_id(log_id: str, user: dict = Depends(get_current_user)):
    """admin_logs 한 건 조회 (모달용). 관리자만."""
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")
    if not log_id or not log_id.strip():
        raise HTTPException(status_code=400, detail="log_id required")
    try:
        client = supabase_service.get_admin_client()
        result = (
            client.table("admin_logs")
            .select("id, timestamp, user_question, final_answer, conversation_history")
            .eq("id", log_id.strip())
            .limit(1)
            .execute()
        )
        data = result.data or []
        if not data:
            return {"log": None}
        r = data[0]
        return {
            "log": {
                "id": r.get("id"),
                "timestamp": r.get("timestamp"),
                "userQuestion": r.get("user_question") or "",
                "finalAnswer": r.get("final_answer") or "",
                "conversationHistory": r.get("conversation_history") or [],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/path-excel")
async def get_path_excel(user: dict = Depends(get_current_user)):
    """
    관리자 공용 유입경로 엑셀 데이터 조회. 한 번 넣어두면 모든 관리자가 동일하게 봄.
    """
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        client = supabase_service.get_admin_client()
        result = (
            client.table("admin_settings")
            .select("value")
            .eq("key", PATH_EXCEL_KEY)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"pathData": [], "selectedPathSource": ""}
        val = rows[0].get("value") or {}
        path_data = val.get("pathData", [])
        selected = val.get("selectedPathSource", "") or ""
        # 정규화: 프론트 기대 필드명 (camelCase)
        path_data = [_path_row_to_payload(r) for r in path_data]
        return {"pathData": path_data, "selectedPathSource": selected}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get path excel: {str(e)}. Run migration 26_create_admin_settings.sql if needed.")


@router.put("/stats/path-excel")
async def put_path_excel(body: PathExcelPayload, user: dict = Depends(get_current_user)):
    """
    관리자 공용 유입경로 엑셀 데이터 저장. 저장 후 다른 관리자도 동일하게 조회됨.
    """
    if not is_admin_account(email=user.get("email")):
        raise HTTPException(status_code=403, detail="Admin only")
    try:
        client = supabase_service.get_admin_client()
        value = {
            "pathData": [r.model_dump() for r in body.pathData],
            "selectedPathSource": body.selectedPathSource or "",
        }
        client.table("admin_settings").upsert(
            {"key": PATH_EXCEL_KEY, "value": value},
            on_conflict="key",
        ).execute()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save path excel: {str(e)}")
