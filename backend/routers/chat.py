"""
채팅 API 라우터 (멀티에이전트 기반)
전체 파이프라인: Orchestration Agent → Sub Agents → Final Agent → 최종 답변
"""
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Request, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json
import base64

from services.supabase_client import supabase_service
from services.gemini_service import gemini_service
from services.multi_agent import (
    run_orchestration_agent,
    run_orchestration_agent_stream,
    execute_sub_agents,
    generate_final_answer,
    AVAILABLE_AGENTS
)
from utils.timing_logger import TimingLogger
from utils.admin_filter import should_skip_logging
from middleware.auth import optional_auth
from middleware.rate_limit import check_and_increment_usage, get_client_ip
import uuid
from datetime import datetime

router = APIRouter()


def _record_question_sent(session_id: str, user_id: Optional[str]) -> None:
    """실제 채팅 전송 시 events에 question_sent 기록 (깔때기 메시지 전송 수 집계용)"""
    if should_skip_logging(user_id=user_id):
        return
    try:
        client = supabase_service.get_client()
        utm_row = (
            client.table("events")
            .select("utm_source, utm_medium, utm_campaign, utm_content, utm_term")
            .eq("user_session", session_id)
            .order("event_time", desc=False)
            .limit(1)
            .execute()
        )
        utm = utm_row.data[0] if utm_row.data else {}
        event_data = {
            "event_time": datetime.now().isoformat(),
            "event_type": "question_sent",
            "utm_source": utm.get("utm_source"),
            "utm_medium": utm.get("utm_medium"),
            "utm_campaign": utm.get("utm_campaign"),
            "utm_content": utm.get("utm_content"),
            "utm_term": utm.get("utm_term"),
            "user_id": user_id,
            "user_session": session_id,
        }
        client.table("events").insert(event_data).execute()
    except Exception as e:
        print(f"⚠️ question_sent 기록 실패 (무시): {e}")


def _save_messages_to_session_chat(
    user_session: str,
    user_id: Optional[str],
    user_content: str,
    assistant_content: str,
    sources: Optional[List[str]] = None,
    source_urls: Optional[List[str]] = None,
) -> None:
    """session_chat_messages 테이블에 사용자 메시지와 AI 응답 저장"""
    client = supabase_service.client
    user_msg_id = str(uuid.uuid4())
    ai_msg_id = str(uuid.uuid4())
    client.table("session_chat_messages").insert({
        "user_session": user_session,
        "message_id": user_msg_id,
        "role": "user",
        "content": user_content,
        "user_id": user_id,
    }).execute()
    client.table("session_chat_messages").insert({
        "user_session": user_session,
        "message_id": ai_msg_id,
        "role": "assistant",
        "content": assistant_content,
        "sources": sources,
        "source_urls": source_urls,
        "user_id": user_id,
    }).execute()

# 실시간 로그를 위한 큐
log_queues: Dict[str, asyncio.Queue] = {}

# 세션별 대화 히스토리 (메모리)
conversation_sessions: Dict[str, List[Dict[str, Any]]] = {}


async def load_history_from_db(session_id: str) -> List[Dict[str, Any]]:
    """
    DB에서 세션 히스토리 로드 (session_chat_messages)
    """
    try:
        messages_response = supabase_service.client.table("session_chat_messages")\
            .select("role, content")\
            .eq("user_session", session_id)\
            .order("created_at")\
            .limit(20)\
            .execute()
        if messages_response.data:
            return [
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                for msg in messages_response.data
            ]
    except Exception as e:
        print(f"⚠️ DB에서 히스토리 로드 실패 (무시): {e}")
    return []


