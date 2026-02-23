from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agents.profile_agent import ProfileAgentService
from app.schemas import ChatRequest, ChatResponse, ProfileResponse
from app.services.profile_repository import ProfileRepository


BASE_DIR = Path(__file__).resolve().parents[1]  # profile-agent/backend
PROJECT_DIR = BASE_DIR.parent  # profile-agent
FRONTEND_DIR = PROJECT_DIR / "frontend"
DB_PATH = BASE_DIR / "profile_agent.db"

repository = ProfileRepository(DB_PATH)
profile_agent = ProfileAgentService(repository)

app = FastAPI(
    title="UniRoad Profile Agent (Sandbox)",
    description="학생 채팅에서 성적 정보를 추출/보완하여 adiga2 입력 스키마로 저장",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def parse_chat(request: ChatRequest) -> ChatResponse:
    try:
        result = profile_agent.process(request.user_id.strip(), request.message.strip())
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return ChatResponse(
        user_id=result.user_id,
        extracted_scores=result.extracted_scores,
        completed_scores=result.completed_scores,
        adiga_input=result.adiga_input,
        estimated_subjects=result.estimated_subjects,
        db_record=result.db_record,
        agent_trace=result.agent_trace,
    )


@app.get("/api/profile/{user_id}", response_model=ProfileResponse)
def get_profile(user_id: str) -> ProfileResponse:
    profile = repository.get_profile(user_id.strip())
    if not profile:
        raise HTTPException(status_code=404, detail="user_profile not found")
    return ProfileResponse(**profile)


if FRONTEND_DIR.exists():
    # API 라우트 등록 후 마지막에 mount해야 /api/*가 우선된다.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

