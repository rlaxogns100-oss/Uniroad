-- 관리자 분석에서 제외할 이메일 목록 (해당 유저는 모든 통계/목록에 포함되지 않음)

CREATE TABLE IF NOT EXISTS public.admin_analytics_excluded_emails (
  email text PRIMARY KEY
);

COMMENT ON TABLE public.admin_analytics_excluded_emails IS '관리자 통계/행동 분석에서 제외할 auth.users 이메일. 제외 시 가입 수·질문 수·리텐션·same_person 목록 등에 잡히지 않음.';

INSERT INTO public.admin_analytics_excluded_emails (email) VALUES
  ('herry0515@naver.com'),
  ('herry1234@naver.com'),
  ('horse324@naver.com')
ON CONFLICT (email) DO NOTHING;

-- API에서 제외 대상 user_id 목록 조회용 (admin_logs 직접 조회 시 필터에 사용)
CREATE OR REPLACE FUNCTION public.get_admin_analytics_excluded_user_ids()
RETURNS TABLE(user_id uuid)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT u.id AS user_id
  FROM auth.users u
  WHERE u.email IN (SELECT e.email FROM public.admin_analytics_excluded_emails e);
$$;

COMMENT ON FUNCTION public.get_admin_analytics_excluded_user_ids() IS '관리자 분석 제외 이메일에 해당하는 auth.users.id 목록. API에서 admin_logs 조회 시 필터용.';

GRANT EXECUTE ON FUNCTION public.get_admin_analytics_excluded_user_ids() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_analytics_excluded_user_ids() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_analytics_excluded_user_ids() FROM authenticated;

-- 1) 누적 가입자 수: 제외 이메일 제외
CREATE OR REPLACE FUNCTION public.get_auth_user_count()
RETURNS integer
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT count(*)::integer
  FROM auth.users u
  WHERE u.email NOT IN (SELECT e.email FROM public.admin_analytics_excluded_emails e);
$$;

-- 2) 일별/누적 가입자 시계열: 제외 이메일 제외
CREATE OR REPLACE FUNCTION public.get_auth_user_cumulative_timeseries()
RETURNS TABLE(day date, new_users bigint, cumulative_users bigint)
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  WITH daily AS (
    SELECT (u.created_at AT TIME ZONE 'Asia/Seoul')::date AS d, count(*) AS cnt
    FROM auth.users u
    WHERE u.email NOT IN (SELECT e.email FROM public.admin_analytics_excluded_emails e)
    GROUP BY 1
    ORDER BY 1
  )
  SELECT d AS day, cnt AS new_users, sum(cnt) OVER (ORDER BY d) AS cumulative_users
  FROM daily;
$$;

-- 3) 일별/누적 질문 수 시계열: 제외 user_id 로그 제외
CREATE OR REPLACE FUNCTION public.get_admin_logs_question_cumulative_timeseries()
RETURNS TABLE(day date, new_questions bigint, cumulative_questions bigint)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  WITH excluded AS (
    SELECT u.id FROM auth.users u
    WHERE u.email IN (SELECT e.email FROM public.admin_analytics_excluded_emails e)
  ),
  daily AS (
    SELECT (al.created_at AT TIME ZONE 'Asia/Seoul')::date AS d, count(*) AS cnt
    FROM public.admin_logs al
    WHERE (al.user_id IS NULL OR al.user_id NOT IN (SELECT id FROM excluded))
    GROUP BY 1
    ORDER BY 1
  )
  SELECT d AS day, cnt AS new_questions, sum(cnt) OVER (ORDER BY d) AS cumulative_questions
  FROM daily;
$$;

