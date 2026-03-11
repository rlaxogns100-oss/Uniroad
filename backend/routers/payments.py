"""
Gumroad 결제 웹훅 API
- POST /api/v1/payments/webhook: Gumroad 웹훅 수신 후 users.is_premium 업데이트
"""
import json
import logging
from datetime import datetime
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from config.config import settings
from middleware.auth import get_current_user
from services.payment_service import set_user_premium
from services.supabase_client import SupabaseService, supabase_service
from utils.admin_filter import is_admin_account

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


class BankTransferSubmitRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    phone: str = Field(..., min_length=8, max_length=20)
    amount: int = Field(7900, ge=1000)


class CardCheckoutAttemptRequest(BaseModel):
    amount: int = 7900
    source: str = "gumroad"


class UpdateUserPlanRequest(BaseModel):
    user_id: str
    is_premium: bool


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) < 8:
        raise HTTPException(status_code=400, detail="전화번호를 올바르게 입력해주세요.")
    return digits


def _safe_iso(value: Any) -> str:
    s = _to_str(value)
    if not s:
        return ""
    return s


def _extract_auth_user_name(auth_user: Any) -> str:
    metadata = getattr(auth_user, "user_metadata", None) or {}
    if isinstance(metadata, dict):
        name = _to_str(metadata.get("name")) or _to_str(metadata.get("full_name"))
        if name:
            return name
    email = _to_str(getattr(auth_user, "email", None))
    return email.split("@")[0] if "@" in email else ""


def _load_auth_users(client) -> List[Dict[str, Any]]:
    """
    관리자 유저 목록은 auth.users 기반으로 조회한다.
    (public.users는 is_premium 보조 정보로만 사용)
    """
    users: List[Dict[str, Any]] = []
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
            users.append(
                {
                    "id": uid,
                    "email": _to_str(getattr(auth_user, "email", None)),
                    "name": _extract_auth_user_name(auth_user),
                    "created_at": _safe_iso(getattr(auth_user, "created_at", None)),
                }
            )

        if len(batch) < per_page:
            break
        page += 1

    return users


