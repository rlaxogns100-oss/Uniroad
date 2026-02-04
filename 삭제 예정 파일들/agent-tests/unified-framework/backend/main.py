"""
Agent Testing Framework - FastAPI Server
- 개별 에이전트 테스트 (Orchestration, Sub, Final)
- 파이프라인 테스트
- N회 반복 실행
- 구간별 모델 선택
"""

import os
import sys

# 경로 설정을 가장 먼저 수행
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))

# sys.path 설정 (순서 중요)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if os.path.join(PROJECT_ROOT, "backend") not in sys.path:
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import google.generativeai as genai
from dotenv import load_dotenv

# 로컬 모듈 (test_ 접두사로 충돌 방지)
from test_core.test_runner import TestRunner, TestResult
from test_utils.excel_exporter import export_results_to_excel

# 환경 변수 로드
load_dotenv(os.path.join(PROJECT_ROOT, "backend", ".env"))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 스토리지 경로
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
DATASETS_DIR = os.path.join(STORAGE_DIR, "datasets")
PROMPTS_DIR = os.path.join(STORAGE_DIR, "prompts")
RESULTS_DIR = os.path.join(STORAGE_DIR, "results")

# 디렉토리 생성
for d in [DATASETS_DIR, PROMPTS_DIR, RESULTS_DIR]:
    os.makedirs(d, exist_ok=True)

# 사용 가능한 모델 목록
AVAILABLE_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.0-flash",
    "gemini-1.5-pro"
]

app = FastAPI(title="Agent Testing Framework", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Pydantic Models
# ============================================

class TestRequest(BaseModel):
    """테스트 요청"""
    input_data: Dict[str, Any]
    model: str = "gemini-2.5-flash-lite"
    custom_prompt: Optional[str] = None
    iterations: int = 10
    parallel: bool = True


class OrchestrationTestRequest(BaseModel):
    """Orchestration Agent 테스트 요청"""
    message: str
    history: List[Dict[str, str]] = []
    model: str = "gemini-2.5-flash-lite"
    temperature: float = 0.7
    custom_prompt: Optional[str] = None
    iterations: int = 10
    parallel: bool = True


class SubAgentTestRequest(BaseModel):
    """Sub Agent 테스트 요청"""
    execution_plan: List[Dict[str, Any]]
    extracted_scores: Optional[Dict[str, Any]] = None
    model: str = "gemini-2.5-flash-lite"
    temperature: float = 0.7
    iterations: int = 10
    parallel: bool = True


class FinalAgentTestRequest(BaseModel):
    """Final Agent 테스트 요청"""
    user_question: str
    answer_structure: List[Dict[str, Any]]
    sub_agent_results: Dict[str, Any]
    history: List[Dict[str, str]] = []
    model: str = "gemini-2.5-flash-lite"
    temperature: float = 0.7
    custom_prompt: Optional[str] = None
    iterations: int = 10
    parallel: bool = True


class PipelineTestRequest(BaseModel):
    """파이프라인 테스트 요청"""
    message: str
    history: List[Dict[str, str]] = []
    models: Dict[str, str] = {
        "orchestration": "gemini-2.5-flash-lite",
        "sub": "gemini-2.5-flash-lite",
        "final": "gemini-2.5-flash-lite"
    }
    temperatures: Dict[str, float] = {
        "orchestration": 0.7,
        "sub": 0.7,
        "final": 0.7
    }
    custom_prompts: Optional[Dict[str, Optional[str]]] = None
    iterations: int = 10
    parallel: bool = False  # 기본값: 순차 실행 (정확한 속도 측정)


class DatasetSaveRequest(BaseModel):
    """데이터셋 저장 요청"""
    name: str
    agent_type: str
    data: Dict[str, Any]
    description: str = ""


class PromptSaveRequest(BaseModel):
    """프롬프트 저장 요청"""
    name: str
    agent_type: str
    prompt: str
    description: str = ""


# ============================================
# 에이전트 래퍼 함수 (프로덕션 코드 래핑)
# ============================================

async def run_orchestration_with_model(input_data: Dict[str, Any], model: str, temperature: float = 0.7) -> Dict[str, Any]:
    """
    Orchestration Agent 실행 (모델 선택 가능)
    프로덕션 코드를 직접 수정하지 않고 래핑
    """
    try:
        # 프로덕션 코드에서 프롬프트 가져오기
        from backend.services.multi_agent.orchestration_agent import (
            ORCHESTRATION_SYSTEM_PROMPT,
            format_agents_for_prompt,
            parse_orchestration_response
        )
        
        system_prompt = input_data.get("custom_prompt") or ORCHESTRATION_SYSTEM_PROMPT.format(
            agents=format_agents_for_prompt()
        )
        
        # 테스트용 모델로 실행 (temperature 설정 포함)
        test_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt,
            generation_config={"temperature": temperature}
        )
        
        # 대화 이력 구성
        message = input_data.get("message", "")
        history = input_data.get("history", [])
        
        gemini_history = []
        for msg in history:
            role = "user" if msg.get("role") == "user" else "model"
            content = msg.get("content", "")
            gemini_history.append({"role": role, "parts": [content]})
        
        chat = test_model.start_chat(history=gemini_history)
        response = await chat.send_message_async(message)
        
        result = parse_orchestration_response(response.text)
        result["status"] = "success" if "error" not in result else "error"
        result["model_used"] = model
        result["temperature"] = temperature
        
        # 토큰 사용량
        if hasattr(response, 'usage_metadata'):
            result["token_usage"] = getattr(response.usage_metadata, 'total_token_count', 0)
        
        # metadata 추가
        result["metadata"] = {
            "message": message,
            "history": history
        }
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "model_used": model,
            "temperature": temperature
        }


