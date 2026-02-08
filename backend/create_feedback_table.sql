-- 피드백 테이블 생성 SQL (Supabase)
-- Supabase 대시보드의 SQL Editor에서 실행하세요.
-- https://supabase.com/dashboard/project/_/sql

-- feedback 테이블 생성
CREATE TABLE IF NOT EXISTS feedback (
    id BIGSERIAL PRIMARY KEY,
    user_id TEXT,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 인덱스 생성 (성능 향상)
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id);

-- RLS (Row Level Security) 정책 설정 (필요시)
-- ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

-- 모든 사용자가 피드백을 작성할 수 있도록
-- CREATE POLICY "Anyone can insert feedback" ON feedback
--     FOR INSERT
--     TO authenticated, anon
--     WITH CHECK (true);

-- 관리자만 피드백을 조회/삭제할 수 있도록 (service_role 키 필요)
-- CREATE POLICY "Only admins can read feedback" ON feedback
--     FOR SELECT
--     TO authenticated
--     USING (auth.jwt() ->> 'role' = 'admin');

