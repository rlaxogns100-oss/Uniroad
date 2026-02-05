# 이벤트·채팅 테이블 마이그레이션 검증 및 테스트

## 2. 검증 (행 수)

1. Supabase SQL Editor에서 **14_verify_migration.sql** 실행
2. 확인:
   - `events_status`: expected_events_count와 actual_events_count가 같으면 OK
   - `messages_status`: chat_messages_count와 session_chat_messages_count가 같으면 OK

## 3. 동작 테스트

### 자동 스크립트 (백엔드 실행 중일 때)

```bash
BACKEND_URL=http://127.0.0.1:8000 python backend/scripts/test_events_and_chat_migration.py
```

- 랜딩/채팅 page-view → `events`에 landing, chat_page 기록
- user-action send_message → `events`에 question_sent 기록
- 세션 API 호출로 session_chat_messages 기반 동작 확인

### 수동 확인

1. **events**: 앱에서 랜딩/채팅 페이지 접속 후 Supabase `events` 테이블에 최신 행 추가 여부 확인
2. **session_chat_messages**: 채팅에서 질문 한 번 보낸 뒤 `session_chat_messages`에 user/assistant 행 추가 여부 확인
3. 검증 SQL(14_verify_migration.sql)을 다시 실행해 행 수가 늘었는지 확인
