"""
생기부 평가 API 라우터

- prefix: /api/school-record (main.py에서 지정)
- 로그인 유저의 세특 데이터는 user_profiles.metadata.school_record 에 연동 저장
"""
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends, Body

from middleware.auth import optional_auth, get_current_user
from services.supabase_client import SupabaseService

from .models import SchoolRecordEvaluateRequest, SchoolRecordEvaluateResponse
from .service import evaluate_school_record
from .diagnose import diagnose_school_record

router = APIRouter()
MAX_SAVED_ITEMS = 50  # 유저당 최근 저장 개수


@router.get("/health")
async def health():
    """생기부 평가 모듈 헬스 체크"""
    return {"status": "ok", "module": "school_record_eval"}


@router.post("/evaluate", response_model=SchoolRecordEvaluateResponse)
async def evaluate(
    request: SchoolRecordEvaluateRequest,
    authorization: Optional[str] = Header(None),
):
    """
    생기부 텍스트를 평가합니다.
    로그인한 경우 결과를 user_profiles.metadata.school_record 에 저장합니다.
    """
    try:
        result = await evaluate_school_record(request)
        user = await optional_auth(authorization)
        if user and result.get("success") and result.get("result"):
            user_id = user.get("user_id")
            if user_id:
                meta = await SupabaseService.get_user_profile_metadata(user_id) or {}
                school = dict(meta.get("school_record") or {})
                items = list(school.get("items") or [])
                items.append({
                    "content": (request.content or "")[:30000],
                    "hope_major": (request.hope_major or "").strip(),
                    "result": result.get("result"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                school["items"] = items[-MAX_SAVED_ITEMS:]
                await SupabaseService.update_user_profile_metadata(
                    user_id, "school_record", school
                )
        return SchoolRecordEvaluateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"생기부 평가 처리 중 오류: {str(e)}")


@router.post("/diagnose")
async def diagnose(body: dict = Body(...)):
    """
    세특 초안을 4단계 필승구조 + 전공계열 + 체크리스트 기준으로 진단합니다.
    body: { "content": "세특 텍스트", "hope_major": "희망 전공(선택)" }
    returns: success, original_text, highlights, goodPoints, reconsiderPoints, rewritten_version,
             structure_analysis, checklist, admission_comment, error
    """
    try:
        content = (body.get("content") or "").strip()
        hope_major = (body.get("hope_major") or "").strip() or None
        result = await diagnose_school_record(content, hope_major=hope_major)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_school_records(user: dict = Depends(get_current_user)):
    """
    로그인 유저의 user_profiles.metadata.school_record 목록을 반환합니다.
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    meta = await SupabaseService.get_user_profile_metadata(user_id)
    if meta is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    school = meta.get("school_record") or {}
    items = school.get("items") or []
    return {"items": items}


@router.get("/forms")
async def get_school_record_forms(user: dict = Depends(get_current_user)):
    """
    로그인 유저의 생기부 폼 데이터를 반환합니다.
    user_profiles.metadata.school_record.forms
    구분: 창의적체험활동상황, 과목별세부능력및특기사항, 개인별세부능력및특기사항, 행동특성 및 종합의견
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    meta = await SupabaseService.get_user_profile_metadata(user_id)
    if meta is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    school = meta.get("school_record") or {}
    forms = school.get("forms") or {}
    return {"forms": forms}


@router.post("/forms")
async def save_school_record_forms(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """
    생기부 폼 데이터를 저장합니다. (병합)
    body: { "creativeActivity"?, "academicDev"?, "individualDev"?, "behaviorOpinion"? }
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    meta = await SupabaseService.get_user_profile_metadata(user_id)
    if meta is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    school = dict(meta.get("school_record") or {})
    existing_forms = dict(school.get("forms") or {})
    for key in ("creativeActivity", "academicDev", "individualDev", "behaviorOpinion"):
        if key in body and body[key] is not None:
            existing_forms[key] = body[key]
    school["forms"] = existing_forms
    await SupabaseService.update_user_profile_metadata(
        user_id, "school_record", school
    )
    return {"ok": True, "forms": existing_forms}
