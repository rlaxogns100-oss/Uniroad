-- Usage Tracking 테이블 생성
-- 사용자별/IP별 일일 API 사용량 추적

-- 기존 정책 및 테이블 삭제 (있다면)
DROP POLICY IF EXISTS "Users can view own usage" ON usage_tracking;
DROP POLICY IF EXISTS "Service role can manage all usage" ON usage_tracking;
DROP TRIGGER IF EXISTS update_usage_tracking_updated_at ON usage_tracking;
DROP TABLE IF EXISTS usage_tracking;

-- 테이블 생성
CREATE TABLE usage_tracking (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 사용자 식별 (둘 중 하나는 필수)
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,  -- 로그인 유저
    ip_address TEXT,  -- 게스트 (비로그인)
    
    -- 사용량 추적
    chat_count INT DEFAULT 0 NOT NULL CHECK (chat_count >= 0),
    last_reset_date DATE DEFAULT CURRENT_DATE NOT NULL,
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- 제약조건: user_id 또는 ip_address 중 하나는 반드시 있어야 함
    CHECK (
        (user_id IS NOT NULL AND ip_address IS NULL) OR 
        (user_id IS NULL AND ip_address IS NOT NULL)
    ),
    
    -- 유니크 제약: 같은 날짜에 같은 user_id나 ip_address는 1개만
    UNIQUE(user_id, last_reset_date),
    UNIQUE(ip_address, last_reset_date)
);

-- 인덱스 (빠른 조회를 위한)
CREATE INDEX idx_usage_tracking_user_date ON usage_tracking(user_id, last_reset_date) WHERE user_id IS NOT NULL;
CREATE INDEX idx_usage_tracking_ip_date ON usage_tracking(ip_address, last_reset_date) WHERE ip_address IS NOT NULL;
CREATE INDEX idx_usage_tracking_date ON usage_tracking(last_reset_date DESC);

-- updated_at 자동 갱신 트리거
CREATE TRIGGER update_usage_tracking_updated_at
    BEFORE UPDATE ON usage_tracking
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS 활성화
ALTER TABLE usage_tracking ENABLE ROW LEVEL SECURITY;

-- RLS 정책: 자기 자신의 사용량만 조회 가능
CREATE POLICY "Users can view own usage"
    ON usage_tracking FOR SELECT
    USING (user_id = auth.uid());

-- RLS 정책: 서비스 롤은 모든 레코드 관리 가능 (백엔드에서 사용)
CREATE POLICY "Service role can manage all usage"
    ON usage_tracking FOR ALL
    USING (true)
    WITH CHECK (true);

-- 코멘트 추가
COMMENT ON TABLE usage_tracking IS 'API 사용량 추적 (Rate Limiting용)';
COMMENT ON COLUMN usage_tracking.user_id IS '로그인 사용자 ID (로그인 유저인 경우)';
COMMENT ON COLUMN usage_tracking.ip_address IS 'IP 주소 (게스트 유저인 경우)';
COMMENT ON COLUMN usage_tracking.chat_count IS '채팅 API 호출 횟수';
COMMENT ON COLUMN usage_tracking.last_reset_date IS '마지막 리셋 날짜 (자정 기준)';
