-- admin_logs 요약: is_same_person이 null인 행의 수, user_id가 없는 is_same_person 그룹에 속한 행의 수

CREATE OR REPLACE FUNCTION public.get_admin_logs_same_person_summary()
RETURNS TABLE(
  count_is_same_person_null bigint,
  count_no_user_id_same_person bigint
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  WITH no_user_id_groups AS (
    SELECT al.is_same_person
    FROM admin_logs al
    WHERE al.is_same_person IS NOT NULL
    GROUP BY al.is_same_person
    HAVING bool_and(al.user_id IS NULL)
  )
  SELECT
    (SELECT count(*)::bigint FROM admin_logs WHERE is_same_person IS NULL),
    (SELECT count(*)::bigint FROM admin_logs WHERE is_same_person IN (SELECT is_same_person FROM no_user_id_groups));
$$;

COMMENT ON FUNCTION public.get_admin_logs_same_person_summary() IS 'is_same_person null 행 수, user_id가 없는 is_same_person 그룹의 행 수';

GRANT EXECUTE ON FUNCTION public.get_admin_logs_same_person_summary() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_same_person_summary() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_same_person_summary() FROM authenticated;