-- 4) 리텐션 Day-1~7: 제외 user_id 제외
CREATE OR REPLACE FUNCTION public.get_admin_logs_retention_day_series(
  cohort_day_from date DEFAULT NULL,
  cohort_day_to date DEFAULT NULL
)
RETURNS TABLE(
  cohort_day date,
  cohort_users bigint,
  day_1_users bigint,
  day_2_users bigint,
  day_3_users bigint,
  day_4_users bigint,
  day_5_users bigint,
  day_6_users bigint,
  day_7_users bigint,
  day_1_rate numeric,
  day_2_rate numeric,
  day_3_rate numeric,
  day_4_rate numeric,
  day_5_rate numeric,
  day_6_rate numeric,
  day_7_rate numeric
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  WITH excluded AS (
    SELECT u.id FROM auth.users u
    WHERE u.email IN (SELECT e.email FROM public.admin_analytics_excluded_emails e)
  ),
  first_visit AS (
    SELECT al.user_id, (min(al.timestamp) AT TIME ZONE 'Asia/Seoul')::date AS cohort_day
    FROM public.admin_logs al
    WHERE al.user_id IS NOT NULL AND al.user_id NOT IN (SELECT id FROM excluded)
    GROUP BY al.user_id
  ),
  cohort_sizes AS (
    SELECT fv.cohort_day, count(*)::bigint AS cohort_users
    FROM first_visit fv
    WHERE (cohort_day_from IS NULL OR fv.cohort_day >= cohort_day_from)
      AND (cohort_day_to IS NULL OR fv.cohort_day <= cohort_day_to)
    GROUP BY fv.cohort_day
  ),
  log_days AS (
    SELECT al.user_id, fv.cohort_day,
           ((al.timestamp AT TIME ZONE 'Asia/Seoul')::date - fv.cohort_day) AS day_diff
    FROM public.admin_logs al
    JOIN first_visit fv ON fv.user_id = al.user_id
    WHERE al.user_id IS NOT NULL
      AND (cohort_day_from IS NULL OR fv.cohort_day >= cohort_day_from)
      AND (cohort_day_to IS NULL OR fv.cohort_day <= cohort_day_to)
  ),
  day_n_counts AS (
    SELECT cohort_day, day_diff, count(DISTINCT user_id)::bigint AS users_with_day_n
    FROM log_days
    WHERE day_diff BETWEEN 1 AND 7
    GROUP BY cohort_day, day_diff
  ),
  d1 AS (SELECT cohort_day, users_with_day_n FROM day_n_counts WHERE day_diff = 1),
  d2 AS (SELECT cohort_day, users_with_day_n FROM day_n_counts WHERE day_diff = 2),
  d3 AS (SELECT cohort_day, users_with_day_n FROM day_n_counts WHERE day_diff = 3),
  d4 AS (SELECT cohort_day, users_with_day_n FROM day_n_counts WHERE day_diff = 4),
  d5 AS (SELECT cohort_day, users_with_day_n FROM day_n_counts WHERE day_diff = 5),
  d6 AS (SELECT cohort_day, users_with_day_n FROM day_n_counts WHERE day_diff = 6),
  d7 AS (SELECT cohort_day, users_with_day_n FROM day_n_counts WHERE day_diff = 7)
  SELECT
    cs.cohort_day, cs.cohort_users,
    coalesce(d1.users_with_day_n, 0)::bigint AS day_1_users,
    coalesce(d2.users_with_day_n, 0)::bigint AS day_2_users,
    coalesce(d3.users_with_day_n, 0)::bigint AS day_3_users,
    coalesce(d4.users_with_day_n, 0)::bigint AS day_4_users,
    coalesce(d5.users_with_day_n, 0)::bigint AS day_5_users,
    coalesce(d6.users_with_day_n, 0)::bigint AS day_6_users,
    coalesce(d7.users_with_day_n, 0)::bigint AS day_7_users,
    round(100.0 * coalesce(d1.users_with_day_n, 0) / nullif(cs.cohort_users, 0), 2) AS day_1_rate,
    round(100.0 * coalesce(d2.users_with_day_n, 0) / nullif(cs.cohort_users, 0), 2) AS day_2_rate,
    round(100.0 * coalesce(d3.users_with_day_n, 0) / nullif(cs.cohort_users, 0), 2) AS day_3_rate,
    round(100.0 * coalesce(d4.users_with_day_n, 0) / nullif(cs.cohort_users, 0), 2) AS day_4_rate,
    round(100.0 * coalesce(d5.users_with_day_n, 0) / nullif(cs.cohort_users, 0), 2) AS day_5_rate,
    round(100.0 * coalesce(d6.users_with_day_n, 0) / nullif(cs.cohort_users, 0), 2) AS day_6_rate,
    round(100.0 * coalesce(d7.users_with_day_n, 0) / nullif(cs.cohort_users, 0), 2) AS day_7_rate
  FROM cohort_sizes cs
  LEFT JOIN d1 ON d1.cohort_day = cs.cohort_day
  LEFT JOIN d2 ON d2.cohort_day = cs.cohort_day
  LEFT JOIN d3 ON d3.cohort_day = cs.cohort_day
  LEFT JOIN d4 ON d4.cohort_day = cs.cohort_day
  LEFT JOIN d5 ON d5.cohort_day = cs.cohort_day
  LEFT JOIN d6 ON d6.cohort_day = cs.cohort_day
  LEFT JOIN d7 ON d7.cohort_day = cs.cohort_day
  ORDER BY cs.cohort_day;
$$;

-- 5) same_person 활동: 제외 user_id가 있는 그룹/로그 제외
DROP FUNCTION IF EXISTS public.get_admin_logs_same_person_activity();

