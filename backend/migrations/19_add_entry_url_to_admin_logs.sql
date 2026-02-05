-- admin_logs에 진입 URL 컬럼 추가 (사용자가 들어온 랜딩 페이지 URL)
-- 한글 컬럼명 사용 시 따옴표 필요
ALTER TABLE admin_logs
ADD COLUMN IF NOT EXISTS "진입_url" TEXT;

COMMENT ON COLUMN admin_logs."진입_url" IS '사용자가 진입한 랜딩 페이지 전체 URL (path + query)';
