-- storage_file_name 컬럼 추가
-- Supabase Dashboard > SQL Editor에서 실행하세요

ALTER TABLE documents_metadata
ADD COLUMN IF NOT EXISTS storage_file_name TEXT;

-- 기존 데이터의 storage_file_name을 file_name과 동일하게 설정
UPDATE documents_metadata
SET storage_file_name = file_name
WHERE storage_file_name IS NULL;
