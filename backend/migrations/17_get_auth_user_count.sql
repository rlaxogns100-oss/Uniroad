-- 누적 가입자 수: auth.users 행 수를 반환하는 함수
-- 관리자 API에서만 호출 (service_role 키 사용)

CREATE OR REPLACE FUNCTION public.get_auth_user_count()
RETURNS integer
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT count(*)::integer FROM auth.users;
$$;

COMMENT ON FUNCTION public.get_auth_user_count() IS 'Supabase Auth 사용자 수 (누적 가입자). service_role로만 호출 권장.';

-- service_role만 실행 가능 (anon/authenticated는 호출 불가)
GRANT EXECUTE ON FUNCTION public.get_auth_user_count() TO service_role;
REVOKE EXECUTE ON FUNCTION public.get_auth_user_count() FROM anon;
REVOKE EXECUTE ON FUNCTION public.get_auth_user_count() FROM authenticated;
