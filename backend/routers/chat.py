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

        # 로그 수집 (현재 질문에만 기반 - 이전 로그와 격리)
        logs.clear()  # 이전 로그 완전히 제거
        
        def log_and_emit(msg: str):
            print(msg)
            logs.append(msg)

        # 현재 질문 정보를 명확히 표시
        log_and_emit(f"{'#'*80}")
        log_and_emit(f"# 🚀 멀티에이전트 파이프라인 시작")
        log_and_emit(f"# ⏰ 시작 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log_and_emit(f"# 세션: {session_id}")
        log_and_emit(f"# 📝 현재 질문: {message}")
        log_and_emit(f"# Request ID: {request_id}")
        log_and_emit(f"{'#'*80}")

        # 세션 히스토리 로드 (Supabase와 동기화)
        # UUID 형식의 세션 ID는 Supabase 세션, 그 외는 인메모리만 사용
        import re
        is_uuid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', session_id, re.I)
        
        if is_uuid:
            # Supabase 세션인 경우 conversation_context에서 로드
            try:
                context_response = supabase_service.client.table("conversation_context")\
                    .select("context")\
                    .eq("session_id", session_id)\
                    .execute()
                
                if context_response.data and len(context_response.data) > 0:
                    history = context_response.data[0].get("context", [])
                    conversation_sessions[session_id] = history
                    log_and_emit(f"   💾 Supabase에서 대화 히스토리 로드: {len(history)}개 메시지")
                else:
                    # Supabase에 컨텍스트가 없으면 빈 배열로 시작
                    history = []
                    conversation_sessions[session_id] = []
                    log_and_emit(f"   📝 새 Supabase 세션 시작")
            except Exception as e:
                # Supabase 조회 실패 시 인메모리로 폴백
                print(f"⚠️ Supabase 컨텍스트 조회 실패: {e}")
                if session_id not in conversation_sessions:
                    conversation_sessions[session_id] = []
                history = conversation_sessions[session_id]
        else:
            # 인메모리 세션 (로컬 개발용)
            if session_id not in conversation_sessions:
                conversation_sessions[session_id] = []
            history = conversation_sessions[session_id]

        # ========================================
        # 1단계: Orchestration Agent
        # ========================================
        log_and_emit("")
        log_and_emit("="*80)
        log_and_emit("🎯 [1단계] Orchestration Agent 실행")
        log_and_emit("="*80)
        
        # 사용자에게 진행 상황을 더 자세히 표시 (실제 값 포함)
        log_and_emit(f"📝 받은 질문: \"{message}\"")
        log_and_emit("🔍 질문 분석을 시작합니다...")
        
        # 질문에서 키워드 추출하여 표시
        keywords = []
        universities = ['서울대', '연세대', '고려대', '성균관대', '경희대', '서강대', 'SKY', '스카이']
        years = ['2024', '2025', '2026', '2027']
        admission_types = ['정시', '수시', '입결', '모집요강', '전형', '커트라인']
        
        for univ in universities:
            if univ in message:
                keywords.append(univ)
        for year in years:
            if year in message:
                keywords.append(f"{year}학년도")
        for atype in admission_types:
            if atype in message:
                keywords.append(atype)
        
        if keywords:
            log_and_emit(f"   → 키워드 발견: {', '.join(keywords)}")
        
        # 성적 정보 감지
        import re
        grade_patterns = [
            r'(\d)[등급]',
            r'국어\s*(\d)',
            r'수학\s*(\d)',
            r'영어\s*(\d)',
            r'탐구\s*(\d)',
            r'(\d{2,3})점',
        ]
        has_grades = any(re.search(p, message) for p in grade_patterns)
        if has_grades:
            log_and_emit("   → 성적 정보 감지됨 - 합격 분석 가능")
        
        log_and_emit("   → AI가 최적의 답변 전략을 수립 중...")
        
        # 실시간 로그 콜백 설정 (현재 요청에만 적용)
        from services.multi_agent import orchestration_agent, sub_agents, final_agent
        
        # 각 요청마다 새로운 콜백 설정 (이전 로그와 격리)
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
        user_intent = orchestration_result.get('user_intent', 'N/A')
        
        log_and_emit("")
        log_and_emit(f"📋 Orchestration 결과:")
        log_and_emit(f"   사용자 의도: {user_intent}")
        log_and_emit(f"   실행 계획: {len(execution_plan)}개 step")
        log_and_emit(f"   답변 구조: {len(answer_structure)}개 섹션")
        
        # 사용자 의도를 명확히 표시 (프론트엔드 파싱용)
        if user_intent and user_intent != 'N/A':
            log_and_emit(f"💡 사용자 의도 파악: {user_intent}")
        
        # extracted_scores 로그 - 상세 정보 포함
        if extracted_scores:
            log_and_emit(f"   📊 추출된 성적: {len(extracted_scores)}개 과목")
            # 성적 상세 정보를 사용자 친화적으로 표시
            score_details = []
            for subject, info in extracted_scores.items():
                if isinstance(info, dict):
                    grade = info.get('등급') or info.get('grade')
                    score = info.get('점수') or info.get('score') or info.get('표준점수')
                    percentile = info.get('백분위') or info.get('percentile')
                    if grade:
                        score_details.append(f"{subject} {grade}등급")
                    elif score:
                        score_details.append(f"{subject} {score}점")
                    elif percentile:
                        score_details.append(f"{subject} 백분위 {percentile}")
                elif isinstance(info, (int, float, str)):
                    score_details.append(f"{subject}: {info}")
            if score_details:
                log_and_emit(f"   → 성적 분석: {', '.join(score_details[:5])}")
                if len(score_details) > 5:
                    log_and_emit(f"   → 외 {len(score_details) - 5}개 과목")
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
                history = history[-20:]
                conversation_sessions[session_id] = history
            
            # Supabase 세션인 경우 conversation_context에 저장
            import re
            is_uuid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', session_id, re.I)
            if is_uuid:
                try:
                    supabase_service.client.table("conversation_context")\
                        .upsert({
                            "session_id": session_id,
                            "context": history,
                        })\
                        .execute()
                except Exception as e:
                    print(f"⚠️ Supabase 컨텍스트 저장 실패: {e}")

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
        log_and_emit("🤖 [2단계] Sub Agents 실행")
        log_and_emit("="*80)
        log_and_emit(f"📋 실행 계획: {len(execution_plan)}개 Step")
        
        for step in execution_plan:
            step_num = step.get('step', '?')
            agent_name = step.get('agent', 'Unknown')
            query = step.get('query', '')
            query_preview = query[:80] + "..." if len(query) > 80 else query
            log_and_emit(f"   Step {step_num}: {agent_name}")
            log_and_emit(f"      📝 Query: {query_preview}")
        
        log_and_emit("")
        log_and_emit("   🚀 병렬 실행 시작...")
        
        sub_start = time.time()
        sub_agent_results = await execute_sub_agents(
            execution_plan,
            extracted_scores=extracted_scores,
            user_message=message
        )
        sub_time = time.time() - sub_start
        
        log_and_emit("")
        log_and_emit("   📊 Sub Agents 실행 결과:")
        for key, result in sub_agent_results.items():
            status = result.get('status', 'unknown')
            agent = result.get('agent', 'Unknown')
            sources_count = len(result.get('sources', []))
            exec_time = result.get('execution_time', 0)
            status_icon = "✅" if status == "success" else "❌"
            sources_info = f"출처 {sources_count}개" if sources_count > 0 else "출처 없음"
            log_and_emit(f"      {status_icon} {key} ({agent}): {status} ({sources_info}, ⏱️ {exec_time:.2f}초)")
        log_and_emit(f"   ⏱️  총 Sub Agents 처리 시간: {sub_time:.2f}초")
        log_and_emit("="*80)

        # ========================================
        # 3단계: Final Agent - 최종 답변 생성
        # ========================================
        log_and_emit("")
        log_and_emit("="*80)
        log_and_emit("📝 [3단계] Final Agent 실행")
        log_and_emit("="*80)
        log_and_emit(f"   📋 답변 구조: {len(answer_structure)}개 섹션")
        for idx, section in enumerate(answer_structure[:5], 1):  # 상위 5개만 표시
            section_title = section.get('title', '제목 없음') or section.get('section', '섹션')
            log_and_emit(f"      {idx}. {section_title}")
        if len(answer_structure) > 5:
            log_and_emit(f"      ... 외 {len(answer_structure) - 5}개 섹션")
        
        log_and_emit("")
        log_and_emit("   ✍️  최종 답변 작성 중...")
        
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
            history = history[-20:]
            conversation_sessions[session_id] = history
        
        # Supabase 세션인 경우 conversation_context에 저장
        import re
        is_uuid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', session_id, re.I)
        if is_uuid:
            try:
                supabase_service.client.table("conversation_context")\
                    .upsert({
                        "session_id": session_id,
                        "context": history,
                    })\
                    .execute()
                log_and_emit(f"   💾 Supabase에 대화 히스토리 저장 완료")
            except Exception as e:
                print(f"⚠️ Supabase 컨텍스트 저장 실패: {e}")
                # 저장 실패해도 계속 진행

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
        
        # 로그 콜백 초기화 (다음 요청과 격리)
        orchestration_agent.set_log_callback(None)
        sub_agents.set_log_callback(None)
        final_agent.set_log_callback(None)
        
        print(f"🟢 [REQUEST_END] {request_id}\n")

        return ChatResponse(
            response=final_answer,
            raw_answer=raw_answer,  # ✅ 원본 답변 추가
            sources=sources,
            source_urls=source_urls,
            used_chunks=final_result.get("used_chunks", []),  # 사용된 청크 추가
            orchestration_result=orchestration_result,
            sub_agent_results=sub_agent_results,
            metadata=final_result.get("metadata", {}),
            logs=logs  # 로그 추가
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
        pipeline_active = True  # 파이프라인 활성 상태
        
        try:
            session_id = request.session_id
            message = request.message
            
            # 중복 호출 방지 체크 및 시간 측정 시작
            import time
            pipeline_start = time.time()
            request_id = f"{session_id}:{message}:{int(time.time())}"
            print(f"\n🔵 [STREAM_REQUEST_START] {request_id}")

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
            
            # 로그를 실시간으로 전송하는 태스크 (백그라운드)
            async def stream_logs_background():
                """백그라운드에서 로그를 계속 읽어서 즉시 전송"""
                while pipeline_active:
                    try:
                        # 매우 짧은 타임아웃으로 빠른 응답
                        msg = await asyncio.wait_for(log_queue.get(), timeout=0.01)
                        yield f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"
                    except asyncio.TimeoutError:
                        # 큐가 비어있으면 잠시 대기 후 계속
                        await asyncio.sleep(0.01)
                        continue
                    except Exception as e:
                        print(f"로그 스트리밍 오류: {e}")
                        break
                
                # 파이프라인 종료 후 남은 로그 처리
                while not log_queue.empty():
                    try:
                        msg = log_queue.get_nowait()
                        yield f"data: {json.dumps({'type': 'log', 'message': msg})}\n\n"
                    except:
                        break

            # 로그 초기화 (현재 질문에만 기반)
            logs.clear()
            
            yield send_log(f"{'#'*80}")
            yield send_log(f"# 🚀 멀티에이전트 파이프라인 시작")
            yield send_log(f"# ⏰ 시작 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            yield send_log(f"# 세션: {session_id}")
            yield send_log(f"# 📝 현재 질문: {message}")
            yield send_log(f"# Request ID: {request_id}")
            yield send_log(f"{'#'*80}")

            # 세션 히스토리 로드 (Supabase와 동기화)
            import re
            is_uuid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', session_id, re.I)
            
            if is_uuid:
                # Supabase 세션인 경우 conversation_context에서 로드
                try:
                    context_response = supabase_service.client.table("conversation_context")\
                        .select("context")\
                        .eq("session_id", session_id)\
                        .execute()
                    
                    if context_response.data and len(context_response.data) > 0:
                        history = context_response.data[0].get("context", [])
                        conversation_sessions[session_id] = history
                        yield send_log(f"   💾 Supabase에서 대화 히스토리 로드: {len(history)}개 메시지")
                    else:
                        history = []
                        conversation_sessions[session_id] = []
                        yield send_log(f"   📝 새 Supabase 세션 시작")
                except Exception as e:
                    print(f"⚠️ Supabase 컨텍스트 조회 실패: {e}")
                    if session_id not in conversation_sessions:
                        conversation_sessions[session_id] = []
                    history = conversation_sessions[session_id]
            else:
                # 인메모리 세션 (로컬 개발용)
                if session_id not in conversation_sessions:
                    conversation_sessions[session_id] = []
                history = conversation_sessions[session_id]

            # ========================================
            # 1단계: Orchestration Agent
            # ========================================
            yield send_log("")
            yield send_log("="*80)
            yield send_log("🎯 [1단계] Orchestration Agent 실행")
            yield send_log("="*80)
            yield send_log(f"📝 받은 질문: \"{message}\"")
            yield send_log("🔍 질문 분석을 시작합니다...")
            
            # 질문에서 키워드 추출하여 즉시 표시
            keywords = []
            universities = ['서울대', '연세대', '고려대', '성균관대', '경희대', '서강대', 'SKY', '스카이']
            years = ['2024', '2025', '2026', '2027', '2028']
            admission_types = ['정시', '수시', '입결', '모집요강', '전형', '커트라인', '변경사항', '요강']
            
            for univ in universities:
                if univ in message:
                    keywords.append(univ)
            for year in years:
                if year in message:
                    keywords.append(f"{year}학년도")
            for atype in admission_types:
                if atype in message:
                    keywords.append(atype)
            
            if keywords:
                yield send_log(f"   → 키워드 발견: {', '.join(keywords)}")
            
            # 성적 정보 감지
            grade_patterns = [
                r'(\d)[등급]',
                r'국어\s*(\d)',
                r'수학\s*(\d)',
                r'영어\s*(\d)',
                r'탐구\s*(\d)',
                r'(\d{2,3})점',
            ]
            has_grades = any(re.search(p, message) for p in grade_patterns)
            if has_grades:
                yield send_log("   → 성적 정보 감지됨 - 합격 분석 가능")
            
            yield send_log("   → AI가 최적의 답변 전략을 수립 중...")
            yield send_log(f"💭 이전 대화: {len(history)}개 메시지")
            
            # Agent들이 로그를 찍을 때마다 큐에 추가
            from services.multi_agent import orchestration_agent, sub_agents, final_agent
            
            orchestration_agent.set_log_callback(log_callback)
            sub_agents.set_log_callback(log_callback)
            final_agent.set_log_callback(log_callback)
            
            # Orchestration Agent 실행 (백그라운드)
            orch_start = time.time()
            async def run_orch():
                return await run_orchestration_agent(message, history)
            
            orch_task = asyncio.create_task(run_orch())
            
            # 로그를 실시간으로 스트리밍 (Orchestration Agent 실행 중)
            # 매우 짧은 타임아웃으로 빠른 응답 (0.01초)
            while not orch_task.done():
                try:
                    log_msg = await asyncio.wait_for(log_queue.get(), timeout=0.01)
                    yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                except asyncio.TimeoutError:
                    # 태스크가 완료되었는지 확인
                    if orch_task.done():
                        break
                    # 태스크가 아직 실행 중이면 계속 대기
                    await asyncio.sleep(0.01)
                    continue
            
            # 남은 로그 즉시 처리
            while not log_queue.empty():
                try:
                    log_msg = log_queue.get_nowait()
                    yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                except:
                    break
            
            orchestration_result = orch_task.result()
            orch_time = time.time() - orch_start

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
            yield send_log(f"📋 [Orchestration 결과]")
            
            # 사용자 의도 상세 표시
            user_intent = orchestration_result.get('user_intent', 'N/A')
            if user_intent and user_intent != 'N/A':
                short_intent = user_intent[:80] + '...' if len(user_intent) > 80 else user_intent
                yield send_log(f"   💡 파악된 의도: {short_intent}")
            
            # 실행 계획 상세 표시
            if execution_plan:
                yield send_log(f"   📝 실행 계획: {len(execution_plan)}개 단계")
                for idx, step in enumerate(execution_plan[:3], 1):  # 최대 3개만 표시
                    agent_name = step.get('agent', 'Unknown')
                    step_query = step.get('query', '')[:50]
                    yield send_log(f"      {idx}. {agent_name}: \"{step_query}...\"")
                if len(execution_plan) > 3:
                    yield send_log(f"      ... 외 {len(execution_plan) - 3}개 단계")
            
            # 답변 구조 상세 표시
            if answer_structure:
                yield send_log(f"   📋 답변 구조: {len(answer_structure)}개 섹션")
                for idx, section in enumerate(answer_structure[:4], 1):  # 최대 4개만 표시
                    section_title = section.get('section', section.get('title', 'Unknown'))
                    yield send_log(f"      {idx}. {section_title}")
            
            # 추출된 성적 상세 표시
            if extracted_scores:
                yield send_log(f"   📊 추출된 성적:")
                scores_list = extracted_scores.get('과목별_성적', extracted_scores)
                if isinstance(scores_list, dict):
                    for subject, score_info in list(scores_list.items())[:4]:  # 최대 4개
                        if isinstance(score_info, dict):
                            grade = score_info.get('등급', score_info.get('grade', ''))
                            percentile = score_info.get('백분위', score_info.get('percentile', ''))
                            if grade:
                                yield send_log(f"      • {subject}: {grade}등급 (백분위 {percentile})")
                            else:
                                yield send_log(f"      • {subject}: {score_info}")
            
            # 즉시 응답 체크
            if direct_response:
                yield send_log(f"   ⚡ 즉시 응답 모드")
            
            yield send_log(f"   ⏱️ 분석 시간: {orch_time:.2f}초")
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
                    history = history[-20:]
                    conversation_sessions[session_id] = history
                
                # Supabase 세션인 경우 conversation_context에 저장
                import re
                is_uuid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', session_id, re.I)
                if is_uuid:
                    try:
                        supabase_service.client.table("conversation_context")\
                            .upsert({
                                "session_id": session_id,
                                "context": history,
                            })\
                            .execute()
                    except Exception as e:
                        print(f"⚠️ Supabase 컨텍스트 저장 실패: {e}")

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
                
                # 로그 콜백 초기화 (다음 요청과 격리)
                orchestration_agent.set_log_callback(None)
                sub_agents.set_log_callback(None)
                final_agent.set_log_callback(None)
                
                # 파이프라인 종료
                pipeline_active = False
                
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
            yield send_log("🤖 [2단계] Sub Agents 실행")
            yield send_log("="*80)
            yield send_log(f"📋 실행 계획: {len(execution_plan)}개 Step")
            
            for step in execution_plan:
                step_num = step.get('step', '?')
                agent_name = step.get('agent', 'Unknown')
                query = step.get('query', '')
                query_preview = query[:80] + "..." if len(query) > 80 else query
                yield send_log(f"   Step {step_num}: {agent_name}")
                yield send_log(f"      📝 Query: {query_preview}")
            
            yield send_log("")
            yield send_log("   🚀 병렬 실행 시작...")
            
            # Sub Agents 실행 (백그라운드)
            sub_start = time.time()
            async def run_subs():
                return await execute_sub_agents(
                    execution_plan,
                    extracted_scores=extracted_scores,
                    user_message=message
                )
            
            subs_task = asyncio.create_task(run_subs())
            
            # 큐에서 로그를 읽어서 스트리밍 (실시간 전송)
            max_wait_time = 180.0  # 최대 3분 대기
            wait_start = time.time()
            while not subs_task.done():
                # 최대 대기 시간 초과 체크
                if time.time() - wait_start > max_wait_time:
                    yield send_log("⚠️ Sub Agents 처리 시간이 초과되었습니다. 계속 진행합니다...")
                    break
                    
                try:
                    # 매우 짧은 타임아웃으로 빠른 응답 (실시간 스트리밍)
                    log_msg = await asyncio.wait_for(log_queue.get(), timeout=0.01)
                    yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                except asyncio.TimeoutError:
                    # 태스크가 완료되었는지 확인
                    if subs_task.done():
                        break
                    # 태스크가 아직 실행 중이면 계속 대기
                    await asyncio.sleep(0.01)
                    continue
            
            # 남은 로그 즉시 처리
            while not log_queue.empty():
                try:
                    log_msg = log_queue.get_nowait()
                    yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                except:
                    break
            
            sub_agent_results = subs_task.result()
            sub_time = time.time() - sub_start
            
            yield send_log("")
            yield send_log(f"📋 [Sub Agents 결과 요약]")
            
            for key, result in sub_agent_results.items():
                status = result.get('status', 'unknown')
                agent = result.get('agent', 'Unknown')
                sources = result.get('sources', [])
                exec_time = result.get('execution_time', 0)
                status_icon = "✅" if status == "success" else "❌"
                
                yield send_log(f"{status_icon} {agent}:")
                
                # 에이전트 종류에 따라 결과물 표시
                if '대학' in agent or 'University' in agent:
                    # 대학 에이전트: 발견된 문서 표시
                    if sources:
                        yield send_log(f"   📚 발견된 자료: {len(sources)}개")
                        for idx, source in enumerate(sources[:2], 1):  # 최대 2개 표시
                            short_source = source[:40] + '...' if len(source) > 40 else source
                            yield send_log(f"      {idx}. {short_source}")
                        if len(sources) > 2:
                            yield send_log(f"      ... 외 {len(sources) - 2}개")
                    
                    # 핵심 발견 내용 (result에서 추출)
                    content = result.get('content', result.get('summary', ''))
                    if content and isinstance(content, str) and len(content) > 50:
                        # 첫 100자 정도만 표시
                        preview = content[:100].replace('\n', ' ').strip()
                        yield send_log(f"   💡 핵심 정보: \"{preview}...\"")
                
                elif '컨설팅' in agent or 'Consulting' in agent:
                    # 컨설팅 에이전트: 계산된 점수 표시
                    content = result.get('content', '')
                    
                    # 환산 점수 정보 추출 (정규화된 성적에서)
                    if isinstance(content, dict):
                        normalized = content.get('학생_정규화_성적', content)
                        if isinstance(normalized, dict):
                            # 대학별 환산 점수 표시
                            for univ in ['서울대', '연세대', '고려대', '경희대', '서강대']:
                                key_name = f"{univ}_환산점수"
                                if key_name in normalized:
                                    scores = normalized[key_name]
                                    if isinstance(scores, dict):
                                        for track, score_data in list(scores.items())[:1]:  # 첫 번째만
                                            if isinstance(score_data, dict) and score_data.get('계산_가능'):
                                                final_score = score_data.get('최종점수', 'N/A')
                                                yield send_log(f"   📊 {univ} {track}: {final_score}점")
                    
                    # 합격 가능성 요약
                    summary = result.get('summary', '')
                    if summary and len(summary) > 20:
                        preview = summary[:80].replace('\n', ' ').strip()
                        yield send_log(f"   💡 분석 결과: \"{preview}...\"")
                
                elif '선생님' in agent or 'Teacher' in agent:
                    # 선생님 에이전트: 조언 내용 표시
                    content = result.get('content', result.get('summary', ''))
                    if content and isinstance(content, str) and len(content) > 30:
                        preview = content[:80].replace('\n', ' ').strip()
                        yield send_log(f"   💡 조언: \"{preview}...\"")
                
                yield send_log(f"   ⏱️ 처리 시간: {exec_time:.2f}초")
            
            yield send_log(f"")
            yield send_log(f"   🎯 총 Sub Agents 처리 시간: {sub_time:.2f}초")
            yield send_log("="*80)

            # ========================================
            # 3단계: Final Agent - 최종 답변 생성
            # ========================================
            yield send_log("")
            yield send_log("="*80)
            yield send_log("📝 [3단계] Final Agent 실행")
            yield send_log("="*80)
            yield send_log(f"   📋 답변 구조: {len(answer_structure)}개 섹션")
            for idx, section in enumerate(answer_structure[:5], 1):  # 상위 5개만 표시
                section_title = section.get('title', '제목 없음') or section.get('section', '섹션')
                yield send_log(f"      {idx}. {section_title}")
            if len(answer_structure) > 5:
                yield send_log(f"      ... 외 {len(answer_structure) - 5}개 섹션")
            
            yield send_log("")
            yield send_log("   ✍️  최종 답변 작성 중...")
            
            # Final Agent 실행 (백그라운드) - 스트리밍 답변 지원
            final_start = time.time()
            streaming_answer_chunks = []  # 스트리밍 답변 청크 수집
            
            # 스트리밍 콜백 함수
            def stream_answer_chunk(chunk: str):
                """답변 청크를 큐에 추가하여 실시간 전송"""
                streaming_answer_chunks.append(chunk)
                try:
                    log_queue.put_nowait(f"__STREAM_ANSWER__:{chunk}")
                except:
                    pass
            
            async def run_final():
                return await generate_final_answer(
                    user_question=message,
                    answer_structure=answer_structure,
                    sub_agent_results=sub_agent_results,
                    history=history,
                    stream_callback=stream_answer_chunk  # 스트리밍 콜백 전달
                )
            
            final_task = asyncio.create_task(run_final())
            
            # 큐에서 로그와 답변 청크를 읽어서 스트리밍 (실시간 전송)
            max_wait_time = 180.0  # 최대 3분 대기
            wait_start = time.time()
            while not final_task.done():
                # 최대 대기 시간 초과 체크
                if time.time() - wait_start > max_wait_time:
                    yield send_log("⚠️ Final Agent 처리 시간이 초과되었습니다. 계속 진행합니다...")
                    break
                    
                try:
                    # 매우 짧은 타임아웃으로 빠른 응답 (실시간 스트리밍)
                    log_msg = await asyncio.wait_for(log_queue.get(), timeout=0.01)
                    
                    # 답변 스트리밍 청크인지 확인
                    if log_msg.startswith("__STREAM_ANSWER__:"):
                        chunk = log_msg.replace("__STREAM_ANSWER__:", "")
                        yield f"data: {json.dumps({'type': 'answer_chunk', 'chunk': chunk})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                except asyncio.TimeoutError:
                    # 태스크가 완료되었는지 확인
                    if final_task.done():
                        break
                    # 태스크가 아직 실행 중이면 계속 대기
                    await asyncio.sleep(0.01)
                    continue
            
            # 남은 로그와 답변 청크 즉시 처리
            while not log_queue.empty():
                try:
                    log_msg = log_queue.get_nowait()
                    if log_msg.startswith("__STREAM_ANSWER__:"):
                        chunk = log_msg.replace("__STREAM_ANSWER__:", "")
                        yield f"data: {json.dumps({'type': 'answer_chunk', 'chunk': chunk})}\n\n"
                    else:
                        yield f"data: {json.dumps({'type': 'log', 'message': log_msg})}\n\n"
                except:
                    break
            
            final_result = await final_task
            final_time = time.time() - final_start

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
                history = history[-20:]
                conversation_sessions[session_id] = history
            
            # Supabase 세션인 경우 conversation_context에 저장
            import re
            is_uuid = re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', session_id, re.I)
            if is_uuid:
                try:
                    supabase_service.client.table("conversation_context")\
                        .upsert({
                            "session_id": session_id,
                            "context": history,
                        })\
                        .execute()
                    yield send_log(f"   💾 Supabase에 대화 히스토리 저장 완료")
                except Exception as e:
                    print(f"⚠️ Supabase 컨텍스트 저장 실패: {e}")
                    # 저장 실패해도 계속 진행

            # 채팅 로그 저장
            await supabase_service.insert_chat_log(
                message,
                final_answer,
                is_fact_mode=len(sources) > 0
            )

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
            
            # 로그 콜백 초기화 (다음 요청과 격리)
            orchestration_agent.set_log_callback(None)
            sub_agents.set_log_callback(None)
            final_agent.set_log_callback(None)
            
            # 파이프라인 종료
            pipeline_active = False
            
            print(f"🟢 [STREAM_REQUEST_END] {request_id}\n")

            # 최종 응답 전송
            result = ChatResponse(
                response=final_answer,
                raw_answer=raw_answer,  # ✅ 원본 답변 추가
                sources=sources,
                source_urls=source_urls,
                used_chunks=used_chunks,  # 사용된 청크 추가
                orchestration_result=orchestration_result,
                sub_agent_results=sub_agent_results,
                metadata=final_result.get("metadata", {}),
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
