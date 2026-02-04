-- 임베딩 기반 문서 스키마 생성

create extension if not exists vector;

create table if not exists documents (
  id bigserial primary key,
  school_name text not null,
  filename text not null,
  summary text,
  embedding_summary vector(768),
  file_url text,
  metadata jsonb,
  created_at timestamptz default now()
);

create table if not exists document_sections (
  id bigserial primary key,
  document_id bigint references documents(id) on delete cascade,
  section_name text,
  page_start int,
  page_end int
);

create table if not exists document_chunks (
  id bigserial primary key,
  document_id bigint references documents(id) on delete cascade,
  section_id bigint references document_sections(id) on delete set null,
  content text,
  raw_data text,
  embedding vector(768),
  page_number int,
  chunk_type text,
  created_at timestamptz default now()
);

create index if not exists idx_documents_school_name on documents (school_name);
create index if not exists idx_document_sections_doc_id on document_sections (document_id);
create index if not exists idx_document_chunks_doc_id on document_chunks (document_id);
create index if not exists idx_document_chunks_section_id on document_chunks (section_id);

-- ivfflat: lists는 대략 sqrt(행수) 이상 권장. 초기에는 작게 설정 후 데이터 증가 시 재생성 가능
create index if not exists idx_document_chunks_embedding on document_chunks
using ivfflat (embedding vector_cosine_ops) with (lists = 10);

drop function if exists match_document_chunks(
  vector(768),
  float,
  int,
  text,
  bigint
);

create or replace function match_document_chunks(
  query_embedding vector(768),
  match_threshold float,
  match_count int,
  filter_school_name text default null,
  filter_section_id bigint default null
)
returns table (
  id bigint,
  document_id bigint,
  section_id bigint,
  content text,
  raw_data text,
  embedding vector(768),
  page_number int,
  chunk_type text,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    dc.id,
    dc.document_id,
    dc.section_id,
    dc.content,
    dc.raw_data,
    dc.embedding,
    dc.page_number,
    dc.chunk_type,
    1 - (dc.embedding <=> query_embedding) as similarity
  from document_chunks dc
  join documents d on d.id = dc.document_id
  where (filter_school_name is null or d.school_name = filter_school_name)
    and (filter_section_id is null or dc.section_id = filter_section_id)
    and (1 - (dc.embedding <=> query_embedding)) > match_threshold
  order by dc.embedding <=> query_embedding
  limit match_count;
end;
$$;