async def run_sub_agents_with_model(input_data: Dict[str, Any], model: str, temperature: float = 0.7) -> Dict[str, Any]:
    """
    Sub Agents 실행 (모델 선택 가능)
    Note: Sub Agents는 프로덕션 코드를 사용하므로 temperature는 로깅용으로만 사용
    """
    try:
        from backend.services.multi_agent.sub_agents import (
            get_agent,
            UniversityAgent,
            ConsultingAgent,
            TeacherAgent
        )
        from backend.services.multi_agent.score_preprocessing import build_preprocessed_query
        
        execution_plan = input_data.get("execution_plan", [])
        extracted_scores = input_data.get("extracted_scores")
        
        results = {}
        
        for step in execution_plan:
            step_num = step.get("step")
            agent_name = step.get("agent")
            query = step.get("query")
            
            # 모델명을 지정하여 에이전트 생성
            if "컨설팅" in agent_name:
                agent = ConsultingAgent(model_name=model)
                # 성적 전처리
                if extracted_scores:
                    query = build_preprocessed_query(extracted_scores, query)
                result = await agent.execute(query, extracted_scores=extracted_scores)
            elif "선생님" in agent_name:
                agent = TeacherAgent(model_name=model)
                result = await agent.execute(query)
            else:
                # 대학 에이전트
                for univ in UniversityAgent.SUPPORTED_UNIVERSITIES:
                    if univ in agent_name:
                        agent = UniversityAgent(univ, model_name=model)
                        result = await agent.execute(query)
                        break
                else:
                    result = {"status": "error", "error": f"Unknown agent: {agent_name}"}
            
            result["model_used"] = model
            result["temperature"] = temperature
            results[f"Step{step_num}_Result"] = result
        
        return {
            "status": "success",
            "results": results,
            "model_used": model,
            "temperature": temperature,
            "metadata": {
                "execution_plan": execution_plan,
                "extracted_scores": extracted_scores
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "model_used": model,
            "temperature": temperature
        }


async def run_final_agent_with_model(input_data: Dict[str, Any], model: str, temperature: float = 0.7) -> Dict[str, Any]:
    """
    Final Agent 실행 (모델 선택 가능)
    """
    try:
        from backend.services.multi_agent.agent_prompts import get_final_agent_prompt
        
        user_question = input_data.get("user_question", "")
        answer_structure = input_data.get("answer_structure", [])
        sub_agent_results = input_data.get("sub_agent_results", {})
        history = input_data.get("history", [])
        custom_prompt = input_data.get("custom_prompt")
        
        # 히스토리 병합
        if history:
            history_text = "\n".join([
                f"[{m.get('role', 'user').capitalize()}] {m.get('content', '')[:200]}"
                for m in history[-10:]
            ])
            user_question_with_context = f"## 이전 대화 맥락\n{history_text}\n\n## 현재 질문\n{user_question}"
        else:
            user_question_with_context = user_question
        
        # Sub Agent 결과 포맷팅
        results_text = ""
        all_citations = []
        for step_key, result in sub_agent_results.items():
            agent_name = result.get("agent", "Unknown")
            status = result.get("status", "unknown")
            content = result.get("result", "결과 없음")
            sources = result.get("sources", [])
            citations = result.get("citations", [])
            
            all_citations.extend(citations)
            source_info = f"\n[출처: {', '.join(sources)}]" if sources else ""
            results_text += f"\n### {step_key} ({agent_name})\n상태: {status}\n\n{content}{source_info}\n"
        
        # Answer Structure 포맷팅
        structure_text = ""
        for section in answer_structure:
            sec_num = section.get("section", "?")
            sec_type = section.get("type", "unknown")
            source = section.get("source_from", "없음")
            instruction = section.get("instruction", "")
            structure_text += f"\n**섹션 {sec_num}** [{sec_type}]\n- 참조: {source}\n- 지시: {instruction}\n"
        
        # 프롬프트 생성
        if custom_prompt:
            prompt = custom_prompt.format(
                user_question=user_question_with_context,
                structure_text=structure_text,
                results_text=results_text,
                all_citations=json.dumps(all_citations, ensure_ascii=False)
            )
        else:
            prompt = get_final_agent_prompt(
                "prompt5",
                user_question=user_question_with_context,
                structure_text=structure_text,
                results_text=results_text,
                all_citations=all_citations
            )
        
        # 테스트용 모델로 실행 (temperature 적용)
        test_model = genai.GenerativeModel(model_name=model)
        response = test_model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "max_output_tokens": 4096}
        )
        
        result = {
            "status": "success",
            "final_answer": response.text,
            "model_used": model,
            "temperature": temperature,
            "metadata": {
                "user_question": user_question,
                "history": history,
                "answer_structure": answer_structure,
                "sub_agent_results": sub_agent_results
            }
        }
        
        if hasattr(response, 'usage_metadata'):
            result["token_usage"] = getattr(response.usage_metadata, 'total_token_count', 0)
        
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "model_used": model,
            "temperature": temperature
        }