def get_or_load_history(session_id: str) -> List[Dict[str, Any]]:
    """
    메모리에서 히스토리 가져오기. 없으면 빈 리스트 반환 (async 버전 사용 권장)
    """
    if session_id not in conversation_sessions:
        conversation_sessions[session_id] = []
    return conversation_sessions[session_id][-20:]


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    response: str
    raw_answer: Optional[str] = None  # ✅ Final Agent 원본 출력
    sources: List[str] = []
    source_urls: List[str] = []
    used_chunks: Optional[List[Dict[str, Any]]] = None  # 답변에 사용된 청크
    # 멀티에이전트 디버그 데이터
    router_output: Optional[Dict[str, Any]] = None  # Router 출력 (최상위)
    function_results: Optional[Dict[str, Any]] = None  # Function 결과 (최상위)
    orchestration_result: Optional[Dict[str, Any]] = None
    sub_agent_results: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    logs: List[str] = []


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    멀티에이전트 기반 채팅 메시지 처리

    파이프라인:
    1. Orchestration Agent → Execution Plan + Answer Structure
    2. Sub Agents 실행 → 결과 수집
    3. Final Agent → 최종 답변 생성
    """
    logs = []
    
    try:
        # ========================================
        # Rate Limiting 체크
        # ========================================
        # 1. IP 추출
        client_ip = get_client_ip(http_request)
        
        # 2. 선택적 인증
        user = await optional_auth(authorization)
        user_id = user["user_id"] if user else None
        
        # 3. Rate Limit 체크 및 증가
        is_allowed, current_count, limit = await check_and_increment_usage(user_id, client_ip)
        if not is_allowed:
            if user_id is None:
                # 비로그인 사용자
                raise HTTPException(
                    status_code=429,
                    detail=f"일일 사용량을 초과했습니다 ({current_count}/{limit}회). 로그인을 통해 더 많은 입시 정보와 개인별로 갈 수 있는 대학을 확인해보세요!!"
                )
            else:
                # 로그인 사용자
                raise HTTPException(
                    status_code=429,
                    detail=f"일일 사용량을 초과했습니다 ({current_count}/{limit}회). 내일 00:00에 초기화됩니다."
                )
        
        # 로그에 사용량 정보 추가
        logs.append(f"📊 API 사용량: {current_count}/{limit}회")
        print(f"📊 API 사용량: {current_count}/{limit}회 (user_id={user_id}, ip={client_ip})")
        
        # ========================================
        # 기존 채팅 로직
        # ========================================
        session_id = request.session_id
        message = request.message
        
        # 중복 호출 방지 체크 및 시간 측정 시작
        import time
        pipeline_start = time.time()
        request_id = f"{session_id}:{message}:{int(time.time())}"
        print(f"\n🔵 [REQUEST_START] {request_id}")

        # 로그 수집
        def log_and_emit(msg: str):
            print(msg)
            logs.append(msg)

        log_and_emit(f"{'#'*80}")
        log_and_emit(f"# 🚀 멀티에이전트 파이프라인 시작")
        log_and_emit(f"# 세션: {session_id}")
        log_and_emit(f"# 질문: {message}")
        log_and_emit(f"# Request ID: {request_id}")
        log_and_emit(f"{'#'*80}")

        # 세션별 히스토리 로드 (메모리에 없으면 DB에서 로드)
        if session_id not in conversation_sessions or len(conversation_sessions[session_id]) == 0:
            db_history = await load_history_from_db(session_id)
            if db_history:
                conversation_sessions[session_id] = db_history
            else:
                conversation_sessions[session_id] = []
        history = conversation_sessions[session_id][-20:]
        # user_id는 optional_auth에서 이미 설정됨 (프로필 점수 활용용)

        # ========================================
        # 1단계: Orchestration Agent
        # ========================================
        log_and_emit("")
        log_and_emit("="*80)
        log_and_emit("🎯 Orchestration Agent 실행")
        log_and_emit("="*80)
        log_and_emit(f"질문: {message}")
        
        # 실시간 로그 콜백 설정
        from services.multi_agent import orchestration_agent, sub_agents, final_agent
        
        orchestration_agent.set_log_callback(log_and_emit)
        sub_agents.set_log_callback(log_and_emit)
        final_agent.set_log_callback(log_and_emit)
        
        orch_start = time.time()
        orchestration_result = await run_orchestration_agent(message, history, user_id=user_id)
        orch_time = time.time() - orch_start

        if "error" in orchestration_result:
            error_msg = f"❌ Orchestration 오류: {orchestration_result.get('error')}"
            log_and_emit(error_msg)
            return ChatResponse(
                response="죄송합니다. 질문 분석 중 오류가 발생했습니다. 다시 시도해주세요.",
                sources=[],
                source_urls=[],
                router_output=orchestration_result.get("router_output"),
                function_results=orchestration_result.get("function_results"),
                orchestration_result=orchestration_result,
                sub_agent_results=None,
                metadata=None
            )

        execution_plan = orchestration_result.get("execution_plan", [])
        answer_structure = orchestration_result.get("answer_structure", [])
        direct_response = orchestration_result.get("direct_response", None)
        extracted_scores = orchestration_result.get("extracted_scores", {})
        
        log_and_emit("")
        log_and_emit(f"📋 Orchestration 결과:")
        log_and_emit(f"   사용자 의도: {orchestration_result.get('user_intent', 'N/A')}")
        log_and_emit(f"   실행 계획: {len(execution_plan)}개 step")
        log_and_emit(f"   답변 구조: {len(answer_structure)}개 섹션")
        
        # extracted_scores 로그
        if extracted_scores:
            log_and_emit(f"   📊 추출된 성적: {len(extracted_scores)}개 과목")
        else:
            log_and_emit(f"   ℹ️  성적 추출 없음")
        
        # 즉시 응답 체크
        if direct_response:
            log_and_emit(f"   ⚡ 즉시 응답 모드")
        
        log_and_emit(f"   ⏱️ 처리 시간: {orch_time:.2f}초")
        log_and_emit("="*80)

        # ========================================
        # 즉시 응답 처리
        # ========================================
        if direct_response:
            log_and_emit("")
            log_and_emit("="*80)
            log_and_emit("⚡ 즉시 응답 - Sub Agents 및 Final Agent 생략")
            log_and_emit("="*80)
            log_and_emit(f"   응답 길이: {len(direct_response)}자")
            
            # 히스토리 저장
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": direct_response})
            conversation_sessions[session_id] = history[-20:]  # 최근 20개만 유지

            # 채팅 로그 저장
            await supabase_service.insert_chat_log(
                message,
                direct_response,
                is_fact_mode=False
            )

            # 전체 파이프라인 시간 계산
            pipeline_time = time.time() - pipeline_start
            
            log_and_emit("")
            log_and_emit(f"{'#'*80}")
            log_and_emit(f"# ✅ 즉시 응답 완료")
            log_and_emit(f"# 응답 길이: {len(direct_response)}자")
            log_and_emit(f"# ⏱️ 처리 시간: {pipeline_time:.2f}초")
            log_and_emit(f"{'#'*80}")
            
            print(f"🟢 [REQUEST_END] {request_id}\n")

            # 메시지를 session_chat_messages에 저장 + question_sent 이벤트 기록
            try:
                if not should_skip_logging(user_id=user_id):
                    _record_question_sent(session_id, user_id)
                    _save_messages_to_session_chat(
                        user_session=session_id,
                        user_id=user_id,
                        user_content=message,
                        assistant_content=direct_response,
                    )
                    print(f"💾 메시지 저장 완료: {session_id}")
            except Exception as save_error:
                print(f"⚠️ 메시지 저장 실패: {save_error}")
                import traceback
                traceback.print_exc()

            return ChatResponse(
                response=direct_response,
                raw_answer=direct_response,
                sources=[],
                source_urls=[],
                used_chunks=[],
                router_output=orchestration_result.get("router_output"),
                function_results=orchestration_result.get("function_results"),
                orchestration_result=orchestration_result,
                sub_agent_results=None,
                metadata={
                    "immediate_response": True, 
                    "pipeline_time": pipeline_time,
                    "timing": orchestration_result.get("timing", {})
                }
            )

        # ========================================
        # 2단계: Sub Agents 실행
        # ========================================
        log_and_emit("")
        log_and_emit("="*80)
        log_and_emit("🤖 Sub Agents 실행")
        log_and_emit("="*80)
        
        for step in execution_plan:
            log_and_emit(f"   Step {step['step']}: {step['agent']}")
            log_and_emit(f"   Query: {step['query']}")
        
        sub_start = time.time()
        sub_agent_results = await execute_sub_agents(
            execution_plan,
            extracted_scores=extracted_scores,
            user_message=message
        )
        sub_time = time.time() - sub_start
        
        log_and_emit("")
        for key, result in sub_agent_results.items():
            status = result.get('status', 'unknown')
            agent = result.get('agent', 'Unknown')
            sources_count = len(result.get('sources', []))
            exec_time = result.get('execution_time', 0)
            status_icon = "✅" if status == "success" else "❌"
            log_and_emit(f"{status_icon} {key} ({agent}): {status} (출처 {sources_count}개, ⏱️ {exec_time:.2f}초)")
        log_and_emit(f"   총 Sub Agents 처리 시간: {sub_time:.2f}초")
        log_and_emit("="*80)

        # ========================================
        # 3단계: Final Agent - 최종 답변 생성
        # ========================================
        log_and_emit("")
        log_and_emit("="*80)
        log_and_emit("📝 Final Agent 실행")
        log_and_emit("="*80)
        log_and_emit(f"   섹션 수: {len(answer_structure)}")
        
        final_start = time.time()
        final_result = await generate_final_answer(
            user_question=message,
            answer_structure=answer_structure,
            sub_agent_results=sub_agent_results,
            history=history
        )
        final_time = time.time() - final_start

        final_answer = final_result.get("final_answer", "답변 생성 실패")
        raw_answer = final_result.get("raw_answer", "")  # ✅ 원본 답변
        sources = final_result.get("sources", [])
        source_urls = final_result.get("source_urls", [])
        
        log_and_emit(f"   최종 답변 길이: {len(final_answer)}자")
        log_and_emit(f"   원본 답변 길이: {len(raw_answer)}자")
        log_and_emit(f"   ⏱️ 처리 시간: {final_time:.2f}초")
        log_and_emit("="*80)

        # 히스토리 저장
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": final_answer})
        conversation_sessions[session_id] = history[-20:]  # 최근 20개만 유지

        # 채팅 로그 저장
        await supabase_service.insert_chat_log(
            message,
            final_answer,
            is_fact_mode=len(sources) > 0
        )

        # 전체 파이프라인 시간 계산
        pipeline_time = time.time() - pipeline_start
        
        log_and_emit("")
        log_and_emit(f"{'#'*80}")
        log_and_emit(f"# ✅ 파이프라인 완료")
        log_and_emit(f"# 최종 답변 길이: {len(final_answer)}자")
        log_and_emit(f"# 원본 답변 길이: {len(raw_answer)}자")
        log_and_emit(f"# 출처 수: {len(sources)}개")
        log_and_emit(f"#")
        log_and_emit(f"# ⏱️ 처리 시간 분석:")
        log_and_emit(f"#   • Orchestration: {orch_time:.2f}초 ({orch_time/pipeline_time*100:.1f}%)")
        log_and_emit(f"#   • Sub Agents: {sub_time:.2f}초 ({sub_time/pipeline_time*100:.1f}%)")
        log_and_emit(f"#   • Final Agent: {final_time:.2f}초 ({final_time/pipeline_time*100:.1f}%)")
        log_and_emit(f"#   • 전체: {pipeline_time:.2f}초")
        log_and_emit(f"{'#'*80}")
        
        print(f"🟢 [REQUEST_END] {request_id}\n")

        # 메시지를 session_chat_messages에 저장 + question_sent 이벤트 기록
        try:
            if not should_skip_logging(user_id=user_id):
                _record_question_sent(session_id, user_id)
                _save_messages_to_session_chat(
                    user_session=session_id,
                    user_id=user_id,
                    user_content=message,
                    assistant_content=final_answer,
                    sources=sources,
                    source_urls=source_urls,
                )
                print(f"💾 메시지 저장 완료: {session_id}")
        except Exception as save_error:
            print(f"⚠️ 메시지 저장 실패 (계속 진행): {save_error}")
            import traceback
            traceback.print_exc()

        return ChatResponse(
            response=final_answer,
            raw_answer=raw_answer,  # ✅ 원본 답변 추가
            sources=sources,
            source_urls=source_urls,
            used_chunks=final_result.get("used_chunks", []),  # 사용된 청크 추가
            router_output=orchestration_result.get("router_output"),
            function_results=orchestration_result.get("function_results"),
            orchestration_result=orchestration_result,
            sub_agent_results=sub_agent_results,
            metadata=final_result.get("metadata", {})
        )

    except Exception as e:
        print(f"\n{'='*80}")
        print(f"❌ 채팅 오류: {e}")
        print(f"{'='*80}\n")
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"채팅 처리 중 오류가 발생했습니다: {str(e)}")


# 지원하는 이미지 MIME 타입
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpeg",
    "image/png": "png", 
    "image/gif": "gif",
    "image/webp": "webp"
}
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024


@router.post("/v2/stream/with-image")
async def chat_stream_v2_with_image(
    message: str = Form(...),
    session_id: str = Form(default="default"),
    image: UploadFile = File(...),
    http_request: Request = None,
    authorization: Optional[str] = Header(None)
):
    """
    이미지와 함께 스트리밍 채팅 - 이미지 분석 후 멀티에이전트 파이프라인으로 전달
    
    흐름:
    1. Gemini로 이미지 분석 (설명/OCR)
    2. 분석 결과를 사용자 메시지에 포함
    3. 기존 멀티에이전트 파이프라인으로 답변 생성
    
    SSE (Server-Sent Events) 형식:
    - {"type": "status", "step": "image_analysis", "message": "이미지 분석 중..."}
    - {"type": "status", "step": "...", "message": "..."}
    - {"type": "chunk", "text": "응답 텍스트 조각"}
    - {"type": "done", "response": "전체 응답", "image_analysis": "이미지 분석 결과"}
    """
    import time
    
    # ========================================
    # Rate Limiting 체크
    # ========================================
    client_ip = get_client_ip(http_request)
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    
    is_allowed, current_count, limit = await check_and_increment_usage(user_id, client_ip)
    if not is_allowed:
        if user_id is None:
            # 비로그인 사용자
            raise HTTPException(
                status_code=429,
                detail=f"일일 사용량을 초과했습니다 ({current_count}/{limit}회). 로그인을 통해 더 많은 입시 정보와 개인별로 갈 수 있는 대학을 확인해보세요!!"
            )
        else:
            # 로그인 사용자
            raise HTTPException(
                status_code=429,
                detail=f"일일 사용량을 초과했습니다 ({current_count}/{limit}회). 내일 00:00에 초기화됩니다."
            )
    
    print(f"📊 API 사용량: {current_count}/{limit}회 (user_id={user_id}, ip={client_ip})")
    
    # ========================================
    # 이미지 검증
    # ========================================
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            400, 
            f"지원하지 않는 이미지 형식입니다. 지원 형식: {', '.join(ALLOWED_IMAGE_TYPES.keys())}"
        )
    
    # 이미지 데이터 읽기
    image_data = await image.read()
    
    if len(image_data) > MAX_IMAGE_SIZE_BYTES:
        raise HTTPException(400, f"이미지 크기는 {MAX_IMAGE_SIZE_MB}MB를 초과할 수 없습니다.")
    
    def generate():
        pipeline_start = time.time()
        print(f"\n🔵 [STREAM_V2_IMAGE_START] {session_id}:{message[:30]}")
        print(f"🖼️ 이미지: {image.filename}, {image.content_type}, {len(image_data)} bytes")
        
        # 세션별 히스토리 로드
        if session_id not in conversation_sessions:
            conversation_sessions[session_id] = []
        history = conversation_sessions[session_id][-20:]
        
        full_response = ""
        image_analysis = ""
        timing = {}
        function_results = {}
        router_output = {}
        sources = []
        source_urls = []
        used_chunks = []
        
        try:
            # 1단계: 이미지 분석 시작 상태 전송
            yield f"data: {json.dumps({'type': 'status', 'step': 'image_analysis', 'message': '이미지를 분석하는 중...'}, ensure_ascii=False)}\n\n"
            
            # 2단계: Gemini로 이미지 분석 (설명/OCR만 수행, 답변 생성 X)
            image_prompt = """이 이미지를 자세히 분석해주세요. 다음 내용을 포함해주세요:

