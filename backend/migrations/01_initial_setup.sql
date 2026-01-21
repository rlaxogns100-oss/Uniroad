-- 이 SQL을 Supabase SQL Editor에서 실행하세요

-- 1. 벡터 검색 함수 생성
create or replace function match_documents (
  query_embedding vector(1536),
  match_threshold float,
  match_count int
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
language sql stable
as $$
  select
    policy_documents.id,
    policy_documents.content,
    policy_documents.metadata,
    1 - (policy_documents.embedding <=> query_embedding) as similarity
  from policy_documents
  where 1 - (policy_documents.embedding <=> query_embedding) > match_threshold
  order by policy_documents.embedding <=> query_embedding
  limit match_count;
$$;

-- 2. 인덱스 생성 (벡터 검색 성능 향상)
create index if not exists policy_documents_embedding_idx 
  on policy_documents 
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- 참고: DB에 이미 테이블들이 생성되어 있다고 가정합니다.
-- 만약 테이블이 없다면 제공된 스키마대로 테이블을 먼저 생성하세요.

