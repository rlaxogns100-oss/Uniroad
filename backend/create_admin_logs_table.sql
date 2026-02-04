-- Admin Execution Logs 테이블 생성
-- 에이전트 실행 로그를 저장하는 테이블

CREATE TABLE IF NOT EXISTS admin_logs (
    id VARCHAR(6) PRIMARY KEY,  -- 6자리 랜덤 ID
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,  -- 사용자 ID (nullable)
    timestamp TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    conversation_history JSONB DEFAULT '[]'::jsonb,  -- 이전 대화 기록
    user_question TEXT NOT NULL,  -- 사용자 질문
    router_output JSONB,  -- Router 출력
    function_result JSONB,  -- Function 결과
    final_answer TEXT,  -- 최종 답변
    elapsed_time INTEGER DEFAULT 0,  -- 총 소요시간 (ms)
    
    -- 단계별 시간 측정
    timing_router INTEGER DEFAULT 0,  -- Router Agent 시간 (ms)
    timing_function INTEGER DEFAULT 0,  -- Function 실행 시간 (ms)
    timing_main_agent INTEGER DEFAULT 0,  -- Main Agent 시간 (ms)
    
    -- 평가 결과
    eval_router_status VARCHAR(10) DEFAULT 'pending',  -- ok, warning, error, pending
    eval_function_status VARCHAR(10) DEFAULT 'pending',
    eval_answer_status VARCHAR(10) DEFAULT 'pending',
    eval_time_status VARCHAR(10) DEFAULT 'pending',
    eval_router_comment TEXT,
    eval_function_comment TEXT,
    eval_answer_comment TEXT,
    eval_time_comment TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_admin_logs_timestamp ON admin_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_admin_logs_user_id ON admin_logs(user_id);

-- RLS 비활성화 (관리자 전용 테이블)
ALTER TABLE admin_logs DISABLE ROW LEVEL SECURITY;

-- 코멘트 추가
COMMENT ON TABLE admin_logs IS 'Admin Agent 실행 로그 저장 테이블';
COMMENT ON COLUMN admin_logs.id IS '6자리 랜덤 고유 ID';
COMMENT ON COLUMN admin_logs.user_id IS '로그인한 사용자 ID (nullable)';
