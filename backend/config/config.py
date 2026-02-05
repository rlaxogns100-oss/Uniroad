"""
환경 변수 설정
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


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
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # .env의 VITE_* 등 미정의 변수 무시


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# 전역 설정 객체
settings = get_settings()

