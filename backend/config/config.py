"""
환경 변수 설정
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    # OpenAI (임베딩용)
    OPENAI_API_KEY: str
    
    # Gemini (채팅/분류용)
    GEMINI_API_KEY: str
    
    # LlamaParse
    LLAMA_API_KEY: str
    
    # Server
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"
    
    # PDF Parser
    PDF_PARSER: str = "gemini"  # 'gemini' or 'llamaparse'
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# 전역 설정 객체
settings = get_settings()

