-- Polar 결제: public.users 테이블에 is_premium 컬럼 사용
-- 웹훅에서 client_reference_id(Supabase user id)로 해당 유저의 is_premium을 true로 업데이트함.

-- 1) public.users 테이블이 없다면 생성 (id = auth.users.id)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    is_premium BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2) 이미 테이블이 있는 경우만 컬럼 추가
ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS is_premium BOOLEAN NOT NULL DEFAULT false;

-- 3) updated_at 자동 갱신 (선택)
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_updated_at ON public.users;
CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON public.users
    FOR EACH ROW
    EXECUTE PROCEDURE public.set_updated_at();

-- 4) 기존 auth.users에 대응하는 행이 없으면, 웹훅 시 업데이트가 0건일 수 있음.
--    회원가입 시 public.users에 행을 넣으려면 아래 트리거 사용 (선택).
-- CREATE OR REPLACE FUNCTION public.sync_user_to_public_users()
-- RETURNS TRIGGER AS $$
-- BEGIN
--     INSERT INTO public.users (id, is_premium)
--     VALUES (NEW.id, false)
--     ON CONFLICT (id) DO NOTHING;
--     RETURN NEW;
-- END;
-- $$ LANGUAGE plpgsql SECURITY DEFINER;
-- DROP TRIGGER IF EXISTS on_auth_user_created_sync_users ON auth.users;
-- CREATE TRIGGER on_auth_user_created_sync_users
--     AFTER INSERT ON auth.users
--     FOR EACH ROW EXECUTE PROCEDURE public.sync_user_to_public_users();
