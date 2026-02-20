"""
Gumroad 결제 웹훅 API
- POST /api/v1/payments/webhook: Gumroad 웹훅 수신 후 users.is_premium 업데이트
"""
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from config.config import settings
from services.payment_service import set_user_premium
from services.supabase_client import SupabaseService

logger = logging.getLogger(__name__)
router = APIRouter()


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


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
