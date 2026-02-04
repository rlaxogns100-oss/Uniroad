"""
Analytics Router
- 사용자 로그인 통계
- 실시간 대시보드 데이터
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
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
        
@router.get("/api/analytics/utm-questions")
async def get_utm_questions(
    utm_source: Optional[str] = None,
    utm_medium: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """
    UTM별 인기 질문 분석
    - 어떤 매체에서 온 사용자가 어떤 질문을 많이 하는지
    """
    try:
        client = supabase_service.get_client()
        
        # 기본 쿼리
        query = client.table("chat_sessions")\
            .select("utm_source, utm_medium, utm_campaign, chat_messages(content, created_at)")\
            .gte("created_at", (datetime.now() - timedelta(days=days)).isoformat())
        
        # UTM 필터 적용
        if utm_source:
            query = query.eq("utm_source", utm_source)
        if utm_medium:
            query = query.eq("utm_medium", utm_medium)
        
        response = query.execute()
        
        # 질문 패턴 분석
        question_patterns = {
            "합격 가능성": ["합격", "가능", "확률", "가능성"],
            "점수/성적": ["점수", "성적", "등급", "백분위", "표준점수"],
            "전형 관련": ["전형", "수시", "정시", "학종", "교과"],
            "학과/전공": ["학과", "전공", "학부", "계열"],
            "대학 정보": ["대학", "학교", "캠퍼스"],
            "경쟁률": ["경쟁률", "지원", "인원"],
        }
        
        # UTM별 질문 분석
        utm_analysis = {}
        
        for session in response.data:
            utm_key = f"{session.get('utm_source', 'direct')}_{session.get('utm_medium', 'none')}"
            
            if utm_key not in utm_analysis:
                utm_analysis[utm_key] = {
                    "utm_source": session.get('utm_source', 'direct'),
                    "utm_medium": session.get('utm_medium', 'none'),
                    "utm_campaign": session.get('utm_campaign'),
                    "total_questions": 0,
                    "patterns": {pattern: 0 for pattern in question_patterns},
                    "sample_questions": []
                }
            
            # 사용자 메시지만 분석
            for msg in session.get('chat_messages', []):
                if msg.get('content'):
                    content = msg['content'].lower()
                    utm_analysis[utm_key]["total_questions"] += 1
                    
                    # 샘플 질문 저장 (최대 5개)
                    if len(utm_analysis[utm_key]["sample_questions"]) < 5:
                        utm_analysis[utm_key]["sample_questions"].append(msg['content'][:100])
                    
                    # 패턴 매칭
                    for pattern, keywords in question_patterns.items():
                        if any(keyword in content for keyword in keywords):
                            utm_analysis[utm_key]["patterns"][pattern] += 1
        
        # 결과 정리
        results = []
        for utm_key, data in utm_analysis.items():
            if data["total_questions"] > 0:
                # 패턴별 비율 계산
                pattern_percentages = {
                    pattern: round(100 * count / data["total_questions"], 1)
                    for pattern, count in data["patterns"].items()
                }
                
                results.append({
                    "utm_source": data["utm_source"],
                    "utm_medium": data["utm_medium"],
                    "utm_campaign": data["utm_campaign"],
                    "total_questions": data["total_questions"],
                    "pattern_percentages": pattern_percentages,
                    "top_patterns": sorted(
                        pattern_percentages.items(), 
                        key=lambda x: x[1], 
                        reverse=True
                    )[:3],
                    "sample_questions": data["sample_questions"]
                })
        
        # 총 질문 수로 정렬
        results.sort(key=lambda x: x["total_questions"], reverse=True)
        
        return {
            "success": True,
            "period_days": days,
            "utm_analysis": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ UTM 질문 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
