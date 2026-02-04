"""
TestRunner - N회 반복 실행 및 결과 수집
- 병렬/순차 실행 지원
- 각 단계별 타이밍 측정
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
import traceback


@dataclass
class TestResult:
    """단일 테스트 결과"""
    run_id: int
    agent_type: str
    model: str
    step: str = ""
    input_summary: str = ""
    output: Any = None
    processing_time_ms: float = 0
    success: bool = False
    timestamp: str = ""
    token_usage: int = 0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "agent_type": self.agent_type,
            "model": self.model,
            "step": self.step,
            "input_summary": self.input_summary,
            "output": self.output,
            "processing_time_ms": self.processing_time_ms,
            "success": self.success,
            "timestamp": self.timestamp,
            "token_usage": self.token_usage,
            "error": self.error,
            "metadata": self.metadata
        }


class TestRunner:
    """
    테스트 실행기
    
    Usage:
        runner = TestRunner(iterations=10)
        results = await runner.run(
            agent_func=my_agent_function,
            input_data={"message": "hello"},
            agent_type="orchestration",
            model="gemini-2.5-flash-lite"
        )
    """
    
    def __init__(self, iterations: int = 10, parallel: bool = True):
        """
        Args:
            iterations: 반복 실행 횟수 (기본 10회)
            parallel: True면 병렬 실행, False면 순차 실행
        """
        self.iterations = iterations
        self.parallel = parallel
    
    async def run(
        self,
        agent_func: Callable,
        input_data: Dict[str, Any],
        agent_type: str,
        model: str,
        step: str = ""
    ) -> List[TestResult]:
        """
        에이전트 함수를 N회 실행하고 결과 수집
        
        Args:
            agent_func: 실행할 에이전트 함수 (async)
            input_data: 입력 데이터
            agent_type: 에이전트 유형
            model: 사용할 모델명
            step: 단계 (파이프라인일 경우)
            
        Returns:
            TestResult 리스트
        """
        input_summary = self._summarize_input(input_data)
        
        if self.parallel:
            results = await self._run_parallel(
                agent_func, input_data, agent_type, model, step, input_summary
            )
        else:
            results = await self._run_sequential(
                agent_func, input_data, agent_type, model, step, input_summary
            )
        
        return results
    
    async def _run_parallel(
        self,
        agent_func: Callable,
        input_data: Dict[str, Any],
        agent_type: str,
        model: str,
        step: str,
        input_summary: str
    ) -> List[TestResult]:
        """병렬 실행"""
        tasks = []
        for i in range(self.iterations):
            task = self._run_single(
                agent_func, input_data, agent_type, model, step, input_summary, i + 1
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외를 TestResult로 변환
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(TestResult(
                    run_id=i + 1,
                    agent_type=agent_type,
                    model=model,
                    step=step,
                    input_summary=input_summary,
                    output=None,
                    processing_time_ms=0,
                    success=False,
                    timestamp=datetime.now().isoformat(),
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _run_sequential(
        self,
        agent_func: Callable,
        input_data: Dict[str, Any],
        agent_type: str,
        model: str,
        step: str,
        input_summary: str
    ) -> List[TestResult]:
        """순차 실행"""
        results = []
        for i in range(self.iterations):
            try:
                result = await self._run_single(
                    agent_func, input_data, agent_type, model, step, input_summary, i + 1
                )
                results.append(result)
            except Exception as e:
                results.append(TestResult(
                    run_id=i + 1,
                    agent_type=agent_type,
                    model=model,
                    step=step,
                    input_summary=input_summary,
                    output=None,
                    processing_time_ms=0,
                    success=False,
                    timestamp=datetime.now().isoformat(),
                    error=str(e)
                ))
        return results
    
    async def _run_single(
        self,
        agent_func: Callable,
        input_data: Dict[str, Any],
        agent_type: str,
        model: str,
        step: str,
        input_summary: str,
        run_id: int
    ) -> TestResult:
        """단일 실행"""
        start_time = time.time()
        timestamp = datetime.now().isoformat()
        
        try:
            # 에이전트 함수 실행
            result = await agent_func(input_data, model)
            
            end_time = time.time()
            processing_time_ms = (end_time - start_time) * 1000
            
            # 결과에서 출력 추출
            output = result.get("output") or result.get("result") or result.get("final_answer") or result
            success = result.get("status", "success") == "success"
            token_usage = result.get("token_usage", 0)
            
            return TestResult(
                run_id=run_id,
                agent_type=agent_type,
                model=model,
                step=step,
                input_summary=input_summary,
                output=output,
                processing_time_ms=processing_time_ms,
                success=success,
                timestamp=timestamp,
                token_usage=token_usage,
                metadata=result.get("metadata", {})
            )
            
        except Exception as e:
            end_time = time.time()
            processing_time_ms = (end_time - start_time) * 1000
            
            return TestResult(
                run_id=run_id,
                agent_type=agent_type,
                model=model,
                step=step,
                input_summary=input_summary,
                output=None,
                processing_time_ms=processing_time_ms,
                success=False,
                timestamp=timestamp,
                error=f"{str(e)}\n{traceback.format_exc()}"
            )
    
    def _summarize_input(self, input_data: Dict[str, Any]) -> str:
        """입력 데이터 요약"""
        if "message" in input_data:
            msg = input_data["message"]
            return msg[:100] + "..." if len(msg) > 100 else msg
        elif "user_question" in input_data:
            q = input_data["user_question"]
            return q[:100] + "..." if len(q) > 100 else q
        elif "query" in input_data:
            q = input_data["query"]
            return q[:100] + "..." if len(q) > 100 else q
        else:
            return str(input_data)[:100]


class PipelineRunner:
    """
    파이프라인 테스트 실행기
    Orchestration -> Sub Agents -> Final Agent 전체 흐름 테스트
    """
    
    def __init__(self, iterations: int = 10):
        self.iterations = iterations
    
    async def run_pipeline(
        self,
        input_data: Dict[str, Any],
        orchestration_func: Callable,
        sub_agents_func: Callable,
        final_agent_func: Callable,
        models: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        전체 파이프라인 N회 실행
        
        Args:
            input_data: 초기 입력 (message, history)
            orchestration_func: Orchestration Agent 함수
            sub_agents_func: Sub Agents 실행 함수
            final_agent_func: Final Agent 함수
            models: 에이전트별 모델 설정 {"orchestration": "...", "sub": "...", "final": "..."}
            
        Returns:
            각 실행의 전체 결과 리스트
        """
        all_results = []
        
        for i in range(self.iterations):
            run_result = {
                "run_id": i + 1,
                "timestamp": datetime.now().isoformat(),
                "stages": {},
                "total_time_ms": 0,
                "success": True
            }
            
            total_start = time.time()
            
            try:
                # Stage 1: Orchestration
                orch_start = time.time()
                orch_result = await orchestration_func(
                    input_data, 
                    models.get("orchestration", "gemini-2.5-flash-lite")
                )
                orch_time = (time.time() - orch_start) * 1000
                
                run_result["stages"]["orchestration"] = {
                    "time_ms": orch_time,
                    "success": orch_result.get("status") != "error",
                    "output": orch_result
                }
                
                if orch_result.get("status") == "error":
                    run_result["success"] = False
                    run_result["error"] = "Orchestration failed"
                    all_results.append(run_result)
                    continue
                
                # Stage 2: Sub Agents
                sub_start = time.time()
                sub_result = await sub_agents_func(
                    orch_result,
                    models.get("sub", "gemini-2.5-flash-lite")
                )
                sub_time = (time.time() - sub_start) * 1000
                
                run_result["stages"]["sub_agents"] = {
                    "time_ms": sub_time,
                    "success": True,
                    "output": sub_result
                }
                
                # Stage 3: Final Agent
                final_start = time.time()
                final_result = await final_agent_func(
                    input_data,
                    orch_result,
                    sub_result,
                    models.get("final", "gemini-2.5-flash-lite")
                )
                final_time = (time.time() - final_start) * 1000
                
                run_result["stages"]["final_agent"] = {
                    "time_ms": final_time,
                    "success": final_result.get("status") == "success",
                    "output": final_result
                }
                
                if final_result.get("status") != "success":
                    run_result["success"] = False
                
            except Exception as e:
                run_result["success"] = False
                run_result["error"] = str(e)
            
            run_result["total_time_ms"] = (time.time() - total_start) * 1000
            all_results.append(run_result)
        
        return all_results
