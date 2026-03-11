"""
환경 변수 설정
"""
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# backend/config/config.py 기준으로 backend/.env 경로 고정 (RAG Lab 등 루트에서 실행해도 동일하게 로드)
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str = ""  # 관리자 작업용 (선택사항)
    SUPABASE_JWT_SECRET: str = "your-jwt-secret"  # JWT 토큰 검증용
    
    # Gemini (채팅/분류/임베딩용)
    GEMINI_API_KEY: str
    
    # Google Analytics 4
    GA4_PROPERTY_ID: str = "521910579"
    GOOGLE_APPLICATION_CREDENTIALS: str = ""  # Google 서비스 계정 JSON 파일 경로 (선택사항)
    
    # Server
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"
    
    # Documents
    SCORE_CONVERSION_GUIDE_URL: str = ""  # 점수 변환 가이드 PDF URL (선택사항)

    # Polar.sh 결제
    POLAR_WEBHOOK_SECRET: str = ""  # Polar 대시보드 웹훅 엔드포인트에서 발급한 시크릿
    POLAR_ACCESS_TOKEN: str = ""  # Polar API 토큰 (구독 상태 조회 등)
    GUMROAD_WEBHOOK_TOKEN: str = ""  # Gumroad 웹훅 URL 토큰
    PAYAPP_USERID: str = ""
    PAYAPP_LINKKEY: str = ""
    PAYAPP_LINKVAL: str = ""
    PAYAPP_FEEDBACK_TOKEN: str = ""
    
    class Config:
        env_file = str(_ENV_FILE) if _ENV_FILE.exists() else ".env"
        case_sensitive = True
        extra = "ignore"  # .env의 VITE_* 등 미정의 변수 무시


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# 전역 설정 객체
settings = get_settings()