1. 이미지에 보이는 내용을 상세히 설명
2. 텍스트가 있다면 모두 읽어서 정확히 기록 (OCR)
3. 표, 그래프, 숫자 등이 있다면 구조화된 형태로 정리
4. 문서 유형 (성적표, 모집요강, 안내문 등) 파악

분석 결과:"""
            
            # 동기적으로 이미지 분석 실행 (generator 내부이므로)
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                image_analysis = loop.run_until_complete(
                    gemini_service.generate_with_image(
                        prompt=image_prompt,
                        image_data=image_data,
                        mime_type=image.content_type
                    )
                )
                print(f"✅ 이미지 분석 완료: {len(image_analysis)}자")
            except Exception as e:
                print(f"❌ 이미지 분석 실패: {e}")
                image_analysis = "이미지를 분석할 수 없습니다."
            finally:
                loop.close()
            
            # 3단계: 이미지 분석 결과를 포함한 메시지 구성
            enhanced_message = f"""[사용자가 이미지를 첨부했습니다]

=== 이미지 분석 결과 ===
{image_analysis}
=== 이미지 분석 끝 ===

사용자 질문: {message}

위 이미지 분석 결과를 참고하여 사용자의 질문에 답변해주세요."""
            
            yield f"data: {json.dumps({'type': 'status', 'step': 'agent_start', 'message': '답변을 생성하는 중...'}, ensure_ascii=False)}\n\n"
            
            # 4단계: 기존 멀티에이전트 파이프라인 실행
            for event in run_orchestration_agent_stream(enhanced_message, history):
                event_type = event.get("type")
                
                if event_type == "status":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
                elif event_type == "chunk":
                    full_response += event.get("text", "")
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
                elif event_type == "done":
                    timing = event.get("timing", {})
                    function_results = event.get("function_results", {})
                    router_output = event.get("router_output", {})
                    full_response = event.get("response", full_response)
                    sources = event.get("sources", [])
                    source_urls = event.get("source_urls", [])
                    used_chunks = event.get("used_chunks", [])
                
                elif event_type == "error":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    return
            
            # 대화 이력에 추가 (이미지 포함 메시지로 표시)
            user_content = f"[이미지 첨부] {message}"
            history.append({"role": "user", "content": user_content})
            history.append({"role": "assistant", "content": full_response})
            conversation_sessions[session_id] = history[-20:]
            
            pipeline_time = time.time() - pipeline_start
            
            # 메시지 저장 (session_chat_messages) + question_sent 이벤트 기록
            try:
                if not should_skip_logging(user_id=user_id):
                    _record_question_sent(session_id, user_id)
                    _save_messages_to_session_chat(
                        user_session=session_id,
                        user_id=user_id,
                        user_content=user_content,
                        assistant_content=full_response,
                        sources=sources,
                        source_urls=source_urls,
                    )
                    print(f"💾 메시지 저장 완료: {session_id}")
            except Exception as e:
                print(f"❌ 메시지 저장 실패: {e}")
            
            # 완료 이벤트 전송 (멀티에이전트 파이프라인 결과 포함)
            done_event = {
                "type": "done",
                "response": full_response,
                "image_analysis": image_analysis,
                "timing": timing,
                "pipeline_time": round(pipeline_time * 1000),
                "router_output": router_output,
                "function_results": function_results,
                "sources": sources,
                "source_urls": source_urls,
                "used_chunks": used_chunks
            }
            yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
            
            print(f"🟢 [STREAM_V2_IMAGE_END] 총 {pipeline_time:.2f}초, {len(full_response)}자")
            
        except Exception as e:
            print(f"❌ 이미지 채팅 오류: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/v2/stream")
async def chat_stream_v2(
    request: ChatRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    스트리밍 채팅 v2 - Main Agent 응답을 실시간 스트리밍
    
    SSE (Server-Sent Events) 형식:
    - {"type": "status", "step": "router", "message": "..."}
    - {"type": "chunk", "text": "응답 텍스트 조각"}
    - {"type": "done", "timing": {...}, "response": "전체 응답"}
    """
    import time
    
    # ========================================
    # Rate Limiting 체크 (generator 외부에서 실행)
    # ========================================
    client_ip = get_client_ip(http_request)
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    
    is_allowed, current_count, limit = await check_and_increment_usage(user_id, client_ip)
    if not is_allowed:
        if user_id is None:
            # 비로그인 사용자
            raise HTTPException(
                status_code=429,
                detail=f"일일 사용량을 초과했습니다 ({current_count}/{limit}회). 로그인을 통해 더 많은 입시 정보와 개인별로 갈 수 있는 대학을 확인해보세요!!"
            )
        else:
            # 로그인 사용자
            raise HTTPException(
                status_code=429,
                detail=f"일일 사용량을 초과했습니다 ({current_count}/{limit}회). 내일 00:00에 초기화됩니다."
            )
    
    print(f"📊 API 사용량: {current_count}/{limit}회 (user_id={user_id}, ip={client_ip})")
    
    def generate():
        session_id = request.session_id
        message = request.message
        
        pipeline_start = time.time()
        print(f"\n🔵 [STREAM_V2_START] {session_id}:{message[:30]}")
        
        # 세션별 히스토리 로드 (동기 generator이므로 메모리에서만 확인)
        if session_id not in conversation_sessions:
            conversation_sessions[session_id] = []
        history = conversation_sessions[session_id][-20:]
        # user_id는 optional_auth에서 온 클로저 변수 사용 (프로필/저장용)

        full_response = ""
        timing = {}
        function_results = {}
        router_output = {}
        sources = []
        source_urls = []
        used_chunks = []
        
        try:
            # 스트리밍 파이프라인 실행 (user_id 전달)
            for event in run_orchestration_agent_stream(message, history, user_id=user_id):
                event_type = event.get("type")
                
                if event_type == "status":
                    # 상태 업데이트 전송
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
                elif event_type == "chunk":
                    # Main Agent 응답 청크 전송
                    full_response += event.get("text", "")
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                
                elif event_type == "done":
                    timing = event.get("timing", {})
                    function_results = event.get("function_results", {})
                    router_output = event.get("router_output", {})
                    full_response = event.get("response", full_response)
                    # 출처 정보 추출
                    sources = event.get("sources", [])
                    source_urls = event.get("source_urls", [])
                    used_chunks = event.get("used_chunks", [])
                
                elif event_type == "error":
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    return
            
            # 대화 이력에 추가
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": full_response})
            conversation_sessions[session_id] = history[-20:]  # 최근 20개만 유지
            
            pipeline_time = time.time() - pipeline_start
            
            # 메시지 저장 (session_chat_messages) + question_sent 이벤트 기록
            try:
                if not should_skip_logging(user_id=user_id):
                    _record_question_sent(session_id, user_id)
                    _save_messages_to_session_chat(
                        user_session=session_id,
                        user_id=user_id,
                        user_content=message,
                        assistant_content=full_response,
                        sources=sources,
                        source_urls=source_urls,
                    )
                    print(f"💾 메시지 저장 완료: {session_id}")
            except Exception as e:
                print(f"❌ 메시지 저장 실패: {e}")
            
            # 완료 이벤트 전송 (출처 정보 포함)
            done_event = {
                "type": "done",
                "response": full_response,
                "timing": timing,
                "pipeline_time": round(pipeline_time * 1000),
                "router_output": router_output,
                "function_results": function_results,
                "sources": sources,
                "source_urls": source_urls,
                "used_chunks": used_chunks
            }
            yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
            
            print(f"🟢 [STREAM_V2_END] 총 {pipeline_time:.2f}초, {len(full_response)}자")
            
        except Exception as e:
            print(f"❌ 스트리밍 오류: {e}")
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 버퍼링 비활성화
        }
    )


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    authorization: Optional[str] = Header(None)
):
    """
    멀티에이전트 기반 채팅 메시지 처리 (스트리밍)
    
    파이프라인:
    1. Orchestration Agent → Execution Plan + Answer Structure
    2. Sub Agents 실행 → 결과 수집
    3. Final Agent → 최종 답변 생성
    """
    # ========================================
    # Rate Limiting 체크 (generator 외부에서 실행)
    # ========================================
    client_ip = get_client_ip(http_request)
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    
    is_allowed, current_count, limit = await check_and_increment_usage(user_id, client_ip)
    if not is_allowed:
        if user_id is None:
            # 비로그인 사용자
            raise HTTPException(
                status_code=429,
                detail=f"일일 사용량을 초과했습니다 ({current_count}/{limit}회). 로그인을 통해 더 많은 입시 정보와 개인별로 갈 수 있는 대학을 확인해보세요!!"
            )
        else:
            # 로그인 사용자
            raise HTTPException(
                status_code=429,
                detail=f"일일 사용량을 초과했습니다 ({current_count}/{limit}회). 내일 00:00에 초기화됩니다."
            )
    
    print(f"📊 API 사용량: {current_count}/{limit}회 (user_id={user_id}, ip={client_ip})")
    
    async def generate():
        logs = []
        log_queue = asyncio.Queue()
        
        try:
            session_id = request.session_id
            message = request.message
            
            # 중복 호출 방지 체크 및 시간 측정 시작
            import time
            pipeline_start = time.time()
            request_id = f"{session_id}:{message[:30]}:{int(time.time())}"
            print(f"\n🔵 [STREAM_REQUEST_START] {request_id}")
            
            # 타이밍 로거 초기화
            timing_logger = TimingLogger(session_id, request_id)

            # 로그를 큐에 추가하는 콜백
            def log_callback(msg: str):
                print(msg)
                logs.append(msg)
                try:
                    log_queue.put_nowait(msg)
                except:
                    pass

            def send_log(msg: str):
                log_callback(msg)
                return f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"

            yield send_log(f"{'#'*80}")
            yield send_log(f"# 🚀 멀티에이전트 파이프라인 시작")
            yield send_log(f"# 세션: {session_id}")
            yield send_log(f"# 질문: {message}")
            yield send_log(f"{'#'*80}")

            # 세션별 히스토리 로드 (메모리에 없으면 DB에서 로드)
            if session_id not in conversation_sessions or len(conversation_sessions[session_id]) == 0:
                db_history = await load_history_from_db(session_id)
                if db_history:
                    conversation_sessions[session_id] = db_history
                else:
                    conversation_sessions[session_id] = []
            history = conversation_sessions[session_id][-20:]
            timing_logger.mark("history_loaded")
            # user_id는 stream_v2 상단 optional_auth에서 설정됨 (클로저로 사용)

            # ========================================
            # 1단계: Orchestration Agent
            # ========================================
            yield send_log("")
            yield send_log("="*80)
            yield send_log("🎯 Orchestration Agent 실행")
            yield send_log("="*80)
            yield send_log(f"질문: {message}")
            
            # Agent들이 로그를 찍을 때마다 큐에 추가
            from services.multi_agent import orchestration_agent, sub_agents, final_agent
            
            orchestration_agent.set_log_callback(log_callback)
            sub_agents.set_log_callback(log_callback)
            final_agent.set_log_callback(log_callback)
            
            # Orchestration Agent 실행 (백그라운드, user_id 전달)
            orch_start = time.time()
            timing_logger.mark("orch_start", orch_start)
            
            async def run_orch():
                return await run_orchestration_agent(message, history, timing_logger, user_id=user_id)
            
            orch_task = asyncio.create_task(run_orch())
            
            # 큐에서 로그를 읽어서 스트리밍
            while not orch_task.done():
                try:
                    log_msg = await asyncio.wait_for(log_queue.get(), timeout=0.1)
                    yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                except asyncio.TimeoutError:
                    continue
            
            # 남은 로그 처리
            while not log_queue.empty():
                log_msg = log_queue.get_nowait()
                yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
            
            orchestration_result = orch_task.result()
            orch_time = time.time() - orch_start
            timing_logger.mark("orch_complete")

            if "error" in orchestration_result:
                error_msg = f"❌ Orchestration 오류: {orchestration_result.get('error')}"
                yield send_log(error_msg)
                
                result = ChatResponse(
                    response="죄송합니다. 질문 분석 중 오류가 발생했습니다. 다시 시도해주세요.",
                    sources=[],
                    source_urls=[],
                    router_output=orchestration_result.get("router_output"),
                    function_results=orchestration_result.get("function_results"),
                    orchestration_result=orchestration_result,
                    sub_agent_results=None,
                    metadata=None,
                    logs=logs
                )
                yield f"data: {json.dumps({'type': 'result', 'data': result.dict()})}\n\n"
                return

            execution_plan = orchestration_result.get("execution_plan", [])
            answer_structure = orchestration_result.get("answer_structure", [])
            direct_response = orchestration_result.get("direct_response", None)
            extracted_scores = orchestration_result.get("extracted_scores", {})
            
            yield send_log("")
            yield send_log(f"📋 Orchestration 결과:")
            yield send_log(f"   사용자 의도: {orchestration_result.get('user_intent', 'N/A')}")
            yield send_log(f"   실행 계획: {len(execution_plan)}개 step")
            yield send_log(f"   답변 구조: {len(answer_structure)}개 섹션")
            
            # extracted_scores 로그
            if extracted_scores:
                yield send_log(f"   📊 추출된 성적: {len(extracted_scores)}개 과목")
            else:
                yield send_log(f"   ℹ️  성적 추출 없음")
            
            # 즉시 응답 체크
            if direct_response:
                yield send_log(f"   ⚡ 즉시 응답 모드")
            
            yield send_log(f"   ⏱️ 처리 시간: {orch_time:.2f}초")
            yield send_log("="*80)

            # ========================================
            # 즉시 응답 처리
            # ========================================
            if direct_response:
                yield send_log("")
                yield send_log("="*80)
                yield send_log("⚡ 즉시 응답 - Sub Agents 및 Final Agent 생략")
                yield send_log("="*80)
                yield send_log(f"   응답 길이: {len(direct_response)}자")
                
                # 히스토리 저장
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": direct_response})
                conversation_sessions[session_id] = history[-20:]  # 최근 20개만 유지

                # 채팅 로그 저장
                await supabase_service.insert_chat_log(
                    message,
                    direct_response,
                    is_fact_mode=False
                )

                # 전체 파이프라인 시간 계산
                pipeline_time = time.time() - pipeline_start
                
                yield send_log("")
                yield send_log(f"{'#'*80}")
                yield send_log(f"# ✅ 즉시 응답 완료")
                yield send_log(f"# 응답 길이: {len(direct_response)}자")
                yield send_log(f"# ⏱️ 처리 시간: {pipeline_time:.2f}초")
                yield send_log(f"{'#'*80}")
                
                print(f"🟢 [STREAM_REQUEST_END] {request_id}\n")

                # 최종 응답 전송
                result = ChatResponse(
                    response=direct_response,
                    raw_answer=direct_response,
                    sources=[],
                    source_urls=[],
                    used_chunks=[],
                    router_output=orchestration_result.get("router_output"),
                    function_results=orchestration_result.get("function_results"),
                    orchestration_result=orchestration_result,
                    sub_agent_results=None,
                    metadata={
                        "immediate_response": True, 
                        "pipeline_time": pipeline_time,
                        "timing": orchestration_result.get("timing", {})
                    },
                    logs=logs
                )
                yield f"data: {json.dumps({'type': 'result', 'data': result.dict()})}\n\n"
                return

            # ========================================
            # 2단계: Sub Agents 실행
            # ========================================
            yield send_log("")
            yield send_log("="*80)
            yield send_log("🤖 Sub Agents 실행")
            yield send_log("="*80)
            
            for step in execution_plan:
                yield send_log(f"   Step {step['step']}: {step['agent']}")
                yield send_log(f"   Query: {step['query']}")
            
            # Sub Agents 실행 (백그라운드)
            sub_start = time.time()
            timing_logger.mark("sub_agents_start", sub_start)
            
            async def run_subs():
                return await execute_sub_agents(
                    execution_plan,
                    extracted_scores=extracted_scores,
                    user_message=message,
                    timing_logger=timing_logger
                )
            
            subs_task = asyncio.create_task(run_subs())
            
            # 큐에서 로그를 읽어서 스트리밍 (최대 대기 시간 추가)
            max_wait_time = 180.0  # 최대 3분 대기
            wait_start = time.time()
            while not subs_task.done():
                # 최대 대기 시간 초과 체크
                if time.time() - wait_start > max_wait_time:
                    yield send_log("⚠️ Sub Agents 처리 시간이 초과되었습니다. 계속 진행합니다...")
                    break
                    
                try:
                    log_msg = await asyncio.wait_for(log_queue.get(), timeout=0.1)
                    yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                except asyncio.TimeoutError:
                    continue
            
            # 남은 로그 처리
            while not log_queue.empty():
                log_msg = log_queue.get_nowait()
                yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
            
            sub_agent_results = subs_task.result()
            sub_time = time.time() - sub_start
            timing_logger.mark("sub_agents_complete")
            
            yield send_log("")
            for key, result in sub_agent_results.items():
                status = result.get('status', 'unknown')
                agent = result.get('agent', 'Unknown')
                sources_count = len(result.get('sources', []))
                exec_time = result.get('execution_time', 0)
                status_icon = "✅" if status == "success" else "❌"
                yield send_log(f"{status_icon} {key} ({agent}): {status} (출처 {sources_count}개, ⏱️ {exec_time:.2f}초)")
            yield send_log(f"   총 Sub Agents 처리 시간: {sub_time:.2f}초")
            yield send_log("="*80)

            # ========================================
            # 3단계: Final Agent - 최종 답변 생성
            # ========================================
            yield send_log("")
            yield send_log("="*80)
            yield send_log("📝 Final Agent 실행")
            yield send_log("="*80)
            yield send_log(f"   섹션 수: {len(answer_structure)}")
            
            # Final Agent 실행 (백그라운드)
            final_start = time.time()
            timing_logger.mark("final_start", final_start)
            
            async def run_final():
                return await generate_final_answer(
                    user_question=message,
                    answer_structure=answer_structure,
                    sub_agent_results=sub_agent_results,
                    history=history,
                    timing_logger=timing_logger
                )
            
            final_task = asyncio.create_task(run_final())
            
            # 큐에서 로그를 읽어서 스트리밍 (최대 대기 시간 추가)
            max_wait_time = 180.0  # 최대 3분 대기
            wait_start = time.time()
            while not final_task.done():
                # 최대 대기 시간 초과 체크
                if time.time() - wait_start > max_wait_time:
                    yield send_log("⚠️ Final Agent 처리 시간이 초과되었습니다. 계속 진행합니다...")
                    break
                    
                try:
                    log_msg = await asyncio.wait_for(log_queue.get(), timeout=0.1)
                    yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                except asyncio.TimeoutError:
                    continue
            
            # 남은 로그 처리
            while not log_queue.empty():
                log_msg = log_queue.get_nowait()
                yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
            
            final_result = final_task.result()
            final_time = time.time() - final_start
            timing_logger.mark("final_complete")

            final_answer = final_result.get("final_answer", "답변 생성 실패")
            raw_answer = final_result.get("raw_answer", "")  # ✅ 원본 답변
            sources = final_result.get("sources", [])
            source_urls = final_result.get("source_urls", [])
            used_chunks = final_result.get("used_chunks", [])
            
            yield send_log(f"   최종 답변 길이: {len(final_answer)}자")
            yield send_log(f"   원본 답변 길이: {len(raw_answer)}자")
            yield send_log(f"   관련 청크 수: {len(used_chunks)}개")
            yield send_log(f"   ⏱️ 처리 시간: {final_time:.2f}초")
            yield send_log("="*80)

            # 히스토리 저장
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": final_answer})
            conversation_sessions[session_id] = history[-20:]  # 최근 20개만 유지
            
            timing_logger.mark("history_saved")

            # 채팅 로그 저장
            await supabase_service.insert_chat_log(
                message,
                final_answer,
                is_fact_mode=len(sources) > 0
            )
            timing_logger.mark("db_saved")

            # 전체 파이프라인 시간 계산
            pipeline_time = time.time() - pipeline_start
            
            yield send_log("")
            yield send_log(f"{'#'*80}")
            yield send_log(f"# ✅ 파이프라인 완료")
            yield send_log(f"# 최종 답변 길이: {len(final_answer)}자")
            yield send_log(f"# 원본 답변 길이: {len(raw_answer)}자")
            yield send_log(f"# 출처 수: {len(sources)}개")
            yield send_log(f"#")
            yield send_log(f"# ⏱️ 처리 시간 분석:")
            yield send_log(f"#   • Orchestration: {orch_time:.2f}초 ({orch_time/pipeline_time*100:.1f}%)")
            yield send_log(f"#   • Sub Agents: {sub_time:.2f}초 ({sub_time/pipeline_time*100:.1f}%)")
            yield send_log(f"#   • Final Agent: {final_time:.2f}초 ({final_time/pipeline_time*100:.1f}%)")
            yield send_log(f"#   • 전체: {pipeline_time:.2f}초")
            yield send_log(f"{'#'*80}")
            
            # 초상세 타이밍 로그 출력
            for timing_line in timing_logger.get_detailed_log_lines():
                yield send_log(timing_line)
            
            # 타이밍 측정 완료 및 저장
            timing_logger.mark("response_sent")
            timing_logger.log_to_file()
            timing_logger.print_summary()
            
            print(f"🟢 [STREAM_REQUEST_END] {request_id}\n")

            # 타이밍 정보 수집
            timing_summary = timing_logger.get_summary()
            
            # metadata에 타이밍 정보 추가
            metadata = final_result.get("metadata", {})
            metadata["timing"] = {
                "total_time": timing_summary.get("total_time", 0),
                "orchestration_time": timing_summary.get("orchestration_time", 0),
                "sub_agents_time": timing_summary.get("sub_agents_time", 0),
                "final_agent_time": timing_summary.get("final_agent_time", 0),
                "durations": timing_summary.get("durations", {}),
                "orchestration_details": timing_summary.get("orchestration_details"),
                "sub_agents_details": timing_summary.get("sub_agents_details"),
                "final_agent_details": timing_summary.get("final_agent_details"),
            }

            # 최종 응답 전송
            result = ChatResponse(
                response=final_answer,
                raw_answer=raw_answer,  # ✅ 원본 답변 추가
                sources=sources,
                source_urls=source_urls,
                used_chunks=used_chunks,  # 사용된 청크 추가
                router_output=orchestration_result.get("router_output"),
                function_results=orchestration_result.get("function_results"),
                orchestration_result=orchestration_result,
                sub_agent_results=sub_agent_results,
                metadata=metadata,
                logs=logs
            )
            yield f"data: {json.dumps({'type': 'result', 'data': result.dict()})}\n\n"

        except Exception as e:
            print(f"\n{'='*80}")
            print(f"❌ 채팅 오류: {e}")
            print(f"{'='*80}\n")
            import traceback
            traceback.print_exc()
            
            error_result = ChatResponse(
                response="죄송합니다. 일시적인 오류가 발생했습니다. 다시 시도해주세요.",
                sources=[],
                source_urls=[],
                logs=logs
            )
            yield f"data: {json.dumps({'type': 'error', 'data': error_result.dict()})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/stream/{session_id}")
async def stream_logs(session_id: str):
    """실시간 로그 스트리밍 (SSE)"""
    queue = asyncio.Queue()
    log_queues[session_id] = queue
    
    async def event_generator():
        try:
            while True:
                log = await queue.get()
                if log == "[DONE]":
                    break
                yield f"data: {json.dumps({'log': log})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if session_id in log_queues:
                del log_queues[session_id]
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


def emit_log(session_id: str, message: str):
    """로그를 큐에 추가"""
    if session_id in log_queues:
        try:
            log_queues[session_id].put_nowait(message)
        except:
            pass


@router.post("/reset")
async def reset_session(session_id: str = "default"):
    """대화 히스토리 초기화"""
    if session_id in conversation_sessions:
        del conversation_sessions[session_id]
    return {"status": "ok", "message": f"세션 {session_id} 초기화 완료"}


@router.get("/agents")
async def get_agents():
    """가용 에이전트 목록 조회"""
    return {"agents": AVAILABLE_AGENTS}


