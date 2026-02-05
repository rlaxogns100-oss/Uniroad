-- 기존 데이터를 events / session_chat_messages 로 복사 (기존 테이블 삭제/수정 없음)
-- Supabase SQL Editor 에서 12 실행 후 실행

-- 1) page_views -> events (landing, chat_page)
INSERT INTO events (event_time, event_type, utm_source, utm_medium, utm_campaign, utm_content, utm_term, user_id, user_session)
SELECT
  created_at,
  CASE page_type
    WHEN 'landing' THEN 'landing'
    WHEN 'chat' THEN 'chat_page'
    ELSE 'landing'
  END,
  utm_source,
  utm_medium,
  utm_campaign,
  utm_content,
  utm_term,
  user_id,
  session_id
FROM page_views
WHERE page_type IN ('landing', 'chat');

-- 2) user_journeys (logged_in=true) -> events (login)
INSERT INTO events (event_time, event_type, utm_source, utm_medium, utm_campaign, utm_content, utm_term, user_id, user_session)
SELECT
  login_at,
  'login',
  first_utm_source,
  first_utm_medium,
  first_utm_campaign,
  first_utm_content,
  first_utm_term,
  user_id,
  session_id
FROM user_journeys
WHERE logged_in = true AND login_at IS NOT NULL;

-- 3) user_actions (send_message) -> events (question_sent)
INSERT INTO events (event_time, event_type, utm_source, utm_medium, utm_campaign, utm_content, utm_term, user_id, user_session)
SELECT
  created_at,
  'question_sent',
  utm_source,
  utm_medium,
  utm_campaign,
  NULL,
  NULL,
  user_id,
  session_id
FROM user_actions
WHERE action_name = 'send_message';

-- 4) chat_sessions + chat_messages -> session_chat_messages
-- (chat_messages에 sources/source_urls 컬럼이 없을 수 있으므로 NULL 사용)
INSERT INTO session_chat_messages (user_session, message_id, role, content, sources, source_urls, created_at, user_id)
SELECT
  COALESCE(cs.browser_session_id, 'legacy-' || cs.id::text),
  cm.id,
  cm.role,
  cm.content,
  NULL::TEXT[],
  NULL::TEXT[],
  cm.created_at,
  cs.user_id
FROM chat_messages cm
JOIN chat_sessions cs ON cs.id = cm.session_id
ON CONFLICT (user_session, message_id) DO NOTHING;

SELECT 'Data migration to events and session_chat_messages completed' AS status;
