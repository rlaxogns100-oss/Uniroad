#!/usr/bin/env python3
"""
이벤트·채팅 마이그레이션 동작 테스트
- 2: 검증 SQL 실행 안내
- 3: API 호출로 events / session_chat_messages 기록 후 검증 안내

사용법:
  BACKEND_URL=http://127.0.0.1:8000 python backend/scripts/test_events_and_chat_migration.py
"""
import os
import sys
import uuid

try:
    import requests
except ImportError:
    print("pip install requests 후 다시 실행하세요.")
    sys.exit(1)

BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:8000")
SESSION_ID = f"test-session-{uuid.uuid4().hex[:12]}"


def main():
    print("=" * 60)
    print("이벤트·채팅 마이그레이션 동작 테스트")
    print("=" * 60)
    print(f"백엔드 URL: {BACKEND_URL}\n")

    # 1) 검증 SQL 안내
    print("[1] 마이그레이션 검증 (Supabase SQL Editor)")
    print("    backend/migrations/14_verify_migration.sql 을 실행하여")
    print("    expected_events_count vs actual_events_count, messages_status 를 확인하세요.\n")

    # 2) 페이지 뷰 추적 → events
    print("[2] 페이지 뷰 추적 (events 테이블)")
    for page_type, label in [("landing", "랜딩"), ("chat", "채팅")]:
        try:
            r = requests.post(
                f"{BACKEND_URL}/api/tracking/page-view",
                json={
                    "session_id": SESSION_ID,
                    "page_type": page_type,
                    "page_path": "/" if page_type == "landing" else "/chat",
                    "page_title": label,
                },
                timeout=5,
            )
            if r.status_code == 200:
                print(f"    {label} page-view: OK")
            else:
                print(f"    {label} page-view: HTTP {r.status_code} - {r.text[:200]}")
        except Exception as e:
            print(f"    {label} page-view: 실패 - {e}")

    # 3) user-action (질문 전송) → events question_sent
    print("\n[3] 사용자 액션 추적 (events - question_sent)")
    try:
        r = requests.post(
            f"{BACKEND_URL}/api/tracking/user-action",
            json={
                "session_id": SESSION_ID,
                "action_type": "submit",
                "action_name": "send_message",
            },
            timeout=5,
        )
        if r.status_code == 200:
            print("    send_message: OK")
        else:
            print(f"    send_message: HTTP {r.status_code} - {r.text[:200]}")
    except Exception as e:
        print(f"    send_message: 실패 - {e}")

    # 4) 세션 목록 (session_chat_messages 사용 여부는 서버 로그/DB로 확인)
    print("\n[4] 세션 API (session_chat_messages 기반)")
    try:
        r = requests.get(
            f"{BACKEND_URL}/api/sessions",
            params={"browser_session_id": SESSION_ID},
            timeout=5,
        )
        if r.status_code == 200:
            print("    GET /api/sessions: OK")
        else:
            print(f"    GET /api/sessions: HTTP {r.status_code}")
    except Exception as e:
        print(f"    GET /api/sessions: 실패 - {e}")

    print("\n" + "=" * 60)
    print("다음 단계:")
    print("  - Supabase에서 events 테이블에 방금 session_id로 들어온 행이 있는지 확인")
    print("  - 14_verify_migration.sql 다시 실행해 행 수 변화 확인")
    print("=" * 60)


if __name__ == "__main__":
    main()
