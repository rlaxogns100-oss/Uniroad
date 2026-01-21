-- documents_metadata 테이블에 file_url 컬럼 추가
-- Supabase SQL Editor에서 실행하세요

ALTER TABLE documents_metadata
ADD COLUMN IF NOT EXISTS file_url TEXT;

COMMENT ON COLUMN documents_metadata.file_url IS 'Supabase Storage에 저장된 PDF 파일의 공개 URL';
