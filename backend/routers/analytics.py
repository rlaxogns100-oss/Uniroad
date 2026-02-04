"""
Analytics Router
- 사용자 로그인 통계
- 실시간 대시보드 데이터
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import Dict, Any, List
from services.supabase_client import supabase_service
from utils.admin_filter import is_admin_account

router = APIRouter()


@router.get("/api/analytics/login-stats")
async def get_login_stats() -> Dict[str, Any]:
    """
    오늘 로그인한 사용자 통계
    - 오늘 로그인한 사용자 수
    - 시간대별 로그인 수
    - 최근 로그인 사용자 목록
    """
    try:
        client = supabase_service.get_client()
        
        # 오늘 자정 기준
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # Supabase auth.users에서 오늘 로그인한 사용자 조회
        response = client.auth.admin.list_users()
        
        # 오늘 로그인한 사용자 필터링
        today_logins = []
        hourly_stats = {f"{i:02d}:00": 0 for i in range(24)}
        
        for user in response.users:
            # last_sign_in_at이 오늘인지 확인
            if user.last_sign_in_at:
                last_signin = datetime.fromisoformat(user.last_sign_in_at.replace('Z', '+00:00'))
                last_signin_local = last_signin.astimezone().replace(tzinfo=None)
                
                if last_signin_local.date() == today:
                    # 관리자 계정 제외
                    if is_admin_account(email=user.email):
                        print(f"⏭️ 관리자 계정 제외: {user.email}")
                        continue
                    
                    hour = last_signin_local.hour
                    hourly_stats[f"{hour:02d}:00"] += 1
                    
                    today_logins.append({
                        "id": user.id,
                        "email": user.email,
                        "display_name": user.user_metadata.get("display_name", user.email.split("@")[0]) if user.user_metadata else user.email.split("@")[0],
                        "last_sign_in": last_signin_local.isoformat(),
                        "created_at": user.created_at.isoformat() if user.created_at else None,
                    })
        
        # 최근 로그인 순으로 정렬
        today_logins.sort(key=lambda x: x["last_sign_in"], reverse=True)
        
        # 시간대별 통계를 리스트로 변환
        hourly_list = [
            {"time": time, "count": count}
            for time, count in hourly_stats.items()
        ]
        
        return {
            "success": True,
            "today": today.isoformat(),
            "total_logins_today": len(today_logins),
            "hourly_stats": hourly_list,
            "recent_logins": today_logins[:20],  # 최근 20명
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 로그인 통계 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/user-summary")
async def get_user_summary() -> Dict[str, Any]:
    """
    사용자 요약 통계
    - 전체 사용자 수
    - 오늘 신규 가입자
    - 오늘 로그인한 사용자
    """
    try:
        client = supabase_service.get_client()
        
        today = datetime.now().date()
        
        # 모든 사용자 조회
        response = client.auth.admin.list_users()
        
        total_users = len(response.users)
        today_new_users = 0
        today_logins = 0
        
        for user in response.users:
            # 오늘 신규 가입자
            if user.created_at:
                created = user.created_at.astimezone().replace(tzinfo=None)
                if created.date() == today:
                    # 관리자 계정 제외
                    if not is_admin_account(email=user.email):
                        today_new_users += 1
            
            # 오늘 로그인한 사용자
            if user.last_sign_in_at:
                last_signin = datetime.fromisoformat(user.last_sign_in_at.replace('Z', '+00:00'))
                last_signin_local = last_signin.astimezone().replace(tzinfo=None)
                if last_signin_local.date() == today:
                    # 관리자 계정 제외
                    if not is_admin_account(email=user.email):
                        today_logins += 1
        
        return {
            "success": True,
            "total_users": total_users,
            "today_new_users": today_new_users,
            "today_logins": today_logins,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 사용자 요약 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
