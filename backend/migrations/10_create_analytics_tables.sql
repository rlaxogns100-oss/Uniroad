-- UTM 기반 분석 테이블 생성
-- 사용자 여정 추적 및 캠페인 성과 분석

-- 1. page_views 테이블 (모든 페이지 뷰 기록)
CREATE TABLE IF NOT EXISTS page_views (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- 세션 정보
  session_id TEXT NOT NULL,
  user_id UUID REFERENCES auth.users(id),
  
  -- 페이지 정보
  page_type TEXT NOT NULL, -- 'landing', 'chat', 'auth', 'admin', 'upload', 'analytics'
  page_path TEXT NOT NULL,
  page_title TEXT,
  
  -- UTM 파라미터
  utm_source TEXT,      -- instagram, facebook, naver, google, kakao, youtube
  utm_medium TEXT,      -- post, story, ad, cpc, organic, email, referral
  utm_campaign TEXT,    -- 20260202_instagram_post
  utm_content TEXT,     -- banner_1, link_bio, story_1
  utm_term TEXT,        -- 수능, 대입, 서울대
  
  -- 추가 추적 정보
  referrer TEXT,        -- 이전 페이지
  referrer_domain TEXT, -- 참조 도메인
  
  -- 디바이스 정보
  user_agent TEXT,
  device_type TEXT,     -- mobile, tablet, desktop
  browser TEXT,         -- chrome, safari, samsung
  os TEXT,              -- ios, android, windows, mac
  
  -- 위치 정보
  ip_address TEXT,
  country TEXT DEFAULT 'KR',
  city TEXT,
  
  -- 상호작용 정보
  time_on_page INTEGER, -- 페이지 체류 시간(초)
  bounce BOOLEAN DEFAULT false,
  
  -- 타임스탬프
  created_at TIMESTAMPTZ DEFAULT NOW(),
  left_at TIMESTAMPTZ   -- 페이지 떠난 시간
);

-- 2. user_journeys 테이블 (사용자 여정 요약)
CREATE TABLE IF NOT EXISTS user_journeys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id TEXT UNIQUE NOT NULL,
  
  -- 첫 유입 정보
  first_utm_source TEXT,
  first_utm_medium TEXT,
  first_utm_campaign TEXT,
  first_utm_content TEXT,
  first_utm_term TEXT,
  first_referrer TEXT,
  
  -- 여정 단계 추적
  visited_landing BOOLEAN DEFAULT false,
  visited_chat BOOLEAN DEFAULT false,
  visited_auth BOOLEAN DEFAULT false,
  logged_in BOOLEAN DEFAULT false,
  asked_question BOOLEAN DEFAULT false,
  
  -- 전환 깔때기
  funnel_stage TEXT DEFAULT 'landing', -- 'landing', 'chat', 'login', 'active_user'
  
  -- 행동 카운트
  page_views_count INTEGER DEFAULT 0,
  chat_messages_count INTEGER DEFAULT 0,
  total_time_spent INTEGER DEFAULT 0, -- 총 체류시간(초)
  
  -- 타임스탬프
  first_visit_at TIMESTAMPTZ DEFAULT NOW(),
  last_visit_at TIMESTAMPTZ DEFAULT NOW(),
  landing_visit_at TIMESTAMPTZ,
  chat_visit_at TIMESTAMPTZ,
  login_at TIMESTAMPTZ,
  first_question_at TIMESTAMPTZ,
  
  -- 사용자 정보
  user_id UUID REFERENCES auth.users(id),
  user_email TEXT,
  user_name TEXT,
  
  -- 디바이스 정보
  device_type TEXT,
  browser TEXT,
  os TEXT,
  
  -- 위치 정보
  ip_address TEXT,
  country TEXT DEFAULT 'KR',
  city TEXT
);

-- 3. campaign_performance 테이블 (캠페인 성과 집계)
CREATE TABLE IF NOT EXISTS campaign_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- 캠페인 정보
  utm_source TEXT NOT NULL,
  utm_medium TEXT NOT NULL,
  utm_campaign TEXT NOT NULL,
  date DATE NOT NULL,
  
  -- 방문자 수
  unique_visitors INTEGER DEFAULT 0,
  total_page_views INTEGER DEFAULT 0,
  
  -- 전환 깔때기
  landing_visitors INTEGER DEFAULT 0,
  chat_visitors INTEGER DEFAULT 0,
  logged_in_users INTEGER DEFAULT 0,
  active_users INTEGER DEFAULT 0, -- 질문한 사용자
  
  -- 전환율
  landing_to_chat_rate DECIMAL(5,2),
  chat_to_login_rate DECIMAL(5,2),
  login_to_active_rate DECIMAL(5,2),
  
  -- 참여도
  avg_time_on_site INTEGER, -- 평균 체류시간(초)
  avg_pages_per_session DECIMAL(5,2),
  bounce_rate DECIMAL(5,2),
  
  -- 타임스탬프
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(utm_source, utm_medium, utm_campaign, date)
);

