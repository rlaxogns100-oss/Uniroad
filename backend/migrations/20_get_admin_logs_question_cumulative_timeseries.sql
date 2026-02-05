-- admin_logs.created_at 기준 일별 질문 수 + 누적 질문 수 시계열
-- 한 행 = 한 질문(user_question)으로 간주

CREATE OR REPLACE FUNCTION public.get_admin_logs_question_cumulative_timeseries()
RETURNS TABLE(day date, new_questions bigint, cumulative_questions bigint)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  WITH daily AS (
    SELECT (created_at AT TIME ZONE 'Asia/Seoul')::date AS d, count(*) AS cnt
    FROM public.admin_logs
    GROUP BY 1
    ORDER BY 1
  )
  SELECT d AS day, cnt AS new_questions, sum(cnt) OVER (ORDER BY d) AS cumulative_questions
  FROM daily;
$$;

COMMENT ON FUNCTION public.get_admin_logs_question_cumulative_timeseries() IS '일별 신규 질문 수와 누적 질문 수 (admin_logs.created_at 기준, 한국 날짜).';

GRANT EXECUTE ON FUNCTION public.get_admin_logs_question_cumulative_timeseries() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_question_cumulative_timeseries() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_question_cumulative_timeseries() FROM authenticated;