# ============================================
# API Endpoints
# ============================================

@app.get("/")
async def root():
    return {"status": "ok", "message": "Agent Testing Framework"}


@app.get("/health")
async def health():
    return {"status": "ok", "api_key_configured": bool(GEMINI_API_KEY)}


@app.get("/models")
async def get_models():
    """사용 가능한 모델 목록"""
    return {"models": AVAILABLE_MODELS}


# ============================================
# 테스트 엔드포인트
# ============================================

@app.post("/test/orchestration")
async def test_orchestration(request: OrchestrationTestRequest):
    """Orchestration Agent 테스트"""
    runner = TestRunner(iterations=request.iterations, parallel=request.parallel)
    
    input_data = {
        "message": request.message,
        "history": request.history,
        "custom_prompt": request.custom_prompt
    }
    
    # temperature를 포함한 래퍼 함수
    async def agent_with_temp(data, model):
        return await run_orchestration_with_model(data, model, request.temperature)
    
    results = await runner.run(
        agent_func=agent_with_temp,
        input_data=input_data,
        agent_type="orchestration",
        model=request.model
    )
    
    # 결과 변환
    results_dicts = [r.to_dict() for r in results]
    
    # 통계 계산
    success_count = sum(1 for r in results if r.success)
    times = [r.processing_time_ms for r in results]
    
    return {
        "status": "completed",
        "iterations": request.iterations,
        "model": request.model,
        "results": results_dicts,
        "statistics": {
            "total": len(results),
            "success": success_count,
            "failure": len(results) - success_count,
            "success_rate": round(success_count / len(results) * 100, 1) if results else 0,
            "avg_time_ms": round(sum(times) / len(times), 2) if times else 0,
            "max_time_ms": round(max(times), 2) if times else 0,
            "min_time_ms": round(min(times), 2) if times else 0
        }
    }


