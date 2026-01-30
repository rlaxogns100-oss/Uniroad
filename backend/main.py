"""
FastAPI 메인 애플리케이션
유니로드 - 백엔드 서버
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routers import chat, upload, documents, auth, sessions, announcements, admin_evaluate, admin_logs
# agent_admin은 router_agent 테스트 중 비활성화

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
        "http://172.30.1.20:5173",  # 로컬 네트워크 접근
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
# app.include_router(agent_admin.router, prefix="/api/agent", tags=["에이전트관리"])  # router_agent 테스트 중 비활성화
app.include_router(announcements.router, prefix="/api/announcements", tags=["공지사항"])
app.include_router(admin_evaluate.router, prefix="/api/admin", tags=["관리자평가"])
app.include_router(admin_logs.router, prefix="/api/admin", tags=["관리자로그"])

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 모델 및 DB 연결 미리 초기화 (실패해도 서버는 계속 실행)"""
    import time
    start_time = time.time()
    
    print("🚀 서버 Warm-up 시작...")
    
    # 1. Supabase 연결 Warm-up
    print("   [1/4] Supabase 연결 중...")
    try:
        from services.supabase_client import SupabaseService
        client = SupabaseService.get_client()
        client.table("chat_sessions").select("id").limit(1).execute()
        print("   ✅ Supabase 연결 Warm-up 완료")
    except Exception as e:
        print(f"   ⚠️ Supabase Warm-up 실패 (무시하고 계속): {e}")
    
    # 2. RAG Functions 초기화
    print("   [2/4] RAGFunctions 초기화 중...")
    try:
        from services.multi_agent.functions import RAGFunctions
        RAGFunctions.get_instance()
        print("   ✅ RAGFunctions 초기화 완료")
    except Exception as e:
        print(f"   ⚠️ RAGFunctions 초기화 실패 (무시하고 계속): {e}")
    
    # 3. Router Agent 초기화
    print("   [3/4] RouterAgent 초기화 중...")
    try:
        from services.multi_agent.router_agent import get_router
        get_router()
        print("   ✅ RouterAgent 초기화 완료")
    except Exception as e:
        print(f"   ⚠️ RouterAgent 초기화 실패 (무시하고 계속): {e}")
    
    # 4. Main Agent 초기화
    print("   [4/4] MainAgent 초기화 중...")
    try:
        from services.multi_agent.main_agent import get_main_agent
        get_main_agent()
        print("   ✅ MainAgent 초기화 완료")
    except Exception as e:
        print(f"   ⚠️ MainAgent 초기화 실패 (무시하고 계속): {e}")
    
    elapsed = time.time() - start_time
    print(f"🎉 서버 Warm-up 완료! (총 {elapsed:.2f}초) - 서버는 정상 기동됩니다.")


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

