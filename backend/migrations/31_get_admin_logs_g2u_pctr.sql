-- G2U(게스트→유저 전환율) 및 PCTR(전환 전 평균 질문 수). 제외 이메일 적용.

CREATE OR REPLACE FUNCTION public.get_admin_logs_g2u_pctr()
RETURNS TABLE(
  g2u_converted_count bigint,
  g2u_guest_only_count bigint,
  g2u_rate numeric,
  pctr_avg numeric,
  pctr_groups_count bigint
)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  WITH excluded AS (
    SELECT u.id FROM auth.users u
    WHERE u.email IN (SELECT e.email FROM public.admin_analytics_excluded_emails e)
  ),
  groups_with_guest AS (
    SELECT DISTINCT al.is_same_person
    FROM admin_logs al
    WHERE al.is_same_person IS NOT NULL AND al.user_id IS NULL
  ),
  groups_with_valid_user AS (
    SELECT DISTINCT al.is_same_person
    FROM admin_logs al
    WHERE al.is_same_person IS NOT NULL
      AND al.user_id IS NOT NULL
      AND al.user_id NOT IN (SELECT id FROM excluded)
  ),
  converted_groups AS (
    SELECT g.is_same_person
    FROM groups_with_guest g
    WHERE g.is_same_person IN (SELECT is_same_person FROM groups_with_valid_user)
  ),
  guest_only_groups AS (
    SELECT g.is_same_person
    FROM groups_with_guest g
    WHERE g.is_same_person NOT IN (SELECT is_same_person FROM groups_with_valid_user)
  ),
  first_user_ts AS (
    SELECT al.is_same_person, min(al.timestamp) AS first_ts
    FROM admin_logs al
    WHERE al.user_id IS NOT NULL AND al.user_id NOT IN (SELECT id FROM excluded)
    GROUP BY al.is_same_person
  ),
  questions_before_per_group AS (
    SELECT c.is_same_person, count(al.id)::bigint AS cnt
    FROM converted_groups c
    JOIN first_user_ts f ON f.is_same_person = c.is_same_person
    JOIN admin_logs al ON al.is_same_person = c.is_same_person
      AND al.user_id IS NULL
      AND al.timestamp < f.first_ts
    GROUP BY c.is_same_person
  ),
  converted_cnt AS (SELECT count(*)::bigint AS n FROM converted_groups),
  guest_only_cnt AS (SELECT count(*)::bigint AS n FROM guest_only_groups),
  total_guest AS (
    SELECT (SELECT n FROM converted_cnt) + (SELECT n FROM guest_only_cnt) AS total
  ),
  pctr_agg AS (
    SELECT
      count(*)::bigint AS grp_cnt,
      coalesce(round(avg(q.cnt)::numeric, 2), 0) AS avg_q
    FROM questions_before_per_group q
  )
  SELECT
    (SELECT n FROM converted_cnt) AS g2u_converted_count,
    (SELECT n FROM guest_only_cnt) AS g2u_guest_only_count,
    CASE
      WHEN (SELECT total FROM total_guest) > 0
      THEN round(100.0 * (SELECT n FROM converted_cnt) / (SELECT total FROM total_guest), 2)
      ELSE 0
    END AS g2u_rate,
    (SELECT avg_q FROM pctr_agg) AS pctr_avg,
    (SELECT grp_cnt FROM pctr_agg) AS pctr_groups_count;
$$;

COMMENT ON FUNCTION public.get_admin_logs_g2u_pctr() IS 'G2U(게스트→유저 전환율) 및 PCTR(전환 전 평균 질문 수). is_same_person 기준, 제외 이메일 적용.';

GRANT EXECUTE ON FUNCTION public.get_admin_logs_g2u_pctr() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_g2u_pctr() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_g2u_pctr() FROM authenticated;
