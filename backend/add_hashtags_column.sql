-- hashtags 컬럼 추가
-- Supabase Dashboard > SQL Editor에서 실행하세요

ALTER TABLE documents_metadata
ADD COLUMN IF NOT EXISTS hashtags TEXT[];

-- 기존 데이터에 빈 배열 설정
UPDATE documents_metadata
SET hashtags = ARRAY[]::TEXT[]
WHERE hashtags IS NULL;

-- 해시태그 검색을 위한 GIN 인덱스 추가 (성능 향상)
CREATE INDEX IF NOT EXISTS idx_documents_hashtags 
ON documents_metadata USING GIN(hashtags);
