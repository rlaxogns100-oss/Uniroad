"""
초상세 타이밍 측정 및 로깅 유틸리티

질문-답변 플로우의 모든 단계별 시간을 매우 상세하게 측정하고 로깅합니다.
- 각 Agent의 전체 시간
- LLM 호출 내부: 프롬프트 준비, API 전송, 응답 대기, 파싱
- 함수 실행 시간
- DB 쿼리 시간
- 두 번 이상 호출 시 각각 따로 기록
"""

import time
import json
import csv
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


class LLMCallTiming:
    """개별 LLM 호출 타이밍"""
    def __init__(self, call_id: str, model: str = "gemini"):
        self.call_id = call_id
        self.model = model
        self.timing = {
            "call_start": 0,           # 호출 시작
            "prompt_ready": 0,          # 프롬프트 준비 완료
            "api_request_sent": 0,      # API 요청 전송
            "first_token_received": 0,  # 첫 토큰 수신 (스트리밍)
            "api_response_received": 0, # API 응답 완료
            "response_parsed": 0,       # 응답 파싱 완료
            "call_complete": 0,         # 호출 완료
        }
        self.metadata = {
            "prompt_length": 0,
            "response_length": 0,
            "token_count": 0,
        }
    
    def mark(self, checkpoint: str, value: Optional[float] = None):
        self.timing[checkpoint] = value if value is not None else time.time()
    
    def set_metadata(self, key: str, value: Any):
        self.metadata[key] = value
    
    def get_durations(self) -> Dict[str, float]:
        """세부 소요 시간 계산"""
        def elapsed(start: str, end: str) -> float:
            s = self.timing.get(start, 0)
            e = self.timing.get(end, 0)
            return e - s if s and e else 0
        
        return {
            "total": elapsed("call_start", "call_complete"),
            "prompt_preparation": elapsed("call_start", "prompt_ready"),
            "api_request_send": elapsed("prompt_ready", "api_request_sent"),
            "api_wait": elapsed("api_request_sent", "api_response_received"),
            "response_parsing": elapsed("api_response_received", "response_parsed"),
            "post_processing": elapsed("response_parsed", "call_complete"),
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "model": self.model,
            "timing": self.timing,
            "durations": self.get_durations(),
            "metadata": self.metadata,
        }


class FunctionTiming:
    """개별 함수 실행 타이밍"""
    def __init__(self, func_name: str):
        self.func_name = func_name
        self.start_time = time.time()
        self.end_time = 0
        self.metadata = {}
    
    def complete(self):
        self.end_time = time.time()
    
    def get_duration(self) -> float:
        if self.end_time == 0:
            return 0
        return self.end_time - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "func_name": self.func_name,
            "duration": self.get_duration(),
            "metadata": self.metadata,
        }


