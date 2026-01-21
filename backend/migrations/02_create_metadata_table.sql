-- documents_metadata 테이블 생성
-- 실행 방법: Supabase Dashboard > SQL Editor에서 실행

-- 1. documents_metadata 테이블 생성 (파일당 1개 행)
CREATE TABLE IF NOT EXISTS documents_metadata (
  file_name TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  source TEXT,
  summary TEXT NOT NULL,                    -- 목차 형식 요약
  total_pages INTEGER,
  total_chunks INTEGER,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 2. policy_documents 테이블의 metadata 간소화
-- 주의: 이미 데이터가 있다면 모두 삭제 후 다시 업로드해야 함
-- 기존 데이터 삭제 (필요시)
-- DELETE FROM policy_documents;

-- 3. 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_documents_metadata_title ON documents_metadata(title);
CREATE INDEX IF NOT EXISTS idx_documents_metadata_created_at ON documents_metadata(created_at DESC);

-- 완료!
SELECT 'documents_metadata 테이블 생성 완료!' AS status;
