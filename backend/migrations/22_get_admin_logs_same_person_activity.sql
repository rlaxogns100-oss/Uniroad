-- is_same_person별: 총 질문 횟수, 첫 질문~마지막 질문 간 시간 차이(시간 단위, 소수 버림) (user_id 있음 + 최신 행 conversation_history 비어있지 않은 그룹만)
-- 각 is_same_person 값당 한 행 반환
-- 반환 타입 변경 시 기존 함수 제거 후 재생성 필요

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
  WITH has_user_id AS (
    SELECT DISTINCT al.is_same_person
    FROM admin_logs al
    WHERE al.is_same_person IS NOT NULL AND al.user_id IS NOT NULL
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
    l.is_same_person,
    l.latest_ts,
    t.cnt AS total_questions,
    floor(EXTRACT(EPOCH FROM (l.latest_ts - f.first_ts)) / 3600)::bigint AS distinct_hour_appearances
  FROM latest_per_person l
  JOIN first_ts_per_person f ON f.is_same_person = l.is_same_person
  JOIN total_per_person t ON t.is_same_person = l.is_same_person
  ORDER BY l.latest_ts DESC;
$$;

COMMENT ON FUNCTION public.get_admin_logs_same_person_activity() IS 'is_same_person별: 총 질문 횟수, 첫 질문~마지막 질문 간 시간(시간 단위, 소수 버림)';

GRANT EXECUTE ON FUNCTION public.get_admin_logs_same_person_activity() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_same_person_activity() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_admin_logs_same_person_activity() FROM authenticated;
