"""
생기부 평가 API 라우터

- prefix: /api/school-record (main.py에서 지정)
- 로그인 유저의 세특 데이터는 user_profiles.metadata.school_record 에 연동 저장
"""
import copy
import json
import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Depends, Body, UploadFile, File

from middleware.auth import optional_auth, get_current_user
from services.supabase_client import SupabaseService
from utils.school_record_context import has_meaningful_school_record

from .models import SchoolRecordEvaluateRequest, SchoolRecordEvaluateResponse
from .service import evaluate_school_record
from .diagnose import diagnose_school_record
from .uniroad_school_record_support import (
    MAX_PDF_SIZE,
    MAX_PDF_SIZE_MB,
    MIN_EXTRACTED_TEXT_CHARS,
    RULE_PARSER_VERSION,
    _build_pdf_file_hash,
    _build_forms_from_pdf_text,
    _build_parsed_preview,
    _extract_text_from_pdf_bytes,
    _is_cache_compatible,
    _merge_forms_from_parsed_preview,
    _normalize_academic_subjects,
)

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
    로그인한 경우 결과를 user_profiles.school_record + metadata.school_record 에 저장합니다.
    """
    try:
        result = await evaluate_school_record(request)
        user = await optional_auth(authorization)
        if user and result.get("success") and result.get("result"):
            user_id = user.get("user_id")
            if user_id:
                school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
                school = dict(school_loaded or {})
                items = list(school.get("items") or [])
                items.append({
                    "content": (request.content or "")[:30000],
                    "hope_major": (request.hope_major or "").strip(),
                    "result": result.get("result"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })
                school["items"] = items[-MAX_SAVED_ITEMS:]
                await SupabaseService.update_user_profile_school_record(user_id, school)
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
    로그인 유저의 user_profiles.school_record 목록을 반환합니다.
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    school = dict(school_loaded or {})
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
    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    school = dict(school_loaded or {})
    forms = school.get("forms") if isinstance(school.get("forms"), dict) else {}
    if not forms:
        forms = {}
    for key in (
        "creativeActivity",
        "academicDev",
        "individualDev",
        "behaviorOpinion",
        "volunteerActivity",
        "parsedSchoolRecord",
        "parsedSchoolRecordSummary",
        "rawSchoolRecordText",
        "pdfImportMeta",
    ):
        if key not in forms and key in school:
            forms[key] = school.get(key)

    parsed_school_record = forms.get("parsedSchoolRecord")
    raw_text = str(forms.get("rawSchoolRecordText") or "")
    import_meta = dict(forms.get("pdfImportMeta") or {})
    parse_method = str(import_meta.get("parse_method") or "").strip().lower()
    parser_version = (
        str((parsed_school_record or {}).get("parserVersion") or "")
        if isinstance(parsed_school_record, dict)
        else ""
    )
    should_rebuild_from_raw = (
        bool(raw_text.strip())
        and parse_method != "gemini"
        and (
            not isinstance(parsed_school_record, dict)
            or not parsed_school_record
            or parser_version != RULE_PARSER_VERSION
        )
    )
    mutated = False
    if should_rebuild_from_raw:
        rebuilt_forms = _build_forms_from_pdf_text(raw_text)
        rebuilt_parsed = rebuilt_forms.get("parsedSchoolRecord") or {}
        _normalize_academic_subjects(rebuilt_parsed)
        forms["creativeActivity"] = rebuilt_forms.get("creativeActivity") or {}
        forms["academicDev"] = rebuilt_forms.get("academicDev") or {}
        forms["individualDev"] = rebuilt_forms.get("individualDev") or {}
        forms["behaviorOpinion"] = rebuilt_forms.get("behaviorOpinion") or {}
        forms["volunteerActivity"] = rebuilt_forms.get("volunteerActivity") or {}
        forms["parsedSchoolRecord"] = rebuilt_parsed
        forms["parsedSchoolRecordSummary"] = rebuilt_forms.get("parseSummary") or {}
        parsed_school_record = rebuilt_parsed
        mutated = True

    if isinstance(parsed_school_record, dict) and parsed_school_record:
        before = json.dumps(parsed_school_record, ensure_ascii=False, sort_keys=True)
        _normalize_academic_subjects(parsed_school_record)
        after = json.dumps(parsed_school_record, ensure_ascii=False, sort_keys=True)
        if before != after:
            forms["parsedSchoolRecord"] = parsed_school_record
            mutated = True
    if mutated:
        school["forms"] = forms
        school["parsedSchoolRecord"] = copy.deepcopy(forms.get("parsedSchoolRecord") or {})
        school["parsedSchoolRecordSummary"] = copy.deepcopy(forms.get("parsedSchoolRecordSummary") or {})
        school["saved_at"] = datetime.now(timezone.utc).isoformat()
        await SupabaseService.update_user_profile_school_record(user_id, school)
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
    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    school = dict(school_loaded or {})
    existing_forms = dict(school.get("forms") or {})
    for key in (
        "creativeActivity",
        "academicDev",
        "individualDev",
        "behaviorOpinion",
        "volunteerActivity",
        "parsedSchoolRecord",
        "parsedSchoolRecordSummary",
        "pdfImportMeta",
        "rawSchoolRecordText",
    ):
        if key in body and body[key] is not None:
            existing_forms[key] = body[key]
    school["forms"] = existing_forms
    await SupabaseService.update_user_profile_school_record(user_id, school)
    return {"ok": True, "forms": existing_forms}


@router.get("/status")
async def get_school_record_status(user: dict = Depends(get_current_user)):
    """
    로그인 유저의 생기부 연동 상태만 반환합니다.
    - linked: user_profiles.school_record(또는 metadata.school_record) 에 의미 있는 데이터가 있으면 True
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")
    linked = has_meaningful_school_record(dict(school_loaded or {}))
    return {"linked": linked}


