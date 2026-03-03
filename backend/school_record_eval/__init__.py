"""
생기부(학교생활기록부) 평가 기능 모듈

- 별도 폴더로 분리되어 기존 라우터/서비스와 충돌 없음
- main.py에서 include_router로 연동
"""
from .router import router

__all__ = ["router"]
