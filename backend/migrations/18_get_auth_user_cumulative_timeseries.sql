-- Created at 기준 일별 가입자 수 + 누적 가입자 수 시계열
-- 관리자 API에서만 호출 (service_role 키 사용)

CREATE OR REPLACE FUNCTION public.get_auth_user_cumulative_timeseries()
RETURNS TABLE(day date, new_users bigint, cumulative_users bigint)
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  WITH daily AS (
    SELECT (created_at AT TIME ZONE 'Asia/Seoul')::date AS d, count(*) AS cnt
    FROM auth.users
    GROUP BY 1
    ORDER BY 1
  )
  SELECT d AS day, cnt AS new_users, sum(cnt) OVER (ORDER BY d) AS cumulative_users
  FROM daily;
$$;

COMMENT ON FUNCTION public.get_auth_user_cumulative_timeseries() IS '일별 신규 가입자 수와 누적 가입자 수 (auth.users created_at 기준). service_role로만 호출 권장.';

GRANT EXECUTE ON FUNCTION public.get_auth_user_cumulative_timeseries() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_auth_user_cumulative_timeseries() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_auth_user_cumulative_timeseries() FROM authenticated;
