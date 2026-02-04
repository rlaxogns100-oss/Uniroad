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
        # 관리자 권한 클라이언트 사용
        client = supabase_service.get_admin_client()
        
        # 오늘 자정 기준
        today = datetime.now().date()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())
        
        # Supabase auth.users에서 오늘 로그인한 사용자 조회
        try:
            response = client.auth.admin.list_users()
        except Exception as auth_error:
            print(f"⚠️ Auth admin API 접근 실패, 대체 방법 사용: {auth_error}")
            # 대체 방법: user_profiles 테이블 사용
            return {
                "success": True,
                "today": today.isoformat(),
                "total_logins_today": 0,
                "hourly_stats": [{"time": f"{i:02d}:00", "count": 0} for i in range(24)],
                "recent_logins": [],
                "timestamp": datetime.now().isoformat(),
                "note": "Auth admin API 접근 불가"
            }
        
        # response가 list인 경우와 객체인 경우 모두 처리
        if isinstance(response, list):
            users = response
        else:
            users = response.users if hasattr(response, 'users') else []
        
        # 오늘 로그인한 사용자 필터링
        today_logins = []
        hourly_stats = {f"{i:02d}:00": 0 for i in range(24)}
        
        for user in users:
            # last_sign_in_at이 오늘인지 확인
            if user.last_sign_in_at:
                try:
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
                except Exception as e:
                    print(f"⚠️ last_sign_in_at 파싱 오류: {e}, user: {user}")
        
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
        # 관리자 권한 클라이언트 사용
        client = supabase_service.get_admin_client()
        
        today = datetime.now().date()
        
        # 모든 사용자 조회
        try:
            response = client.auth.admin.list_users()
        except Exception as auth_error:
            print(f"⚠️ Auth admin API 접근 실패, 대체 방법 사용: {auth_error}")
            # 대체 방법: user_profiles 테이블 사용
            return {
                "success": True,
                "total_users": 0,
                "today_new_users": 0,
                "today_logins": 0,
                "timestamp": datetime.now().isoformat(),
                "note": "Auth admin API 접근 불가"
            }
        
        # response가 list인 경우와 객체인 경우 모두 처리
        if isinstance(response, list):
            users = response
        else:
            users = response.users if hasattr(response, 'users') else []
            
        total_users = len(users)
        today_new_users = 0
        today_logins = 0
        
        for user in users:
            # 오늘 신규 가입자
            if user.created_at:
                try:
                    # created_at이 문자열인 경우 처리
                    if isinstance(user.created_at, str):
                        created = datetime.fromisoformat(user.created_at.replace('Z', '+00:00'))
                    else:
                        created = user.created_at
                    created_local = created.astimezone().replace(tzinfo=None)
                    if created_local.date() == today:
                        # 관리자 계정 제외
                        if not is_admin_account(email=user.email):
                            today_new_users += 1
                except Exception as e:
                    print(f"⚠️ created_at 파싱 오류: {e}, user: {user}")
            
            # 오늘 로그인한 사용자
            if user.last_sign_in_at:
                try:
                    last_signin = datetime.fromisoformat(user.last_sign_in_at.replace('Z', '+00:00'))
                    last_signin_local = last_signin.astimezone().replace(tzinfo=None)
                    if last_signin_local.date() == today:
                        # 관리자 계정 제외
                        if not is_admin_account(email=user.email):
                            today_logins += 1
                except Exception as e:
                    print(f"⚠️ last_sign_in_at 파싱 오류: {e}, user: {user}")
        
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


