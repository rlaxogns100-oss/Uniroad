-- 오늘 기준 롤링 창(1일~14일) 활성 사용자 수. 활성 사용자 = 로그인 유저 중 해당 기간에 질문한 유저. 1일=오늘만, 2일=어제+오늘, …, 7일=1주, 14일=2주 (admin_logs, 제외 이메일 적용)

CREATE OR REPLACE FUNCTION public.get_admin_logs_active_users_rolling()
RETURNS TABLE(days integer, active_users bigint)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  WITH today AS (
    SELECT (now() AT TIME ZONE 'Asia/Seoul')::date AS d
  ),
  excluded AS (
    SELECT u.id FROM auth.users u
    WHERE u.email IN (SELECT e.email FROM public.admin_analytics_excluded_emails e)
  ),
  day_series AS (
    SELECT generate_series(1, 14) AS n
  ),
  ranges AS (
    SELECT ds.n,
           (SELECT t.d FROM today t) - ds.n + 1 AS from_d,
           (SELECT t.d FROM today t) AS to_d
    FROM day_series ds
  ),
  log_dates AS (
    SELECT
      al.user_id,
      (al.timestamp AT TIME ZONE 'Asia/Seoul')::date AS log_date
    FROM public.admin_logs al
    WHERE al.user_id IS NOT NULL
      AND al.user_id NOT IN (SELECT id FROM excluded)
  )
  SELECT
    r.n::integer AS days,
    count(DISTINCT ld.user_id)::bigint AS active_users
  FROM ranges r
  LEFT JOIN log_dates ld ON ld.log_date >= r.from_d AND ld.log_date <= r.to_d
  GROUP BY r.n
  ORDER BY r.n;
$$;

COMMENT ON FUNCTION public.get_admin_logs_active_users_rolling() IS '오늘 기준 롤링 창: 1일~14일 구간별 활성 사용자 수. 활성 사용자=로그인 유저 중 해당 기간에 질문한 유저(admin_logs, 제외 이메일 적용).';

GRANT EXECUTE ON FUNCTION public.get_admin_logs_active_users_rolling() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_active_users_rolling() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_active_users_rolling() FROM authenticated;