@app.post("/test/sub")
async def test_sub_agents(request: SubAgentTestRequest):
    """Sub Agent 테스트"""
    runner = TestRunner(iterations=request.iterations, parallel=request.parallel)
    
    input_data = {
        "execution_plan": request.execution_plan,
        "extracted_scores": request.extracted_scores
    }
    
    # temperature를 포함한 래퍼 함수
    async def agent_with_temp(data, model):
        return await run_sub_agents_with_model(data, model, request.temperature)
    
    results = await runner.run(
        agent_func=agent_with_temp,
        input_data=input_data,
        agent_type="sub_agents",
        model=request.model
    )
    
    results_dicts = [r.to_dict() for r in results]
    success_count = sum(1 for r in results if r.success)
    times = [r.processing_time_ms for r in results]
    
    return {
        "status": "completed",
        "iterations": request.iterations,
        "model": request.model,
        "results": results_dicts,
        "statistics": {
            "total": len(results),
            "success": success_count,
            "failure": len(results) - success_count,
            "success_rate": round(success_count / len(results) * 100, 1) if results else 0,
            "avg_time_ms": round(sum(times) / len(times), 2) if times else 0,
            "max_time_ms": round(max(times), 2) if times else 0,
            "min_time_ms": round(min(times), 2) if times else 0
        }
    }


@app.post("/test/final")
async def test_final_agent(request: FinalAgentTestRequest):
    """Final Agent 테스트"""
    runner = TestRunner(iterations=request.iterations, parallel=request.parallel)
    
    input_data = {
        "user_question": request.user_question,
        "answer_structure": request.answer_structure,
        "sub_agent_results": request.sub_agent_results,
        "history": request.history,
        "custom_prompt": request.custom_prompt
    }
    
    # temperature를 포함한 래퍼 함수
    async def agent_with_temp(data, model):
        return await run_final_agent_with_model(data, model, request.temperature)
    
    results = await runner.run(
        agent_func=agent_with_temp,
        input_data=input_data,
        agent_type="final_agent",
        model=request.model
    )
    
    results_dicts = [r.to_dict() for r in results]
    success_count = sum(1 for r in results if r.success)
    times = [r.processing_time_ms for r in results]
    
    return {
        "status": "completed",
        "iterations": request.iterations,
        "model": request.model,
        "results": results_dicts,
        "statistics": {
            "total": len(results),
            "success": success_count,
            "failure": len(results) - success_count,
            "success_rate": round(success_count / len(results) * 100, 1) if results else 0,
            "avg_time_ms": round(sum(times) / len(times), 2) if times else 0,
            "max_time_ms": round(max(times), 2) if times else 0,
            "min_time_ms": round(min(times), 2) if times else 0
        }
    }


