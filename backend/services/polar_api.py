"""
Polar API 클라이언트 (구독 상태 조회)
- POLAR_ACCESS_TOKEN으로 인증
- external_customer_id = Supabase user id (체크아웃 시 client_reference_id로 전달된 값)
"""
import logging
from typing import Optional
import httpx
from config.config import settings

logger = logging.getLogger(__name__)
POLAR_API_BASE = "https://api.polar.sh"


def get_subscriptions_by_external_customer_id(
    external_customer_id: str,
    active_only: bool = True,
) -> list[dict]:
    """
    Polar API: 해당 external_customer_id(Supabase user id)의 구독 목록 조회
    - active=True면 활성/트라이얼 구독만
    - Returns: list of subscription objects (또는 API 오류 시 빈 리스트)
    """
    token = getattr(settings, "POLAR_ACCESS_TOKEN", None) or ""
    if not token or not external_customer_id:
        return []

    url = f"{POLAR_API_BASE}/v1/subscriptions/"
    params = {"external_customer_id": external_customer_id}
    if active_only:
        params["active"] = "true"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items") if isinstance(data, dict) else []
        return items if isinstance(items, list) else []
    except httpx.HTTPStatusError as e:
        logger.warning("Polar API subscriptions list error: %s %s", e.response.status_code, e.response.text)
        return []
    except Exception as e:
        logger.warning("Polar API request error: %s", e)
        return []


def has_active_subscription(external_customer_id: str) -> bool:
    """해당 유저가 활성 구독(active 또는 trialing)을 하나라도 갖고 있는지 여부"""
    subs = get_subscriptions_by_external_customer_id(external_customer_id, active_only=True)
    active_statuses = {"active", "trialing"}
    return any((s.get("status") or "").lower() in active_statuses for s in subs)