def _append_payment_metadata(user_id: str, key: str, item: dict) -> bool:
    client = SupabaseService.get_admin_client()
    try:
        existing = (
            client.table("user_profiles")
            .select("user_id, scores, metadata")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if existing.data and len(existing.data) > 0:
            row = existing.data[0]
            meta = dict(row.get("metadata") or {})
            current = meta.get(key)
            if not isinstance(current, list):
                current = []
            current.append(item)
            meta[key] = current
            (
                client.table("user_profiles")
                .update({"metadata": meta})
                .eq("user_id", user_id)
                .execute()
            )
        else:
            meta = {key: [item]}
            (
                client.table("user_profiles")
                .insert({"user_id": user_id, "scores": {}, "metadata": meta})
                .execute()
            )
        return True
    except Exception as e:
        logger.warning("payment metadata append 실패 user_id=%s key=%s err=%s", user_id, key, e)
        return False


def _parse_custom_fields(payload: dict) -> dict:
    custom_fields = payload.get("custom_fields")
    if isinstance(custom_fields, dict):
        return custom_fields
    if isinstance(custom_fields, str):
        try:
            decoded = json.loads(custom_fields)
            if isinstance(decoded, dict):
                return decoded
        except Exception:
            return {}
    return {}


def _extract_token(payload: dict, request: Request) -> str:
    query_token = _to_str(request.query_params.get("token"))
    if query_token:
        return query_token
    for key in ("token", "webhook_token", "gumroad_webhook_token"):
        value = _to_str(payload.get(key))
        if value:
            return value
    return ""


def _extract_user_id(payload: dict) -> Optional[str]:
    direct_keys = (
        "user_id",
        "client_reference_id",
        "external_customer_id",
        "custom_fields[user_id]",
        "custom_field[user_id]",
        "url_params[user_id]",
    )
    for key in direct_keys:
        value = _to_str(payload.get(key))
        if value:
            return value

    custom_fields = _parse_custom_fields(payload)
    value = _to_str(custom_fields.get("user_id"))
    if value:
        return value
    return None


def _extract_email(payload: dict) -> Optional[str]:
    for key in ("email", "purchaser_email", "url_params[email]"):
        value = _to_str(payload.get(key))
        if value:
            return value
    return None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    s = _to_str(value).lower()
    return s in {"1", "true", "yes", "y"}


def _is_purchase_success(payload: dict) -> bool:
    # 명시적 실패/테스트 신호는 즉시 차단
    if _to_bool(payload.get("test")):
        return False
    if any(
        _to_bool(payload.get(key))
        for key in ("refunded", "is_refunded", "chargebacked", "chargeback", "disputed")
    ):
        return False

    # 이벤트 타입이 오면 sale/subscription만 허용
    resource_name = _to_str(payload.get("resource_name")).lower()
    if resource_name and resource_name not in {"sale", "subscription"}:
        return False

    # 상태값이 있을 때만 성공 상태 허용
    status = _to_str(payload.get("status")).lower()
    if status:
        return status in {"paid", "completed", "complete", "succeeded", "success"}

    # status가 비어 있으면 판매 이벤트로 보이는 최소 필드 조합이 있어야 성공 처리
    has_email = bool(_extract_email(payload))
    has_sale_identifier = any(
        _to_str(payload.get(key))
        for key in ("sale_id", "purchase_id", "order_id", "order_number", "id")
    )
    has_product = any(_to_str(payload.get(key)) for key in ("product_id", "product_name", "permalink"))
    has_price = any(
        _to_str(payload.get(key))
        for key in ("price", "amount_cents", "formatted_display_price", "currency")
    )
    return has_email and (has_sale_identifier or (has_product and has_price))


async def _find_user_id_by_email(email: str) -> Optional[str]:
    if not email:
        return None
    client = SupabaseService.get_admin_client()
    try:
        response = (
            client.table("users")
            .select("id")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        if response.data and len(response.data) > 0:
            return _to_str(response.data[0].get("id")) or None
    except Exception as e:
        logger.warning("users 테이블 email 조회 실패: %s", e)
    return None


@router.post("/bank-transfer/submit")
async def submit_bank_transfer(
    body: BankTransferSubmitRequest,
    user: dict = Depends(get_current_user),
):
    """
    무통장입금 신청:
    - 이름/전화번호를 user_profiles.metadata.bank_transfer_requests에 기록
    - 즉시 Pro 적용 (요청사항 반영)
    """
    user_id = _to_str(user.get("user_id"))
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    phone = _normalize_phone(body.phone)
    item = {
        "name": _to_str(body.name),
        "phone": phone,
        "amount": int(body.amount or 7900),
        "bank_account": "3333354523620",
        "bank_name": "카카오뱅크",
        "account_holder": "김태훈",
        "status": "applied",
        "created_at": datetime.utcnow().isoformat(),
    }
    _append_payment_metadata(user_id, "bank_transfer_requests", item)
    premium_ok = await set_user_premium(user_id, is_premium=True)
    return {"ok": True, "premium_applied": premium_ok}


@router.post("/card-checkout/attempt")
async def log_card_checkout_attempt(
    body: CardCheckoutAttemptRequest,
    user: dict = Depends(get_current_user),
):
    """
    카드결제 버튼 클릭 이력 기록 (관리자 결제 신청내역 표시용).
    """
    user_id = _to_str(user.get("user_id"))
    if not user_id:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")

    item = {
        "amount": int(body.amount or 7900),
        "source": _to_str(body.source) or "gumroad",
        "status": "requested",
        "created_at": datetime.utcnow().isoformat(),
    }
    ok = _append_payment_metadata(user_id, "card_checkout_requests", item)
    return {"ok": ok}


@router.get("/admin/users-overview")
async def get_admin_users_overview(user: dict = Depends(get_current_user)):
    """
    관리자 유저 화면 데이터:
    - 무통장입금 신청 내역
    - 카드결제 신청 내역
    - Pro/Basic 유저 목록 (가입일/총 채팅/최근 접속/요금제)
    """
    if not is_admin_account(email=user.get("email"), name=user.get("name")):
        raise HTTPException(status_code=403, detail="Admin only")

    client = supabase_service.get_admin_client()
    try:
        # 이름/메일은 auth.users를 기준으로 조회
        try:
            auth_users = _load_auth_users(client)
        except Exception as e:
            logger.warning("auth.users 조회 실패(users 테이블 fallback): %s", e)
            auth_users = []
        auth_total_users = len(auth_users)

        # public.users는 요금제 상태(is_premium) 보조 정보
        try:
            users_resp = (
                client.table("users")
                .select("id, is_premium, created_at, email, name")
                .execute()
            )
        except Exception:
            users_resp = (
                client.table("users")
                .select("id, is_premium, created_at")
                .execute()
            )
        users = users_resp.data or []
        auth_by_user = {_to_str(u.get("id")): u for u in auth_users if _to_str(u.get("id"))}
        public_by_user = {_to_str(u.get("id")): u for u in users if _to_str(u.get("id"))}
        merged_user_ids = list(auth_by_user.keys())
        merged_user_ids.extend([uid for uid in public_by_user.keys() if uid not in auth_by_user])
        try:
            count_resp = client.rpc("get_auth_user_count").execute()
            data = count_resp.data
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                if isinstance(first, int):
                    auth_total_users = first
                elif isinstance(first, dict):
                    auth_total_users = int(first.get("get_auth_user_count", len(auth_users)))
                else:
                    auth_total_users = int(first)
            elif isinstance(data, int):
                auth_total_users = data
            elif data is not None:
                auth_total_users = int(data)
        except Exception as e:
            logger.warning("get_auth_user_count 조회 실패(users 길이 사용): %s", e)

        stats_by_user: Dict[str, Dict[str, Any]] = {}
        start = 0
        batch = 1000
        while True:
            rows_resp = (
                client.table("session_chat_messages")
                .select("user_id, created_at, role")
                .not_.is_("user_id", "null")
                .range(start, start + batch - 1)
                .execute()
            )
            rows = rows_resp.data or []
            if not rows:
                break
            for row in rows:
                uid = _to_str(row.get("user_id"))
                if not uid:
                    continue
                if uid not in stats_by_user:
                    stats_by_user[uid] = {
                        "total_chat_count": 0,
                        "last_active_at": "",
                    }
                role = _to_str(row.get("role"))
                if role == "user":
                    stats_by_user[uid]["total_chat_count"] += 1
                created_at = _safe_iso(row.get("created_at"))
                if created_at and created_at > stats_by_user[uid]["last_active_at"]:
                    stats_by_user[uid]["last_active_at"] = created_at
            if len(rows) < batch:
                break
            start += batch

        profiles_resp = client.table("user_profiles").select("user_id, metadata").execute()
        profiles = profiles_resp.data or []
        profile_by_user = {
            _to_str(r.get("user_id")): (r.get("metadata") or {})
            for r in profiles
            if _to_str(r.get("user_id"))
        }

        email_by_user: Dict[str, str] = {}
        name_by_user: Dict[str, str] = {}
        for uid in merged_user_ids:
            auth_row = auth_by_user.get(uid, {})
            public_row = public_by_user.get(uid, {})
            email_by_user[uid] = _to_str(auth_row.get("email")) or _to_str(public_row.get("email"))
            name_by_user[uid] = _to_str(auth_row.get("name")) or _to_str(public_row.get("name"))

        bank_requests: List[dict] = []
        card_requests: List[dict] = []
        for uid, meta in profile_by_user.items():
            if not isinstance(meta, dict):
                continue

            bank_items = meta.get("bank_transfer_requests")
            if isinstance(bank_items, list):
                for item in bank_items:
                    if not isinstance(item, dict):
                        continue
                    bank_requests.append(
                        {
                            "user_id": uid,
                            "email": email_by_user.get(uid, ""),
                            "user_name": name_by_user.get(uid, ""),
                            "name": _to_str(item.get("name")),
                            "phone": _to_str(item.get("phone")),
                            "amount": int(item.get("amount") or 7900),
                            "status": _to_str(item.get("status")) or "applied",
                            "created_at": _safe_iso(item.get("created_at")),
                        }
                    )

            card_items = meta.get("card_checkout_requests")
            if isinstance(card_items, list):
                for item in card_items:
                    if not isinstance(item, dict):
                        continue
                    card_requests.append(
                        {
                            "user_id": uid,
                            "email": email_by_user.get(uid, ""),
                            "user_name": name_by_user.get(uid, ""),
                            "amount": int(item.get("amount") or 7900),
                            "source": _to_str(item.get("source")) or "gumroad",
                            "status": _to_str(item.get("status")) or "requested",
                            "created_at": _safe_iso(item.get("created_at")),
                        }
                    )

        bank_requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        card_requests.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        premium_users: List[dict] = []
        basic_users: List[dict] = []
        for uid in merged_user_ids:
            auth_row = auth_by_user.get(uid, {})
            public_row = public_by_user.get(uid, {})
            is_premium = bool(public_row.get("is_premium"))
            stat = stats_by_user.get(uid, {})
            row = {
                "id": uid,
                "email": _to_str(auth_row.get("email")) or _to_str(public_row.get("email")),
                "name": _to_str(auth_row.get("name")) or _to_str(public_row.get("name")),
                "recent_signup_at": _safe_iso(auth_row.get("created_at")) or _safe_iso(public_row.get("created_at")),
                "total_chat_count": int(stat.get("total_chat_count") or 0),
                "last_active_at": _safe_iso(stat.get("last_active_at")),
                "plan_status": "Pro" if is_premium else "Basic",
            }
            if is_premium:
                premium_users.append(row)
            else:
                basic_users.append(row)

        premium_users.sort(key=lambda x: x.get("recent_signup_at", ""), reverse=True)
        basic_users.sort(key=lambda x: x.get("recent_signup_at", ""), reverse=True)

        return {
            "bank_transfer_requests": bank_requests,
            "card_checkout_requests": card_requests,
            "premium_users": premium_users,
            "basic_users": basic_users,
            "total_users": auth_total_users,
            "total_users_users_table": len(users),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"users overview 조회 실패: {str(e)}")


@router.patch("/admin/user-plan")
async def update_user_plan(
    body: UpdateUserPlanRequest,
    user: dict = Depends(get_current_user),
):
    if not is_admin_account(email=user.get("email"), name=user.get("name")):
        raise HTTPException(status_code=403, detail="Admin only")
    user_id = _to_str(body.user_id)
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id가 필요합니다.")
    ok = await set_user_premium(user_id, is_premium=bool(body.is_premium))
    if not ok:
        raise HTTPException(status_code=500, detail="요금제 상태 변경에 실패했습니다.")
    return {"ok": True, "user_id": user_id, "is_premium": bool(body.is_premium)}


async def _parse_payload(request: Request) -> dict:
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
            return body if isinstance(body, dict) else {}
        except Exception:
            return {}

    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        return {k: v for k, v in form.items()}

    raw = await request.body()
    if not raw:
        return {}
    try:
        body = json.loads(raw.decode("utf-8"))
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


@router.post("/webhook")
async def gumroad_webhook(request: Request):
    expected_token = _to_str(getattr(settings, "GUMROAD_WEBHOOK_TOKEN", ""))
    if not expected_token:
        logger.warning("GUMROAD_WEBHOOK_TOKEN 미설정")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    payload = await _parse_payload(request)
    incoming_token = _extract_token(payload, request)
    if not incoming_token or incoming_token != expected_token:
        logger.warning("Gumroad webhook token 검증 실패")
        raise HTTPException(status_code=403, detail="Invalid webhook token")

    if not _is_purchase_success(payload):
        return JSONResponse(status_code=200, content={"ok": True, "message": "Not paid"})

    user_id = _extract_user_id(payload)
    if not user_id:
        email = _extract_email(payload)
        user_id = await _find_user_id_by_email(email or "")

    if not user_id:
        logger.warning("Gumroad webhook 사용자 매핑 실패. payload_keys=%s", list(payload.keys()))
        return JSONResponse(status_code=200, content={"ok": False, "message": "User mapping failed"})

    ok = await set_user_premium(user_id, is_premium=True)
    return JSONResponse(status_code=200, content={"ok": ok, "user_id": user_id})


@router.post("/payapp/feedback")
async def payapp_feedback(request: Request):
    """
    PayApp feedbackurl 엔드포인트.
    결제 완료(pay_state=4) 시 자동으로 Pro 활성화.
    """
    payload = await _parse_payload(request)

    expected_token = _to_str(getattr(settings, "PAYAPP_FEEDBACK_TOKEN", ""))
    incoming_token = _to_str(request.query_params.get("token"))
    if expected_token and incoming_token != expected_token:
        logger.warning("PayApp feedback token 검증 실패")
        raise HTTPException(status_code=403, detail="Invalid PayApp feedback token")

    mul_no = _to_str(payload.get("mul_no"))
    pay_state = _to_str(payload.get("pay_state"))

    logger.info(
        "PayApp feedback 수신 mul_no=%s pay_state=%s price=%s pay_type=%s var1=%s",
        mul_no, pay_state,
        _to_str(payload.get("price")),
        _to_str(payload.get("pay_type")),
        _to_str(payload.get("var1")),
    )

    configured_userid = _to_str(getattr(settings, "PAYAPP_USERID", ""))
    if configured_userid:
        incoming_userid = _to_str(payload.get("userid"))
        if incoming_userid and incoming_userid != configured_userid:
            logger.warning("PayApp feedback userid 불일치: expected=%s got=%s", configured_userid, incoming_userid)
            return PlainTextResponse("FAIL", status_code=200)

    configured_linkkey = _to_str(getattr(settings, "PAYAPP_LINKKEY", ""))
    if configured_linkkey:
        incoming_linkkey = _to_str(payload.get("linkkey"))
        if incoming_linkkey and incoming_linkkey != configured_linkkey:
            logger.warning("PayApp feedback linkkey 불일치 mul_no=%s", mul_no)
            return PlainTextResponse("FAIL", status_code=200)

    configured_linkval = _to_str(getattr(settings, "PAYAPP_LINKVAL", ""))
    if configured_linkval:
        incoming_linkval = _to_str(payload.get("linkval"))
        if incoming_linkval and incoming_linkval != configured_linkval:
            logger.warning("PayApp feedback linkval 불일치 mul_no=%s", mul_no)
            return PlainTextResponse("FAIL", status_code=200)

    if pay_state != "4":
        logger.info("PayApp feedback 결제완료 아님 pay_state=%s mul_no=%s", pay_state, mul_no)
        return PlainTextResponse("SUCCESS", status_code=200)

    user_id = _to_str(payload.get("var1"))
    if not user_id:
        logger.warning("PayApp feedback var1(user_id) 누락 mul_no=%s", mul_no)
        return PlainTextResponse("SUCCESS", status_code=200)

    ok = await set_user_premium(user_id, is_premium=True)
    logger.info("PayApp Pro 활성화 user_id=%s ok=%s mul_no=%s", user_id, ok, mul_no)

    _append_payment_metadata(user_id, "payapp_payments", {
        "mul_no": mul_no,
        "price": _to_str(payload.get("price")),
        "pay_type": _to_str(payload.get("pay_type")),
        "pay_date": _to_str(payload.get("pay_date")),
        "pay_state": pay_state,
        "source": "payapp_feedback",
        "created_at": datetime.utcnow().isoformat(),
    })

    return PlainTextResponse("SUCCESS", status_code=200)