CREATE OR REPLACE FUNCTION public.get_admin_logs_same_person_activity()
RETURNS TABLE(
  is_same_person text,
  latest_ts timestamptz,
  total_questions bigint,
  distinct_hour_appearances bigint
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  WITH excluded AS (
    SELECT u.id FROM auth.users u
    WHERE u.email IN (SELECT e.email FROM public.admin_analytics_excluded_emails e)
  ),
  has_user_id AS (
    SELECT DISTINCT al.is_same_person
    FROM admin_logs al
    WHERE al.is_same_person IS NOT NULL AND al.user_id IS NOT NULL
      AND al.user_id NOT IN (SELECT id FROM excluded)
  ),
  latest_per_person_raw AS (
    SELECT al.is_same_person, max(al.timestamp) AS latest_ts
    FROM admin_logs al
    JOIN has_user_id h ON h.is_same_person = al.is_same_person
    GROUP BY al.is_same_person
  ),
  has_conversation AS (
    SELECT l.is_same_person
    FROM latest_per_person_raw l
    JOIN admin_logs al ON al.is_same_person = l.is_same_person AND al.timestamp = l.latest_ts
    WHERE jsonb_array_length(COALESCE(al.conversation_history, '[]'::jsonb)) > 0
  ),
  latest_per_person AS (
    SELECT l.is_same_person, l.latest_ts
    FROM latest_per_person_raw l
    JOIN has_conversation c ON c.is_same_person = l.is_same_person
  ),
  total_per_person AS (
    SELECT al.is_same_person, count(al.id)::bigint AS cnt
    FROM admin_logs al
    JOIN has_conversation c ON c.is_same_person = al.is_same_person
    GROUP BY al.is_same_person
  ),
  first_ts_per_person AS (
    SELECT al.is_same_person, min(al.timestamp) AS first_ts
    FROM admin_logs al
    JOIN has_conversation c ON c.is_same_person = al.is_same_person
    GROUP BY al.is_same_person
  )
  SELECT
    l.is_same_person, l.latest_ts, t.cnt AS total_questions,
    floor(EXTRACT(EPOCH FROM (l.latest_ts - f.first_ts)) / 3600)::bigint AS distinct_hour_appearances
  FROM latest_per_person l
  JOIN first_ts_per_person f ON f.is_same_person = l.is_same_person
  JOIN total_per_person t ON t.is_same_person = l.is_same_person
  ORDER BY l.latest_ts DESC;
$$;

-- 6) same_person 요약: is_same_person null 행 수에서 제외 user_id 행 제외
CREATE OR REPLACE FUNCTION public.get_admin_logs_same_person_summary()
RETURNS TABLE(
  count_is_same_person_null bigint,
  count_no_user_id_same_person bigint
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  WITH excluded AS (
    SELECT u.id FROM auth.users u
    WHERE u.email IN (SELECT e.email FROM public.admin_analytics_excluded_emails e)
  ),
  no_user_id_groups AS (
    SELECT al.is_same_person
    FROM admin_logs al
    WHERE al.is_same_person IS NOT NULL
    GROUP BY al.is_same_person
    HAVING bool_and(al.user_id IS NULL)
  )
  SELECT
    (SELECT count(*)::bigint FROM admin_logs al
     WHERE al.is_same_person IS NULL
       AND (al.user_id IS NULL OR al.user_id NOT IN (SELECT id FROM excluded))) AS count_is_same_person_null,
    (SELECT count(*)::bigint FROM admin_logs al
     WHERE al.is_same_person IN (SELECT is_same_person FROM no_user_id_groups)) AS count_no_user_id_same_person;
$$;
