"""
채팅 API 라우터 (멀티에이전트 기반)
전체 파이프라인: Orchestration Agent → Sub Agents → Final Agent → 최종 답변
"""
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, Request, Header, Query
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
from services.multi_agent.router_agent import route_query
from services.score_review import (
    run_router_and_profile_parallel,
    resolve_score_id_from_message,
    extract_naesin_candidate,
    build_school_grade_input_from_card,
)
from utils.school_record_context import build_school_record_context_text
from school_record_eval.report_context import build_school_record_report_context_text
from school_record_eval.report_agent import (
    generate_school_record_report,
    generate_school_record_report_stream,
)
from utils.timing_logger import TimingLogger
from utils.admin_filter import should_skip_logging
from middleware.auth import optional_auth, optional_auth_with_state
from middleware.rate_limit import check_and_increment_usage, get_client_ip
import uuid
from datetime import datetime

router = APIRouter()

AUTH_EXPIRED_DETAIL = "세션이 만료되었거나 유효하지 않습니다. 다시 로그인해 주세요."


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
# 키 형식: "{user_id}:{session_id}" 또는 "guest:{session_id}"
conversation_sessions: Dict[str, List[Dict[str, Any]]] = {}


def get_cache_key(user_id: Optional[str], session_id: str) -> str:
    """
    대화 히스토리 캐시 키 생성
    - 사용자별로 세션을 분리하여 다른 사용자의 대화가 섞이지 않도록 함
    """
    return f"{user_id or 'guest'}:{session_id}"