-- 4. user_actions 테이블 (사용자 행동 이벤트)
CREATE TABLE IF NOT EXISTS user_actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  
  -- 세션 정보
  session_id TEXT NOT NULL,
  user_id UUID REFERENCES auth.users(id),
  
  -- 이벤트 정보
  action_type TEXT NOT NULL, -- 'click', 'scroll', 'submit', 'download', 'share'
  action_name TEXT NOT NULL, -- 'cta_button', 'chat_start', 'login_submit'
  action_category TEXT,      -- 'engagement', 'conversion', 'navigation'
  
  -- 컨텍스트
  page_type TEXT,
  element_id TEXT,
  element_text TEXT,
  
  -- UTM 정보 (해당 세션의)
  utm_source TEXT,
  utm_medium TEXT,
  utm_campaign TEXT,
  
  -- 타임스탬프
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. daily_stats 테이블 (일별 통계 스냅샷)
CREATE TABLE IF NOT EXISTS daily_stats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  date DATE NOT NULL,
  
  -- 전체 통계
  total_visitors INTEGER DEFAULT 0,
  new_visitors INTEGER DEFAULT 0,
  returning_visitors INTEGER DEFAULT 0,
  
  -- 페이지별 통계
  landing_page_views INTEGER DEFAULT 0,
  chat_page_views INTEGER DEFAULT 0,
  
  -- 사용자 통계
  new_signups INTEGER DEFAULT 0,
  active_users INTEGER DEFAULT 0,
  
  -- 참여도
  avg_session_duration INTEGER,
  avg_pages_per_session DECIMAL(5,2),
  
  created_at TIMESTAMPTZ DEFAULT NOW(),
  
  UNIQUE(date)
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_page_views_session ON page_views(session_id);
CREATE INDEX IF NOT EXISTS idx_page_views_created ON page_views(created_at);
CREATE INDEX IF NOT EXISTS idx_page_views_utm ON page_views(utm_source, utm_medium, utm_campaign);
CREATE INDEX IF NOT EXISTS idx_page_views_user ON page_views(user_id) WHERE user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_page_views_page_type ON page_views(page_type);

CREATE INDEX IF NOT EXISTS idx_journeys_utm ON user_journeys(first_utm_source, first_utm_medium);
CREATE INDEX IF NOT EXISTS idx_journeys_created ON user_journeys(first_visit_at);
CREATE INDEX IF NOT EXISTS idx_journeys_funnel ON user_journeys(funnel_stage);
CREATE INDEX IF NOT EXISTS idx_journeys_user ON user_journeys(user_id) WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_actions_session ON user_actions(session_id);
CREATE INDEX IF NOT EXISTS idx_actions_type ON user_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_actions_created ON user_actions(created_at);

CREATE INDEX IF NOT EXISTS idx_campaign_perf ON campaign_performance(utm_source, utm_medium, utm_campaign, date);

-- RLS 정책 (관리자만 접근 가능)
ALTER TABLE page_views ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_journeys ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_stats ENABLE ROW LEVEL SECURITY;

-- 관리자 정책 (김도균만 접근)
CREATE POLICY "Admin can view all page_views" ON page_views
  FOR ALL USING (
    auth.uid() IN (
      SELECT id FROM auth.users WHERE email = 'herry0515@naver.com'
    )
  );

CREATE POLICY "Admin can view all user_journeys" ON user_journeys
  FOR ALL USING (
    auth.uid() IN (
      SELECT id FROM auth.users WHERE email = 'herry0515@naver.com'
    )
  );

CREATE POLICY "Admin can view all campaign_performance" ON campaign_performance
  FOR ALL USING (
    auth.uid() IN (
      SELECT id FROM auth.users WHERE email = 'herry0515@naver.com'
    )
  );

CREATE POLICY "Admin can view all user_actions" ON user_actions
  FOR ALL USING (
    auth.uid() IN (
      SELECT id FROM auth.users WHERE email = 'herry0515@naver.com'
    )
  );

CREATE POLICY "Admin can view all daily_stats" ON daily_stats
  FOR ALL USING (
    auth.uid() IN (
      SELECT id FROM auth.users WHERE email = 'herry0515@naver.com'
    )
  );

-- 완료 메시지
SELECT 'Analytics tables created successfully!' AS status;