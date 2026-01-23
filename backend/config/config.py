"""
환경 변수 설정
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_JWT_SECRET: str = "your-jwt-secret"  # JWT 토큰 검증용
    
    # Gemini (채팅/분류/임베딩용)
    GEMINI_API_KEY: str
    
    # Server
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"
    
    # Documents
    SCORE_CONVERSION_GUIDE_URL: str = ""  # 점수 변환 가이드 PDF URL (선택사항)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# 전역 설정 객체
settings = get_settings()