async def load_history_from_db(session_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    DB에서 세션 히스토리 로드 (session_chat_messages)
    - user_id가 있으면 해당 사용자의 메시지만 로드
    """
    try:
        query = supabase_service.client.table("session_chat_messages")\
            .select("role, content")\
            .eq("user_session", session_id)
        
        # user_id가 있으면 해당 사용자의 메시지만 필터링
        if user_id:
            query = query.eq("user_id", user_id)
        
        messages_response = query.order("created_at").limit(20).execute()
        
        if messages_response.data:
            return [
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                for msg in messages_response.data
            ]
    except Exception as e:
        print(f"⚠️ DB에서 히스토리 로드 실패 (무시): {e}")
    return []


def get_or_load_history(session_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    메모리에서 히스토리 가져오기. 없으면 빈 리스트 반환 (async 버전 사용 권장)
    """
    cache_key = get_cache_key(user_id, session_id)
    if cache_key not in conversation_sessions:
        conversation_sessions[cache_key] = []
    return conversation_sessions[cache_key][-20:]


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    thinking: Optional[bool] = False  # Thinking 모드 활성화 여부
    score_id: Optional[str] = None
    skip_score_review: Optional[bool] = False  # True면 연동된 성적로 바로 답변(성적 확인 카드 생략)
    use_school_record: Optional[bool] = False  # 생기부 컨텍스트 사용 여부
    use_linked_naesin: Optional[bool] = False  # '@내신 성적' 명시 선택 시 연동 내신 카드 강제


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


class ScoreReviewApproveRequest(BaseModel):
    pending_id: str
    session_id: str
    title: str
    scores: Dict[str, Any]


class ScoreReviewSkipSessionRequest(BaseModel):
    pending_id: Optional[str] = None
    session_id: str


class ContinueAfterNaesinRequest(BaseModel):
    """내신 카드 확인 후 답변 생성 요청 (사용량 차감 없음)"""
    session_id: str
    score_id: Optional[str] = None
    # 카드에서 수정한 성적 반영 (있으면 프로필 업데이트 후 답변 생성)
    grade_summary: Optional[Dict[str, Any]] = None  # overall_average, core_average, semester_averages


class ContinueAfterScoreConfirmRequest(BaseModel):
    """모의고사 성적 카드 확인 후 답변 생성 요청 (사용량 차감 없음)"""
    session_id: str
    score_id: str


class ScoreSetCreateRequest(BaseModel):
    name: str
    scores: Dict[str, Any]
    session_id: Optional[str] = None


class ScoreSetUpdateRequest(BaseModel):
    name: str
    scores: Dict[str, Any]
    session_id: Optional[str] = None


def _resolve_score_owner(user_id: Optional[str], session_id: Optional[str]) -> str:
    if user_id:
        return user_id
    if session_id:
        return f"guest:{session_id}"
    raise HTTPException(status_code=400, detail="session_id 또는 로그인 정보가 필요합니다.")


async def _prepare_score_review_gate(
    message: str,
    history: List[Dict[str, Any]],
    user_id: Optional[str],
    session_id: str,
    score_id_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Run router/profile in parallel and decide review gate."""
    if score_id_override:
        return {"mode": "pass", "score_id": score_id_override}

    score_id_from_token = await resolve_score_id_from_message(user_id, message)
    if score_id_from_token:
        return {"mode": "pass", "score_id": score_id_from_token}

    skip_session = await supabase_service.get_session_skip_score_review(session_id, user_id)
    score_owner = user_id or f"guest:{session_id}"
    existing = await supabase_service.list_user_score_sets(score_owner, limit=20)

    router_coro = route_query(message, history, user_id=user_id)
    router_output, candidate = await run_router_and_profile_parallel(
        router_coro=router_coro,
        message=message,
        existing_score_sets=existing,
    )

    if not candidate.has_candidate:
        return {"mode": "pass", "score_id": None, "router_output": router_output}

    title_auto = candidate.title_auto
    title_without_at = title_auto[1:] if title_auto.startswith("@") else title_auto

    if skip_session:
        saved = await supabase_service.upsert_user_score_set(
            user_id=score_owner,
            name=title_without_at,
            scores=candidate.completed_scores,
            source_message=message,
            title_auto_generated=True,
        )
        return {
            "mode": "auto",
            "score_id": saved.get("id") if saved else None,
            "score_name": f"@{saved.get('name')}" if saved else title_auto,
            "router_output": router_output,
        }

    pending = await supabase_service.create_chat_score_pending(
        user_id=user_id,
        session_id=session_id,
        raw_message=message,
        router_output=router_output,
        candidate_scores=candidate.completed_scores,
        title_auto=title_without_at,
    )
    if not pending:
        return {"mode": "pass", "score_id": None, "router_output": router_output}

    return {
        "mode": "review",
        "pending_id": pending.get("id"),
        "title_auto": title_auto,
        "scores": candidate.completed_scores,
    }


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
        auth_header = authorization or (http_request.headers.get("authorization") if http_request else None)
        user, auth_failed = await optional_auth_with_state(auth_header)
        if auth_failed or (auth_header and auth_header.startswith("Bearer ") and user is None):
            raise HTTPException(status_code=401, detail=AUTH_EXPIRED_DETAIL)
        user_id = user["user_id"] if user else None
        
        # 3. Rate Limit 체크 및 증가
        is_allowed, current_count, limit, require_login = await check_and_increment_usage(user_id, client_ip)
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
        print(f"📊 API 사용량: {current_count}/{limit}회 (user_id={user_id}, ip={client_ip}, require_login={require_login})")
        
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
        cache_key = get_cache_key(user_id, session_id)
        if cache_key not in conversation_sessions or len(conversation_sessions[cache_key]) == 0:
            db_history = await load_history_from_db(session_id, user_id)
            if db_history:
                conversation_sessions[cache_key] = db_history
            else:
                conversation_sessions[cache_key] = []
        history = conversation_sessions[cache_key][-20:]
        # user_id는 optional_auth에서 이미 설정됨 (프로필 점수 활용용)

        # ========================================
        # (Optional) 생기부 컨텍스트 로드
        # ========================================
        school_record_context = None
        school_record_report_context = None
        if request.use_school_record:
            if not user_id:
                return ChatResponse(
                    response="생기부 분석 기능은 로그인 후 사용할 수 있습니다.",
                    raw_answer="생기부 분석 기능은 로그인 후 사용할 수 있습니다.",
                    sources=[],
                    source_urls=[],
                    used_chunks=[],
                    metadata={"agent_mode": "school_record_dedicated_agent", "reason": "auth_required"},
                )
            try:
                school_loaded = await supabase_service.get_user_profile_school_record(user_id)
                school_profile = dict(school_loaded or {})
                school_record_context = build_school_record_context_text(school_profile)
                school_record_report_context = build_school_record_report_context_text(school_profile)
                if school_record_context:
                    log_and_emit(f"   📎 생기부 컨텍스트 적용: {len(school_record_context)}자")
                else:
                    log_and_emit("   ℹ️  생기부 컨텍스트 없음(미연동 또는 빈 데이터)")
            except Exception as e:
                log_and_emit(f"⚠️ 생기부 컨텍스트 로드 실패(무시): {e}")
                school_record_context = None
                school_record_report_context = None

        # A안: 생기부 모드일 때는 score review를 우회하고 전용 리포트로 진입
        if request.use_school_record:
            if not school_record_report_context:
                return ChatResponse(
                    response="연동된 생기부 데이터가 없습니다. 먼저 생활기록부를 연동해 주세요.",
                    raw_answer="연동된 생기부 데이터가 없습니다. 먼저 생활기록부를 연동해 주세요.",
                    sources=[],
                    source_urls=[],
                    used_chunks=[],
                    metadata={"agent_mode": "school_record_dedicated_agent", "reason": "missing_school_record"},
                )

            log_and_emit("")
            log_and_emit("=" * 80)
            log_and_emit("📘 생기부 전용 에이전트 실행")
            log_and_emit("=" * 80)

            report_result = await generate_school_record_report(
                message=message,
                history=history,
                school_record_context=school_record_report_context,
                school_record=school_profile,
                user_id=user_id,
            )

            final_answer = report_result.get("response", "생기부 분석 보고서를 생성하지 못했습니다.")
            sources = report_result.get("sources", []) or []
            source_urls = report_result.get("source_urls", []) or []
            used_chunks = report_result.get("used_chunks", []) or []

            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": final_answer})
            conversation_sessions[cache_key] = history[-20:]

            await supabase_service.insert_chat_log(
                message,
                final_answer,
                is_fact_mode=len(sources) > 0
            )

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

            return ChatResponse(
                response=final_answer,
                raw_answer=final_answer,
                sources=sources,
                source_urls=source_urls,
                used_chunks=used_chunks,
                router_output=report_result.get("router_output"),
                function_results=report_result.get("function_results"),
                orchestration_result={
                    "mode": "school_record_dedicated_agent",
                    "execution_plan": [],
                    "answer_structure": [],
                },
                sub_agent_results=None,
                metadata={
                    "agent_mode": "school_record_dedicated_agent",
                    "timing": report_result.get("timing", {}),
                },
            )

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
        orchestration_result = await run_orchestration_agent(
            message, history, user_id=user_id, school_record_context=school_record_context
        )
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
            conversation_sessions[cache_key] = history[-20:]  # 최근 20개만 유지

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
        conversation_sessions[cache_key] = history[-20:]  # 최근 20개만 유지

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
    score_id: Optional[str] = Form(default=None),
    use_school_record: bool = Form(default=False),
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
    auth_header = authorization or (http_request.headers.get("authorization") if http_request else None)
    user, auth_failed = await optional_auth_with_state(auth_header)
    if auth_failed or (auth_header and auth_header.startswith("Bearer ") and user is None):
        raise HTTPException(status_code=401, detail=AUTH_EXPIRED_DETAIL)
    user_id = user["user_id"] if user else None
    
    is_allowed, current_count, limit, require_login = await check_and_increment_usage(user_id, client_ip)
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
    
    print(f"📊 API 사용량: {current_count}/{limit}회 (user_id={user_id}, ip={client_ip}, require_login={require_login})")

    # (Optional) 생기부 컨텍스트 로드 (이미지 분석 전에 1회만)
    school_record_context = None
    school_record_report_context = None
    if use_school_record and user_id:
        try:
            school_loaded = await supabase_service.get_user_profile_school_record(user_id)
            school_profile = dict(school_loaded or {})
            school_record_context = build_school_record_context_text(school_profile) or None
            school_record_report_context = build_school_record_report_context_text(school_profile) or None
        except Exception as e:
            print(f"⚠️ 생기부 컨텍스트 로드 실패(무시): {e}")
            school_record_context = None
            school_record_report_context = None
    
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
        nonlocal require_login  # 클로저에서 사용
        pipeline_start = time.time()
        print(f"\n🔵 [STREAM_V2_IMAGE_START] {session_id}:{message[:30]}")
        print(f"🖼️ 이미지: {image.filename}, {image.content_type}, {len(image_data)} bytes")
        
        # 세션별 히스토리 로드 (user_id 기반 캐시 키 사용)
        cache_key = get_cache_key(user_id, session_id)
        if cache_key not in conversation_sessions:
            conversation_sessions[cache_key] = []
        history = conversation_sessions[cache_key][-20:]
        
        full_response = ""
        image_analysis = ""
        timing = {}
        function_results = {}
        router_output = {}
        sources = []
        source_urls = []
        used_chunks = []
        active_score_id = score_id
        
        try:
            if use_school_record and not user_id:
                yield f"data: {json.dumps({'type': 'error', 'message': '생기부 분석 기능은 로그인 후 사용할 수 있습니다.'}, ensure_ascii=False)}\n\n"
                return
            if use_school_record and not school_record_report_context:
                yield f"data: {json.dumps({'type': 'error', 'message': '연동된 생기부 데이터가 없습니다. 먼저 생활기록부를 연동해 주세요.'}, ensure_ascii=False)}\n\n"
                return

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

            # 내신/수시 짧은 입력 감지 (score review 보다 먼저)
            naesin = extract_naesin_candidate(enhanced_message)
            if naesin.has_candidate and user_id:
                _nloop = asyncio.new_event_loop()
                asyncio.set_event_loop(_nloop)
                try:
                    _nloop.run_until_complete(
                        supabase_service.update_user_profile_metadata(
                            user_id, "school_grade_input", naesin.school_grade_input
                        )
                    )
                finally:
                    _nloop.close()
                naesin_event = {
                    "type": "school_grade_saved",
                    "overall_average": naesin.overall_average,
                    "core_average": naesin.core_average,
                    "semester_averages": naesin.school_grade_input.get("gradeSummary", {}).get("semesterAverages", {}),
                }
                yield f"data: {json.dumps(naesin_event, ensure_ascii=False)}\n\n"
                # 확인 버튼을 눌러야 답변 생성 시작 → 여기서 스트림 종료, 히스토리에만 사용자 메시지 저장
                history.append({"role": "user", "content": enhanced_message})
                conversation_sessions[cache_key] = history[-20:]
                return

            if not use_school_record:
                # 내신으로 이미 처리된 메시지는 정시 성적 리뷰 건너뜀 (내신 카드만 보이고 답변 계속)
                if not (naesin.has_candidate and user_id):
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        gate = loop.run_until_complete(
                            _prepare_score_review_gate(
                                message=enhanced_message,
                                history=history,
                                user_id=user_id,
                                session_id=session_id,
                                score_id_override=active_score_id,
                            )
                        )
                    finally:
                        loop.close()

                    gate_mode = gate.get("mode")
                    if gate_mode == "review":
                        review_event = {
                            "type": "score_review_required",
                            "pending_id": gate.get("pending_id"),
                            "title_auto": gate.get("title_auto"),
                            "scores": gate.get("scores", {}),
                            "constraints": {
                                "title_max_length": 10,
                                "standard_score": {"min": 0, "max": 200},
                                "percentile": {"min": 0, "max": 100},
                                "grade": {"min": 1, "max": 9},
                            },
                            "actions": ["edit", "approve", "skip_session"],
                        }
                        yield f"data: {json.dumps(review_event, ensure_ascii=False)}\n\n"
                        history.append({"role": "user", "content": enhanced_message})
                        conversation_sessions[cache_key] = history[-20:]
                        return
                    if gate_mode in {"auto", "pass"}:
                        active_score_id = gate.get("score_id") or active_score_id

            # 4단계: 멀티에이전트 or 생기부 전용 에이전트 실행
            event_iter = (
                generate_school_record_report_stream(
                    message=enhanced_message,
                    history=history,
                    school_record_context=school_record_report_context,
                    school_record=school_profile,
                    user_id=user_id,
                )
                if use_school_record
                else run_orchestration_agent_stream(
                    enhanced_message,
                    history,
                    user_id=user_id,
                    score_id=active_score_id,
                )
            )
            for event in event_iter:
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
            conversation_sessions[cache_key] = history[-20:]
            
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
                "used_chunks": used_chunks,
                "require_login": require_login,  # 비로그인 3회째 질문 시 True
                "score_id": active_score_id,
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
    
    thinking=True일 경우:
    - Router -> RAG -> MainAgentThinking (재질문 가능) -> 최종 답변
    
    thinking=False일 경우 (기본):
    - Router -> RAG -> MainAgent -> 최종 답변
    
    SSE (Server-Sent Events) 형식:
    - {"type": "status", "step": "router", "message": "..."}
    - {"type": "log", "content": "..."} (thinking 모드)
    - {"type": "chunk", "text": "응답 텍스트 조각"}
    - {"type": "done", "timing": {...}, "response": "전체 응답"}
    """
    import time
    
    # ========================================
    # Rate Limiting 체크 (generator 외부에서 실행)
    # ========================================
    client_ip = get_client_ip(http_request)
    auth_header = authorization or (http_request.headers.get("authorization") if http_request else None)
    user, auth_failed = await optional_auth_with_state(auth_header)
    if auth_failed or (auth_header and auth_header.startswith("Bearer ") and user is None):
        raise HTTPException(status_code=401, detail=AUTH_EXPIRED_DETAIL)
    user_id = user["user_id"] if user else None
    
    is_allowed, current_count, limit, require_login = await check_and_increment_usage(user_id, client_ip)
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
    
    print(f"📊 API 사용량: {current_count}/{limit}회 (user_id={user_id}, ip={client_ip}, require_login={require_login})")
    
    # Thinking 모드 체크
    thinking_mode = request.thinking
    use_school_record = request.use_school_record is True

    # (Optional) 생기부 컨텍스트 로드 (스트리밍 시작 전에 1회만)
    school_record_context = None
    school_record_report_context = None
    if use_school_record and user_id:
        try:
            school_loaded = await supabase_service.get_user_profile_school_record(user_id)
            school_profile = dict(school_loaded or {})
            school_record_context = build_school_record_context_text(school_profile) or None
            school_record_report_context = build_school_record_report_context_text(school_profile) or None
        except Exception as e:
            print(f"⚠️ 생기부 컨텍스트 로드 실패(무시): {e}")
            school_record_context = None
            school_record_report_context = None
    
    def generate():
        nonlocal require_login  # 클로저에서 사용
        session_id = request.session_id
        message = request.message
        
        pipeline_start = time.time()
        if use_school_record:
            mode_label = "SCHOOL_RECORD"
        else:
            mode_label = "THINKING" if thinking_mode else "NORMAL"
        print(f"\n🔵 [STREAM_V2_START] [{mode_label}] {session_id}:{message[:30]}")
        
        # 세션별 히스토리 로드 (동기 generator이므로 메모리에서만 확인)
        # user_id 기반 캐시 키 사용
        cache_key = get_cache_key(user_id, session_id)
        if cache_key not in conversation_sessions:
            conversation_sessions[cache_key] = []
        history = conversation_sessions[cache_key][-20:]
        # user_id는 optional_auth에서 온 클로저 변수 사용 (프로필/저장용)

        full_response = ""
        timing = {}
        function_results = {}
        router_output = {}
        sources = []
        source_urls = []
        used_chunks = []
        active_score_id = request.score_id
        message_for_pipeline = message
        
        try:
            # 연동 내신 카드 강제는 프론트에서 명시적으로 요청한 경우(use_linked_naesin)만 수행
            _msg_raw = (message or "").strip()
            _msg_norm = _msg_raw.replace("＠", "@")
            _msg_lower = _msg_norm.replace("\n", " ").lower()
            _msg_compact = _msg_lower.replace(" ", "")
            _is_linked_naesin_query = bool(getattr(request, "use_linked_naesin", False))
            if _is_linked_naesin_query:
                if not user_id:
                    yield f"data: {json.dumps({'type': 'error', 'message': '내신 연동 기반 추천은 로그인 후 사용할 수 있습니다.'}, ensure_ascii=False)}\n\n"
                    return
                _nloop_naesin = asyncio.new_event_loop()
                asyncio.set_event_loop(_nloop_naesin)
                try:
                    meta = _nloop_naesin.run_until_complete(supabase_service.get_user_profile_metadata(user_id))
                except Exception as _e:
                    meta = {}
                    print(f"⚠️ get_user_profile_metadata(연동 내신): {_e}")
                finally:
                    _nloop_naesin.close()
                sgi = (meta or {}).get("school_grade_input") or {}
                gs = sgi.get("gradeSummary") or {}
                has_gs = gs.get("overallAverage") is not None or gs.get("coreAverage") is not None or (gs.get("semesterAverages") and len(gs.get("semesterAverages", {})) > 0)
                if has_gs:
                    try:
                        ov = float(gs.get("overallAverage") or gs.get("coreAverage") or 0)
                    except (TypeError, ValueError):
                        ov = 2.5
                    try:
                        co = float(gs.get("coreAverage") or gs.get("overallAverage") or 0)
                    except (TypeError, ValueError):
                        co = 2.5
                    sem_avgs = gs.get("semesterAverages") or {}
                else:
                    yield f"data: {json.dumps({'type': 'error', 'message': '연동된 내신 성적이 없습니다. 내신 성적과 모의고사 성적을 먼저 연동해 주세요.'}, ensure_ascii=False)}\n\n"
                    return
                naesin_event = {
                    "type": "school_grade_saved",
                    "overall_average": ov,
                    "core_average": co,
                    "semester_averages": sem_avgs,
                }
                if not getattr(request, "skip_score_review", False):
                    # 기존 동작: 카드 표시 후 확인/수정 단계 진행
                    yield f"data: {json.dumps(naesin_event, ensure_ascii=False)}\n\n"
                    history.append({"role": "user", "content": message})
                    conversation_sessions[cache_key] = history[-20:]
                    return
                # 카드 생략 모드: 연동 내신 요약을 파이프라인 입력에만 주입해 바로 답변 생성
                sem_lines = []
                for k in ["1-1", "1-2", "2-1", "2-2", "3-1", "3-2"]:
                    v = (sem_avgs or {}).get(k) or {}
                    o = v.get("overall")
                    c = v.get("core")
                    if o is not None or c is not None:
                        sem_lines.append(f"{k} 전체 {o if o is not None else '-'} / 국영수탐 {c if c is not None else '-'}")
                sem_text = "\n".join(sem_lines) if sem_lines else "학기별 데이터 없음"
                message_for_pipeline = (
                    f"{message}\n\n"
                    f"[연동 내신 성적 요약]\n"
                    f"- 전체 평균 내신: {ov}\n"
                    f"- 국영수탐 평균 내신: {co}\n"
                    f"- 학기별:\n{sem_text}\n"
                    f"- 위 연동 내신 성적을 기준으로 답변하세요.\n"
                    f"- 답변의 첫 문장은 반드시 '@내신 성적을 기반으로 분석해 드릴게요.' 또는 '@내신 성적을 기준으로 ...' 처럼 '@내신 성적'을 포함한 문장으로 자연스럽게 시작하세요."
                )

            if use_school_record:
                if not user_id:
                    yield f"data: {json.dumps({'type': 'error', 'message': '생기부 분석 기능은 로그인 후 사용할 수 있습니다.'}, ensure_ascii=False)}\n\n"
                    return
                if not school_record_report_context:
                    yield f"data: {json.dumps({'type': 'error', 'message': '연동된 생기부 데이터가 없습니다. 먼저 생활기록부를 연동해 주세요.'}, ensure_ascii=False)}\n\n"
                    return

                for event in generate_school_record_report_stream(
                    message=message,
                    history=history,
                    school_record_context=school_record_report_context,
                    school_record=school_profile,
                    user_id=user_id,
                ):
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

            else:
                # 메시지의 성적 토큰(@내성적N 등)으로 선택된 score_id가 있으면 내신 파싱보다 우선한다.
                if not active_score_id and user_id:
                    _loop_sid = asyncio.new_event_loop()
                    asyncio.set_event_loop(_loop_sid)
                    try:
                        active_score_id = _loop_sid.run_until_complete(
                            resolve_score_id_from_message(user_id, message)
                        ) or active_score_id
                    finally:
                        _loop_sid.close()

                naesin_has_candidate = False
                # 내신/수시 짧은 입력 감지 (연동 내신/저장 성적 토큰은 위·아래 분기에서 우선 처리)
                if not active_score_id:
                    naesin = extract_naesin_candidate(message)
                    naesin_has_candidate = bool(naesin.has_candidate and user_id)
                    if naesin_has_candidate and user_id:
                        _nloop2 = asyncio.new_event_loop()
                        asyncio.set_event_loop(_nloop2)
                        try:
                            _nloop2.run_until_complete(
                                supabase_service.update_user_profile_metadata(
                                    user_id, "school_grade_input", naesin.school_grade_input
                                )
                            )
                        finally:
                            _nloop2.close()
                        naesin_event = {
                            "type": "school_grade_saved",
                            "overall_average": naesin.overall_average,
                            "core_average": naesin.core_average,
                            "semester_averages": naesin.school_grade_input.get("gradeSummary", {}).get("semesterAverages", {}),
                        }
                        yield f"data: {json.dumps(naesin_event, ensure_ascii=False)}\n\n"
                        history.append({"role": "user", "content": message})
                        conversation_sessions[cache_key] = history[-20:]
                        return

                # 모의고사(@새성적_0 등) 선택 시: 카드 먼저 띄우고, 확인 후 답변 생성
                # 연동된 성적으로 바로 답변할 때(skip_score_review)는 성적 확인 카드 생략
                if active_score_id and user_id and not getattr(request, "skip_score_review", False):
                    _loop_ss = asyncio.new_event_loop()
                    asyncio.set_event_loop(_loop_ss)
                    try:
                        row = _loop_ss.run_until_complete(
                            supabase_service.get_user_score_set_by_id(active_score_id, user_id)
                        )
                    finally:
                        _loop_ss.close()
                    if row:
                        name = (row.get("name") or "성적").replace("@", "").strip()
                        scores = row.get("scores") or {}
                        review_event = {
                            "type": "score_review_required",
                            "pending_id": active_score_id,
                            "title_auto": f"@{name}" if not name.startswith("@") else name,
                            "scores": scores,
                            "use_existing_score_id": True,
                            "constraints": {
                                "title_max_length": 10,
                                "standard_score": {"min": 0, "max": 200},
                                "percentile": {"min": 0, "max": 100},
                                "grade": {"min": 1, "max": 9},
                            },
                            "actions": ["edit", "approve", "skip_session"],
                        }
                        yield f"data: {json.dumps(review_event, ensure_ascii=False)}\n\n"
                        history.append({"role": "user", "content": message})
                        conversation_sessions[cache_key] = history[-20:]
                        return

                # 내신으로 이미 처리된 메시지는 정시 성적 리뷰 건너뜀
                if not naesin_has_candidate:
                    # 성적 리뷰 게이트 (Router/Profile 동시 실행)
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        gate = loop.run_until_complete(
                            _prepare_score_review_gate(
                                message=message_for_pipeline,
                                history=history,
                                user_id=user_id,
                                session_id=session_id,
                                score_id_override=active_score_id,
                            )
                        )
                    finally:
                        loop.close()

                    gate_mode = gate.get("mode")
                    if gate_mode == "review":
                        review_event = {
                            "type": "score_review_required",
                            "pending_id": gate.get("pending_id"),
                            "title_auto": gate.get("title_auto"),
                            "scores": gate.get("scores", {}),
                            "constraints": {
                                "title_max_length": 10,
                                "standard_score": {"min": 0, "max": 200},
                                "percentile": {"min": 0, "max": 100},
                                "grade": {"min": 1, "max": 9},
                            },
                            "actions": ["edit", "approve", "skip_session"],
                        }
                        yield f"data: {json.dumps(review_event, ensure_ascii=False)}\n\n"
                        history.append({"role": "user", "content": message})
                        conversation_sessions[cache_key] = history[-20:]
                        return

                    if gate_mode in {"auto", "pass"}:
                        active_score_id = gate.get("score_id") or active_score_id

            if not use_school_record and thinking_mode:
                # ========================================
                # Thinking 모드: MainAgentThinking 사용
                # main_agent와 동일한 로그 형식 사용
                # ========================================
                
                from services.multi_agent.main_agent_thinking import generate_thinking_stream
                from services.multi_agent.router_agent import RouterAgent
                from services.multi_agent.functions import execute_function_calls
                
                # 1. Router로 1차 검색
                yield f"data: {json.dumps({'type': 'status', 'step': 'router', 'message': '🔄 [1/3] Router Agent 호출 중...'}, ensure_ascii=False)}\n\n"
                
                router = RouterAgent()
                loop = asyncio.new_event_loop()
                
                try:
                    router_result = loop.run_until_complete(router.route(message_for_pipeline, history))
                    router_output = router_result
                    
                    function_calls = router_result.get("function_calls", [])
                    for call in function_calls:
                        if call.get("function") == "consult_jungsi":
                            params = call.setdefault("params", {})
                            params.pop("j_scores", None)
                            if active_score_id:
                                params["score_id"] = active_score_id
                    
                    # Router 완료 시 검색 쿼리 상세 정보 포함 (main_agent와 동일)
                    queries_detail = []
                    for call in function_calls:
                        func_name = call.get("function", "")
                        params = call.get("params", {})
                        if func_name == "univ":
                            queries_detail.append({
                                "type": "univ",
                                "university": params.get("university", ""),
                                "query": params.get("query", "")
                            })
                        elif func_name == "consult":
                            queries_detail.append({
                                "type": "consult",
                                "target_univ": params.get("target_univ", []),
                                "query": "성적 분석"
                            })
                    
                    yield f"data: {json.dumps({'type': 'status', 'step': 'router_complete', 'message': f'✅ Router 완료: {len(function_calls)}개 함수 호출', 'detail': {'function_calls': queries_detail, 'count': len(function_calls)}}, ensure_ascii=False)}\n\n"
                    
                    # 2. RAG 검색 실행
                    if function_calls:
                        yield f"data: {json.dumps({'type': 'status', 'step': 'function', 'message': '🔄 [2/3] Functions 실행 중...'}, ensure_ascii=False)}\n\n"
                        
                        # 검색 시작 상세 정보 전송
                        for idx, call in enumerate(function_calls):
                            func_name = call.get("function", "")
                            params = call.get("params", {})
                            if func_name == "univ":
                                univ_name = params.get('university', '')
                                univ_query = params.get('query', '')
                                yield f"data: {json.dumps({'type': 'status', 'step': 'search_start', 'message': f'🔍 검색 중: {univ_name}', 'detail': {'index': idx, 'university': univ_name, 'query': univ_query}}, ensure_ascii=False)}\n\n"
                            elif func_name == "consult":
                                target_univ = params.get('target_univ', [])
                                yield f"data: {json.dumps({'type': 'status', 'step': 'search_start', 'message': '📊 성적 분석 중...', 'detail': {'index': idx, 'type': 'consult', 'target_univ': target_univ}}, ensure_ascii=False)}\n\n"
                        
                        initial_results = loop.run_until_complete(
                            execute_function_calls(function_calls, user_id=user_id)
                        )
                        function_results = initial_results
                        
                        # 검색 완료 상세 정보 추출 (찾은 문서 목록)
                        search_results_detail = []
                        for key, func_result in initial_results.items():
                            if isinstance(func_result, dict) and "chunks" in func_result:
                                university = func_result.get("university", "")
                                doc_titles = func_result.get("document_titles", {})
                                doc_count = func_result.get("count", 0)
                                unique_titles = list(set(doc_titles.values())) if doc_titles else []
                                search_results_detail.append({
                                    "university": university,
                                    "query": func_result.get("query", ""),
                                    "doc_count": doc_count,
                                    "documents": unique_titles[:5]
                                })
                        
                        total_count = sum(r.get("doc_count", 0) for r in search_results_detail)
                        yield f"data: {json.dumps({'type': 'status', 'step': 'search_complete', 'message': f'✅ Functions 완료: {len(initial_results)}개 결과', 'detail': {'results': search_results_detail, 'total_count': total_count}}, ensure_ascii=False)}\n\n"
                    else:
                        initial_results = {}
                        yield f"data: {json.dumps({'type': 'status', 'step': 'function', 'message': 'ℹ️ 함수 호출 없음'}, ensure_ascii=False)}\n\n"
                    
                    # 3. MainAgentThinking으로 분석 및 재질문
                    # (답변 작성하기 로그는 실제 답변 생성 시 main_agent_thinking.py에서 전송)
                    
                    for chunk in generate_thinking_stream(message_for_pipeline, history, initial_results):
                        chunk_type = chunk.get("type")
                        
                        if chunk_type == "log":
                            # Thinking 내부 로그 - step, iteration, detail 정보 포함하여 전송
                            log_data = {
                                'type': 'log',
                                'content': chunk.get('content', ''),
                                'step': chunk.get('step'),
                                'iteration': chunk.get('iteration'),
                                'detail': chunk.get('detail')
                            }
                            yield f"data: {json.dumps(log_data, ensure_ascii=False)}\n\n"
                        
                        elif chunk_type == "text":
                            # 최종 답변 텍스트
                            full_response = chunk.get("content", "")
                            # 청크 단위로 스트리밍 (한 번에 전송)
                            yield f"data: {json.dumps({'type': 'chunk', 'text': full_response}, ensure_ascii=False)}\n\n"
                        
                        elif chunk_type == "done":
                            # 완료 정보 - 출처 정보 철저히 관리
                            citations = chunk.get("citations", [])
                            
                            # citations에서 sources, source_urls 추출
                            sources = []
                            source_urls = []
                            for c in citations:
                                source = c.get("source", "")
                                url = c.get("url", "")
                                # 빈 값이나 유효하지 않은 URL 제외
                                if source and url and url.startswith("http"):
                                    sources.append(source)
                                    source_urls.append(url)
                            
                            # function_results에서 used_chunks 추출 (실제 검색된 청크들)
                            used_chunks = []
                            for key, result in function_results.items():
                                chunks = result.get("chunks", [])
                                doc_titles = result.get("document_titles", {})
                                doc_urls = result.get("document_urls", {})
                                
                                for c in chunks:
                                    doc_id = c.get("document_id")
                                    title = doc_titles.get(doc_id, f"문서 {doc_id}")
                                    url = doc_urls.get(doc_id, "")
                                    
                                    # 유효한 URL만 포함
                                    if url and url.startswith("http"):
                                        used_chunks.append({
                                            "id": c.get("chunk_id", ""),
                                            "content": c.get("content", "")[:200],  # 미리보기용
                                            "title": title,
                                            "source": f"{title} {c.get('page_number', '')}p".strip(),
                                            "file_url": url,
                                            "metadata": {
                                                "page_number": c.get("page_number"),
                                                "document_id": doc_id
                                            }
                                        })
                            
                            timing = {
                                "iterations": chunk.get("iterations", 1),
                                "total_chunks": chunk.get("total_chunks", 0)
                            }
                        
                        elif chunk_type == "error":
                            yield f"data: {json.dumps({'type': 'error', 'message': chunk.get('message', '')}, ensure_ascii=False)}\n\n"
                            return
                
                finally:
                    loop.close()
            
            elif not use_school_record:
                # ========================================
                # 기본 모드: 기존 파이프라인 사용
                # ========================================
                for event in run_orchestration_agent_stream(
                    message_for_pipeline,
                    history,
                    user_id=user_id,
                    score_id=active_score_id,
                ):
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
            conversation_sessions[cache_key] = history[-20:]  # 최근 20개만 유지
            
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
                "used_chunks": used_chunks,
                "thinking_mode": thinking_mode,
                "require_login": require_login,  # 비로그인 3회째 질문 시 True
                "score_id": active_score_id,
            }
            yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
            
            print(f"🟢 [STREAM_V2_END] [{mode_label}] 총 {pipeline_time:.2f}초, {len(full_response)}자")
            
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


@router.post("/v2/stream/continue-after-naesin")
async def chat_stream_continue_after_naesin(
    request: ContinueAfterNaesinRequest,
    authorization: Optional[str] = Header(None),
):
    """
    내신 카드에서 '확인'을 눌렀을 때 호출. 이미 저장된 마지막 사용자 메시지로 답변 생성만 스트리밍.
    사용량 차감 없음 (같은 질문의 연속 요청).
    """
    user, auth_failed = await optional_auth_with_state(authorization)
    if auth_failed or (authorization and authorization.startswith("Bearer ") and user is None):
        raise HTTPException(status_code=401, detail=AUTH_EXPIRED_DETAIL)
    user_id = user["user_id"] if user else None
    if not user_id:
        raise HTTPException(status_code=401, detail="내신 확인 후 답변 생성은 로그인 후 이용할 수 있습니다.")

    session_id = request.session_id
    cache_key = get_cache_key(user_id, session_id)
    if cache_key not in conversation_sessions or not conversation_sessions[cache_key]:
        raise HTTPException(status_code=400, detail="대기 중인 내신 확인이 없습니다.")
    history = conversation_sessions[cache_key]
    if history[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="대기 중인 내신 확인이 없습니다.")

    message = history[-1]["content"]
    score_id = request.score_id

    # 카드에서 수정한 성적이 있으면 프로필에 반영
    if request.grade_summary and user_id:
        gs = request.grade_summary
        try:
            school_grade_input = build_school_grade_input_from_card(
                overall_average=gs.get("overall_average") or gs.get("overallAverage") or "",
                core_average=gs.get("core_average") or gs.get("coreAverage") or "",
                semester_averages=gs.get("semester_averages") or gs.get("semesterAverages") or {},
            )
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    supabase_service.update_user_profile_metadata(
                        user_id, "school_grade_input", school_grade_input
                    )
                )
            finally:
                loop.close()
        except Exception as e:
            print(f"⚠️ continue-after-naesin grade_summary 반영 실패(무시): {e}")
    full_response = ""
    timing = {}
    function_results = {}
    router_output = {}
    sources = []
    source_urls = []
    used_chunks = []

    def generate_continue():
        nonlocal full_response, timing, function_results, router_output, sources, source_urls, used_chunks
        try:
            for event in run_orchestration_agent_stream(
                message,
                history,
                user_id=user_id,
                score_id=score_id,
            ):
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

            history.append({"role": "assistant", "content": full_response})
            conversation_sessions[cache_key] = history[-20:]

            try:
                if not should_skip_logging(user_id=user_id):
                    _save_messages_to_session_chat(
                        user_session=session_id,
                        user_id=user_id,
                        user_content=message,
                        assistant_content=full_response,
                        sources=sources,
                        source_urls=source_urls,
                    )
            except Exception as e:
                print(f"❌ continue-after-naesin 메시지 저장 실패: {e}")

            done_event = {
                "type": "done",
                "response": full_response,
                "timing": timing,
                "router_output": router_output,
                "function_results": function_results,
                "sources": sources,
                "source_urls": source_urls,
                "used_chunks": used_chunks,
                "score_id": score_id,
            }
            yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_continue(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/v2/stream/continue-after-score-confirm")
async def chat_stream_continue_after_score_confirm(
    request: ContinueAfterScoreConfirmRequest,
    authorization: Optional[str] = Header(None),
):
    """
    모의고사 성적 카드에서 '확인'을 눌렀을 때 호출. 마지막 사용자 메시지로 해당 score_id 기준 답변만 스트리밍.
    사용량 차감 없음.
    """
    user, auth_failed = await optional_auth_with_state(authorization)
    if auth_failed or (authorization and authorization.startswith("Bearer ") and user is None):
        raise HTTPException(status_code=401, detail=AUTH_EXPIRED_DETAIL)
    user_id = user["user_id"] if user else None
    if not user_id:
        raise HTTPException(status_code=401, detail="성적 확인 후 답변 생성은 로그인 후 이용할 수 있습니다.")

    session_id = request.session_id
    score_id = request.score_id
    cache_key = get_cache_key(user_id, session_id)
    if cache_key not in conversation_sessions or not conversation_sessions[cache_key]:
        raise HTTPException(status_code=400, detail="대기 중인 성적 확인이 없습니다.")
    history = conversation_sessions[cache_key]
    if history[-1]["role"] != "user":
        raise HTTPException(status_code=400, detail="대기 중인 성적 확인이 없습니다.")

    message = history[-1]["content"]
    full_response = ""
    timing = {}
    function_results = {}
    router_output = {}
    sources = []
    source_urls = []
    used_chunks = []

    def generate_continue():
        nonlocal full_response, timing, function_results, router_output, sources, source_urls, used_chunks
        try:
            for event in run_orchestration_agent_stream(
                message,
                history,
                user_id=user_id,
                score_id=score_id,
            ):
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

            history.append({"role": "assistant", "content": full_response})
            conversation_sessions[cache_key] = history[-20:]
            try:
                if not should_skip_logging(user_id=user_id):
                    _save_messages_to_session_chat(
                        user_session=session_id,
                        user_id=user_id,
                        user_content=message,
                        assistant_content=full_response,
                        sources=sources,
                        source_urls=source_urls,
                    )
            except Exception as e:
                print(f"❌ continue-after-score-confirm 메시지 저장 실패: {e}")

            done_event = {
                "type": "done",
                "response": full_response,
                "timing": timing,
                "router_output": router_output,
                "function_results": function_results,
                "sources": sources,
                "source_urls": source_urls,
                "used_chunks": used_chunks,
                "score_id": score_id,
            }
            yield f"data: {json.dumps(done_event, ensure_ascii=False)}\n\n"
        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate_continue(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
    auth_header = authorization or (http_request.headers.get("authorization") if http_request else None)
    user, auth_failed = await optional_auth_with_state(auth_header)
    if auth_failed or (auth_header and auth_header.startswith("Bearer ") and user is None):
        raise HTTPException(status_code=401, detail=AUTH_EXPIRED_DETAIL)
    user_id = user["user_id"] if user else None
    
    is_allowed, current_count, limit, require_login = await check_and_increment_usage(user_id, client_ip)
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
    
    print(f"📊 API 사용량: {current_count}/{limit}회 (user_id={user_id}, ip={client_ip}, require_login={require_login})")
    
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
            # user_id 기반 캐시 키 사용
            cache_key = get_cache_key(user_id, session_id)
            if cache_key not in conversation_sessions or len(conversation_sessions[cache_key]) == 0:
                db_history = await load_history_from_db(session_id, user_id)
                if db_history:
                    conversation_sessions[cache_key] = db_history
                else:
                    conversation_sessions[cache_key] = []
            history = conversation_sessions[cache_key][-20:]
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
                conversation_sessions[cache_key] = history[-20:]  # 최근 20개만 유지

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
            conversation_sessions[cache_key] = history[-20:]  # 최근 20개만 유지
            
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


@router.post("/v2/score-review/approve")
async def approve_score_review(
    request: ScoreReviewApproveRequest,
    authorization: Optional[str] = Header(None),
):
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    pending = await supabase_service.get_chat_score_pending(
        request.pending_id, session_id=request.session_id
    )
    if not pending:
        raise HTTPException(status_code=404, detail="pending review를 찾을 수 없습니다.")
    if pending.get("status") != "review_required":
        raise HTTPException(status_code=400, detail="이미 처리된 pending review입니다.")

    owner = user_id or f"guest:{request.session_id}"
    title = (request.title or pending.get("title_auto") or "내성적1").strip()
    if title.startswith("@"):
        title = title[1:]
    if len(title) > 10:
        raise HTTPException(status_code=400, detail="성적 제목은 최대 10자입니다.")

    saved = await supabase_service.upsert_user_score_set(
        user_id=owner,
        name=title,
        scores=request.scores or {},
        source_message=pending.get("raw_message") or "",
        title_auto_generated=False,
    )
    if not saved:
        raise HTTPException(status_code=500, detail="성적 저장에 실패했습니다.")

    await supabase_service.resolve_chat_score_pending(
        request.pending_id, status="approved", score_set_id=str(saved["id"])
    )
    return {
        "pending_id": request.pending_id,
        "score_id": saved["id"],
        "score_name": f"@{saved['name']}",
    }


@router.post("/v2/score-review/skip-session")
async def skip_score_review_for_session(
    request: ScoreReviewSkipSessionRequest,
    authorization: Optional[str] = Header(None),
):
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    await supabase_service.set_session_skip_score_review(
        session_id=request.session_id,
        user_id=user_id,
        skip=True,
    )
    if request.pending_id:
        await supabase_service.resolve_chat_score_pending(request.pending_id, status="skipped")
    return {"ok": True, "skip_session": True}


@router.get("/v2/score-sets/suggest")
async def suggest_score_sets(
    q: str = Query(default=""),
    limit: int = Query(default=8, ge=1, le=20),
    session_id: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(None),
):
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    if user_id:
        owner = user_id
    elif session_id:
        owner = f"guest:{session_id}"
    else:
        return {"items": []}

    rows = await supabase_service.list_user_score_sets(owner, keyword=q, limit=limit)
    items = [{"id": row.get("id"), "name": f"@{row.get('name')}"} for row in rows]
    return {"items": items}


@router.get("/v2/score-set/{name}")
async def get_score_set(
    name: str,
    session_id: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(None),
):
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    if user_id:
        owner = user_id
    elif session_id:
        owner = f"guest:{session_id}"
    else:
        raise HTTPException(status_code=400, detail="session_id 또는 로그인 정보가 필요합니다.")

    row = await supabase_service.get_user_score_set_by_name(owner, name)
    if not row:
        raise HTTPException(status_code=404, detail="성적 세트를 찾을 수 없습니다.")
    return {"id": row.get("id"), "name": f"@{row.get('name')}", "scores": row.get("scores", {})}


@router.get("/v2/score-sets")
async def list_score_sets(
    session_id: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(None),
):
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    owner = _resolve_score_owner(user_id, session_id)
    rows = await supabase_service.list_user_score_sets(owner, limit=100, include_scores=True)
    items = [
        {
            "id": row.get("id"),
            "name": f"@{row.get('name')}",
            "scores": row.get("scores", {}),
            "updated_at": row.get("updated_at"),
        }
        for row in rows
    ]
    return {"items": items}


@router.post("/v2/score-sets")
async def create_score_set(
    request: ScoreSetCreateRequest,
    authorization: Optional[str] = Header(None),
):
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    owner = _resolve_score_owner(user_id, request.session_id)

    raw_name = (request.name or "").strip()
    if not raw_name:
        raise HTTPException(status_code=400, detail="성적 이름은 필수입니다.")
    name = raw_name[1:] if raw_name.startswith("@") else raw_name
    if len(name) > 10:
        raise HTTPException(status_code=400, detail="성적 제목은 최대 10자입니다.")

    existing = await supabase_service.get_user_score_set_by_name(owner, name)
    if existing:
        raise HTTPException(status_code=409, detail="이미 같은 이름의 성적이 있습니다.")

    saved = await supabase_service.upsert_user_score_set(
        user_id=owner,
        name=name,
        scores=request.scores or {},
        source_message=None,
        title_auto_generated=False,
    )
    if not saved:
        raise HTTPException(status_code=500, detail="성적 생성에 실패했습니다.")
    return {
        "id": saved.get("id"),
        "name": f"@{saved.get('name')}",
        "scores": saved.get("scores", {}),
        "updated_at": saved.get("updated_at"),
    }


@router.put("/v2/score-sets/{score_set_id}")
async def update_score_set(
    score_set_id: str,
    request: ScoreSetUpdateRequest,
    authorization: Optional[str] = Header(None),
):
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    owner = _resolve_score_owner(user_id, request.session_id)

    target = await supabase_service.get_user_score_set_by_id(score_set_id, user_id=owner)
    if not target:
        raise HTTPException(status_code=404, detail="성적 세트를 찾을 수 없습니다.")

    raw_name = (request.name or "").strip()
    if not raw_name:
        raise HTTPException(status_code=400, detail="성적 이름은 필수입니다.")
    name = raw_name[1:] if raw_name.startswith("@") else raw_name
    if len(name) > 10:
        raise HTTPException(status_code=400, detail="성적 제목은 최대 10자입니다.")

    same_name = await supabase_service.get_user_score_set_by_name(owner, name)
    if same_name and str(same_name.get("id")) != str(score_set_id):
        raise HTTPException(status_code=409, detail="이미 같은 이름의 성적이 있습니다.")

    updated = await supabase_service.update_user_score_set_by_id(
        user_id=owner,
        score_set_id=score_set_id,
        name=name,
        scores=request.scores or {},
    )
    if not updated:
        raise HTTPException(status_code=500, detail="성적 수정에 실패했습니다.")

    return {
        "id": updated.get("id"),
        "name": f"@{updated.get('name')}",
        "scores": updated.get("scores", {}),
        "updated_at": updated.get("updated_at"),
    }


@router.delete("/v2/score-sets/{score_set_id}")
async def delete_score_set(
    score_set_id: str,
    session_id: Optional[str] = Query(default=None),
    authorization: Optional[str] = Header(None),
):
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    owner = _resolve_score_owner(user_id, session_id)

    target = await supabase_service.get_user_score_set_by_id(score_set_id, user_id=owner)
    if not target:
        raise HTTPException(status_code=404, detail="성적 세트를 찾을 수 없습니다.")

    ok = await supabase_service.delete_user_score_set_by_id(owner, score_set_id)
    if not ok:
        raise HTTPException(status_code=500, detail="성적 삭제에 실패했습니다.")
    return {"ok": True}


@router.post("/reset")
async def reset_session(
    session_id: str = "default",
    authorization: Optional[str] = Header(None)
):
    """대화 히스토리 초기화"""
    # 선택적 인증으로 user_id 확인
    user = await optional_auth(authorization)
    user_id = user["user_id"] if user else None
    
    # user_id 기반 캐시 키 사용
    cache_key = get_cache_key(user_id, session_id)
    if cache_key in conversation_sessions:
        del conversation_sessions[cache_key]
    await supabase_service.set_session_skip_score_review(session_id, user_id, False)
    return {"status": "ok", "message": f"세션 {session_id} 초기화 완료"}


@router.get("/agents")
async def get_agents():
    """가용 에이전트 목록 조회"""
    return {"agents": AVAILABLE_AGENTS}
