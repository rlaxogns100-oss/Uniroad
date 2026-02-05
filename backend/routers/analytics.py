"""
Analytics Router
- 사용자 로그인 통계, 실시간 대시보드 데이터

데이터 소스 (RAG 제외):
- user-summary: Auth(전체/신규) + events(오늘 로그인, 깔때기와 동일 소스)
- login-stats: Auth (오늘 로그인 목록/시간대)
- funnel: events + session_chat_messages (전환 깔때기)
- utm-questions: events(세션별 첫 UTM) + session_chat_messages(질문)
- device-stats: events(landing/chat_page의 device_type, browser, os)
- popular-questions: session_chat_messages(role=user)
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
    - 전체 사용자 수, 오늘 신규 가입자: Auth 기준
    - 오늘 로그인: events 기준 (깔때기·전환율과 동일 데이터 소스)
    """
    try:
        admin_client = supabase_service.get_admin_client()
        client = supabase_service.get_client()
        today = datetime.now().date()
        tz = datetime.now().astimezone().tzinfo
        today_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=tz)
        today_end = datetime.combine(today, datetime.max.time()).replace(tzinfo=tz)

        # 오늘 로그인: events 테이블 기준 (깔때기와 동일 소스)
        today_logins = 0
        try:
            login_res = client.table("events").select("id, user_id").eq("event_type", "login").gte("event_time", today_start.isoformat()).lte("event_time", today_end.isoformat()).execute()
            for row in login_res.data or []:
                if row.get("user_id") and is_admin_account(user_id=row["user_id"]):
                    continue
                today_logins += 1
        except Exception as e:
            print(f"⚠️ events 오늘 로그인 조회 실패: {e}")

        # 전체 사용자 수, 오늘 신규: Auth 기준
        try:
            response = admin_client.auth.admin.list_users()
        except Exception as auth_error:
            print(f"⚠️ Auth admin API 접근 실패: {auth_error}")
            return {
                "success": True,
                "total_users": 0,
                "today_new_users": 0,
                "today_logins": today_logins,
                "timestamp": datetime.now().isoformat(),
                "note": "Auth 접근 불가, today_logins만 events 기준 반영",
            }
        if isinstance(response, list):
            users = response
        else:
            users = response.users if hasattr(response, "users") else []
        total_users = len(users)
        today_new_users = 0
        for user in users:
            if user.created_at:
                try:
                    created = datetime.fromisoformat(user.created_at.replace("Z", "+00:00")) if isinstance(user.created_at, str) else user.created_at
                    if created.astimezone().replace(tzinfo=None).date() == today and not is_admin_account(email=user.email):
                        today_new_users += 1
                except Exception as e:
                    print(f"⚠️ created_at 파싱 오류: {e}")
        return {
            "success": True,
            "total_users": total_users,
            "today_new_users": today_new_users,
            "today_logins": today_logins,
            "timestamp": datetime.now().isoformat(),
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
    UTM별 인기 질문 분석 (events + session_chat_messages)
    - 어떤 매체에서 온 사용자가 어떤 질문을 많이 하는지
    """
    try:
        client = supabase_service.get_client()
        start = (datetime.now() - timedelta(days=days)).isoformat()

        # 세션별 첫 UTM: events (landing/chat_page)에서 user_session당 첫 행
        events_res = client.table("events").select("user_session, utm_source, utm_medium, utm_campaign, event_time").in_("event_type", ["landing", "chat_page"]).gte("event_time", start).order("event_time").execute()
        first_utm_by_session: Dict[str, Dict[str, Any]] = {}
        for row in (events_res.data or []):
            s = row.get("user_session")
            if s and s not in first_utm_by_session:
                first_utm_by_session[s] = {
                    "utm_source": row.get("utm_source") or "direct",
                    "utm_medium": row.get("utm_medium") or "none",
                    "utm_campaign": row.get("utm_campaign"),
                }

        # 사용자 질문 메시지 (session_chat_messages)
        msg_res = client.table("session_chat_messages").select("user_session, content, created_at").eq("role", "user").gte("created_at", start).execute()
        messages = msg_res.data or []

        # UTM 필터
        if utm_source:
            messages = [m for m in messages if (first_utm_by_session.get(m.get("user_session")) or {}).get("utm_source") == utm_source]
        if utm_medium:
            messages = [m for m in messages if (first_utm_by_session.get(m.get("user_session")) or {}).get("utm_medium") == utm_medium]

        question_patterns = {
            "합격 가능성": ["합격", "가능", "확률", "가능성"],
            "점수/성적": ["점수", "성적", "등급", "백분위", "표준점수"],
            "전형 관련": ["전형", "수시", "정시", "학종", "교과"],
            "학과/전공": ["학과", "전공", "학부", "계열"],
            "대학 정보": ["대학", "학교", "캠퍼스"],
            "경쟁률": ["경쟁률", "지원", "인원"],
        }
        utm_analysis: Dict[str, Dict[str, Any]] = {}

        for msg in messages:
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            sess = msg.get("user_session")
            utm = first_utm_by_session.get(sess) or {"utm_source": "direct", "utm_medium": "none", "utm_campaign": None}
            utm_key = f"{utm['utm_source']}_{utm['utm_medium']}"
            if utm_key not in utm_analysis:
                utm_analysis[utm_key] = {
                    "utm_source": utm["utm_source"],
                    "utm_medium": utm["utm_medium"],
                    "utm_campaign": utm["utm_campaign"],
                    "total_questions": 0,
                    "patterns": {p: 0 for p in question_patterns},
                    "sample_questions": [],
                }
            utm_analysis[utm_key]["total_questions"] += 1
            if len(utm_analysis[utm_key]["sample_questions"]) < 5:
                utm_analysis[utm_key]["sample_questions"].append(content[:100])
            content_lower = content.lower()
            for pattern, keywords in question_patterns.items():
                if any(kw in content_lower for kw in keywords):
                    utm_analysis[utm_key]["patterns"][pattern] += 1

        results = []
        for data in utm_analysis.values():
            if data["total_questions"] > 0:
                pattern_percentages = {p: round(100 * c / data["total_questions"], 1) for p, c in data["patterns"].items()}
                results.append({
                    "utm_source": data["utm_source"],
                    "utm_medium": data["utm_medium"],
                    "utm_campaign": data["utm_campaign"],
                    "total_questions": data["total_questions"],
                    "pattern_percentages": pattern_percentages,
                    "top_patterns": sorted(pattern_percentages.items(), key=lambda x: x[1], reverse=True)[:3],
                    "sample_questions": data["sample_questions"],
                })
        results.sort(key=lambda x: x["total_questions"], reverse=True)

        return {
            "success": True,
            "period_days": days,
            "utm_analysis": results,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"❌ UTM 질문 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analytics/funnel")
async def get_funnel_analysis(days: int = 7) -> Dict[str, Any]:
    """
    전환 깔때기 분석 (events + session_chat_messages)
    - 단계별 포함 관계: 랜딩 → (랜딩한 사람 중 채팅한 사람) → (그중 로그인한 사람) → (그중 메시지 전송한 사람)
    - 랜딩 ≥ 채팅 ≥ 로그인 ≥ 메시지 전송, 전환율 100% 이하
    """
    try:
        client = supabase_service.get_client()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start_iso = start_date.isoformat()

        # events에서 기간 내 이벤트 전부 조회 (페이지네이션으로 5만 건 제한 없이)
        PAGE = 10000
        events_list: List[Dict[str, Any]] = []
        offset = 0
        while True:
            chunk = (
                client.table("events")
                .select("user_session, event_type, event_time, utm_source, utm_medium, user_id")
                .gte("event_time", start_iso)
                .order("event_time", desc=False)
                .range(offset, offset + PAGE - 1)
                .execute()
            )
            data = chunk.data or []
            events_list.extend(data)
            if len(data) < PAGE:
                break
            offset += PAGE

        # 세션별 집계 (첫 UTM + 단계별 카운트)
        sessions: Dict[str, Dict[str, Any]] = {}
        for e in events_list:
            if e.get("user_id") and is_admin_account(user_id=e["user_id"]):
                continue
            sess = e.get("user_session")
            if not sess:
                continue
            if sess not in sessions:
                sessions[sess] = {
                    "first_utm_source": "direct",
                    "first_utm_medium": "none",
                    "landing_visits": 0,
                    "chat_visits": 0,
                    "logged_in": 0,
                    "sent_message": 0,
                }
            t = e.get("event_type")
            if t == "landing":
                sessions[sess]["landing_visits"] += 1
            elif t == "chat_page":
                sessions[sess]["chat_visits"] += 1
            elif t == "login":
                sessions[sess]["logged_in"] += 1
            elif t == "question_sent":
                sessions[sess]["sent_message"] += 1
            if sessions[sess]["first_utm_source"] == "direct" and (e.get("utm_source") or e.get("utm_medium")):
                sessions[sess]["first_utm_source"] = e.get("utm_source") or "direct"
                sessions[sess]["first_utm_medium"] = e.get("utm_medium") or "none"

        # completed_session: 해당 기간에 메시지가 1건 이상인 세션 (페이지네이션)
        msg_sessions: set = set()
        offset = 0
        while True:
            msg_chunk = (
                client.table("session_chat_messages")
                .select("user_session")
                .gte("created_at", start_iso)
                .order("created_at", desc=False)
                .range(offset, offset + PAGE - 1)
                .execute()
            )
            data = msg_chunk.data or []
            for row in data:
                msg_sessions.add(row.get("user_session"))
            if len(data) < PAGE:
                break
            offset += PAGE

        # 단계별 포함 관계: 랜딩 → (랜딩한 사람 중) 채팅 → (채팅한 사람 중) 로그인 → (로그인한 사람 중) 메시지 전송
        total_stats = {"landing_visits": 0, "chat_visits": 0, "logged_in": 0, "sent_message": 0, "completed_session": 0}
        utm_stats: Dict[str, Dict[str, Any]] = {}

        for sess, data in sessions.items():
            has_landing = data["landing_visits"] > 0
            has_chat = data["chat_visits"] > 0
            has_login = data["logged_in"] > 0
            has_message = data["sent_message"] > 0

            total_stats["landing_visits"] += 1 if has_landing else 0
            total_stats["chat_visits"] += 1 if (has_landing and has_chat) else 0
            total_stats["logged_in"] += 1 if (has_landing and has_chat and has_login) else 0
            total_stats["sent_message"] += 1 if (has_landing and has_chat and has_login and has_message) else 0
            if sess in msg_sessions:
                total_stats["completed_session"] += 1

            utm_key = f"{data['first_utm_source']}|{data['first_utm_medium']}"
            if utm_key not in utm_stats:
                utm_stats[utm_key] = {
                    "utm_source": data["first_utm_source"],
                    "utm_medium": data["first_utm_medium"],
                    "landing_visits": 0,
                    "chat_visits": 0,
                    "logged_in": 0,
                    "sent_message": 0,
                }
            if has_landing:
                utm_stats[utm_key]["landing_visits"] += 1
            if has_landing and has_chat:
                utm_stats[utm_key]["chat_visits"] += 1
            if has_landing and has_chat and has_login:
                utm_stats[utm_key]["logged_in"] += 1
            if has_landing and has_chat and has_login and has_message:
                utm_stats[utm_key]["sent_message"] += 1

        def calculate_conversion(from_value: int, to_value: int) -> float:
            return round((to_value / from_value * 100) if from_value > 0 else 0, 1)

        total_conversions = {
            "landing_to_chat": calculate_conversion(total_stats["landing_visits"], total_stats["chat_visits"]),
            "chat_to_login": calculate_conversion(total_stats["chat_visits"], total_stats["logged_in"]),
            "login_to_message": calculate_conversion(total_stats["logged_in"], total_stats["sent_message"]),
        }
        utm_conversions = []
        for stats in utm_stats.values():
            utm_conversions.append({
                "utm_source": stats["utm_source"],
                "utm_medium": stats["utm_medium"],
                "stats": stats,
                "conversions": {
                    "landing_to_chat": calculate_conversion(stats["landing_visits"], stats["chat_visits"]),
                    "chat_to_login": calculate_conversion(stats["chat_visits"], stats["logged_in"]),
                    "login_to_message": calculate_conversion(stats["logged_in"], stats["sent_message"]),
                },
            })
        utm_conversions.sort(key=lambda x: x["stats"]["landing_visits"], reverse=True)

        return {
            "success": True,
            "period_days": days,
            "total_stats": total_stats,
            "total_conversions": total_conversions,
            "utm_conversions": utm_conversions[:10],
            "timestamp": datetime.now().isoformat(),
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
        
        # events에서 디바이스 정보 조회 (landing/chat_page 이벤트)
        # migration 15 미적용 시 컬럼 없음 → 빈 통계 반환
        device_stats = {}
        browser_stats = {}
        os_stats = {}
        rows: List[Dict[str, Any]] = []
        try:
            result = client.table("events") \
                .select("device_type, browser, os") \
                .in_("event_type", ["landing", "chat_page"]) \
                .gte("event_time", start_date.isoformat()) \
                .execute()
            rows = result.data or []
        except Exception as col_err:
            print(f"⚠️ device-stats: events에 device 컬럼 없음 또는 조회 실패 (migration 15 적용 후 반영): {col_err}")
        
        for view in rows:
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
        total_views = len(rows)
        
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
        
        # 모든 질문 가져오기 (session_chat_messages)
        result = client.table("session_chat_messages") \
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


@router.get("/api/analytics/data-verification")
async def get_data_verification() -> Dict[str, Any]:
    """
    각 지표별 데이터 적재 여부 검증용.
    최근 1시간/24시간 events 건수(event_type별), session_chat_messages 건수 반환.
    """
    try:
        client = supabase_service.get_client()
        now = datetime.now()
        start_1h = (now - timedelta(hours=1)).isoformat()
        start_24h = (now - timedelta(hours=24)).isoformat()

        def count_events(since: str) -> Dict[str, int]:
            res = client.table("events").select("event_type").gte("event_time", since).execute()
            data = res.data or []
            out: Dict[str, int] = {"landing": 0, "chat_page": 0, "login": 0, "question_sent": 0}
            for row in data:
                t = row.get("event_type")
                if t in out:
                    out[t] += 1
            return out

        def count_messages(since: str) -> int:
            res = client.table("session_chat_messages").select("message_id").gte("created_at", since).execute()
            return len(res.data or [])

        events_1h = count_events(start_1h)
        events_24h = count_events(start_24h)
        messages_1h = count_messages(start_1h)
        messages_24h = count_messages(start_24h)

        return {
            "success": True,
            "last_1h": {
                "events": events_1h,
                "session_chat_messages": messages_1h,
            },
            "last_24h": {
                "events": events_24h,
                "session_chat_messages": messages_24h,
            },
            "note": "랜딩/채팅은 page-view, 로그인은 page-view 시 세션당 1회, question_sent는 채팅 전송 시 백엔드 기록.",
            "timestamp": now.isoformat(),
        }
    except Exception as e:
        print(f"❌ 데이터 검증 조회 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
