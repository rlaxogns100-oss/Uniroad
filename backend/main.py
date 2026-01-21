"""
FastAPI 메인 애플리케이션
유니로드 - 백엔드 서버
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from config import settings
from routers import chat, upload, documents, agent_admin, auth, sessions

# FastAPI 앱 생성
app = FastAPI(
    title="유니로드 API",
    description="대학 입시 상담 AI 백엔드",
    version="2.0.0",
)

# CORS 설정 (프론트엔드 연결)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",  # Next.js 호환
        "http://3.107.178.26",  # 프로덕션 서버
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 라우터 등록
app.include_router(auth.router, prefix="/api/auth", tags=["인증"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["세션관리"])
app.include_router(chat.router, prefix="/api/chat", tags=["채팅"])
app.include_router(upload.router, prefix="/api/upload", tags=["업로드"])
app.include_router(documents.router, prefix="/api/documents", tags=["문서관리"])
app.include_router(agent_admin.router, prefix="/api/agent", tags=["에이전트관리"])


@app.get("/")
async def root():
    """루트 엔드포인트 - 서버 상태 확인"""
    return {
        "status": "online",
        "service": "유니로드",
        "version": "2.0.0",
        "backend": "FastAPI",
    }


@app.get("/api/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.BACKEND_PORT,
        reload=True,
    )

