# DB 테이블 사용 현황 분석

코드베이스와 마이그레이션을 기준으로, **사용 중인 테이블**과 **정의만 있고 사용되지 않는 테이블**을 정리한 문서입니다.

---

## 1. 사용 중인 테이블

아래 테이블은 백엔드 Python 코드에서 `client.table("테이블명")` 또는 `supabase.table("테이블명")`으로 참조됩니다.

| 테이블명 | 정의 위치 | 사용처 (요약) |
|----------|-----------|----------------|
| **admin_logs** | [create_admin_logs_table.sql](backend/create_admin_logs_table.sql) | [admin_logs.py](backend/routers/admin_logs.py) – 실행 로그 CRUD |
| **announcements** | [07_create_announcements.sql](backend/migrations/07_create_announcements.sql) | [announcements.py](backend/routers/announcements.py) – 공지 CRUD |
| **chat_logs** | (마이그레이션 폴더 내 CREATE 없음, 01 등 별도 스크립트 추정) | [supabase_client.py](backend/services/supabase_client.py) `insert_chat_log`, [chat.py](backend/routers/chat.py)에서 호출 |
| **chat_messages** | [06_add_user_sessions.sql](backend/migrations/06_add_user_sessions.sql) | [chat.py](backend/routers/chat.py), [sessions.py](backend/routers/sessions.py) – 메시지 저장/조회 |
| **chat_sessions** | [06_add_user_sessions.sql](backend/migrations/06_add_user_sessions.sql) | [chat.py](backend/routers/chat.py), [sessions.py](backend/routers/sessions.py), [main.py](backend/main.py) – 세션 생성/조회 |
| **conversation_context** | [06_add_user_sessions.sql](backend/migrations/06_add_user_sessions.sql) | [sessions.py](backend/routers/sessions.py) – 컨텍스트 저장/조회 |
| **document_chunks** | [09_create_documents_tables.sql](backend/migrations/09_create_documents_tables.sql) | [supabase_client.py](backend/services/supabase_client.py) – 청크 삭제/삽입 |
| **documents** | [09_create_documents_tables.sql](backend/migrations/09_create_documents_tables.sql) | [supabase_client.py](backend/services/supabase_client.py), [documents.py](backend/routers/documents.py), [functions.py](backend/services/multi_agent/functions.py) – 문서 CRUD·검색 |
| **document_sections** | [09_create_documents_tables.sql](backend/migrations/09_create_documents_tables.sql) | [supabase_client.py](backend/services/supabase_client.py) – 섹션 삭제/삽입 |
| **documents_metadata** | [02_create_metadata_table.sql](backend/migrations/02_create_metadata_table.sql) | [supabase_client.py](backend/services/supabase_client.py) – 메타데이터 삽입 |
| **page_views** | [10_create_analytics_tables.sql](backend/migrations/10_create_analytics_tables.sql) | [tracking.py](backend/routers/tracking.py) insert, [analytics.py](backend/routers/analytics.py) device-stats |
| **policy_documents** | (README 기준 01_initial_setup 등에서 생성 추정) | [supabase_client.py](backend/services/supabase_client.py) insert, [check_dimensions.py](backend/check_dimensions.py) – 벡터/청크 용도 |
| **user_actions** | [10_create_analytics_tables.sql](backend/migrations/10_create_analytics_tables.sql) | [tracking.py](backend/routers/tracking.py) – 행동 이벤트 insert |
| **user_journeys** | [10_create_analytics_tables.sql](backend/migrations/10_create_analytics_tables.sql) | [tracking.py](backend/routers/tracking.py), [analytics.py](backend/routers/analytics.py) funnel – 여정 추적 |
| **user_profiles** | [create_user_profiles_table.sql](backend/create_user_profiles_table.sql) | [supabase_client.py](backend/services/supabase_client.py) – 프로필 조회/upsert |
| **usage_tracking** | [08_create_usage_tracking.sql](backend/migrations/08_create_usage_tracking.sql) | [rate_limit.py](backend/middleware/rate_limit.py) – 사용량/ rate limit |

---

## 2. 사용되지 않는 테이블 (정의만 존재)

다음 테이블은 마이그레이션에서 **CREATE** 되지만, 백엔드 코드에서 **어디에서도 `.table("이름")`으로 참조되지 않습니다.**

| 테이블명 | 정의 위치 | 비고 |
|----------|-----------|------|
| **campaign_performance** | [10_create_analytics_tables.sql](backend/migrations/10_create_analytics_tables.sql) | UTM·캠페인별 성과 집계용으로 생성됐으나, 집계/조회하는 코드 없음. |
| **daily_stats** | [10_create_analytics_tables.sql](backend/migrations/10_create_analytics_tables.sql) | 일별 통계 스냅샷용으로 생성됐으나, insert/select 하는 코드 없음. |

즉, **현재 애플리케이션 로직에서는 사용되지 않고**, 나중에 배치/관리 도구에서 채울 계획이 없다면 “미사용 테이블”로 보면 됩니다.

---

## 3. CREATE 위치가 불명확한 테이블 (코드에서는 사용 중)

| 테이블명 | 코드 사용 | CREATE 위치 |
|----------|-----------|-------------|
| **chat_logs** | [supabase_client.insert_chat_log](backend/services/supabase_client.py), [chat.py](backend/routers/chat.py)에서 호출 | `migrations/` 폴더 내에는 CREATE 없음. 01_initial_setup 등 다른 스크립트에 있을 수 있음. |
| **policy_documents** | [supabase_client](backend/services/supabase_client.py), [check_dimensions.py](backend/check_dimensions.py) | [migrations/README.md](backend/migrations/README.md)에선 `01_initial_setup.sql`에서 생성한다고 명시. 해당 파일은 현재 migrations 목록에 없음. |

실제 Supabase에 이 테이블들이 있다면, 초기 셋업용 스크립트가 다른 경로에 있거나 수동 실행된 것으로 보면 됩니다.

---

## 4. 요약

- **사용 중:** 16개 테이블 (admin_logs, announcements, chat_logs, chat_messages, chat_sessions, conversation_context, document_chunks, documents, document_sections, documents_metadata, page_views, policy_documents, user_actions, user_journeys, user_profiles, usage_tracking)
- **미사용 (정의만 있음):** 2개 테이블 (campaign_performance, daily_stats)
- **CREATE 위치 불명확:** chat_logs, policy_documents (코드에서는 사용 중)

추가로, **Supabase Auth**의 `auth.users`는 Python에서 직접 테이블명으로 참조하지 않고 Auth Admin API(`list_users` 등)로만 사용됩니다.
