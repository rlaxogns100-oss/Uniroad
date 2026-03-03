-- 채팅 공유 기능을 위한 테이블 생성
-- 사용자가 특정 질문/답변을 공유할 때 사용

CREATE TABLE IF NOT EXISTS shared_chats (
  share_id TEXT PRIMARY KEY,              -- 짧은 고유 ID (예: abc123xyz)
  user_query TEXT NOT NULL,               -- 사용자 질문
  assistant_response TEXT NOT NULL,       -- AI 답변
  sources TEXT[],                         -- 출처 목록
  source_urls TEXT[],                     -- 출처 URL
  created_at TIMESTAMPTZ DEFAULT NOW(),   -- 생성 시간
  view_count INTEGER DEFAULT 0            -- 조회수
);

-- 인덱스 생성 (share_id로 빠른 조회)
CREATE INDEX IF NOT EXISTS idx_shared_chats_created_at ON shared_chats(created_at DESC);

-- RLS 정책 설정
ALTER TABLE shared_chats ENABLE ROW LEVEL SECURITY;

-- 모든 사용자가 공유된 채팅을 조회할 수 있도록 허용
CREATE POLICY "Anyone can view shared chats" ON shared_chats
  FOR SELECT USING (true);

-- 인증된 사용자와 익명 사용자 모두 공유 생성 가능
CREATE POLICY "Anyone can create shared chats" ON shared_chats
  FOR INSERT WITH CHECK (true);

-- 조회수 업데이트 허용
CREATE POLICY "Anyone can update view count" ON shared_chats
  FOR UPDATE USING (true) WITH CHECK (true);
