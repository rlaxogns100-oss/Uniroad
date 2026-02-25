-- Score review workflow tables (chat v2)

create table if not exists user_score_sets (
  id uuid primary key default gen_random_uuid(),
  user_id text not null,
  name varchar(10) not null,
  scores jsonb not null,
  source_message text,
  title_auto_generated boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, name)
);

create index if not exists idx_user_score_sets_user_updated
  on user_score_sets (user_id, updated_at desc);

create table if not exists chat_score_pending (
  id uuid primary key default gen_random_uuid(),
  user_id text,
  session_id text not null,
  raw_message text not null,
  router_output jsonb not null,
  candidate_scores jsonb not null,
  title_auto varchar(10) not null,
  status text not null check (status in ('review_required', 'approved', 'skipped', 'expired')),
  score_set_id uuid references user_score_sets(id) on delete set null,
  expires_at timestamptz not null default (now() + interval '30 minutes'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_chat_score_pending_session_status
  on chat_score_pending (session_id, status, updated_at desc);

create table if not exists chat_session_flags (
  id uuid primary key default gen_random_uuid(),
  session_id text not null,
  user_id text not null default 'guest',
  skip_score_review boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (session_id, user_id)
);

create index if not exists idx_chat_session_flags_session
  on chat_session_flags (session_id, updated_at desc);

create table if not exists chat_score_links (
  id uuid primary key default gen_random_uuid(),
  session_id text not null,
  user_message_id text,
  assistant_message_id text,
  score_set_id uuid not null references user_score_sets(id) on delete cascade,
  score_name varchar(10) not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_chat_score_links_session_created
  on chat_score_links (session_id, created_at desc);
