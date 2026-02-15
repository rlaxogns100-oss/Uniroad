"""
Polar 결제 웹훅 API
- POST /api/v1/payments/webhook: checkout.updated / subscription.created 처리, 결제 완료 시 users.is_premium 업데이트
- GET /api/v1/payments/subscription-status: 로그인 유저의 Polar 구독 상태 조회
"""
import json
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from config.config import settings
from middleware.auth import get_current_user
from services.payment_service import set_user_premium
from services.polar_api import get_subscriptions_by_external_customer_id
from utils.polar_webhook import verify_polar_webhook

logger = logging.getLogger(__name__)
router = APIRouter()

# 결제 완료로 간주할 checkout status 값
CHECKOUT_COMPLETED_STATUSES = {"completed", "succeeded", "complete"}


def _get_client_reference_id(data: dict) -> str | None:
    """Polar 웹훅 data에서 client_reference_id 추출 (다양한 위치 대응)"""
    if not data:
        return None
    for key in ("client_reference_id", "customer_id", "external_customer_id"):
        if data.get(key):
            return str(data[key]).strip() or None
    sub = data.get("subscription") or data.get("subscription_id")
    if isinstance(sub, dict) and sub.get("client_reference_id"):
        return str(sub["client_reference_id"]).strip()
    checkout = data.get("checkout")
    if isinstance(checkout, dict):
        cid = checkout.get("client_reference_id")
        if cid:
            return str(cid).strip()
        # checkout 객체 자체에 없으면 data 루트에서
        cid = checkout.get("customer", {}).get("external_id") if isinstance(checkout.get("customer"), dict) else None
        if cid:
            return str(cid).strip()
    return None


def _is_checkout_completed(data: dict) -> bool:
    """checkout.updated 데이터에서 결제 완료 여부 판단"""
    checkout = data.get("checkout") if isinstance(data.get("checkout"), dict) else None
    if not checkout:
        status = data.get("status")
    else:
        status = checkout.get("status") or data.get("status")
    if not status:
        return False
    return str(status).strip().lower() in CHECKOUT_COMPLETED_STATUSES


@router.post("/webhook")
async def polar_webhook(request: Request):
    """
    Polar 웹훅 수신.
    - POLAR_WEBHOOK_SECRET으로 서명 검증
    - checkout.updated / subscription.created 시 결제 완료면 client_reference_id로 users.is_premium = true
    """
    print("[Polar webhook] 요청 수신")
    secret = getattr(settings, "POLAR_WEBHOOK_SECRET", None) or ""
    if not secret:
        print("[Polar webhook] ❌ POLAR_WEBHOOK_SECRET 미설정")
        logger.warning("POLAR_WEBHOOK_SECRET 미설정")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    body = await request.body()
    headers = dict(request.headers)
    print(f"[Polar webhook] 본문 길이={len(body)} bytes, 서명 검증 시도")

    if not verify_polar_webhook(body, headers, secret):
        print("[Polar webhook] ❌ 서명 검증 실패 (Invalid signature)")
        logger.warning("Polar webhook signature verification failed")
        raise HTTPException(status_code=403, detail="Invalid signature")
    print("[Polar webhook] ✅ 서명 검증 성공")

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as e:
        print(f"[Polar webhook] ❌ JSON 파싱 실패: {e}")
        logger.warning("Webhook body decode error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid body")

    event_type = payload.get("type") or payload.get("event_type")
    data = payload.get("data") or payload
    print(f"[Polar webhook] 이벤트 타입={event_type}, data 키={list(data.keys()) if isinstance(data, dict) else 'n/a'}")

    if event_type == "subscription.created":
        user_id = _get_client_reference_id(data)
        print(f"[Polar webhook] subscription.created → client_reference_id={user_id}")
        if not user_id:
            print("[Polar webhook] subscription.created: client_reference_id 없음, 스킵")
            logger.warning("subscription.created: client_reference_id not found in payload")
            return JSONResponse(
                status_code=200,
                content={"ok": True, "message": "No client_reference_id, skipped"},
            )
        print(f"[Polar webhook] 결제 완료 처리: user_id={user_id}, is_premium=true 반영 중")
        ok = await set_user_premium(user_id, is_premium=True)
        print(f"[Polar webhook] subscription.created 처리 완료: ok={ok}, user_id={user_id}")
        return JSONResponse(status_code=200, content={"ok": ok, "user_id": user_id})

    if event_type == "checkout.updated":
        if not _is_checkout_completed(data):
            print(f"[Polar webhook] checkout.updated: 결제 완료 상태 아님 (status 등 확인), 200 반환")
            return JSONResponse(status_code=200, content={"ok": True, "message": "Not completed"})
        user_id = _get_client_reference_id(data)
        print(f"[Polar webhook] checkout.updated (결제 완료) → client_reference_id={user_id}")
        if not user_id:
            print("[Polar webhook] checkout.updated: client_reference_id 없음, 스킵")
            return JSONResponse(
                status_code=200,
                content={"ok": True, "message": "No client_reference_id, skipped"},
            )
        print(f"[Polar webhook] 결제 완료 처리: user_id={user_id}, is_premium=true 반영 중")
        ok = await set_user_premium(user_id, is_premium=True)
        print(f"[Polar webhook] checkout.updated 처리 완료: ok={ok}, user_id={user_id}")
        return JSONResponse(status_code=200, content={"ok": ok, "user_id": user_id})

    print(f"[Polar webhook] 미처리 이벤트 타입={event_type}, 200 반환")
    return JSONResponse(status_code=200, content={"ok": True})


@router.get("/subscription-status")
async def get_subscription_status(user: dict = Depends(get_current_user)):
    """
    현재 로그인한 유저의 Polar 구독 상태 조회.
    POLAR_ACCESS_TOKEN으로 Polar API를 호출하며, external_customer_id = Supabase user id 사용.
    """
    token = getattr(settings, "POLAR_ACCESS_TOKEN", None) or ""
    if not token:
        raise HTTPException(
            status_code=503,
            detail="Polar API not configured (POLAR_ACCESS_TOKEN missing)",
        )
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User id not found")
    subs = get_subscriptions_by_external_customer_id(user_id, active_only=True)
    active_statuses = {"active", "trialing"}
    active_subs = [s for s in subs if (s.get("status") or "").lower() in active_statuses]
    is_active = len(active_subs) > 0
    # 클라이언트에 필요한 최소 정보만 반환
    summary = [
        {
            "id": s.get("id"),
            "status": s.get("status"),
            "current_period_end": s.get("current_period_end"),
            "cancel_at_period_end": s.get("cancel_at_period_end"),
        }
        for s in active_subs
    ]
    return {
        "is_active": is_active,
        "subscriptions": summary,
    }
