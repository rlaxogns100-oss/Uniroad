-- user_id가 없는 is_same_person 목록 및 그룹별 행 수

CREATE OR REPLACE FUNCTION public.get_admin_logs_no_user_id_same_person_list()
RETURNS TABLE(
  is_same_person text,
  row_count bigint
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT al.is_same_person::text, count(*)::bigint AS row_count
  FROM admin_logs al
  WHERE al.is_same_person IS NOT NULL
  GROUP BY al.is_same_person
  HAVING bool_and(al.user_id IS NULL)
  ORDER BY row_count DESC, al.is_same_person;
$$;

COMMENT ON FUNCTION public.get_admin_logs_no_user_id_same_person_list() IS 'user_id가 없는 is_same_person 목록 및 그룹별 행 수';

GRANT EXECUTE ON FUNCTION public.get_admin_logs_no_user_id_same_person_list() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_no_user_id_same_person_list() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_no_user_id_same_person_list() FROM authenticated;
