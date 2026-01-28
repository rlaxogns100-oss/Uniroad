"""
채팅 API 라우터 (멀티에이전트 기반)
전체 파이프라인: Orchestration Agent → Sub Agents → Final Agent → 최종 답변
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import asyncio
import json

from services.supabase_client import supabase_service
from services.multi_agent import (
    run_orchestration_agent,
    execute_sub_agents,
    generate_final_answer,
    AVAILABLE_AGENTS
)
from utils.timing_logger import TimingLogger

router = APIRouter()

# 실시간 로그를 위한 큐
log_queues: Dict[str, asyncio.Queue] = {}

# 세션별 대화 히스토리 (메모리)
conversation_sessions: Dict[str, List[Dict[str, Any]]] = {}


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
    orchestration_result: Optional[Dict[str, Any]] = None
    sub_agent_results: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    logs: List[str] = []


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    멀티에이전트 기반 채팅 메시지 처리

    파이프라인:
    1. Orchestration Agent → Execution Plan + Answer Structure
    2. Sub Agents 실행 → 결과 수집
    3. Final Agent → 최종 답변 생성
    """
    logs = []
    
    try:
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

        # 세션 히스토리 초기화
        if session_id not in conversation_sessions:
            conversation_sessions[session_id] = []

        history = conversation_sessions[session_id]

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
        orchestration_result = await run_orchestration_agent(message, history)
        orch_time = time.time() - orch_start

        if "error" in orchestration_result:
            error_msg = f"❌ Orchestration 오류: {orchestration_result.get('error')}"
            log_and_emit(error_msg)
            return ChatResponse(
                response="죄송합니다. 질문 분석 중 오류가 발생했습니다. 다시 시도해주세요.",
                sources=[],
                source_urls=[],
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
            
            # 대화 이력에 추가
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": direct_response})

            # 최근 10턴만 유지
            if len(history) > 20:
                conversation_sessions[session_id] = history[-20:]

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

            return ChatResponse(
                response=direct_response,
                raw_answer=direct_response,
                sources=[],
                source_urls=[],
                used_chunks=[],
                orchestration_result=orchestration_result,
                sub_agent_results=None,
                metadata={"immediate_response": True, "pipeline_time": pipeline_time}
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

        # 대화 이력에 추가
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": final_answer})

        # 최근 10턴만 유지
        if len(history) > 20:
            conversation_sessions[session_id] = history[-20:]

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

        return ChatResponse(
            response=final_answer,
            raw_answer=raw_answer,  # ✅ 원본 답변 추가
            sources=sources,
            source_urls=source_urls,
            used_chunks=final_result.get("used_chunks", []),  # 사용된 청크 추가
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


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    멀티에이전트 기반 채팅 메시지 처리 (스트리밍)
    
    파이프라인:
    1. Orchestration Agent → Execution Plan + Answer Structure
    2. Sub Agents 실행 → 결과 수집
    3. Final Agent → 최종 답변 생성
    """
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

            # 세션 히스토리 초기화
            if session_id not in conversation_sessions:
                conversation_sessions[session_id] = []

            history = conversation_sessions[session_id]
            timing_logger.mark("history_loaded")

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
            
            # Orchestration Agent 실행 (백그라운드)
            orch_start = time.time()
            timing_logger.mark("orch_start", orch_start)
            
            async def run_orch():
                return await run_orchestration_agent(message, history, timing_logger)
            
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
                
                # 대화 이력에 추가
                history.append({"role": "user", "content": message})
                history.append({"role": "assistant", "content": direct_response})

                # 최근 10턴만 유지
                if len(history) > 20:
                    conversation_sessions[session_id] = history[-20:]

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
                    orchestration_result=orchestration_result,
                    sub_agent_results=None,
                    metadata={"immediate_response": True, "pipeline_time": pipeline_time},
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

            # 대화 이력에 추가
            history.append({"role": "user", "content": message})
            history.append({"role": "assistant", "content": final_answer})

            # 최근 10턴만 유지
            if len(history) > 20:
                conversation_sessions[session_id] = history[-20:]
            
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


@router.post("/agents")
async def add_agent(agent: Dict[str, Any]):
    """새 Sub Agent 추가 (런타임)"""
    from services.multi_agent.orchestration_agent import AVAILABLE_AGENTS as agents_list
    
    if "name" not in agent or "description" not in agent:
        raise HTTPException(status_code=400, detail="name과 description은 필수입니다")

    if any(a["name"] == agent["name"] for a in agents_list):
        raise HTTPException(status_code=400, detail=f"이미 존재하는 에이전트: {agent['name']}")

    new_agent = {"name": agent["name"], "description": agent["description"]}
    agents_list.append(new_agent)
    return {"message": "에이전트 추가 완료", "agent": new_agent}


@router.delete("/agents/{agent_name}")
async def delete_agent(agent_name: str):
    """Sub Agent 삭제 (런타임)"""
    from services.multi_agent.orchestration_agent import AVAILABLE_AGENTS as agents_list
    
    original_len = len(agents_list)
    agents_list[:] = [a for a in agents_list if a["name"] != agent_name]

    if len(agents_list) == original_len:
        raise HTTPException(status_code=404, detail=f"에이전트를 찾을 수 없음: {agent_name}")

    return {"message": "에이전트 삭제 완료", "agent_name": agent_name}