class AgentDetailedTiming:
    """에이전트별 초상세 타이밍"""
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.start_time = time.time()
        self.end_time = 0
        self.llm_calls: List[LLMCallTiming] = []
        self.db_queries: List[Dict[str, Any]] = []
        self.functions: List[FunctionTiming] = []
        self.checkpoints: Dict[str, float] = {}
    
    def mark(self, checkpoint: str, value: Optional[float] = None):
        self.checkpoints[checkpoint] = value if value is not None else time.time()
    
    def start_llm_call(self, call_id: str, model: str = "gemini") -> LLMCallTiming:
        llm_call = LLMCallTiming(call_id, model)
        llm_call.mark("call_start")
        self.llm_calls.append(llm_call)
        return llm_call
    
    def start_db_query(self, query_name: str) -> Dict[str, Any]:
        query = {
            "name": query_name,
            "start": time.time(),
            "end": 0,
            "rows": 0,
        }
        self.db_queries.append(query)
        return query
    
    def complete_db_query(self, query: Dict[str, Any], rows: int = 0):
        query["end"] = time.time()
        query["rows"] = rows
    
    def start_function(self, func_name: str) -> FunctionTiming:
        func = FunctionTiming(func_name)
        self.functions.append(func)
        return func
    
    def complete(self):
        self.end_time = time.time()
    
    def get_total_duration(self) -> float:
        if self.end_time == 0:
            return 0
        return self.end_time - self.start_time
    
    def get_summary(self) -> Dict[str, Any]:
        llm_total = sum(call.get_durations()["total"] for call in self.llm_calls)
        db_total = sum(q["end"] - q["start"] for q in self.db_queries if q["end"] > 0)
        func_total = sum(f.get_duration() for f in self.functions)
        
        # checkpoints에서 LLM 시간 계산 (하위 호환성)
        if llm_total == 0 and self.checkpoints:
            llm_start = self.checkpoints.get("llm_call_start", 0)
            llm_end = self.checkpoints.get("llm_call_complete", 0)
            if llm_start and llm_end:
                llm_total = llm_end - llm_start
        
        # checkpoints에서 DB 시간 계산 (하위 호환성)
        if db_total == 0 and self.checkpoints:
            db_start = self.checkpoints.get("db_query_start", 0)
            db_end = self.checkpoints.get("db_query_complete", 0)
            if db_start and db_end:
                db_total = db_end - db_start
        
        # checkpoints에서 LLM 호출 세부 정보 생성 (하위 호환성)
        llm_calls_from_checkpoints = []
        if not self.llm_calls and self.checkpoints.get("llm_call_start"):
            llm_calls_from_checkpoints.append({
                "call_id": f"{self.agent_name}_llm_1",
                "model": "gemini",
                "durations": {
                    "total": llm_total,
                    "prompt_preparation": self._get_checkpoint_elapsed("llm_call_start", "llm_prompt_ready"),
                    "api_request_send": self._get_checkpoint_elapsed("llm_prompt_ready", "llm_api_sent"),
                    "api_wait": self._get_checkpoint_elapsed("llm_api_sent", "llm_api_received"),
                    "response_parsing": self._get_checkpoint_elapsed("llm_api_received", "llm_parsed"),
                    "post_processing": self._get_checkpoint_elapsed("llm_parsed", "llm_call_complete"),
                },
                "metadata": {}
            })
        
        return {
            "agent_name": self.agent_name,
            "total_duration": self.get_total_duration(),
            "llm_calls_count": len(self.llm_calls) or (1 if llm_calls_from_checkpoints else 0),
            "llm_calls_total_time": llm_total,
            "db_queries_count": len(self.db_queries) or (1 if db_total > 0 else 0),
            "db_queries_total_time": db_total,
            "functions_count": len(self.functions),
            "functions_total_time": func_total,
            "llm_calls": [call.to_dict() for call in self.llm_calls] or llm_calls_from_checkpoints,
            "db_queries": [{
                "name": q["name"],
                "duration": q["end"] - q["start"] if q["end"] > 0 else 0,
                "rows": q["rows"]
            } for q in self.db_queries] or ([{"name": "db_query", "duration": db_total, "rows": 0}] if db_total > 0 else []),
            "functions": [f.to_dict() for f in self.functions],
            "checkpoints": self.checkpoints,
        }
    
    def _get_checkpoint_elapsed(self, start_key: str, end_key: str) -> float:
        """체크포인트 사이 경과 시간"""
        start = self.checkpoints.get(start_key, 0)
        end = self.checkpoints.get(end_key, 0)
        if start and end:
            return end - start
        return 0