@router.get("/api/analytics/funnel")
async def get_funnel_analysis(days: int = 7) -> Dict[str, Any]:
    """
    전환 깔때기 분석
    - 랜딩 → 채팅 → 로그인 → 메시지 전송
    """
    try:
        client = supabase_service.get_client()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # user_journeys 테이블에서 데이터 조회
        result = client.table("user_journeys") \
            .select("*") \
            .gte("first_visit_at", start_date.isoformat()) \
            .execute()
        
        # 전체 깔때기 통계
        total_stats = {
            "landing_visits": 0,
            "chat_visits": 0,
            "logged_in": 0,
            "sent_message": 0,
            "completed_session": 0
        }
        
        # UTM별 통계
        utm_stats = {}
        
        for journey in result.data:
            # 관리자 필터링
            if journey.get("user_id") and is_admin_account(user_id=journey["user_id"]):
                continue
                
            # 전체 통계 업데이트
            if journey.get("visited_landing"):
                total_stats["landing_visits"] += 1
            if journey.get("visited_chat"):
                total_stats["chat_visits"] += 1
            if journey.get("logged_in"):
                total_stats["logged_in"] += 1
            if journey.get("asked_question"):
                total_stats["sent_message"] += 1
            if journey.get("chat_messages_count", 0) > 0:
                total_stats["completed_session"] += 1
            
            # UTM별 통계
            utm_key = f"{journey.get('first_utm_source', 'direct')}|{journey.get('first_utm_medium', 'none')}"
            if utm_key not in utm_stats:
                utm_stats[utm_key] = {
                    "utm_source": journey.get("first_utm_source", "direct"),
                    "utm_medium": journey.get("first_utm_medium", "none"),
                    "landing_visits": 0,
                    "chat_visits": 0,
                    "logged_in": 0,
                    "sent_message": 0
                }
            
            if journey.get("visited_landing"):
                utm_stats[utm_key]["landing_visits"] += 1
            if journey.get("visited_chat"):
                utm_stats[utm_key]["chat_visits"] += 1
            if journey.get("logged_in"):
                utm_stats[utm_key]["logged_in"] += 1
            if journey.get("asked_question"):
                utm_stats[utm_key]["sent_message"] += 1
        
        # 전환율 계산
        def calculate_conversion(from_value: int, to_value: int) -> float:
            return round((to_value / from_value * 100) if from_value > 0 else 0, 1)
        
        # 전체 전환율
        total_conversions = {
            "landing_to_chat": calculate_conversion(
                total_stats["landing_visits"], 
                total_stats["chat_visits"]
            ),
            "chat_to_login": calculate_conversion(
                total_stats["chat_visits"], 
                total_stats["logged_in"]
            ),
            "login_to_message": calculate_conversion(
                total_stats["logged_in"], 
                total_stats["sent_message"]
            )
        }
        
        # UTM별 전환율
        utm_conversions = []
        for utm_key, stats in utm_stats.items():
            utm_conversions.append({
                "utm_source": stats["utm_source"],
                "utm_medium": stats["utm_medium"],
                "stats": stats,
                "conversions": {
                    "landing_to_chat": calculate_conversion(
                        stats["landing_visits"], 
                        stats["chat_visits"]
                    ),
                    "chat_to_login": calculate_conversion(
                        stats["chat_visits"], 
                        stats["logged_in"]
                    ),
                    "login_to_message": calculate_conversion(
                        stats["logged_in"], 
                        stats["sent_message"]
                    )
                }
            })
        
        # 방문자 수 기준으로 정렬
        utm_conversions.sort(
            key=lambda x: x["stats"]["landing_visits"], 
            reverse=True
        )
        
        return {
            "success": True,
            "period_days": days,
            "total_stats": total_stats,
            "total_conversions": total_conversions,
            "utm_conversions": utm_conversions[:10],  # 상위 10개만
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 깔때기 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/device-stats")
async def get_device_stats(days: int = 7) -> Dict[str, Any]:
    """
    디바이스 및 브라우저 통계
    """
    try:
        client = supabase_service.get_client()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # page_views에서 디바이스 정보 조회
        result = client.table("page_views") \
            .select("device_type, browser, os") \
            .gte("created_at", start_date.isoformat()) \
            .execute()
        
        # 통계 집계
        device_stats = {}
        browser_stats = {}
        os_stats = {}
        
        for view in result.data:
            # 디바이스 타입
            device = view.get("device_type", "unknown")
            device_stats[device] = device_stats.get(device, 0) + 1
            
            # 브라우저
            browser = view.get("browser", "unknown")
            browser_stats[browser] = browser_stats.get(browser, 0) + 1
            
            # OS
            os = view.get("os", "unknown")
            os_stats[os] = os_stats.get(os, 0) + 1
        
        # 백분율 계산 및 정렬
        total_views = len(result.data)
        
        def to_percentage_list(stats_dict):
            total = sum(stats_dict.values())
            return sorted(
                [
                    {
                        "name": name,
                        "count": count,
                        "percentage": round((count / total * 100) if total > 0 else 0, 1)
                    }
                    for name, count in stats_dict.items()
                ],
                key=lambda x: x["count"],
                reverse=True
            )[:5]  # 상위 5개만
        
        return {
            "success": True,
            "period_days": days,
            "total_views": total_views,
            "device_stats": to_percentage_list(device_stats),
            "browser_stats": to_percentage_list(browser_stats),
            "os_stats": to_percentage_list(os_stats),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 디바이스 통계 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/popular-questions")
async def get_popular_questions(days: int = 30) -> Dict[str, Any]:
    """
    인기 질문 분석
    """
    try:
        client = supabase_service.get_client()
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 모든 질문 가져오기
        result = client.table("chat_messages") \
            .select("content, role, created_at") \
            .gte("created_at", start_date.isoformat()) \
            .eq("role", "user") \
            .execute()
        
        # 질문 패턴 분석
        question_patterns = {
            "합격 가능성": [],
            "점수/성적": [],
            "전형 관련": [],
            "학과/전공": [],
            "대학 정보": [],
            "경쟁률": [],
            "기타": []
        }
        
        # 키워드 빈도
        keyword_frequency = {}
        
        for msg in result.data:
            question = msg.get("content", "")
            
            # 패턴 분류
            classified = False
            if any(keyword in question for keyword in ["합격", "가능", "갈 수 있", "될까", "되나요"]):
                question_patterns["합격 가능성"].append(question)
                classified = True
            if any(keyword in question for keyword in ["점수", "성적", "등급", "백분위"]):
                question_patterns["점수/성적"].append(question)
                classified = True
            if any(keyword in question for keyword in ["전형", "정시", "수시", "논술"]):
                question_patterns["전형 관련"].append(question)
                classified = True
            if any(keyword in question for keyword in ["학과", "전공", "계열"]):
                question_patterns["학과/전공"].append(question)
                classified = True
            if any(keyword in question for keyword in ["대학", "학교", "캠퍼스"]):
                question_patterns["대학 정보"].append(question)
                classified = True
            if any(keyword in question for keyword in ["경쟁률", "경쟁", "지원"]):
                question_patterns["경쟁률"].append(question)
                classified = True
            
            if not classified:
                question_patterns["기타"].append(question)
            
            # 키워드 추출 (간단한 방식)
            words = question.split()
            for word in words:
                if len(word) >= 2 and not word.isdigit():
                    keyword_frequency[word] = keyword_frequency.get(word, 0) + 1
        
        # 패턴별 통계
        pattern_stats = []
        total_questions = sum(len(questions) for questions in question_patterns.values())
        
        for pattern, questions in question_patterns.items():
            if len(questions) > 0:
                pattern_stats.append({
                    "pattern": pattern,
                    "count": len(questions),
                    "percentage": round((len(questions) / total_questions * 100) if total_questions > 0 else 0, 1),
                    "sample_questions": questions[:3]  # 샘플 3개
                })
        
        # 카운트 기준 정렬
        pattern_stats.sort(key=lambda x: x["count"], reverse=True)
        
        # 상위 키워드
        top_keywords = sorted(
            keyword_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]
        
        return {
            "success": True,
            "period_days": days,
            "total_questions": total_questions,
            "pattern_stats": pattern_stats,
            "top_keywords": [
                {"keyword": keyword, "count": count}
                for keyword, count in top_keywords
            ],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        print(f"❌ 인기 질문 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
