"""
채팅 API 라우터 (Router Agent 기반)
Router Agent가 사용자 질문을 분석하고 함수 호출을 결정
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
import json
import time

from services.multi_agent.router_agent import RouterAgent

router = APIRouter()

# 세션별 대화 히스토리 (메모리)
conversation_sessions: Dict[str, List[Dict[str, Any]]] = {}

# Router Agent 인스턴스
router_agent = RouterAgent()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: Dict[str, Any]  # Router Agent JSON 결과
    processing_time: float
    session_id: str


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Router Agent 기반 채팅 처리
    사용자 질문을 분석하고 함수 호출 JSON을 반환
    """
    try:
        session_id = request.session_id
        message = request.message
        
        start_time = time.time()
        print(f"\n🔵 [ROUTER] 질문: {message}")
        
        # Router Agent 실행
        result = await router_agent.route(message)
        
        processing_time = time.time() - start_time
        print(f"🟢 [ROUTER] 완료 ({processing_time:.2f}초)")
        print(f"   결과: {json.dumps(result, ensure_ascii=False, indent=2)}")
        
        return ChatResponse(
            response=result,
            processing_time=processing_time,
            session_id=session_id
        )

    except Exception as e:
        print(f"❌ Router 오류: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"채팅 처리 중 오류: {str(e)}")


@router.post("/reset")
async def reset_session(session_id: str = "default"):
    """대화 히스토리 초기화"""
    if session_id in conversation_sessions:
        del conversation_sessions[session_id]
    return {"status": "ok", "message": f"세션 {session_id} 초기화 완료"}
