-- events + session_chat_messages 테이블 (행동/채팅 통합)
-- 기존 테이블 유지, 새 테이블만 추가

-- 1. events (이벤트 시간, 유형, UTM, user_id, user_session)
CREATE TABLE IF NOT EXISTS events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_time TIMESTAMPTZ NOT NULL,
  event_type TEXT NOT NULL,
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  utm_content TEXT,
  utm_term TEXT,
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  user_session TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_events_user_session_time ON events(user_session, event_time);
CREATE INDEX IF NOT EXISTS idx_events_event_type_time ON events(event_type, event_time);
CREATE INDEX IF NOT EXISTS idx_events_user_id ON events(user_id) WHERE user_id IS NOT NULL;

COMMENT ON TABLE events IS '행동 이벤트: 랜딩/챗봇 진입, 질문 전송, 로그인 (30분 user_session 기준)';

-- 2. session_chat_messages (user_session + message_id 복합키, 세션별 채팅)
CREATE TABLE IF NOT EXISTS session_chat_messages (
  user_session TEXT NOT NULL,
  message_id UUID NOT NULL DEFAULT gen_random_uuid(),
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  sources TEXT[],
  source_urls TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW(),
  user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  PRIMARY KEY (user_session, message_id)
);

CREATE INDEX IF NOT EXISTS idx_session_chat_messages_session_created ON session_chat_messages(user_session, created_at);
CREATE INDEX IF NOT EXISTS idx_session_chat_messages_user_created ON session_chat_messages(user_id, created_at) WHERE user_id IS NOT NULL;

COMMENT ON TABLE session_chat_messages IS '세션별 채팅 내역 (user_session = 30분 세션 ID 또는 conversation ID)';

-- RLS (선택: 관리자 또는 본인만)
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_chat_messages ENABLE ROW LEVEL SECURITY;

-- 서비스 역할이 모든 행 접근 가능하도록 (백엔드가 service key 사용)
CREATE POLICY "Service role full access events" ON events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access session_chat_messages" ON session_chat_messages FOR ALL USING (true) WITH CHECK (true);

SELECT 'events and session_chat_messages tables created' AS status;
