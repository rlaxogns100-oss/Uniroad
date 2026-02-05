-- 마이그레이션 검증: events / session_chat_messages 행 수 확인
-- 12, 13 실행 후 사용. (page_views, user_journeys, user_actions 제거 후에는 아래만 유효)

-- 1) events 행 수
SELECT (SELECT COUNT(*) FROM events) AS events_count;

-- 2) session_chat_messages vs chat_messages (참고용, chat_messages 유지 시)
SELECT
  (SELECT COUNT(*) FROM chat_messages) AS chat_messages_count,
  (SELECT COUNT(*) FROM session_chat_messages) AS session_chat_messages_count;

-- 3) 요약 (events, session_chat_messages만)
SELECT 'events' AS table_name, (SELECT COUNT(*) FROM events)::BIGINT AS row_count
UNION ALL
SELECT 'session_chat_messages', (SELECT COUNT(*) FROM session_chat_messages)::BIGINT;