@app.post("/test/pipeline")
async def test_pipeline(request: PipelineTestRequest):
    """전체 파이프라인 테스트 (병렬 실행)"""
    import time as time_module
    import asyncio
    
    # 에이전트별 temperature와 프롬프트 추출
    temps = request.temperatures or {}
    orch_temp = temps.get("orchestration", 0.7)
    sub_temp = temps.get("sub", 0.7)
    final_temp = temps.get("final", 0.7)
    
    prompts = request.custom_prompts or {}
    orch_prompt = prompts.get("orchestration")
    final_prompt = prompts.get("final")
    
    async def run_single_pipeline(run_id: int) -> Dict[str, Any]:
        """단일 파이프라인 실행"""
        run_result = {
            "run_id": run_id,
            "agent_type": "pipeline",
            "timestamp": datetime.now().isoformat(),
            "total_time_ms": 0,
            "success": True,
            "error": "",
            # 상세 데이터
            "input_message": request.message,
            "input_history": request.history,
            "orchestration_output": {},
            "sub_agents_output": {},
            "final_output": ""
        }
        
        total_start = time_module.time()
        
        try:
            # Stage 1: Orchestration
            print(f"[Run #{run_id}] Orchestration 시작...")
            orch_start = time_module.time()
            orch_input = {
                "message": request.message,
                "history": request.history,
                "custom_prompt": orch_prompt
            }
            orch_model = request.models.get("orchestration", "gemini-2.5-flash-lite")
            orch_result = await run_orchestration_with_model(orch_input, orch_model, orch_temp)
            orch_time = (time_module.time() - orch_start) * 1000
            print(f"[Run #{run_id}] Orchestration 완료 ({orch_time:.0f}ms)")
            
            run_result["orchestration_output"] = {
                "time_ms": round(orch_time, 2),
                "model": orch_model,
                "temperature": orch_temp,
                "success": orch_result.get("status") != "error",
                "user_intent": orch_result.get("user_intent", ""),
                "extracted_scores": orch_result.get("extracted_scores"),
                "execution_plan": orch_result.get("execution_plan", []),
                "answer_structure": orch_result.get("answer_structure", []),
                "raw_output": orch_result
            }
            
            if orch_result.get("status") == "error":
                run_result["success"] = False
                run_result["error"] = f"Orchestration failed: {orch_result.get('error', 'unknown')}"
                run_result["total_time_ms"] = round((time_module.time() - total_start) * 1000, 2)
                return run_result
            
            # Stage 2: Sub Agents
            print(f"[Run #{run_id}] Sub Agents 시작...")
            sub_start = time_module.time()
            execution_plan = orch_result.get("execution_plan", [])
            sub_input = {
                "execution_plan": execution_plan,
                "extracted_scores": None
            }
            sub_model = request.models.get("sub", "gemini-2.5-flash-lite")
            sub_result = await run_sub_agents_with_model(sub_input, sub_model, sub_temp)
            sub_time = (time_module.time() - sub_start) * 1000
            print(f"[Run #{run_id}] Sub Agents 완료 ({sub_time:.0f}ms)")
            
            run_result["sub_agents_output"] = {
                "time_ms": round(sub_time, 2),
                "model": sub_model,
                "temperature": sub_temp,
                "success": sub_result.get("status") != "error",
                "execution_plan": execution_plan,
                "results": sub_result.get("results", {}),
                "raw_output": sub_result
            }
            
            # Stage 3: Final Agent
            print(f"[Run #{run_id}] Final Agent 시작...")
            final_start = time_module.time()
            final_input = {
                "user_question": request.message,
                "answer_structure": orch_result.get("answer_structure", []),
                "sub_agent_results": sub_result.get("results", {}),
                "history": request.history,
                "custom_prompt": final_prompt
            }
            final_model = request.models.get("final", "gemini-2.5-flash-lite")
            final_result = await run_final_agent_with_model(final_input, final_model, final_temp)
            final_time = (time_module.time() - final_start) * 1000
            print(f"[Run #{run_id}] Final Agent 완료 ({final_time:.0f}ms)")
            
            run_result["final_output"] = final_result.get("final_answer", "")
            run_result["final_agent_details"] = {
                "time_ms": round(final_time, 2),
                "model": final_model,
                "temperature": final_temp,
                "success": final_result.get("status") == "success"
            }
            
            if final_result.get("status") != "success":
                run_result["success"] = False
                run_result["error"] = f"Final Agent failed: {final_result.get('error', 'unknown')}"
                
        except Exception as e:
            import traceback
            run_result["success"] = False
            run_result["error"] = f"{str(e)}\n{traceback.format_exc()}"
        
        run_result["total_time_ms"] = round((time_module.time() - total_start) * 1000, 2)
        print(f"[Run #{run_id}] 완료 (총 {run_result['total_time_ms']:.0f}ms, 성공: {run_result['success']})")
        return run_result
    
    # 병렬 또는 순차 실행
    execution_mode = "병렬" if request.parallel else "순차"
    print(f"\n{'='*50}")
    print(f"Pipeline 테스트 시작: {request.iterations}회 {execution_mode} 실행")
    print(f"{'='*50}")
    
    if request.parallel:
        # 병렬 실행 (빠르지만 개별 속도 부정확)
        tasks = [run_single_pipeline(i + 1) for i in range(request.iterations)]
        all_results = await asyncio.gather(*tasks)
    else:
        # 순차 실행 (정확한 속도 측정)
        all_results = []
        for i in range(request.iterations):
            result = await run_single_pipeline(i + 1)
            all_results.append(result)
    
    print(f"\n{'='*50}")
    print(f"Pipeline 테스트 완료: {len(all_results)}회 실행됨 ({execution_mode})")
    print(f"{'='*50}\n")
    
    # 결과 형식 (상세 정보 포함)
    formatted_results = []
    for r in all_results:
        orch = r.get("orchestration_output", {})
        sub = r.get("sub_agents_output", {})
        
        formatted_results.append({
            "run_id": r["run_id"],
            "agent_type": "pipeline",
            "model": json.dumps(request.models),
            "processing_time_ms": r["total_time_ms"],
            "success": r["success"],
            "timestamp": r["timestamp"],
            "error": r.get("error", ""),
            # 상세 정보 (엑셀용)
            "input_message": r.get("input_message", ""),
            "input_history": json.dumps(r.get("input_history", []), ensure_ascii=False),
            "orchestration_user_intent": orch.get("user_intent", ""),
            "orchestration_extracted_scores": json.dumps(orch.get("extracted_scores", {}), ensure_ascii=False, indent=2) if orch.get("extracted_scores") else "",
            "orchestration_execution_plan": json.dumps(orch.get("execution_plan", []), ensure_ascii=False, indent=2),
            "orchestration_answer_structure": json.dumps(orch.get("answer_structure", []), ensure_ascii=False, indent=2),
            "orchestration_time_ms": orch.get("time_ms", 0),
            "sub_agents_results": json.dumps(sub.get("results", {}), ensure_ascii=False, indent=2),
            "sub_agents_time_ms": sub.get("time_ms", 0),
            "final_output": r.get("final_output", ""),
            "final_time_ms": r.get("final_agent_details", {}).get("time_ms", 0),
            "output": r.get("final_output", ""),
            "metadata": {
                "temperatures": temps
            }
        })
    
    # 통계 계산
    success_count = sum(1 for r in all_results if r.get("success", False))
    times = [r.get("total_time_ms", 0) for r in all_results]
    
    return {
        "status": "completed",
        "iterations": request.iterations,
        "models": request.models,
        "temperatures": temps,
        "results": formatted_results,
        "statistics": {
            "total": len(all_results),
            "success": success_count,
            "failure": len(all_results) - success_count,
            "success_rate": round(success_count / len(all_results) * 100, 1) if all_results else 0,
            "avg_time_ms": round(sum(times) / len(times), 2) if times else 0,
            "max_time_ms": round(max(times), 2) if times else 0,
            "min_time_ms": round(min(times), 2) if times else 0
        }
    }


