-- events에 디바이스 정보 컬럼 추가 (page_views 제거 후 디바이스 통계용)
-- 12 실행 후, 16 실행 전에 적용

ALTER TABLE events
  ADD COLUMN IF NOT EXISTS device_type TEXT,
  ADD COLUMN IF NOT EXISTS browser TEXT,
  ADD COLUMN IF NOT EXISTS os TEXT;

COMMENT ON COLUMN events.device_type IS 'mobile, tablet, desktop';
COMMENT ON COLUMN events.browser IS '브라우저명';
COMMENT ON COLUMN events.os IS 'OS명';

SELECT 'events device columns added' AS status;
