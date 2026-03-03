"""
Polar 결제 웹훅 처리 서비스
- checkout.updated / subscription.created 시 client_reference_id로 Supabase users 테이블 is_premium 업데이트
- user_profiles.metadata.is_premium 동기화 (기존 호환)
"""
from typing import Optional
from services.supabase_client import SupabaseService


async def set_user_premium_in_users_table(user_id: str, is_premium: bool = True) -> bool:
    """
    Supabase public.users 테이블에서 해당 id 유저의 is_premium 컬럼을 업데이트.
    - 행이 없으면 upsert로 삽입 후 true 반환.
    """
    if not user_id or not user_id.strip():
        print("[payment_service] set_user_premium_in_users_table: user_id 비어 있음, 스킵")
        return False
    client = SupabaseService.get_admin_client()
    try:
        print(f"[payment_service] users 테이블 업데이트 시도: id={user_id}, is_premium={is_premium}")
        result = (
            client.table("users")
            .update({"is_premium": is_premium})
            .eq("id", user_id)
            .execute()
        )
        count = len(result.data) if result.data is not None else 0
        if count > 0:
            print(f"[payment_service] users 테이블 업데이트 완료: id={user_id}, 영향 행 수={count}")
            return True
        print(f"[payment_service] users 테이블에 해당 id 없음, upsert 시도: id={user_id}")
        upsert_result = (
            client.table("users")
            .upsert({"id": user_id, "is_premium": is_premium}, on_conflict="id")
            .execute()
        )
        ok = upsert_result.data and len(upsert_result.data) > 0
        print(f"[payment_service] users 테이블 upsert 완료: id={user_id}, ok={ok}")
        return ok
    except Exception as e:
        print(f"[payment_service] ❌ users 테이블 업데이트 오류: user_id={user_id}, e={e}")
        return False


async def set_user_premium(user_id: str, is_premium: bool = True) -> bool:
    """
    결제 완료 시 유저를 프리미엄으로 설정.
    - public.users 테이블의 is_premium 컬럼 업데이트
    - user_profiles.metadata.is_premium 동기화 (기존 로직 유지)
    """
    if not user_id or not user_id.strip():
        print("[payment_service] set_user_premium: user_id 비어 있음, 스킵")
        return False
    print(f"[payment_service] set_user_premium 시작: user_id={user_id}")
    ok_users = await set_user_premium_in_users_table(user_id, is_premium)
    ok_profiles = await _set_user_premium_in_profiles(user_id, is_premium)
    print(f"[payment_service] set_user_premium 완료: users={ok_users}, profiles={ok_profiles}")
    return ok_users or ok_profiles


async def _set_user_premium_in_profiles(user_id: str, is_premium: bool) -> bool:
    """Supabase user_profiles에 is_premium 반영 (metadata에 저장)."""
    client = SupabaseService.get_admin_client()
    try:
        existing = (
            client.table("user_profiles")
            .select("user_id, scores, metadata")
            .eq("user_id", user_id)
            .execute()
        )
        metadata = {"is_premium": is_premium}
        if existing.data and len(existing.data) > 0:
            row = existing.data[0]
            existing_meta = row.get("metadata") or {}
            if isinstance(existing_meta, dict):
                metadata = {**existing_meta, "is_premium": is_premium}
            client.table("user_profiles").update({"metadata": metadata}).eq(
                "user_id", user_id
            ).execute()
            print(f"[payment_service] user_profiles metadata 업데이트 완료: user_id={user_id}")
        else:
            client.table("user_profiles").insert(
                {"user_id": user_id, "scores": {}, "metadata": metadata}
            ).execute()
            print(f"[payment_service] user_profiles 새 행 삽입 완료: user_id={user_id}")
        return True
    except Exception as e:
        print(f"[payment_service] ❌ user_profiles 오류: user_id={user_id}, e={e}")
        return False
