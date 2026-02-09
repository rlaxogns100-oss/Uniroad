-- 특정 코호트(태생일)의 유저 목록 조회. Day-N 달성 유저만 볼 수도 있음. 각 유저의 최신 대화 1건 포함 (관리자 분석 제외 이메일 적용)
-- 반환 타입 변경 시 기존 함수 제거 후 재생성 필요

DROP FUNCTION IF EXISTS public.get_admin_logs_retention_cohort_users(date, integer);

CREATE OR REPLACE FUNCTION public.get_admin_logs_retention_cohort_users(
  p_cohort_day date,
  p_day_n integer DEFAULT NULL
)
RETURNS TABLE(
  user_id uuid,
  email text,
  latest_log_id text,
  latest_timestamp timestamptz,
  latest_user_question text,
  latest_final_answer text,
  latest_conversation_history jsonb
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
  cohort_user_ids AS (
    SELECT fv.user_id
    FROM first_visit fv
    WHERE fv.cohort_day = p_cohort_day
      AND (p_day_n IS NULL
           OR EXISTS (
             SELECT 1 FROM public.admin_logs al2
             WHERE al2.user_id = fv.user_id
               AND ((al2.timestamp AT TIME ZONE 'Asia/Seoul')::date - p_cohort_day) = p_day_n
           ))
  )
  SELECT
    c.user_id,
    u.email::text,
    lat.latest_log_id,
    lat.latest_timestamp,
    lat.latest_user_question,
    lat.latest_final_answer,
    lat.latest_conversation_history
  FROM cohort_user_ids c
  JOIN auth.users u ON u.id = c.user_id
  LEFT JOIN LATERAL (
    SELECT
      al.id::text AS latest_log_id,
      al.timestamp AS latest_timestamp,
      al.user_question AS latest_user_question,
      al.final_answer AS latest_final_answer,
      al.conversation_history AS latest_conversation_history
    FROM public.admin_logs al
    WHERE al.user_id = c.user_id
    ORDER BY al.timestamp DESC
    LIMIT 1
  ) lat ON true
  ORDER BY u.email;
$$;

COMMENT ON FUNCTION public.get_admin_logs_retention_cohort_users(date, integer) IS '코호트(태생일)별 유저 목록 + 각 유저 최신 대화 1건. p_day_n 넣으면 해당 Day-N 달성 유저만. 제외 이메일 적용.';

GRANT EXECUTE ON FUNCTION public.get_admin_logs_retention_cohort_users(date, integer) TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_retention_cohort_users(date, integer) FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_retention_cohort_users(date, integer) FROM authenticated;
