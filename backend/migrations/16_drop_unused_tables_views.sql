-- 불필요한 뷰·테이블 제거 (events + session_chat_messages로 대체된 항목)
-- 15(events 디바이스 컬럼) 적용 후, 앱 배포 후 실행

-- 1) 뷰 제거 (테이블보다 먼저)
DROP VIEW IF EXISTS utm_chat_analysis;
DROP VIEW IF EXISTS utm_user_journey;

-- 2) 테이블 제거
DROP TABLE IF EXISTS user_actions;
DROP TABLE IF EXISTS user_journeys;
DROP TABLE IF EXISTS page_views;

SELECT 'Dropped utm_chat_analysis, utm_user_journey, user_actions, user_journeys, page_views' AS status;