class TimingLogger:
    """초상세 타이밍 측정 및 로깅 클래스"""
    
    def __init__(self, session_id: str, request_id: str):
        self.session_id = session_id
        self.request_id = request_id
        self.pipeline_start = time.time()
        
        # 기본 체크포인트
        self.checkpoints: Dict[str, float] = {
            "pipeline_start": self.pipeline_start,
        }
        
        # 에이전트별 상세 타이밍
        self.orchestration: Optional[AgentDetailedTiming] = None
        self.sub_agents: Dict[str, AgentDetailedTiming] = {}
        self.final_agent: Optional[AgentDetailedTiming] = None
        
        # 기타 타이밍
        self.misc_functions: List[FunctionTiming] = []
        
    def mark(self, checkpoint: str, value: Optional[float] = None):
        """기본 체크포인트 기록"""
        self.checkpoints[checkpoint] = value if value is not None else time.time()
    
    def start_orchestration(self) -> AgentDetailedTiming:
        """Orchestration Agent 시작"""
        self.orchestration = AgentDetailedTiming("orchestration")
        return self.orchestration
    
    def start_sub_agent(self, agent_name: str) -> AgentDetailedTiming:
        """Sub Agent 시작"""
        agent = AgentDetailedTiming(agent_name)
        self.sub_agents[agent_name] = agent
        return agent
    
    def start_final_agent(self) -> AgentDetailedTiming:
        """Final Agent 시작"""
        self.final_agent = AgentDetailedTiming("final_agent")
        return self.final_agent
    
    def mark_agent(self, agent_name: str, checkpoint: str, value: Optional[float] = None):
        """Sub Agent 체크포인트 기록 (하위 호환성)"""
        if agent_name not in self.sub_agents:
            self.sub_agents[agent_name] = AgentDetailedTiming(agent_name)
        self.sub_agents[agent_name].mark(checkpoint, value)
    
    def start_function(self, func_name: str) -> FunctionTiming:
        """기타 함수 타이밍 시작"""
        func = FunctionTiming(func_name)
        self.misc_functions.append(func)
        return func
    
    def get_elapsed(self, start_key: str, end_key: str) -> float:
        """두 체크포인트 사이의 경과 시간 계산 (초)"""
        start = self.checkpoints.get(start_key, 0)
        end = self.checkpoints.get(end_key, 0)
        if start == 0 or end == 0:
            return 0
        return end - start
    
    def get_agent_elapsed(self, agent_name: str, start_key: str, end_key: str) -> float:
        """Agent별 경과 시간 계산 (하위 호환성)"""
        if agent_name not in self.sub_agents:
            return 0
        agent = self.sub_agents[agent_name]
        start = agent.checkpoints.get(start_key, 0)
        end = agent.checkpoints.get(end_key, 0)
        if start == 0 or end == 0:
            return 0
        return end - start
        
    def calculate_durations(self) -> Dict[str, Any]:
        """각 단계별 소요 시간 계산"""
        durations = {
            "total": self.get_elapsed("pipeline_start", "response_sent"),
            "history_load": self.get_elapsed("pipeline_start", "history_loaded"),
            "orchestration": {
                "total": self.get_elapsed("orch_start", "orch_complete"),
                "prompt_generation": self.get_elapsed("orch_start", "orch_prompt_ready"),
                "api_call": self.get_elapsed("orch_api_sent", "orch_api_received"),
                "parsing": self.get_elapsed("orch_api_received", "orch_parsed"),
            },
            "sub_agents": {
                "total": self.get_elapsed("sub_agents_start", "sub_agents_complete"),
                "agents": {}
            },
            "final_agent": {
                "total": self.get_elapsed("final_start", "final_complete"),
                "history_merge": self.get_elapsed("final_start", "final_history_merged"),
                "results_format": self.get_elapsed("final_history_merged", "final_results_formatted"),
                "structure_format": self.get_elapsed("final_results_formatted", "final_structure_formatted"),
                "prompt_assembly": self.get_elapsed("final_structure_formatted", "final_prompt_ready"),
                "api_call": self.get_elapsed("final_api_sent", "final_api_received"),
                "postprocessing": self.get_elapsed("final_api_received", "final_postprocessed"),
            },
            "history_save": self.get_elapsed("final_complete", "history_saved"),
            "db_save": self.get_elapsed("history_saved", "db_saved"),
        }
        
        # Sub Agents별 세부 시간 계산
        for agent_name, agent_timing in self.sub_agents.items():
            if isinstance(agent_timing, AgentDetailedTiming):
                durations["sub_agents"]["agents"][agent_name] = agent_timing.get_summary()
            else:
                # 하위 호환성
                agent_durations = {
                    "total": self.get_agent_elapsed(agent_name, "start", "complete"),
                    "db_query": self.get_agent_elapsed(agent_name, "db_query_start", "db_query_complete"),
                    "llm_call_total": self.get_agent_elapsed(agent_name, "llm_call_start", "llm_call_complete"),
                    "llm_prompt_ready": self.get_agent_elapsed(agent_name, "llm_call_start", "llm_prompt_ready"),
                    "llm_api_wait": self.get_agent_elapsed(agent_name, "llm_api_sent", "llm_api_received"),
                    "llm_parsing": self.get_agent_elapsed(agent_name, "llm_api_received", "llm_parsed"),
                    "processing": self.get_agent_elapsed(agent_name, "llm_call_complete", "complete"),
                }
                durations["sub_agents"]["agents"][agent_name] = agent_durations
            
        return durations
    
    def get_summary(self) -> Dict[str, Any]:
        """타이밍 요약 정보 반환"""
        durations = self.calculate_durations()
        
        return {
            "timestamp": datetime.fromtimestamp(self.pipeline_start).isoformat(),
            "session_id": self.session_id,
            "request_id": self.request_id,
            "total_time": durations["total"],
            "orchestration_time": durations["orchestration"]["total"],
            "sub_agents_time": durations["sub_agents"]["total"],
            "final_agent_time": durations["final_agent"]["total"],
            "durations": durations,
            "raw_checkpoints": self.checkpoints,
            "orchestration_details": self.orchestration.get_summary() if self.orchestration else None,
            "sub_agents_details": {k: v.get_summary() if isinstance(v, AgentDetailedTiming) else v 
                                    for k, v in self.sub_agents.items()},
            "final_agent_details": self.final_agent.get_summary() if self.final_agent else None,
        }
    
    def log_to_file(self, log_dir: str = "backend/logs"):
        """타이밍 정보를 파일에 저장"""
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # JSON 로그 저장 (상세 정보)
        json_file = log_path / "timing_details.jsonl"
        summary = self.get_summary()
        
        _lock = threading.Lock()
        with _lock:
            with open(json_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(summary, ensure_ascii=False, default=str) + "\n")
        
        # CSV 로그 저장 (요약 정보)
        csv_file = log_path / "timing_summary.csv"
        file_exists = csv_file.exists()
        
        durations = self.calculate_durations()
        
        with _lock:
            with open(csv_file, "a", newline="", encoding="utf-8") as f:
                fieldnames = [
                    "timestamp", "session_id", "request_id", 
                    "total_time", "orch_time", "sub_agents_time", 
                    "final_time", "db_time", "network_time"
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                if not file_exists:
                    writer.writeheader()
                
                writer.writerow({
                    "timestamp": datetime.fromtimestamp(self.pipeline_start).isoformat(),
                    "session_id": self.session_id,
                    "request_id": self.request_id,
                    "total_time": round(durations["total"], 3),
                    "orch_time": round(durations["orchestration"]["total"], 3),
                    "sub_agents_time": round(durations["sub_agents"]["total"], 3),
                    "final_time": round(durations["final_agent"]["total"], 3),
                    "db_time": round(durations["history_save"] + durations["db_save"], 3),
                    "network_time": round(
                        durations["orchestration"].get("api_call", 0) + 
                        durations["final_agent"].get("api_call", 0), 3
                    )
                })
    
    def get_detailed_log_lines(self) -> List[str]:
        """상세 로그 라인 생성"""
        lines = []
        durations = self.calculate_durations()
        
        lines.append("")
        lines.append("="*80)
        lines.append("⏱️  초상세 타이밍 측정 결과")
        lines.append("="*80)
        lines.append(f"📋 세션 ID: {self.session_id}")
        lines.append(f"🆔 요청 ID: {self.request_id}")
        lines.append(f"⏰ 총 소요 시간: {durations['total']:.3f}초")
        lines.append("-"*80)
        
        # Orchestration Agent 상세
        lines.append("")
        lines.append(f"1️⃣  Orchestration Agent: {durations['orchestration']['total']:.3f}초")
        lines.append(f"   ├─ 프롬프트 생성: {durations['orchestration']['prompt_generation']:.3f}초")
        lines.append(f"   ├─ API 호출 (LLM 대기): {durations['orchestration']['api_call']:.3f}초")
        lines.append(f"   └─ 응답 파싱: {durations['orchestration']['parsing']:.3f}초")
        
        if self.orchestration:
            for i, llm_call in enumerate(self.orchestration.llm_calls):
                d = llm_call.get_durations()
                lines.append(f"   📞 LLM 호출 #{i+1} ({llm_call.call_id}):")
                lines.append(f"      ├─ 프롬프트 준비: {d['prompt_preparation']:.3f}초")
                lines.append(f"      ├─ API 요청 전송: {d['api_request_send']:.3f}초")
                lines.append(f"      ├─ API 응답 대기: {d['api_wait']:.3f}초")
                lines.append(f"      ├─ 응답 파싱: {d['response_parsing']:.3f}초")
                lines.append(f"      └─ 후처리: {d['post_processing']:.3f}초")
        
        # Sub Agents 상세
        lines.append("")
        lines.append(f"2️⃣  Sub Agents: {durations['sub_agents']['total']:.3f}초")
        
        for agent_name, agent_data in durations['sub_agents']['agents'].items():
            if isinstance(agent_data, dict):
                if 'total_duration' in agent_data:
                    # 새로운 상세 형식
                    lines.append(f"   [{agent_name}] 전체: {agent_data['total_duration']:.3f}초")
                    lines.append(f"      ├─ DB 쿼리: {agent_data['db_queries_total_time']:.3f}초 ({agent_data['db_queries_count']}개)")
                    lines.append(f"      ├─ LLM 호출: {agent_data['llm_calls_total_time']:.3f}초 ({agent_data['llm_calls_count']}개)")
                    
                    for i, llm_call in enumerate(agent_data.get('llm_calls', [])):
                        d = llm_call.get('durations', {})
                        lines.append(f"      │  📞 LLM #{i+1} ({llm_call.get('call_id', 'unknown')}):")
                        lines.append(f"      │     ├─ 프롬프트 준비: {d.get('prompt_preparation', 0):.3f}초")
                        lines.append(f"      │     ├─ API 요청 전송: {d.get('api_request_send', 0):.3f}초")
                        lines.append(f"      │     ├─ API 응답 대기: {d.get('api_wait', 0):.3f}초")
                        lines.append(f"      │     ├─ 응답 파싱: {d.get('response_parsing', 0):.3f}초")
                        lines.append(f"      │     └─ 후처리: {d.get('post_processing', 0):.3f}초")
                    
                    for db_q in agent_data.get('db_queries', []):
                        lines.append(f"      │  🔍 DB: {db_q.get('name', 'unknown')}: {db_q.get('duration', 0):.3f}초 ({db_q.get('rows', 0)}행)")
                    
                    lines.append(f"      └─ 함수 실행: {agent_data['functions_total_time']:.3f}초 ({agent_data['functions_count']}개)")
                else:
                    # 하위 호환성
                    lines.append(f"   [{agent_name}]")
                    lines.append(f"      ├─ 전체: {agent_data.get('total', 0):.3f}초")
                    lines.append(f"      ├─ DB 조회: {agent_data.get('db_query', 0):.3f}초")
                    lines.append(f"      ├─ LLM 호출: {agent_data.get('llm_call_total', 0):.3f}초")
                    lines.append(f"      │  ├─ 프롬프트 준비: {agent_data.get('llm_prompt_ready', 0):.3f}초")
                    lines.append(f"      │  ├─ API 대기: {agent_data.get('llm_api_wait', 0):.3f}초")
                    lines.append(f"      │  └─ 파싱: {agent_data.get('llm_parsing', 0):.3f}초")
                    lines.append(f"      └─ 후처리: {agent_data.get('processing', 0):.3f}초")
        
        # Final Agent 상세
        lines.append("")
        lines.append(f"3️⃣  Final Agent: {durations['final_agent']['total']:.3f}초")
        lines.append(f"   ├─ 히스토리 병합: {durations['final_agent']['history_merge']:.3f}초")
        lines.append(f"   ├─ 결과 포맷팅: {durations['final_agent']['results_format']:.3f}초")
        lines.append(f"   ├─ 구조 포맷팅: {durations['final_agent']['structure_format']:.3f}초")
        lines.append(f"   ├─ 프롬프트 조립: {durations['final_agent']['prompt_assembly']:.3f}초")
        lines.append(f"   ├─ API 호출 (LLM 대기): {durations['final_agent']['api_call']:.3f}초")
        lines.append(f"   └─ 후처리: {durations['final_agent']['postprocessing']:.3f}초")
        
        if self.final_agent:
            for i, llm_call in enumerate(self.final_agent.llm_calls):
                d = llm_call.get_durations()
                lines.append(f"   📞 LLM 호출 #{i+1} ({llm_call.call_id}):")
                lines.append(f"      ├─ 프롬프트 준비: {d['prompt_preparation']:.3f}초")
                lines.append(f"      ├─ API 요청 전송: {d['api_request_send']:.3f}초")
                lines.append(f"      ├─ API 응답 대기: {d['api_wait']:.3f}초")
                lines.append(f"      ├─ 응답 파싱: {d['response_parsing']:.3f}초")
                lines.append(f"      └─ 후처리: {d['post_processing']:.3f}초")
        
        # 저장 및 기타
        lines.append("")
        lines.append(f"4️⃣  저장 및 기타:")
        lines.append(f"   ├─ 히스토리 저장: {durations['history_save']:.3f}초")
        lines.append(f"   └─ DB 저장: {durations['db_save']:.3f}초")
        
        lines.append("")
        lines.append("="*80)
        
        return lines
    
    def print_summary(self):
        """타이밍 요약을 콘솔에 출력"""
        for line in self.get_detailed_log_lines():
            print(line)


class AgentTimingLogger:
    """개별 Agent용 타이밍 로거 (하위 호환성)"""
    
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.timing = {
            "start": time.time(),
            "db_query_start": 0,
            "db_query_complete": 0,
            "llm_call_start": 0,
            "llm_prompt_ready": 0,
            "llm_api_sent": 0,
            "llm_api_received": 0,
            "llm_parsed": 0,
            "llm_call_complete": 0,
            "complete": 0
        }
    
    def mark(self, checkpoint: str, value: Optional[float] = None):
        """체크포인트 기록"""
        self.timing[checkpoint] = value if value is not None else time.time()
    
    def get_timing(self) -> Dict[str, float]:
        """타이밍 데이터 반환"""
        return self.timing
    
    def get_elapsed(self, start_key: str, end_key: str) -> float:
        """경과 시간 계산"""
        start = self.timing.get(start_key, 0)
        end = self.timing.get(end_key, 0)
        if start == 0 or end == 0:
            return 0
        return end - start