# ============================================
# 결과 내보내기
# ============================================

class ExportRequest(BaseModel):
    """Excel 내보내기 요청"""
    results: List[Dict[str, Any]]
    status: Optional[str] = None
    iterations: Optional[int] = None
    model: Optional[Any] = None
    models: Optional[Dict[str, str]] = None
    temperatures: Optional[Any] = None
    statistics: Optional[Dict[str, Any]] = None


@app.post("/export/excel")
async def export_to_excel(request: ExportRequest, test_name: str = "test"):
    """테스트 결과를 Excel로 내보내기"""
    try:
        filepath = export_results_to_excel(request.results, RESULTS_DIR, test_name)
        filename = os.path.basename(filepath)
        return {"status": "success", "filename": filename, "path": filepath}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/results/{filename}")
async def download_result(filename: str):
    """결과 파일 다운로드"""
    filepath = os.path.join(RESULTS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(filepath, filename=filename)


@app.get("/results")
async def list_results():
    """결과 파일 목록"""
    files = []
    for f in os.listdir(RESULTS_DIR):
        if f.endswith(".xlsx"):
            filepath = os.path.join(RESULTS_DIR, f)
            files.append({
                "filename": f,
                "created_at": datetime.fromtimestamp(os.path.getctime(filepath)).isoformat(),
                "size_bytes": os.path.getsize(filepath)
            })
    return {"results": sorted(files, key=lambda x: x["created_at"], reverse=True)}


# ============================================
# 데이터셋 관리
# ============================================

@app.get("/datasets")
async def list_datasets():
    """저장된 데이터셋 목록"""
    datasets = []
    for f in os.listdir(DATASETS_DIR):
        if f.endswith(".json"):
            filepath = os.path.join(DATASETS_DIR, f)
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    datasets.append({
                        "id": f.replace(".json", ""),
                        "name": data.get("name", f),
                        "agent_type": data.get("agent_type", "unknown"),
                        "description": data.get("description", ""),
                        "created_at": data.get("created_at", "")
                    })
            except:
                pass
    return {"datasets": sorted(datasets, key=lambda x: x.get("created_at", ""), reverse=True)}


@app.post("/datasets")
async def save_dataset(request: DatasetSaveRequest):
    """데이터셋 저장"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in request.name if c.isalnum() or c in " -_").strip()[:50]
    filename = f"{timestamp}_{safe_name}.json"
    filepath = os.path.join(DATASETS_DIR, filename)
    
    data = {
        "name": request.name,
        "agent_type": request.agent_type,
        "description": request.description,
        "data": request.data,
        "created_at": datetime.now().isoformat()
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return {"status": "success", "id": filename.replace(".json", ""), "filename": filename}


@app.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str):
    """데이터셋 조회"""
    filepath = os.path.join(DATASETS_DIR, f"{dataset_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    """데이터셋 삭제"""
    filepath = os.path.join(DATASETS_DIR, f"{dataset_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
    return {"status": "deleted"}


# ============================================
# 프롬프트 관리
# ============================================

@app.get("/prompts")
async def list_prompts():
    """저장된 프롬프트 목록"""
    prompts = []
    for f in os.listdir(PROMPTS_DIR):
        if f.endswith(".json"):
            filepath = os.path.join(PROMPTS_DIR, f)
            try:
                with open(filepath, 'r', encoding='utf-8') as file:
                    data = json.load(file)
                    prompts.append({
                        "id": f.replace(".json", ""),
                        "name": data.get("name", f),
                        "agent_type": data.get("agent_type", "unknown"),
                        "description": data.get("description", ""),
                        "created_at": data.get("created_at", "")
                    })
            except:
                pass
    return {"prompts": sorted(prompts, key=lambda x: x.get("created_at", ""), reverse=True)}


@app.get("/prompts/sub_agents")
async def get_sub_agent_prompts():
    """Sub Agent들의 프롬프트 조회 (읽기 전용) - 구체적 경로 먼저 정의"""
    return {
        "teacher": {
            "name": "선생님 Agent",
            "description": "학습 계획 및 멘탈 관리 조언",
            "prompt": """당신은 20년 경력의 입시 전문 선생님입니다.
학생의 상황을 파악하고 현실적이면서도 희망을 잃지 않는 조언을 해주세요.

## 조언 원칙
1. 현실적인 목표 설정 (무리한 목표는 지적)
2. 구체적인 시간표와 계획 제시
3. 멘탈 관리 조언 포함
4. 단기/중기/장기 목표 구분
5. 포기하지 않도록 격려하되, 거짓 희망은 주지 않기

## 출력 형식
- 자연어로 친근하게 작성
- 필요시 리스트나 표 사용
- 존댓말 사용""",
            "modifiable": True
        },
        "university": {
            "name": "대학 Agent (RAG 기반)",
            "description": "Supabase에서 대학별 문서 검색 및 정보 추출",
            "prompts": {
                "document_filter": """다음 문서들의 요약본을 읽고, 질문에 답변하는데 필요한 문서만 선택하세요.

질문: "{query}"

문서 목록:
{docs_summary_text}

선택 기준:
1. 질문에 답변하는데 필요한 정보가 포함된 문서만 선택
2. 최대 3개까지만 선택

답변 형식:
관련 문서가 있으면: 번호만 쉼표로 구분 (예: 1, 3)
관련 문서가 없으면: 없음""",
                "info_extraction": """다음 문서에서 질문에 답변하는데 필요한 핵심 정보만 추출하세요.

질문: {query}

사용 가능한 출처 목록:
{sources_list}

문서 내용:
{full_content}

출력 규칙:
1. 핵심 정보만 간결하게 추출
2. 수치 데이터는 정확하게 유지
3. 각 정보가 어느 문서에서 왔는지 [출처: 문서명] 형식으로 반드시 표시
4. 여러 문서에서 정보를 가져왔다면, 각 정보마다 해당 출처를 표시
5. 마지막에 "출처: 문서1, 문서2, ..." 형태로 요약하지 말고, 정보마다 개별 표시
6. JSON이 아닌 자연어로 작성"""
            },
            "modifiable": False
        },
        "consulting": {
            "name": "컨설팅 Agent",
            "description": "성적 기반 합격 가능성 분석 및 대학 추천",
            "prompt": "로컬 계산 기반 (환산점수 계산) + Supabase 입결 데이터 조회",
            "modifiable": False
        }
    }


@app.post("/prompts")
async def save_prompt(request: PromptSaveRequest):
    """프롬프트 저장"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in request.name if c.isalnum() or c in " -_").strip()[:50]
    filename = f"{timestamp}_{safe_name}.json"
    filepath = os.path.join(PROMPTS_DIR, filename)
    
    data = {
        "name": request.name,
        "agent_type": request.agent_type,
        "description": request.description,
        "prompt": request.prompt,
        "created_at": datetime.now().isoformat()
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return {"status": "success", "id": filename.replace(".json", ""), "filename": filename}


@app.get("/prompts/{prompt_id}")
async def get_prompt(prompt_id: str):
    """프롬프트 조회"""
    filepath = os.path.join(PROMPTS_DIR, f"{prompt_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


@app.delete("/prompts/{prompt_id}")
async def delete_prompt(prompt_id: str):
    """프롬프트 삭제"""
    filepath = os.path.join(PROMPTS_DIR, f"{prompt_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
    return {"status": "deleted"}


@app.get("/prompts/default/{agent_type}")
async def get_default_prompt(agent_type: str):
    """기본 프롬프트 조회 (프로덕션 코드에서 로드)"""
    try:
        if agent_type == "orchestration":
            from backend.services.multi_agent.orchestration_agent import (
                ORCHESTRATION_SYSTEM_PROMPT,
                format_agents_for_prompt
            )
            return {
                "agent_type": agent_type,
                "prompt": ORCHESTRATION_SYSTEM_PROMPT.format(agents=format_agents_for_prompt())
            }
        elif agent_type == "final":
            from backend.services.multi_agent.agent_prompts import get_final_agent_prompt
            # 플레이스홀더 포함 프롬프트 반환
            return {
                "agent_type": agent_type,
                "prompt": """[Final Agent System Prompt - prompt5]

플레이스홀더:
- {user_question}: 사용자 질문
- {structure_text}: Answer Structure
- {results_text}: Sub Agent 결과
- {all_citations}: 출처 정보

실제 프롬프트는 get_final_agent_prompt() 함수에서 생성됩니다."""
            }
        else:
            return {"agent_type": agent_type, "prompt": "No default prompt for this agent type"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 서버 실행
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8095)
