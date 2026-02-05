-- admin_logs에 is_same_person 컬럼 추가 (이미 있으면 스킵)
-- null: 한 번만 질문하고 나간 사람
-- 값 있음(UUID 등): 동일 사용자 재방문 질문 시 해당 사용자 식별자

ALTER TABLE public.admin_logs
ADD COLUMN IF NOT EXISTS is_same_person TEXT DEFAULT NULL;

COMMENT ON COLUMN public.admin_logs.is_same_person IS 'null = 한 번만 질문하고 나간 사람, non-null = 동일 사용자 식별(예: user_id)';
