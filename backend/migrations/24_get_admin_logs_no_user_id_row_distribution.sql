-- user_id가 없는 is_same_person 그룹별 행 수 분포 (행이 N개인 is_same_person이 몇 명인지)

CREATE OR REPLACE FUNCTION public.get_admin_logs_no_user_id_row_distribution()
RETURNS TABLE(
  rows_per_person bigint,
  num_persons bigint
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  WITH no_user_id_groups AS (
    SELECT al.is_same_person, count(*)::bigint AS row_count
    FROM admin_logs al
    WHERE al.is_same_person IS NOT NULL
    GROUP BY al.is_same_person
    HAVING bool_and(al.user_id IS NULL)
  )
  SELECT g.row_count AS rows_per_person, count(*)::bigint AS num_persons
  FROM no_user_id_groups g
  GROUP BY g.row_count
  ORDER BY g.row_count;
$$;

COMMENT ON FUNCTION public.get_admin_logs_no_user_id_row_distribution() IS 'user_id가 없는 is_same_person 그룹별 행 수 분포 (rows_per_person, 해당 행 수인 그룹 개수)';

GRANT EXECUTE ON FUNCTION public.get_admin_logs_no_user_id_row_distribution() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_no_user_id_row_distribution() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_no_user_id_row_distribution() FROM authenticated;
