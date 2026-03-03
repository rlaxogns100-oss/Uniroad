-- admin_logs 기준 유저별 태생일(최초 방문일)로 코호트별 Day-1 ~ Day-7 리텐션 시계열
-- user_id가 있는 로그만 사용. 태생일 = user_id별 min(timestamp)의 한국 날짜.

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
  WITH first_visit AS (
    SELECT
      al.user_id,
      (min(al.timestamp) AT TIME ZONE 'Asia/Seoul')::date AS cohort_day
    FROM public.admin_logs al
    WHERE al.user_id IS NOT NULL
    GROUP BY al.user_id
  ),
  cohort_sizes AS (
    SELECT
      fv.cohort_day,
      count(*)::bigint AS cohort_users
    FROM first_visit fv
    WHERE (cohort_day_from IS NULL OR fv.cohort_day >= cohort_day_from)
      AND (cohort_day_to IS NULL OR fv.cohort_day <= cohort_day_to)
    GROUP BY fv.cohort_day
  ),
  log_days AS (
    SELECT
      al.user_id,
      fv.cohort_day,
      ((al.timestamp AT TIME ZONE 'Asia/Seoul')::date - fv.cohort_day) AS day_diff
    FROM public.admin_logs al
    JOIN first_visit fv ON fv.user_id = al.user_id
    WHERE al.user_id IS NOT NULL
      AND (cohort_day_from IS NULL OR fv.cohort_day >= cohort_day_from)
      AND (cohort_day_to IS NULL OR fv.cohort_day <= cohort_day_to)
  ),
  day_n_counts AS (
    SELECT
      cohort_day,
      day_diff,
      count(DISTINCT user_id)::bigint AS users_with_day_n
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
    cs.cohort_day,
    cs.cohort_users,
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

COMMENT ON FUNCTION public.get_admin_logs_retention_day_series(date, date) IS 'admin_logs 기준 유저별 태생일(최초 방문일) 코호트별 Day-1~7 리텐션 시계열. user_id NOT NULL만. 인자 NULL이면 전 기간.';

GRANT EXECUTE ON FUNCTION public.get_admin_logs_retention_day_series(date, date) TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_retention_day_series(date, date) FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_retention_day_series(date, date) FROM authenticated;
