# 관리자 분석에서 특정 이메일 제외 — 구현 계획

## 목표

관리자 페이지의 **모든 분석**에서 아래 3개 이메일 유저가 집계·목록·상세에 잡히지 않도록 한다.

- `herry0515@naver.com`
- `herry1234@naver.com`
- `horse324@naver.com`

---

## 영향 범위 정리

| 구분 | 데이터 소스 | 제외 방식 |
|------|-------------|-----------|
| **Auth 기반** | `auth.users` | 해당 **email** 제외 |
| **admin_logs 기반** | `admin_logs` | 해당 유저의 **user_id**로 남긴 로그 전부 제외 |

---

## 1단계: 제외 대상 저장 (DB)

### 1.1 테이블 추가

- **테이블**: `public.admin_analytics_excluded_emails`
- **컬럼**: `email text PRIMARY KEY`
- **용도**: 분석에서 제외할 이메일 목록. 나중에 추가/삭제 시 INSERT/DELETE만 하면 됨.

### 1.2 초기 데이터

- 위 3개 이메일을 `admin_analytics_excluded_emails`에 INSERT하는 마이그레이션 포함.

---

## 2단계: Auth 기반 지표에서 제외

`auth.users`를 사용하는 RPC에서 **email**이 제외 목록에 있으면 제외.

| 마이그레이션 | 함수 | 변경 요약 |
|-------------|------|-----------|
| **17** | `get_auth_user_count` | `COUNT(*)` 시 `WHERE email NOT IN (SELECT email FROM public.admin_analytics_excluded_emails)` 추가. (`auth.users` 조회 시 제외) |
| **18** | `get_auth_user_cumulative_timeseries` | 일별/누적 집계 시 동일하게 `auth.users`에서 위 이메일 제외 후 집계. |

---

## 3단계: admin_logs 기반 지표에서 제외

`admin_logs`를 읽는 모든 RPC에서, **user_id**가 제외 대상 이메일의 유저이면 그 로그를 사용하지 않음.

- **공통 조건**:  
  `(user_id IS NULL OR user_id NOT IN (SELECT id FROM auth.users WHERE email IN (SELECT email FROM public.admin_analytics_excluded_emails)))`  
  → `admin_logs`를 읽는 CTE/서브쿼리에 위 조건을 반영.

| 마이그레이션 | 함수 | 변경 요약 |
|-------------|------|-----------|
| **20** | `get_admin_logs_question_cumulative_timeseries` | `FROM admin_logs`에 위 제외 조건 추가. |
| **27** | `get_admin_logs_retention_day_series` | `first_visit`, `log_days` 등 `admin_logs`/`user_id` 사용하는 부분에 제외 조건 추가. |
| **22** | `get_admin_logs_same_person_activity` | `has_user_id` 및 `admin_logs`를 쓰는 모든 CTE에서 해당 user_id 제외. |
| **23** | `get_admin_logs_same_person_summary` | `is_same_person IS NULL` 개수 셀 때 제외 user_id 로그 제외. (no_user_id 그룹은 원래 user_id 없는 행만이라 선택적 변경) |
| **24**, **25** | no_user_id 전용 분포/목록 | user_id 없는 행만 대상이므로, 해당 3명(로그인 유저)은 원래 포함되지 않음. **변경 없음**으로 두어도 됨. (일관성을 위해 다른 RPC와 동일한 제외 조건을 넣어도 됨) |

---

## 4단계: 행 단위 반환 API에서 제외

관리자 페이지에서 **admin_logs 행을 그대로** 내려주는 API는, 조회 결과에 제외 대상 user_id가 있으면 노출하지 않음.

| API (admin_stats) | 동작 |
|-------------------|------|
| **GET /stats/behavior/latest-conversation** | `is_same_person`으로 최신 로그 1건 조회 후, 해당 행의 `user_id`가 제외 목록에 있으면 `{"log": null}` 반환. |
| **GET /stats/behavior/log-by-id** | `log_id`로 1건 조회 후, `user_id`가 제외 목록에 있으면 `{"log": null}` 또는 404. |
| **GET /stats/behavior/null-same-person-rows** | `admin_logs` 조회 시 제외 user_id 조건 추가 (Supabase 쿼리 `.not_('user_id', 'in', excluded_user_ids)` 또는 RPC로 대체). |

구현 방식:

- **방식 A**: API 레이어에서 “제외 user_id 목록”을 한 번 조회(캐시 가능)해 두고, 위 3개 API에서만 “반환 전에 user_id 체크” 또는 “쿼리 시 제외 목록 전달”.
- **방식 B**: “제외 user_id 목록 반환” RPC를 하나 만들고, Python에서 해당 목록을 받아서 테이블 조회 시 `.not_('user_id', 'in', list)` 로 필터.  
→ **권장**: RPC `get_admin_analytics_excluded_user_ids()` (또는 기존 제외 테이블과 조인하는 뷰)로 제외 user_id 목록을 반환하고, 위 3개 엔드포인트에서 이 목록을 사용해 필터/검증.

---

## 5단계: 프론트엔드

- 집계/시계열/리텐션/행동 요약은 **전부 DB·API에서 이미 제외**하므로 **추가 수정 없음**.
- 단, “특정 로그 상세 보기” 등으로 제외 유저 로그를 직접 요청하면 4단계에 따라 `log: null` 등으로 내려오므로, 기존 UI가 null 처리만 하고 있으면 그대로 동작.

---

## 작업 순서 요약

1. **마이그레이션 1**: `admin_analytics_excluded_emails` 테이블 생성 + 3개 이메일 INSERT.
2. **마이그레이션 2**: 제외 user_id 목록 반환 RPC 추가 (선택이지만 API 필터에 유리).
3. **기존 RPC 수정 마이그레이션**: 17, 18, 20, 22, 23, 27에서 위 조건 반영. (24, 25는 선택)
4. **admin_stats 라우터**:  
   - `latest-conversation`, `log-by-id`, `null-same-person-rows` 에서 제외 user_id 조회 후 필터/검증 적용.

---

## 주의사항

- **search_path / 스키마**: RPC에서 `auth.users`를 참조할 때 `auth.users`로 스키마까지 명시. `search_path`에 `public`만 있어도 `auth.users`는 호출 가능해야 함 (Supabase 기본 설정).
- **성능**: 제외 목록은 3개로 고정이므로 `NOT IN (SELECT id FROM auth.users WHERE email IN (...))` 부담은 크지 않음. 필요 시 나중에 “제외 user_id만 모은 작은 테이블”로 캐시해 두고 조인할 수 있음.
- **추가/삭제**: 제외할 이메일을 바꿀 때는 `admin_analytics_excluded_emails`만 INSERT/DELETE하면 되고, RPC/API 로직은 수정하지 않아도 됨.

이 순서대로 적용하면 관리자 페이지에서 위 3개 이메일은 모든 분석(집계·목록·상세)에 잡히지 않게 할 수 있습니다.
