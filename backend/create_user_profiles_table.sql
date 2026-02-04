-- User Profiles 테이블 생성
-- 사용자별 모의고사 점수 저장

-- 기존 정책 및 테이블 삭제 (있다면)
DROP POLICY IF EXISTS "Users can view own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can insert own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can update own profile" ON user_profiles;
DROP POLICY IF EXISTS "Users can delete own profile" ON user_profiles;
DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON user_profiles;
DROP TABLE IF EXISTS user_profiles;

-- 테이블 생성
CREATE TABLE user_profiles (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    
    -- 모의고사 점수 (최신 1개만 저장)
    scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- 형식: 등급, 표준점수, 백분위 모두 입력 가능
    -- {
    --   "국어": {"등급": 1, "표준점수": 140, "백분위": 95, "선택과목": "화법과작문"},
    --   "수학": {"등급": 1, "표준점수": 140, "백분위": 95, "선택과목": "미적분"},
    --   "영어": {"등급": 1, "표준점수": null, "백분위": null},
    --   "탐구1": {"등급": 2, "표준점수": null, "백분위": 95, "선택과목": "물리학Ⅰ"},
    --   "탐구2": {"등급": 2, "표준점수": null, "백분위": 90, "선택과목": "화학Ⅱ"}
    -- }
    
    -- 향후 확장용 필드 (생활기록부, 내신 등)
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- 타임스탬프
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 인덱스
CREATE INDEX IF NOT EXISTS idx_user_profiles_updated ON user_profiles(updated_at DESC);

-- updated_at 자동 갱신 트리거
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- RLS 활성화
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- RLS 정책: 자기 자신의 프로필만 CRUD 가능
CREATE POLICY "Users can view own profile"
    ON user_profiles FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY "Users can insert own profile"
    ON user_profiles FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own profile"
    ON user_profiles FOR UPDATE
    USING (user_id = auth.uid());

CREATE POLICY "Users can delete own profile"
    ON user_profiles FOR DELETE
    USING (user_id = auth.uid());

-- 코멘트 추가
COMMENT ON TABLE user_profiles IS '사용자 프로필 정보 (모의고사 점수)';
COMMENT ON COLUMN user_profiles.scores IS '모의고사 점수 (백분위, 표준점수, 선택과목 포함)';
COMMENT ON COLUMN user_profiles.metadata IS '향후 확장용 필드 (생활기록부, 내신 등)';