@router.post("/forms/save-parsed")
async def save_parsed_school_record(
    body: dict,
    user: dict = Depends(get_current_user),
):
    """
    프론트에서 편집된 parsedPreview를 기준으로 생기부 전체 구조를 저장합니다.
    저장 대상:
    - user_profiles.school_record (JSONB)
    - user_profiles.metadata.school_record (호환용)
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")

    parsed_preview = body.get("parsedPreview")
    if not isinstance(parsed_preview, dict) or not isinstance(parsed_preview.get("sections"), dict):
        raise HTTPException(status_code=400, detail="parsedPreview.sections is required")

    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")

    school = dict(school_loaded or {})
    existing_forms = dict(school.get("forms") or {})
    merged_forms = _merge_forms_from_parsed_preview(parsed_preview, existing_forms)

    # 있으면 덮어쓰기 (없으면 기존 유지)
    for opt_key in ("pdfImportMeta", "rawSchoolRecordText", "parsedSchoolRecordSummary"):
        if opt_key in body and body[opt_key] is not None:
            merged_forms[opt_key] = body[opt_key]

    # PDF에서 파싱된 정보 전부가 user_profiles.school_record(JSONB)에 들어가도록 forms + 최상위 동기화
    school["forms"] = merged_forms
    school["pdfImportMeta"] = copy.deepcopy(merged_forms.get("pdfImportMeta") or {})
    school["rawSchoolRecordText"] = merged_forms.get("rawSchoolRecordText") or ""
    school["parsedSchoolRecord"] = copy.deepcopy(merged_forms.get("parsedSchoolRecord") or {})
    school["parsedSchoolRecordSummary"] = copy.deepcopy(merged_forms.get("parsedSchoolRecordSummary") or {})
    school["saved_at"] = datetime.now(timezone.utc).isoformat()

    ok = await SupabaseService.update_user_profile_school_record(user_id, school)
    if not ok:
        raise HTTPException(status_code=500, detail="Profile save failed")

    return {
        "ok": True,
        "message": "생활기록부 저장이 완료되었습니다.",
        "meta": merged_forms.get("pdfImportMeta") or {},
        "summary": merged_forms.get("parsedSchoolRecordSummary") or {},
        "parsedPreview": _build_parsed_preview(merged_forms.get("parsedSchoolRecord") or {}),
    }


@router.post("/forms/upload-pdf")
async def upload_school_record_pdf(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """
    정부24/카카오 전자문서지갑에서 저장한 생기부 PDF를 업로드하여
    user_profiles.school_record/forms에 연동 저장합니다.
    """
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    started_at = time.perf_counter()

    filename = (file.filename or "").strip()
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="빈 파일입니다.")
    if len(file_bytes) > MAX_PDF_SIZE:
        raise HTTPException(status_code=400, detail=f"파일 크기는 {MAX_PDF_SIZE_MB}MB 이하여야 합니다.")
    file_hash = _build_pdf_file_hash(file_bytes)

    school_loaded = await SupabaseService.get_user_profile_school_record(user_id)
    if school_loaded is None:
        raise HTTPException(status_code=500, detail="Profile load failed")

    school = dict(school_loaded or {})
    forms = dict(school.get("forms") or {})

    existing_import_meta = dict(forms.get("pdfImportMeta") or {})
    existing_hash = str(existing_import_meta.get("file_hash") or "")
    has_cached_parse = _is_cache_compatible(forms, existing_import_meta)
    if existing_hash and existing_hash == file_hash and has_cached_parse:
        cached_meta = dict(existing_import_meta)
        cached_meta["filename"] = filename or cached_meta.get("filename") or "school_record.pdf"
        cached_meta["uploaded_at"] = datetime.now(timezone.utc).isoformat()
        forms["pdfImportMeta"] = cached_meta
        school["forms"] = forms
        school["pdfImportMeta"] = forms.get("pdfImportMeta") or {}
        school["rawSchoolRecordText"] = forms.get("rawSchoolRecordText") or ""
        school["parsedSchoolRecord"] = forms.get("parsedSchoolRecord") or {}
        school["parsedSchoolRecordSummary"] = forms.get("parsedSchoolRecordSummary") or {}
        await SupabaseService.update_user_profile_school_record(user_id, school)
        total_ms = int((time.perf_counter() - started_at) * 1000)
        return {
            "ok": True,
            "message": "동일한 PDF가 이미 파싱되어 캐시 결과를 사용했습니다.",
            "meta": cached_meta,
            "summary": forms.get("parsedSchoolRecordSummary") or {},
            "parsedPreview": _build_parsed_preview(forms.get("parsedSchoolRecord") or {}),
            "timings": {
                "cache_hit": True,
                "total_ms": total_ms,
            },
        }

    extract_started_at = time.perf_counter()
    try:
        extracted, page_count, extraction_method = _extract_text_from_pdf_bytes(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF 텍스트 추출 실패: {str(e)}")
    extract_ms = int((time.perf_counter() - extract_started_at) * 1000)

    if page_count <= 0:
        raise HTTPException(
            status_code=400,
            detail="PDF 페이지를 읽을 수 없습니다. 파일이 손상되었거나 지원되지 않는 형식인지 확인해 주세요.",
        )
    if len(extracted.strip()) < MIN_EXTRACTED_TEXT_CHARS:
        raise HTTPException(
            status_code=400,
            detail="텍스트를 거의 추출하지 못했습니다. 텍스트 선택 가능한 PDF이거나 선명한 스캔본인지 확인해 주세요.",
        )

    parse_started_at = time.perf_counter()
    raw_text = extracted
    parse_method = "rule"
    parsed_forms = _build_forms_from_pdf_text(raw_text)
    _normalize_academic_subjects(parsed_forms.get("parsedSchoolRecord") or {})
    parse_ms = int((time.perf_counter() - parse_started_at) * 1000)
    total_ms = int((time.perf_counter() - started_at) * 1000)

    # 심층분석에서 바로 활용할 수 있도록 원문 전체 텍스트 저장
    forms["rawSchoolRecordText"] = raw_text
    forms["pdfImportMeta"] = {
        "filename": filename,
        "char_count": len(raw_text),
        "page_count": page_count,
        "extraction_method": extraction_method,
        "parse_method": parse_method,
        "file_hash": file_hash,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "timings_ms": {
            "extract_ms": extract_ms,
            "parse_ms": parse_ms,
            "total_ms": total_ms,
        },
    }

    # PDF 파싱 결과 전부를 user_profiles.school_record(JSONB)에 저장 (deep copy로 전체 구조 보존)
    full_parsed = copy.deepcopy(parsed_forms["parsedSchoolRecord"])
    full_summary = copy.deepcopy(parsed_forms["parseSummary"])
    forms["creativeActivity"] = parsed_forms["creativeActivity"]
    forms["academicDev"] = parsed_forms["academicDev"]
    forms["individualDev"] = parsed_forms["individualDev"]
    forms["behaviorOpinion"] = parsed_forms["behaviorOpinion"]
    forms["volunteerActivity"] = parsed_forms["volunteerActivity"]
    forms["parsedSchoolRecord"] = full_parsed
    forms["parsedSchoolRecordSummary"] = full_summary

    school["forms"] = forms
    school["pdfImportMeta"] = copy.deepcopy(forms["pdfImportMeta"])
    school["rawSchoolRecordText"] = raw_text
    school["parsedSchoolRecord"] = full_parsed
    school["parsedSchoolRecordSummary"] = full_summary
    await SupabaseService.update_user_profile_school_record(user_id, school)

    # 매칭용 내부 요약 1회 생성 (적합 학교 추천 시 사용, 사용자 비노출)
    try:
        from school_record_eval.matching_summary import generate_matching_summary_from_school_record
        matching_text = await generate_matching_summary_from_school_record(school)
        if matching_text:
            school["matchingSummary"] = matching_text
            forms["matchingSummary"] = matching_text
            school["forms"] = forms
            await SupabaseService.update_user_profile_school_record(user_id, school)
    except Exception as e:
        print(f"⚠️ 매칭용 요약 생성 실패(무시, 최초 추천 요청 시 생성됨): {e}")

    return {
        "ok": True,
        "message": "생기부 PDF를 전체 파싱하여 연동했습니다.",
        "meta": forms.get("pdfImportMeta"),
        "summary": parsed_forms["parseSummary"],
        "parsedPreview": _build_parsed_preview(parsed_forms["parsedSchoolRecord"]),
        "timings": {
            "cache_hit": False,
            "extract_ms": extract_ms,
            "parse_ms": parse_ms,
            "total_ms": total_ms,
        },
    }
