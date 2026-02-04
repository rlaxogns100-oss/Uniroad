-- chat_sessions 테이블에 UTM 정보 추가
-- 채팅 세션과 유입 경로를 직접 연결

-- 1. chat_sessions 테이블에 컬럼 추가
ALTER TABLE chat_sessions 
ADD COLUMN IF NOT EXISTS browser_session_id TEXT,
ADD COLUMN IF NOT EXISTS utm_source TEXT,
ADD COLUMN IF NOT EXISTS utm_medium TEXT,
ADD COLUMN IF NOT EXISTS utm_campaign TEXT,
ADD COLUMN IF NOT EXISTS utm_content TEXT,
ADD COLUMN IF NOT EXISTS utm_term TEXT,
ADD COLUMN IF NOT EXISTS referrer TEXT;

-- 2. 인덱스 추가
CREATE INDEX IF NOT EXISTS idx_chat_sessions_browser_session ON chat_sessions(browser_session_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_utm ON chat_sessions(utm_source, utm_medium);

-- 3. 분석용 뷰 생성: UTM별 질문 내용
CREATE OR REPLACE VIEW utm_chat_analysis AS
SELECT 
    cs.utm_source,
    cs.utm_medium,
    cs.utm_campaign,
    cs.user_id,
    cm.content as question,
    cm.created_at,
    cs.title as session_title
FROM chat_sessions cs
JOIN chat_messages cm ON cm.session_id = cs.id
WHERE cm.role = 'user'
AND cs.utm_source IS NOT NULL;

-- 4. UTM별 인기 질문 분석 함수
CREATE OR REPLACE FUNCTION get_popular_questions_by_utm(
    p_utm_source TEXT DEFAULT NULL,
    p_utm_medium TEXT DEFAULT NULL,
    p_days INTEGER DEFAULT 30
)
RETURNS TABLE (
    utm_source TEXT,
    utm_medium TEXT,
    question_pattern TEXT,
    question_count BIGINT,
    sample_questions TEXT[]
) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH question_analysis AS (
        SELECT 
            cs.utm_source,
            cs.utm_medium,
            cm.content as question,
            -- 질문 패턴 추출 (간단한 키워드 기반)
            CASE 
                WHEN cm.content ILIKE '%합격%' OR cm.content ILIKE '%가능%' THEN '합격 가능성'
                WHEN cm.content ILIKE '%점수%' OR cm.content ILIKE '%성적%' THEN '점수/성적 관련'
                WHEN cm.content ILIKE '%전형%' OR cm.content ILIKE '%수시%' OR cm.content ILIKE '%정시%' THEN '전형 관련'
                WHEN cm.content ILIKE '%학과%' OR cm.content ILIKE '%전공%' THEN '학과/전공 관련'
                WHEN cm.content ILIKE '%대학%' THEN '대학 정보'
                ELSE '기타 질문'
            END as question_pattern
        FROM chat_sessions cs
        JOIN chat_messages cm ON cm.session_id = cs.id
        WHERE cm.role = 'user'
        AND cs.created_at >= CURRENT_DATE - INTERVAL '1 day' * p_days
        AND (p_utm_source IS NULL OR cs.utm_source = p_utm_source)
        AND (p_utm_medium IS NULL OR cs.utm_medium = p_utm_medium)
    )
    SELECT 
        qa.utm_source,
        qa.utm_medium,
        qa.question_pattern,
        COUNT(*) as question_count,
        ARRAY(SELECT DISTINCT question FROM question_analysis qa2 
              WHERE qa2.utm_source = qa.utm_source 
              AND qa2.utm_medium = qa.utm_medium 
              AND qa2.question_pattern = qa.question_pattern 
              ORDER BY question 
              LIMIT 5) as sample_questions
    FROM question_analysis qa
    GROUP BY qa.utm_source, qa.utm_medium, qa.question_pattern
    ORDER BY question_count DESC;
END;
$$;

-- 5. UTM별 사용자 여정 분석
CREATE OR REPLACE VIEW utm_user_journey AS
SELECT 
    uj.first_utm_source,
    uj.first_utm_medium,
    uj.first_utm_campaign,
    uj.session_id as browser_session_id,
    cs.id as chat_session_id,
    uj.visited_landing,
    uj.visited_chat,
    uj.logged_in,
    uj.asked_question,
    COUNT(cm.id) as total_messages,
    MIN(cm.created_at) as first_message_at,
    MAX(cm.created_at) as last_message_at
FROM user_journeys uj
LEFT JOIN chat_sessions cs ON cs.browser_session_id = uj.session_id
LEFT JOIN chat_messages cm ON cm.session_id = cs.id AND cm.role = 'user'
GROUP BY 
    uj.first_utm_source, uj.first_utm_medium, uj.first_utm_campaign,
    uj.session_id, cs.id, uj.visited_landing, uj.visited_chat,
    uj.logged_in, uj.asked_question;

-- 완료 메시지
SELECT 'UTM-Chat 연결 완료!' AS status;