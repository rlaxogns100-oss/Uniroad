-- 관리자 공용 설정 저장 (키-값). 유입경로 엑셀 데이터 등.
-- 백엔드에서 service role로만 접근하며, API에서 관리자 여부 검증함.

CREATE TABLE IF NOT EXISTS admin_settings (
  key TEXT PRIMARY KEY,
  value JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE admin_settings IS '관리자 전용 공유 설정 (path_excel 등). API에서 is_admin 검증 후 접근.';

-- upsert 시 updated_at 자동 갱신
CREATE OR REPLACE FUNCTION update_admin_settings_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_admin_settings_updated_at ON admin_settings;
CREATE TRIGGER trigger_admin_settings_updated_at
BEFORE UPDATE ON admin_settings
FOR EACH ROW
EXECUTE FUNCTION update_admin_settings_updated_at();
